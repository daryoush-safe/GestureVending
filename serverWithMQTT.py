from flask import Flask, jsonify, Response
import cv2
import mediapipe as mp
import numpy as np
import time
from threading import Lock, Thread
import socket
import paho.mqtt.client as mqtt
import json

app = Flask(__name__)

# =======================
# MQTT Configuration
# =======================
# Replace with your actual broker address if not using HiveMQ public broker
MQTT_BROKER = "broker.hivemq.com" 
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "some_email/vending/led_control"
MQTT_TOPIC_CONFIG = "vending/config/grid"

mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    # Subscribe to configuration topic for dynamic updates
    client.subscribe(MQTT_TOPIC_CONFIG)

def on_message(client, userdata, msg):
    global grid_rows, first_row_cols, other_row_cols
    try:
        # Expecting JSON like: {"rows": 6, "first_cols": 5, "other_cols": 10}
        payload = json.loads(msg.payload.decode())
        if 'rows' in payload: grid_rows = int(payload['rows'])
        if 'first_cols' in payload: first_row_cols = int(payload['first_cols'])
        if 'other_cols' in payload: other_row_cols = int(payload['other_cols'])
        print(f"Grid updated via MQTT: {grid_rows}x({first_row_cols}/{other_row_cols})")
    except Exception as e:
        print(f"Failed to update grid config via MQTT: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Start MQTT in a non-blocking way
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"MQTT Connection Failed: {e}")

# =======================
# Network Configuration
# =======================
UDP_IP = "0.0.0.0"
UDP_PORT = 5000
MAX_UDP_PACKET_SIZE = 65536

# =======================
# Grid Configuration (Defaults)
# =======================
grid_rows = 6
first_row_cols = 5
other_row_cols = 10

# =======================
# MediaPipe Setup
# =======================
hand_detector = mp.solutions.hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    model_complexity=0  
)

drawing_utils = mp.solutions.drawing_utils

# =======================
# Thread-safe storage
# =======================
frame_lock = Lock()
latest_frame = None
latest_result = None

# =======================
# Interaction States
# =======================
last_selected_cell = None
cell_select_cooldown = 0.3
last_cell_select_time = 0

last_click_time = 0
click_cooldown = 0.5
click_threshold = 30 

# =======================
# FPS statistics
# =======================
frame_count = 0
last_fps_time = time.time()
fps = 0

# =======================
# Helper Functions
# =======================
def get_grid_cell(x, y, width, height):
    """Determine which grid cell contains the given coordinates"""
    # Use global variables to allow MQTT updates to affect logic immediately
    global grid_rows, first_row_cols, other_row_cols
    
    if grid_rows == 0: return (0, 0, 1) 
    
    row_height = height / grid_rows
    
    row = int(y / row_height)
    if row >= grid_rows: row = grid_rows - 1
    
    if row == 0:
        col_width = width / first_row_cols
        col = int(x / col_width)
        if col >= first_row_cols: col = first_row_cols - 1
        return (row, col, first_row_cols)
    else:
        col_width = width / other_row_cols
        col = int(x / col_width)
        if col >= other_row_cols: col = other_row_cols - 1
        return (row, col, other_row_cols)

def draw_grid(frame):
    """Draw grid overlay on frame"""
    global grid_rows, first_row_cols, other_row_cols
    
    height, width, _ = frame.shape
    row_height = height / grid_rows
    
    # Horizontal lines
    for i in range(1, grid_rows):
        y = int(i * row_height)
        cv2.line(frame, (0, y), (width, y), (255, 255, 255), 1)
    
    # Vertical lines (First Row)
    col_width = width / first_row_cols
    for i in range(1, first_row_cols):
        x = int(i * col_width)
        cv2.line(frame, (x, 0), (x, int(row_height)), (255, 255, 255), 1)
    
    # Vertical lines (Other Rows)
    col_width = width / other_row_cols
    for i in range(1, other_row_cols):
        x = int(i * col_width)
        cv2.line(frame, (x, int(row_height)), (x, height), (255, 255, 255), 1)

def calculate_slot_id(row, col):
    """
    Calculates a unique ID for the slot based on row and col.
    Example: Row 0 is 1-5, Row 1 is 6-15, etc.
    """
    slot_id = 0
    if row == 0:
        slot_id = col + 1
    else:
        # Logic: First row count + ((current_row - 1) * cols_per_other_row) + current_col + 1
        slot_id = first_row_cols + ((row - 1) * other_row_cols) + col + 1
    return slot_id

