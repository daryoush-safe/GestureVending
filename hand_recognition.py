from flask import Flask, request, jsonify, Response
import cv2
import mediapipe as mp
import numpy as np
import time
from threading import Lock

app = Flask(__name__)

# Configure hand detector with optimized settings
hand_detector = mp.solutions.hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    model_complexity=0  # Use lighter model for speed
)

drawing_utils = mp.solutions.drawing_utils

# Grid configuration
grid_rows = 6
first_row_cols = 5
other_row_cols = 10

# Thread-safe frame storage
frame_lock = Lock()
latest_frame = None
latest_result = None

# Cell selection tracking
last_selected_cell = None
cell_select_cooldown = 0.3
last_cell_select_time = 0

last_click_time = 0
click_cooldown = 0.5
click_threshold = 20

# Statistics
frame_count = 0
last_fps_time = time.time()
fps = 0

def get_grid_cell(x, y, width, height):
    """Determine which grid cell contains the given coordinates"""
    row_height = height / grid_rows
    
    row = int(y / row_height)
    if row >= grid_rows:
        row = grid_rows - 1
    
    if row == 0:
        col_width = width / first_row_cols
        col = int(x / col_width)
        if col >= first_row_cols:
            col = first_row_cols - 1
        return (row, col, first_row_cols)
    else:
        col_width = width / other_row_cols
        col = int(x / col_width)
        if col >= other_row_cols:
            col = other_row_cols - 1
        return (row, col, other_row_cols)

def draw_grid(frame):
    """Draw grid overlay on frame"""
    height, width, _ = frame.shape
    row_height = height / grid_rows
    
    # Draw horizontal lines
    for i in range(1, grid_rows):
        y = int(i * row_height)
        cv2.line(frame, (0, y), (width, y), (255, 255, 255), 1)
    
    # Draw vertical lines for first row
    col_width = width / first_row_cols
    for i in range(1, first_row_cols):
        x = int(i * col_width)
        y_end = int(row_height)
        cv2.line(frame, (x, 0), (x, y_end), (255, 255, 255), 1)
    
    # Draw vertical lines for other rows
    col_width = width / other_row_cols
    for i in range(1, other_row_cols):
        x = int(i * col_width)
        y_start = int(row_height)
        cv2.line(frame, (x, y_start), (x, height), (255, 255, 255), 1)

