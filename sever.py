from flask import Flask, request,render_template,send_from_directory,Response, jsonify, redirect, url_for,send_file
import cv2
import numpy as np
import multiprocessing
from ultralytics import YOLO
from PIL import Image
import datetime
import os
from OpenSSL import SSL
import eventlet
import json
from json import load
import time
import requests
import io
import mysql.connector
import bcrypt
import jwt
import hashlib
from collections import deque

model = YOLO("best.pt")

#cap = cv2.VideoCapture(0)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'YOUR_KEY'
app.config['UPLOAD_FOLDER'] = 'photo' 
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

SERVER_IP = "YOUR_IP_ADDRESS"
SERVER_PORT = "YOUR_PORT"

device_ids = []

db_config = 
{
    'host': 'host.docker.internal',
    'user': 'root',
    'password': '', 
   'database': 'smoke' 
}

#測試用
#db_config['host'] = 'localhost'

connection = mysql.connector.connect(**db_config)
if connection.is_connected():
    cursor = connection.cursor()
    cursor.execute("SELECT device_name FROM device")
    results = cursor.fetchall()
    for row in results:
        device_ids.append(row[0])
cursor.close()
connection.close()

#jsonFile = open("static/data.json","r")
#deviceID = json.load(jsonFile)
#while (deviceID["device"] != []):
#    device_ids.append(deviceID["device"][0]["deviceID"])
#    deviceID["device"].pop(0)

image_queues = {device_id: multiprocessing.Queue() for device_id in device_ids}
realtimes_queues = {device_id: multiprocessing.Queue() for device_id in device_ids}

def process_and_display_image(device_id, image_queue,realtimes_queue):

    ifSmoker = deque(maxlen=30)
    
    #10 photos per second
    cooldown = 0
    cooldownBetweenTwoTarget = 600
    howManyframeMadeGIF = 100
    
    gif = []
    
    while True:
        image = image_queue.get()

        if image is not None:
            
            if(cooldown>0):
                cooldown -= 1
                if(cooldown>cooldownBetweenTwoTarget-howManyframeMadeGIF):
                    gif.append(image)
                elif(cooldown==cooldownBetweenTwoTarget-howManyframeMadeGIF):
                    first_frame_array = np.array(gif[0])
                    hash_filename = calculate_sha256(first_frame_array)
                    new_filename = f"{hash_filename}.gif"
                    gif[0].save(
                    f"photo/{new_filename}",
                    save_all=True,
                    append_images=gif[1:],
                    duration=100,
                    loop=0,
                    disposal=0)
                    timestamp = datetime.datetime.now()
                    save_to_database(
                    device_id=device_id,
                    hash_filename=hash_filename,  
                    recognition_time=timestamp)
                    gif.clear()
            else:
                results = model.track(image, conf=0.3, persist=True)
                annotated_frame = results[0].plot()
                image = Image.fromarray(annotated_frame[..., ::-1])
                isSmokingThisFrame = False
                if results[0].boxes and len(results[0].boxes.conf) > 0:
                    boxes = results[0].boxes
                    smoking_mask = boxes.cls == 2
                    if smoking_mask.any():
                        max_conf = boxes.conf[smoking_mask].max().item()
                        if max_conf > 0.5:
                            isSmokingThisFrame = True
                            
                if isSmokingThisFrame:
                    ifSmoker.append(1)
                else:
                    ifSmoker.append(0)
                    
                if sum(ifSmoker)>=27:
                    cooldown = cooldownBetweenTwoTarget
                    ifSmoker.clear()
                
        realtimes_queue.put(image)
            
def calculate_sha256(image_array):
    img_bytes = image_array.tobytes()
    return hashlib.sha256(img_bytes).hexdigest()

def save_to_database(device_id, hash_filename, recognition_time):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO records (device_id, hash_filename, recognition_time) "
            "VALUES (%s, %s, %s)",
            (device_id, hash_filename, recognition_time)
        )
        conn.commit()
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/api/login_data', methods=['POST'])
def login_data():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"message": "Username and password are required"}), 400

        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        cursor.execute("SELECT name, password,id FROM admin WHERE name = %s", (username,))
        result = cursor.fetchone()

        if result:
            stored_password = result[1]
            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                token = jwt.encode({
                    'username': result[0],
                    'id': result[2],
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1) 
                }, app.config['SECRET_KEY'], algorithm='HS256')
                return jsonify({"message": "Login successful", "token": token})
            else:
                return jsonify({"message": "Invalid password"}), 401
        else:
            return jsonify({"message": "User not found"}), 404

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def check_login_data():
    token = request.cookies.get('jwt_token')
    
    if not token:
        return False

    try:
        jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False