def process_frame(frame):
    """Process frame: Detect Hands + Draw Grid + Calculate Interaction"""
    global last_selected_cell, last_cell_select_time, last_click_time
    global frame_count, last_fps_time, fps, grid_rows, first_row_cols, other_row_cols

    # FPS Calculation
    frame_count += 1
    current_time = time.time()
    if current_time - last_fps_time >= 1.0:
        fps = frame_count / (current_time - last_fps_time)
        frame_count = 0
        last_fps_time = current_time

    frame_height, frame_width, _ = frame.shape

    # Resize to 640px width if larger
    if frame_width > 640:
        scale = 640 / frame_width
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
        frame_height, frame_width, _ = frame.shape

    # MediaPipe Processing
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

    draw_grid(frame)

    if hands:
        hand = hands[0]
        landmarks = hand.landmark

        # --- Logic: Index Finger (Pointer) ---
        index_finger = landmarks[8]
        frame_index_x = int(index_finger.x * frame_width)
        frame_index_y = int(index_finger.y * frame_height)

        current_cell = get_grid_cell(frame_index_x, frame_index_y, frame_width, frame_height)
        
        # Calculate a unique slot ID for MQTT topic
        slot_id = calculate_slot_id(current_cell[0], current_cell[1])

        # ---------------------------------------------------------
        # 3. Selection Publishing (Hover)
        # ---------------------------------------------------------
        if current_cell != last_selected_cell and (current_time - last_cell_select_time) > cell_select_cooldown:
            # Topic: some_email/vending/led_control/<slot_id>
            topic = f"{MQTT_TOPIC_PREFIX}/{slot_id}"
            
            print(f"Cell Select: R{current_cell[0]} C{current_cell[1]} (Slot {slot_id}) -> MQTT: {topic}")
            
            # Publish 'selected' or simply an empty message to indicate selection
            mqtt_client.publish(topic, "selected")
            
            last_selected_cell = current_cell
            last_cell_select_time = current_time

        # --- Logic: Thumb (For Click) ---
        thumb = landmarks[4]
        frame_thumb_x = int(thumb.x * frame_width)
        frame_thumb_y = int(thumb.y * frame_height)

        # Distance for click
        distance = ((frame_index_x - frame_thumb_x)**2 + (frame_index_y - frame_thumb_y)**2)**0.5
        is_clicking = distance < click_threshold

        # ---------------------------------------------------------
        # 4. Click Publishing (Payment/Final Select)
        # ---------------------------------------------------------
        if is_clicking and (current_time - last_click_time) > click_cooldown:
            # Topic: some_email/vending/led_control/select
            topic = f"{MQTT_TOPIC_PREFIX}/select"
            
            # We publish the SLOT ID as the payload so the receiver knows WHAT was clicked
            payload = str(slot_id)
            
            print(f"CLICK at Slot {slot_id} -> MQTT: {topic} Payload: {payload}")
            mqtt_client.publish(topic, payload)
            
            last_click_time = current_time

        # Populate Result
        result['hand_detected'] = True
        result['cell'] = {'row': current_cell[0], 'col': current_cell[1], 'total_cols': current_cell[2], 'slot_id': slot_id}
        result['click'] = is_clicking
        result['finger_distance'] = int(distance)

        # --- Drawing Visuals ---
        cv2.circle(frame, (frame_index_x, frame_index_y), 8, (0, 255, 255), -1)
        cv2.circle(frame, (frame_thumb_x, frame_thumb_y), 8, (0, 255, 255), -1)
        cv2.line(frame, (frame_index_x, frame_index_y), (frame_thumb_x, frame_thumb_y), (255, 0, 255), 2)

        # Highlight Cell
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
        
        if is_clicking:
            cv2.putText(frame, "CLICK!", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # Draw FPS
    cv2.putText(frame, f"FPS: {fps:.1f}", (frame_width - 120, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return result, frame


# =======================
# UDP Listener Worker
# =======================
def udp_server_worker():
    global latest_frame, latest_result
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"UDP Server listening on {UDP_IP}:{UDP_PORT}")

    frame_buffer = b''

    while True:
        try:
            data, _ = sock.recvfrom(MAX_UDP_PACKET_SIZE)
            
            if data.startswith(b'\xff\xd8'):
                frame_buffer = data
            else:
                frame_buffer += data

            if frame_buffer.endswith(b'\xff\xd9'):
                nparr = np.frombuffer(frame_buffer, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if frame is not None:
                    result, processed_frame = process_frame(frame)
                    
                    with frame_lock:
                        latest_frame = processed_frame
                        latest_result = result
                
                frame_buffer = b''

        except Exception as e:
            print(f"UDP Error: {e}")
            continue

Thread(target=udp_server_worker, daemon=True).start()


# =======================
# Flask Routes
# =======================
@app.route('/latest_result', methods=['GET'])
def get_latest_result():
    with frame_lock:
        if latest_result is None:
            return jsonify({'error': 'No data available'}), 404
        return jsonify(latest_result), 200

@app.route('/video_stream')
def video_stream():
    def generate():
        while True:
            with frame_lock:
                if latest_frame is not None:
                    ret, buffer = cv2.imencode('.jpg', latest_frame)
                    frame = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.033)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return '''
    <html><head><title>UDP Hand Tracking</title></head>
    <body style="background-color:#222;color:white;font-family:Arial;">
        <h1>ESP32 UDP Stream + MediaPipe + MQTT</h1>
        <img src="/video_stream" width="640" height="480">
        <p>Ensure your ESP32 is running the UDP code.</p>
    </body></html>
    '''

if __name__ == '__main__':
    print("="*50)
    print("ESP32 UDP + MediaPipe Server Running")
    print("MQTT Active on: " + MQTT_TOPIC_PREFIX)
    print("="*50)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)