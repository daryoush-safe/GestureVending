# udp_server.py
import socket
import cv2
import numpy as np
import threading
import config
import shared_state
from hand_tracker import HandProcessor

def udp_server_worker():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((config.UDP_IP, config.UDP_PORT))
    print(f"UDP Server listening on {config.UDP_IP}:{config.UDP_PORT}")

    frame_buffer = b''
    processor = HandProcessor()

    while True:
        try:
            data, _ = sock.recvfrom(config.MAX_UDP_PACKET_SIZE)
            
            if data.startswith(b'\xff\xd8'):
                frame_buffer = data
            else:
                frame_buffer += data

            if frame_buffer.endswith(b'\xff\xd9'):
                nparr = np.frombuffer(frame_buffer, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if frame is not None:
                    result, processed_frame = processor.process(frame)
                    
                    with shared_state.frame_lock:
                        shared_state.latest_frame = processed_frame
                        shared_state.latest_result = result
                
                frame_buffer = b''

        except Exception as e:
            print(f"UDP Error: {e}")
            continue

def start_server():
    threading.Thread(target=udp_server_worker, daemon=True).start()