def check_root_admin():
    
    token = request.cookies.get('jwt_token')
    
    if not token:
        return False

    try:
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return 'id' in decoded and decoded['id'] == 1
        
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False
    except Exception as e:
        app.logger.error(f"Root admin check error: {str(e)}")
        return False

def start_image_process(device_id, image_queue,realtimes_queue):
    image_process = multiprocessing.Process(target=process_and_display_image, args=(device_id, image_queue,realtimes_queue))
    image_process.daemon = True
    image_process.start()

image_folder = "photo"

@app.route('/')
def default():
    if check_login_data():
        return render_template('realtime.html', devices=device_ids)
    else:
        return redirect(url_for('login'))

@app.route('/home.html')
def home():
    if check_login_data():
       return render_template('home.html')
    else:
        return redirect(url_for('login'))
     
@app.route('/realtime.html')
def realtime():
    if check_login_data():
        return render_template('realtime.html', devices=device_ids)
    else:
        return redirect(url_for('login'))
     
@app.route('/records.html')
def records():
    if check_login_data():
        image_files = [
            f for f in os.listdir(app.config['UPLOAD_FOLDER'])
            if f.lower().endswith(".gif") ]
        return render_template('records.html', image_files=image_files)
    else:
        return redirect(url_for('login'))

@app.route('/settings.html')
def settings():
    if check_login_data():
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("SELECT device_name,last_online_time FROM device")
            results = cursor.fetchall()
            devices = []
            for row in results:
                devices.append({
                    'device_name': row[0], 
                    'last_online_time': row[1]
                })
            cursor.close()
            connection.close()
        return render_template('settings.html',devices=devices)
    else:
        return redirect(url_for('login'))

