import cv2
import requests
import time
import logging
import uuid
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_mac_address():
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> 8*i) & 0xff) for i in range(5, -1, -1)])
    return mac
    
logging.basicConfig(
    filename="error_log.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

device_ID = "test_computer"
device_MAC = get_mac_address()
server_ip = "YOUR_IP_ADDRESS"
server_port = "YOUR_PORT"
server_url = "https://" + server_ip + ":" + server_port + "/upload_video/" + device_ID

video_file_path = "output_test_10fps.mp4"

while True:
    try:
        cap = cv2.VideoCapture(video_file_path)
        while cap.isOpened():
            ret, frame = cap.read()

            if not ret:           
                print("影片播放結束，正在循環...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    break

            _, img_encoded = cv2.imencode('.jpg', frame)
            image_data = img_encoded.tobytes()
            response = requests.post(server_url, data=image_data, verify=False, timeout=3)
            response.raise_for_status()

    except Exception as e:
        error_message = f"Exception occurred: {e}"
        print("Wait 5 seconds to restart.", error_message)
        logging.error(error_message) 

    finally:
        cap.release()

    time.sleep(5)