def process_frame(frame):
    """Process frame and detect hand pointing"""
    global last_selected_cell, last_cell_select_time, last_click_time
    global frame_count, last_fps_time, fps

    # Calculate FPS
    frame_count += 1
    current_time = time.time()
    if current_time - last_fps_time >= 1.0:
        fps = frame_count / (current_time - last_fps_time)
        frame_count = 0
        last_fps_time = current_time

    frame_height, frame_width, _ = frame.shape
    
    # Resize for faster processing if frame is large
    if frame_width > 640:
        scale = 640 / frame_width
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
        frame_height, frame_width, _ = frame.shape
    
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    output = hand_detector.process(rgb_frame)
    hands = output.multi_hand_landmarks
    
    result = {
        'hand_detected': False,
        'cell': None,
        'click': False,
        'timestamp': time.time(),
        'fps': round(fps, 1)
    }
    
    # Draw grid (lightweight version)
    draw_grid(frame)
    
    if hands:
        hand = hands[0]
        landmarks = hand.landmark
        
        # Skip drawing landmarks for speed - just draw key points
        # drawing_utils.draw_landmarks(frame, hand, mp.solutions.hands.HAND_CONNECTIONS)
        
        # Get index finger tip (landmark 8)
        index_finger = landmarks[8]
        frame_index_x = int(index_finger.x * frame_width)
        frame_index_y = int(index_finger.y * frame_height)
        
        # Get current cell
        current_cell = get_grid_cell(frame_index_x, frame_index_y, frame_width, frame_height)
        current_time = time.time()
        
        if current_cell != last_selected_cell and (current_time - last_cell_select_time) > cell_select_cooldown:
            print(f"Cell: R{current_cell[0]} C{current_cell[1]}")
            last_selected_cell = current_cell
            last_cell_select_time = current_time
        
        # Get thumb tip (landmark 4)
        thumb = landmarks[4]
        frame_thumb_x = int(thumb.x * frame_width)
        frame_thumb_y = int(thumb.y * frame_height)
        
        # Calculate distance between thumb and index finger
        distance = ((frame_index_x - frame_thumb_x)**2 + 
                   (frame_index_y - frame_thumb_y)**2)**0.5
        
        # Check for click gesture
        is_clicking = distance < click_threshold
        if is_clicking and (current_time - last_click_time) > click_cooldown:
            print(f"CLICK at R{current_cell[0]} C{current_cell[1]}")
            last_click_time = current_time
        
        result['hand_detected'] = True
        result['cell'] = {
            'row': current_cell[0],
            'col': current_cell[1],
            'total_cols': current_cell[2]
        }
        result['click'] = is_clicking
        result['finger_distance'] = int(distance)
        
        # Draw minimal visualization
        cv2.circle(frame, (frame_index_x, frame_index_y), 8, (0, 255, 255), -1)
        cv2.circle(frame, (frame_thumb_x, frame_thumb_y), 8, (0, 255, 255), -1)
        cv2.line(frame, (frame_index_x, frame_index_y), (frame_thumb_x, frame_thumb_y), (255, 0, 255), 2)
        
        # Highlight selected cell
        if current_cell:
            row, col, total_cols = current_cell
            row_height = frame_height / grid_rows
            if row == 0:
                col_width = frame_width / first_row_cols
            else:
                col_width = frame_width / other_row_cols
            
            x1 = int(col * col_width)
            y1 = int(row * row_height)
            x2 = int((col + 1) * col_width)
            y2 = int((row + 1) * row_height)
            
            color = (0, 255, 0) if is_clicking else (255, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Display click status
        if is_clicking:
            cv2.putText(frame, "CLICK!", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 
                       1, (0, 255, 0), 2)
    
    # Display FPS
    cv2.putText(frame, f"FPS: {fps:.1f}", (frame_width - 120, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return result, frame

@app.route('/video_feed', methods=['POST'])
def video_feed():
    """Receive frame from ESP32 and process it"""
    global latest_frame, latest_result
    
    try:
        # Get image data from request
        nparr = np.frombuffer(request.data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Invalid image data'}), 400
        
        # Process frame
        result, processed_frame = process_frame(frame)
        
        # Store latest results
        with frame_lock:
            latest_frame = processed_frame
            latest_result = result
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error processing frame: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/latest_result', methods=['GET'])
def get_latest_result():
    """Get the latest detection result"""
    with frame_lock:
        if latest_result is None:
            return jsonify({'error': 'No data available'}), 404
        return jsonify(latest_result), 200

@app.route('/video_stream')
def video_stream():
    """Stream processed video frames"""
    def generate():
        while True:
            with frame_lock:
                if latest_frame is not None:
                    ret, buffer = cv2.imencode('.jpg', latest_frame)
                    frame = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': time.time()}), 200

@app.route('/')
def index():
    """Simple web interface"""
    return '''
    <html>
    <head><title>Hand Gesture Recognition</title></head>
    <body style="background-color: #222; color: white; font-family: Arial;">
        <h1>Hand Gesture Recognition Stream</h1>
        <img src="/video_stream" width="640" height="480">
        <p>Server is running. ESP32-CAM should send frames to /video_feed</p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Hand Gesture Recognition Server")
    print("="*50)
    print("\nMake sure to update the ESP32 code with this computer's IP address")
    print("You can find it by running 'ipconfig' (Windows) or 'ifconfig' (Linux/Mac)")
    print("\nServer starting on http://0.0.0.0:5000")
    print("View the stream at http://localhost:5000")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)