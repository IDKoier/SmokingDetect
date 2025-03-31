import cv2
import requests
import time

device_ID = "test_computer"
device_MAC = "7c:10:c9:a2:50:1a"
server_ip = "YOUR_IP_ADDRESS"
server_port = ":YOUR_PORT"
server_url = "https://"+server_ip+server_port +"/upload_video/" + device_ID

cap = cv2.VideoCapture(0)

while True:
    try:
        while cap.isOpened():

            ret, frame = cap.read()

            if not ret:           
                print("Webcam is not available.")
                time.sleep(5)
                continue

            _, img_encoded = cv2.imencode('.jpg', frame)

            image_data = img_encoded.tobytes()

            response = requests.post(server_url, data=image_data,verify=False)
    
            print(response.text)
    
            cv2.imshow("upload_video", frame)
    
            if cv2.waitKey(40) & 0xFF == ord('q'):
                break

    except Exception as e:
        print("Wait 5 second to restart.",e)
        time.sleep(5)


cap.release()
cv2.destroyAllWindows()