# config.py

# MQTT Configuration
MQTT_BROKER = "e7ec6292da2b42b8ae51969e638c3277.s1.eu.hivemq.cloud" 
MQTT_PORT = 8883  # TLS/SSL port
MQTT_USERNAME = "gesture_vending"
MQTT_PASSWORD = "pce.38@vuZt_FvY"
MQTT_TOPIC_PREFIX = "some_email/vending/led_control"
MQTT_TOPIC_CONFIG = "vending/config/grid"
# Message structure: {"rows": int, "cols_double": int, "cols_single": int, "double_row_indices": list[int]}

# Network Configuration
UDP_IP = "0.0.0.0"
UDP_PORT = 5000
MAX_UDP_PACKET_SIZE = 65536

# Interaction Configuration
CELL_SELECT_COOLDOWN = 0.3
CLICK_COOLDOWN = 0.5
CLICK_THRESHOLD = 40