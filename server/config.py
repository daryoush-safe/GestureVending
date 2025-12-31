# config.py

# MQTT Configuration
MQTT_BROKER = "broker.hivemq.com" 
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "some_email/vending/led_control"
MQTT_TOPIC_CONFIG = "vending/config/grid"

# Network Configuration
UDP_IP = "0.0.0.0"
UDP_PORT = 5000
MAX_UDP_PACKET_SIZE = 65536

# Interaction Configuration
CELL_SELECT_COOLDOWN = 0.3
CLICK_COOLDOWN = 0.5
CLICK_THRESHOLD = 30