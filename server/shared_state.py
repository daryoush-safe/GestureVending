# shared_state.py
from threading import Lock

frame_lock = Lock()
latest_frame = None
latest_result = None