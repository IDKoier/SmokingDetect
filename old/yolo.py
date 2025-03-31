import cv2
from ultralytics import YOLO
import threading
from flask import Flask, Response

# Initialize Flask app
app = Flask(__name__)

# Create a lock for thread safety
lock = threading.Lock()

# Initialize YOLOv8 model
model = YOLO("best.pt")

# Initialize video capture object
cap = cv2.VideoCapture(0)

# Function to process frames and send to clients
def process_frames():
    global cap
    while True:
        success, frame = cap.read()
        if success:
            with lock:
                results = model.track(frame, conf=0.3,persist=True)
                annotated_frame = results[0].plot()

            # Convert the annotated frame to JPEG format
            ret, jpeg = cv2.imencode('.jpg', annotated_frame)

            # Store the JPEG image in a global variable
            with lock:
                process_frames.jpeg_frame = jpeg.tobytes()

def generate():
    while True:
        with lock:
            if hasattr(process_frames, 'jpeg_frame'):
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + process_frames.jpeg_frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Start the thread for processing frames
    frame_thread = threading.Thread(target=process_frames)
    frame_thread.daemon = True
    frame_thread.start()

    # Start the Flask app to serve the video stream
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)

    # Release the video capture object
    cap.release()
