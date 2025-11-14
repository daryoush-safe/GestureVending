import cv2
import requests
import time
import numpy as np
from threading import Thread, Lock
from queue import Queue

# Server configuration
SERVER_URL = "http://localhost:5000/video_feed"  # Change if server is on different machine

# Thread-safe result storage
result_lock = Lock()
latest_result = {'hand_detected': False}

# Frame queue for async sending
frame_queue = Queue(maxsize=2)  # Limit queue size to prevent memory issues

def send_frames_worker():
    """Background thread to send frames to server"""
    session = requests.Session()  # Reuse connection
    
    while True:
        if not frame_queue.empty():
            frame_data = frame_queue.get()
            if frame_data is None:  # Stop signal
                break
            
            try:
                response = session.post(
                    SERVER_URL,
                    data=frame_data,
                    headers={'Content-Type': 'image/jpeg'},
                    timeout=1
                )
                
                if response.status_code == 200:
                    result = response.json()
                    with result_lock:
                        global latest_result
                        latest_result = result
            except Exception as e:
                # Silently handle errors to not spam console
                pass

# Start background thread
sender_thread = Thread(target=send_frames_worker, daemon=True)
sender_thread.start()

# Open webcam
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

# Reduce buffer to get latest frames
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

print("Starting webcam test client...")
print(f"Sending frames to: {SERVER_URL}")
print("Press 'q' to quit")

frame_count = 0
start_time = time.time()
fps_display = 0

# Frame skipping for sending (send every Nth frame)
frame_skip = 2  # Send every 2nd frame
frame_counter = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame")
        break
    
    # Flip frame horizontally for mirror effect
    frame = cv2.flip(frame, 1)
    
    # Send frame asynchronously (skip frames to reduce load)
    frame_counter += 1
    if frame_counter % frame_skip == 0:
        # Encode frame as JPEG with lower quality for speed
        _, img_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        
        # Add to queue if not full
        if not frame_queue.full():
            frame_queue.put(img_encoded.tobytes())
    
    # Get latest result from background thread
    with result_lock:
        result = latest_result.copy()
    
    # Display result on frame
    if result.get('hand_detected', False):
        cell = result['cell']
        cv2.putText(frame, f"Cell: R{cell['row']} C{cell['col']}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        if result.get('click', False):
            cv2.putText(frame, "CLICK!", (10, 70), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
        
        cv2.putText(frame, f"Distance: {result.get('finger_distance', 'N/A')}", 
                   (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    else:
        cv2.putText(frame, "No hand detected", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    # Calculate and display FPS
    frame_count += 1
    elapsed_time = time.time() - start_time
    if elapsed_time > 0.5:  # Update FPS display every 0.5s
        fps_display = frame_count / elapsed_time
        frame_count = 0
        start_time = time.time()
    
    # Show FPS on frame
    cv2.putText(frame, f"FPS: {fps_display:.1f}", (10, frame.shape[0] - 10), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    # Display frame
    cv2.imshow('Webcam Test Client', frame)
    
    # Check for quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
frame_queue.put(None)  # Stop signal
cap.release()
cv2.destroyAllWindows()
print("Test client stopped")