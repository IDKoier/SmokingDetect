import cv2
import requests
import time
import logging
import uuid

def get_mac_address():
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> 8*i) & 0xff) for i in range(5, -1, -1)])
    return mac
    
logging.basicConfig(
    filename="error_log.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

device_ID = "123"
device_MAC = get_mac_address()
server_ip = "YOUR_IP_ADDRESS"
server_port = "YOUR_PORT"
server_url = "https://" + server_ip + ":" + server_port + "/upload_video/" + device_ID

while True:
    cap = cv2.VideoCapture(0)
    try:
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
        error_message = f"Exception occurred: {e}"
        print("Wait 5 seconds to restart.", error_message)
        logging.error(error_message) 

    finally:
        cap.release()
        cv2.destroyAllWindows()

    time.sleep(5)