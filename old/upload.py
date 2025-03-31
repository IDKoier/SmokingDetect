import cv2
import requests
import numpy as np

server_url = "http://180.176.237.165:YOUR_PORT/upload_video"
#server_url ="http://192.168.0.115:YOUR_PORT/upload_video"

cap = cv2.VideoCapture(0)
while cap.isOpened():

    ret, frame = cap.read()

    if not ret:
        break

    _, img_encoded = cv2.imencode('.jpg', frame)

    image_data = img_encoded.tobytes()

    response = requests.post(server_url, data=image_data)

    print(response.text)
    
    cv2.imshow("upload_video", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()