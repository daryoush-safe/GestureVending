# mqtt_manager.py
import paho.mqtt.client as mqtt
import json
import config
import grid_manager

client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker successfully")
        client.subscribe(config.MQTT_TOPIC_CONFIG)
    elif rc == 4:
        print("Connection failed: Invalid Username or Password (rc=4)")
    elif rc == 5:
        print("Connection failed: Not Authorized (rc=5)")
    else:
        print(f"Connection failed with result code {rc}")

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
    
    client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    client.tls_set()
    
    try:
        print(f"Connecting to MQTT Broker at {config.MQTT_BROKER}:{config.MQTT_PORT} (TLS)")
        print(f"Using username: {config.MQTT_USERNAME}")
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"MQTT Connection Failed: {e}")

def publish(topic, payload):
    client.publish(topic, payload)