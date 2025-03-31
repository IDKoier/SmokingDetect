import cv2
from ultralytics import YOLO
import datetime
from PIL import Image

# Load the YOLOv8 model
model = YOLO("best.pt")

# Open the video file
cap = cv2.VideoCapture(0)

ifSmoker = 0

# Loop through the video frames
while cap.isOpened():
    # Read a frame from the video
    success, frame = cap.read()

    if success:
        # Run YOLOv8 tracking on the frame, persisting tracks between frames
        results = model.track(frame, conf=0.3,persist=True)
        # Visualize the results on the frame
        annotated_frame = results[0].plot()
        im = Image.fromarray(annotated_frame[..., ::-1])  

        if results[0].boxes:
            if(results[0].boxes.conf[0]):
                if(results[0].boxes.conf[0]>0.5):
                    ifSmoker += 1
            else:
                ifSmoker = 0
            
        if(ifSmoker>=20):
            ifSmoker = -99999
            image_filename = "photo/" + datetime.datetime.now().strftime("%Y-%m-%d,%H-%M-%S")  + ".png"
            im.save(image_filename)
            
        # Display the annotated frame
        cv2.imshow("YOLOv8 Tracking", annotated_frame)

        # Break the loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    else:
        # Break the loop if the end of the video is reached
        break

# Release the video capture object and close the display window
cap.release()
cv2.destroyAllWindows()