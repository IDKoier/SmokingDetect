from flask import Flask, request, Response
import cv2
import numpy as np
import threading
from ultralytics import YOLO

# Load the YOLOv8 model
model = YOLO("best.pt")

app = Flask(__name__)

# 用於存儲最新影像的全局變數
latest_frame = None
frame_lock = threading.Lock()

# 影像處理和顯示的函數
def process_and_display_image():
    global latest_frame

    while True:
        if latest_frame is not None:
            # 使用 Lock 保護 latest_frame，確保安全訪問
            with frame_lock:
                results = model.track(latest_frame, conf=0.3,persist=True)
                annotated_frame = results[0].plot()
                cv2.imshow("YOLOv8 Tracking", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

# 啟動影像處理線程
image_thread = threading.Thread(target=process_and_display_image)
image_thread.daemon = True
image_thread.start()

# 建立一個路由來接收影像上傳
@app.route('/upload_video', methods=['POST'])
def upload_video():
    global latest_frame

    # 從 POST 請求中獲取上傳的影像資料
    image_data = request.data

    if image_data:
        # 將接收到的二進制資料轉換成 NumPy 陣列
        nparr = np.fromstring(image_data, np.uint8)

        # 使用 OpenCV 解碼影像
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 使用 Lock 保護 latest_frame，確保安全訪問
        with frame_lock:
            latest_frame = image

        # 返回成功回應
        return '影像上傳成功'

    # 如果未接收到影像資料，返回錯誤回應
    return '未收到影像資料', 400

if __name__ == '__main__':
    app.run(debug=False,host='0.0.0.0', port=YOUR_PORT)
