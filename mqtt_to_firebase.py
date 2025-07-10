# 📁 File: mqtt_to_firebase.py
import json
import ssl
import time
import requests
from datetime import datetime
import paho.mqtt.client as mqtt

# AWS IoT MQTT config
AWS_ENDPOINT = "a1ct2m9u3qf028-ats.iot.ap-south-1.amazonaws.com"
TOPIC = "outTopic"
PORT = 8883

CERT_PATHS = {
    "certfile": "E:/Walmart/crets/device_cert.pem.crt",
    "keyfile": "E:/Walmart/crets/private_key.pem.key",
    "ca_certs": "E:/Walmart/crets/AmazonRootCA1.pem",
}

FIREBASE_LIVE_URL = "https://shelfi-dashboard-default-rtdb.asia-southeast1.firebasedatabase.app/live_data.json"
FIREBASE_HISTORY_URL = "https://shelfi-dashboard-default-rtdb.asia-southeast1.firebasedatabase.app/live_data_history.json"

def on_connect(client, userdata, flags, rc):
    print(f"✅ Connected to AWS IoT (code {rc})")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print("📦 MQTT Payload:", payload)

        # Timestamp key for history
        ts = datetime.now().strftime("%H-%M-%S")

        # Push to live_data
        res_live = requests.put(FIREBASE_LIVE_URL, json=payload)
        if res_live.status_code == 200:
            print(f"✅ Pushed to Firebase at {ts}")
        else:
            print("❌ live_data push failed:", res_live.text)

        # Push to live_data_history
        hist_url = FIREBASE_HISTORY_URL.rstrip(".json") + f"/{ts}.json"
        res_hist = requests.put(hist_url, json=payload)
        if res_hist.status_code != 200:
            print("❌ live_data_history push failed:", res_hist.text)

    except Exception as e:
        print("❌ Error:", e)

def main():
    print("🚀 Connecting to AWS IoT...")
    client = mqtt.Client()
    client.tls_set(**CERT_PATHS, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(AWS_ENDPOINT, PORT, keepalive=60)
    client.loop_forever()

if __name__ == "__main__":
    main()
