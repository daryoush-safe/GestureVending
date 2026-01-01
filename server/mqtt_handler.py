# mqtt_manager.py
import paho.mqtt.client as mqtt
import json
import config
import grid_manager

# MQTT Topics:
# - vending/config/grid: Receives grid configuration
#   Message structure:
#   {
#     "rows": 6,                    # Total number of rows
#     "cols_double": 5,             # Number of columns in double-width rows
#     "cols_single": 10,            # Number of columns in single-width rows  
#     "double_row_indices": [0,1,3] # Indices of rows that use double-width columns
#   }

client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe(config.MQTT_TOPIC_CONFIG)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print(f"Received Config: {payload}")
        grid_manager.update_grid_layout(payload)
    except Exception as e:
        print(f"Failed to update grid config via MQTT: {e}")

def start_mqtt():
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"MQTT Connection Failed: {e}")

def publish(topic, payload):
    client.publish(topic, payload)