@app.route('/save_device', methods=['POST'])
def save_device():
    data = request.get_json()
    device_id = data.get('device_ID') 
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO device (device_name, mac_address, last_online_time) "
            "VALUES (%s, NULL,%s)",
            (device_id,'1970-01-01 00:00:00')
        )
        conn.commit()
        return jsonify({'success': True, 'message': '設備資訊已保存'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/rename_device', methods=['POST'])
def rename_device():
    data = request.get_json()
    old_device_id = data.get('old_device_ID') 
    new_device_id = data.get('new_device_ID') 
    print(old_device_id,new_device_id)
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
        "UPDATE device SET device_name = %s WHERE device_name = %s",
        (new_device_id, old_device_id)
        )
        conn.commit()
        return jsonify({'success': True, 'message': '設備資訊已修改'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/delete_device/<string:device_name>', methods=['DELETE'])
def delete_device(device_name):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
        "DELETE FROM device WHERE device_name = %s",
            (device_name,)
        )
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': '設備不存在'}), 404
        conn.commit()
        return jsonify({'success': True, 'message': '設備資訊已刪除'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/admin/list', methods=['GET'])
def get_AdminList():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
        "SELECT name as username FROM admin")
        results = cursor.fetchall()
        return jsonify({'success': True, 'message': '成功查詢管理員列表','admins':results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e),'admins': []}),500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/admin/add', methods=['POST'])
def add_New_Admin():
    if not check_root_admin():
        return jsonify({
            "success": False,
            "message": "需要 root 管理員權限"
        }), 403
    data = request.get_json()
    username = data.get('username', '').strip() 
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({
            "success": False,
            "message": "使用者名稱和密碼不能為空"
        }), 400
    
    ciphertext = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO admin (name, password) "
            "VALUES (%s,%s)",
            (username,ciphertext)
        )
        conn.commit()
        return jsonify({'success': True, 'message': '成功新增管理員'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}),500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/admin/<string:admin_name>', methods=['DELETE'])
def delete_admin(admin_name):
    if not check_root_admin():
        return jsonify({
            "success": False,
            "message": "需要 root 管理員權限"
        }), 403
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM admin WHERE name = %s", (admin_name,))
        admin = cursor.fetchone()
        
        if not admin:
            return jsonify({
                "success": False,
                "message": "管理員不存在"
            }), 404
            
        if admin['id'] == 1:
            return jsonify({
                "success": False,
                "message": "無法刪除 root 管理員"
            }), 403
        
        cursor.execute(
        "DELETE FROM admin WHERE name = %s",
            (admin_name,)
        )

        conn.commit()
        return jsonify({
            "success": True,
            "message": "管理員已刪除"
        })
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/admin/<string:admin_name>/root_change_password', methods=['PATCH'])
def root_change_admin_password(admin_name):
    if not check_root_admin():
        return jsonify({
            "success": False,
            "message": "需要 root 管理員權限"
        }), 403
    data = request.get_json()
    new_password = data.get('new_password')
    if not new_password:
        return jsonify({"success": False, "message": "新密碼不能為空"}), 400
        
    try:
        ciphertext = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM admin WHERE name = %s", (admin_name,))
        admin = cursor.fetchone()
        
        if not admin:
            return jsonify({
                "success": False,
                "message": "管理員不存在"
            }), 404
            
        if admin['id'] == 1:
            return jsonify({
                "success": False,
                "message": "無法修改 root 管理員的密碼"
            }), 403
        
        cursor.execute(
            "UPDATE admin SET password = %s WHERE name = %s",
            (ciphertext, admin_name)
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/generate_script')
def generate_script():
    device_ID = request.args.get("device_ID", "default_device").strip()

    script_content = f'''import cv2
import requests
import time
import logging
import uuid

def get_mac_address():
    mac = ':'.join(['{{:02x}}'.format((uuid.getnode() >> 8*i) & 0xff) for i in range(5, -1, -1)])
    return mac
    
logging.basicConfig(
    filename="error_log.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

device_ID = "{device_ID}"
device_MAC = get_mac_address()
server_ip = "{SERVER_IP}"
server_port = "{SERVER_PORT}"
server_url = "https://" + server_ip + ":" + server_port + "/upload_video/" + device_ID

cap = cv2.VideoCapture(0)

while True:
    try:
        while cap.isOpened():
            ret, frame = cap.read()

            if not ret:           
                print("Webcam is not available.")
                logging.error("Webcam is not available.")
                time.sleep(5)
                continue

            _, img_encoded = cv2.imencode('.jpg', frame)
            image_data = img_encoded.tobytes()
            response = requests.post(server_url, data=image_data, verify=False)
            print(response.text)

    except Exception as e:
        error_message = f"Exception occurred: {{e}}"
        print("Wait 5 seconds to restart.", error_message)
        logging.error(error_message) 
        time.sleep(5)

    finally:
        cap.release()
        cv2.destroyAllWindows()
'''

    script_path = os.path.join(os.getcwd(), "uploadmul.py")
    with open(script_path, "w", encoding="utf-8") as file:
        file.write(script_content)

    return send_file(script_path, as_attachment=True)

@app.route('/login.html')
def login():
    return render_template('login.html')
     
@app.route('/test.html')
def test():
    return render_template('test.html')

@app.route('/images/<path:filename>')
def get_image(filename):
    return send_from_directory(image_folder, filename)

@app.route('/upload_video/<device_id>', methods=['POST'])
def upload_video(device_id):
    
    image_data = request.data
    
    if image_data:

        nparr = np.frombuffer(image_data, np.uint8)

        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        image_queues[device_id].put(image)

        return '影像上傳成功'

    return '未收到影像資料', 400

def get_image_frames(device_id):
     while True:
        if (realtimes_queues[device_id].get()) is not None:
            image_data = realtimes_queues[device_id].get()
            print(image_data)
            im_data = np.array(image_data)
            im_data_rgb = cv2.cvtColor(im_data, cv2.COLOR_BGR2RGB)
            _, img_encoded = cv2.imencode('.jpg', im_data_rgb)
            image_data_restored = img_encoded.tobytes()
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + image_data_restored + b'\r\n')

@app.route('/api/stream/<device_id>')
def video_stream(device_id):
    return Response(get_image_frames(device_id), mimetype='multipart/x-mixed-replace; boundary=frame')
    
if __name__ == '__main__':
    
    for device_id in device_ids:
        start_image_process(device_id, image_queues[device_id],realtimes_queues[device_id])
    
    app.run(debug=False, host='0.0.0.0', port=SERVER_PORT,ssl_context=("cert/server.crt", "cert/server.key"))

