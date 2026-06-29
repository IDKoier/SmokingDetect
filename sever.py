from flask import Flask, request,render_template,send_from_directory,Response, jsonify, redirect, url_for,send_file
from functools import wraps
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

db_config = {
    'host': 'host.docker.internal',
    'user': 'root',
    'password': '', 
   'database': 'smoke' 
}

#測試用
db_config['host'] = 'localhost'

device_ids = []
device_db_mapping = {}

connection = mysql.connector.connect(**db_config)
if connection.is_connected():
    cursor = connection.cursor()
    cursor.execute("SELECT id, device_name FROM device")
    results = cursor.fetchall()
    for row in results:
        db_id = row[0]
        device_name = row[1]
        device_ids.append(device_name)
        device_db_mapping[device_name] = db_id
cursor.close()
connection.close()

#jsonFile = open("static/data.json","r")
#deviceID = json.load(jsonFile)
#while (deviceID["device"] != []):
#    device_ids.append(deviceID["device"][0]["deviceID"])
#    deviceID["device"].pop(0)

image_queues = {device_id: multiprocessing.Queue() for device_id in device_ids}
realtimes_queues = {device_id: multiprocessing.Queue(maxsize=30) for device_id in device_ids}

image_folder = "photo"

def process_and_display_image(device_id, image_queue, realtimes_queue, db_id):

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
                    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(image_rgb)
                    gif.append(pil_image)
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
                    device_id=db_id,
                    hash_filename=hash_filename,  
                    recognition_time=timestamp)
                    gif.clear()
            else:
                results = model.track(image, conf=0.3, persist=True, classes=[2], device=0)
                image = results[0].plot()
                isSmokingThisFrame = False
                if results[0].boxes and len(results[0].boxes.conf) > 0:
                    boxes = results[0].boxes
                    max_conf = boxes.conf.max().item()
                    if max_conf > 0.7:
                            isSmokingThisFrame = True
                            
                if isSmokingThisFrame:
                    ifSmoker.append(1)
                else:
                    ifSmoker.append(0)
                print('ifSmoker=',sum(ifSmoker))
                if sum(ifSmoker)>=27:
                    cooldown = cooldownBetweenTwoTarget
                    ifSmoker.clear()
                
        if realtimes_queue.full():
            try:
                realtimes_queue.get_nowait()
            except:
                pass

        realtimes_queue.put(image)
            
def calculate_sha256(image_array):
    img_bytes = image_array.tobytes()
    return hashlib.sha256(img_bytes).hexdigest()

def save_to_database(device_id, hash_filename, recognition_time):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO record (device_id, hash_filename, recognition_time) "
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

def login_required(f):
    @wraps(f)
    def check_login_data(*args, **kwargs):
        token = request.cookies.get('jwt_token')
        isApiRequest = request.path.startswith('/api/')
        if not token:
            if isApiRequest:
                return jsonify({"success": False, "message": "未登入"}), 401
            else:
                return redirect(url_for('login'))
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            if isApiRequest:
                return jsonify({"success": False, "message": "認證已過期"}), 401
            else:
                return redirect(url_for('login'))
        except jwt.InvalidTokenError:
            if isApiRequest:
                return jsonify({"success": False, "message": "認證無效"}), 401
            else:
                return redirect(url_for('login'))
    return check_login_data
    
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

def start_image_process(device_id, image_queue, realtimes_queue, db_id):
    image_process = multiprocessing.Process(target=process_and_display_image, args=(device_id, image_queue, realtimes_queue, db_id))
    image_process.daemon = True
    image_process.start()

@app.route('/')
@login_required
def default():
    return render_template('realtime.html', devices=device_ids)


@app.route('/home.html')
@login_required
def home():
       return render_template('home.html')
     
@app.route('/realtime.html')
@login_required
def realtime():
    return render_template('realtime.html', devices=device_ids)
     
@app.route('/records.html')
@login_required
def records():
    return render_template('records.html', devices=device_ids)


@app.route('/api/search_device', methods=['GET'])
@login_required
def search_device():
    device_name = request.args.get('device_name', default=None, type=str)
    time_range = request.args.get('time', default=None, type=str)
    page = request.args.get('page', default=1, type=int)
    if page < 1:
        page = 1
    per_page = 5
    offset = (page - 1) * per_page
    
    query = """
    SELECT d.device_name, r.hash_filename, r.recognition_time 
    FROM record r
    JOIN device d ON r.device_id = d.id
"""
    where_clauses = []
    params = []
    
    if device_name is not None:
        where_clauses.append("d.device_name = %s")
        params.append(device_name)
    else: 
        match time_range:
            case "aHour":
                where_clauses.append("r.recognition_time >= NOW() - INTERVAL 1 HOUR")
            case "sixHour":
                where_clauses.append("r.recognition_time >= NOW() - INTERVAL 6 HOUR")
            case "aDay":
                where_clauses.append("r.recognition_time >= NOW() - INTERVAL 1 DAY")
            case "aWeek":
                where_clauses.append("r.recognition_time >= NOW() - INTERVAL 1 WEEK")
            case "aMonth":
                where_clauses.append("r.recognition_time >= NOW() - INTERVAL 1 MONTH")
            case _:
                pass
                
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY recognition_time DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
                
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        formatted_results = []
        for row in results:
            if isinstance(row['recognition_time'], datetime.datetime):
                row['recognition_time'] = row['recognition_time'].strftime('%Y-%m-%d %H:%M:%S')
            formatted_results.append(row)
        return jsonify({"success": True, "data": formatted_results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/settings.html')
@login_required
def settings():
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


@app.route('/save_device', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
        cap = cv2.VideoCapture(0)
        while cap.isOpened():
            ret, frame = cap.read()

            if not ret:           
                print("Webcam is not available.")
                logging.error("Webcam is not available.")
                break

            _, img_encoded = cv2.imencode('.jpg', frame)
            image_data = img_encoded.tobytes()
            response = requests.post(server_url, data=image_data, verify=False)
            response.raise_for_status()
            print(response.text)

    except Exception as e:
        error_message = f"Exception occurred: {{e}}"
        print("Wait 5 seconds to restart.", error_message)
        logging.error(error_message) 

    finally:
        cap.release()
        cv2.destroyAllWindows()

    time.sleep(5)
'''

    script_path = os.path.join(os.getcwd(), "uploadmul.py")
    with open(script_path, "w", encoding="utf-8") as file:
        file.write(script_content)

    return send_file(script_path, as_attachment=True)

@app.route('/login.html')
def login():
    return render_template('login.html')
     
@app.route('/test.html')
@login_required
def test():
    return render_template('test.html')

@app.route('/images/<path:filename>')
@login_required
def get_image(filename):
    return send_from_directory(image_folder, filename)

last_online_update = {}
@app.route('/upload_video/<device_id>', methods=['POST'])
def upload_video(device_id):
    
    image_data = request.data
    
    if image_data:

        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        image_queues[device_id].put(image)
        now = time.time()
        if now - last_online_update.get(device_id, 0) >= 60:
            last_online_update[device_id] = now
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE device SET last_online_time = %s WHERE device_name = %s",
                    (datetime.datetime.now(), device_id)
                )
                conn.commit()
            except Exception as e:
                print(f"更新 last_online_time 失敗: {e}")
            finally:
                if conn.is_connected():
                    cursor.close()
                    conn.close()
        return '影像上傳成功'

    return '未收到影像資料', 400

def get_image_frames(device_id):
     while True:
        image_data = realtimes_queues[device_id].get()
        if (image_data) is not None:
            _, img_encoded = cv2.imencode('.jpg', image_data)
            image_data_restored = img_encoded.tobytes()
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + image_data_restored + b'\r\n')

@app.route('/api/stream/<device_id>')
@login_required
def video_stream(device_id):
    return Response(get_image_frames(device_id), mimetype='multipart/x-mixed-replace; boundary=frame')
    
if __name__ == '__main__':
    
    for device_id in device_ids:
        start_image_process(device_id, image_queues[device_id], realtimes_queues[device_id], device_db_mapping[device_id])
    
    app.run(debug=False, host='0.0.0.0', port=SERVER_PORT,ssl_context=("cert/server.crt", "cert/server.key"))

