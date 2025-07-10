import json, ssl, time, requests
import paho.mqtt.client as mqtt
from datetime import datetime

AWS_ENDPOINT = "a1ct2m9u3qf028-ats.iot.ap-south-1.amazonaws.com"
TOPIC = "outTopic"
PORT = 8883

CERT_PATHS = {
    "certfile": "E:/Walmart/crets/device_cert.pem.crt",
    "keyfile": "E:/Walmart/crets/private_key.pem.key",
    "ca_certs": "E:/Walmart/crets/AmazonRootCA1.pem",
}

FIREBASE_LIVE_URL = "https://shelfi-dashboard-default-rtdb.asia-southeast1.firebasedatabase.app/live_data.json"
FIREBASE_HISTORY_URL = "https://shelfi-dashboard-default-rtdb.asia-southeast1.firebasedatabase.app/live_data_history"

def on_connect(client, userdata, flags, rc):
    print(f"✅ Connected to AWS IoT (code {rc})")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print("📦 MQTT Payload:", payload)

        # Push current payload
        requests.put(FIREBASE_LIVE_URL, json=payload)

        # Push to history with timestamp key
        ts = datetime.now().strftime("%H-%M-%S")
        res = requests.patch(FIREBASE_HISTORY_URL + ".json", json={ts: payload})
        if res.status_code == 200:
            print(f"✅ Pushed to Firebase at {ts}")
        else:
            print("❌ Firebase push failed:", res.text)

    except Exception as e:
        print("🔥 Error:", e)

def main():
    client = mqtt.Client()
    client.tls_set(**CERT_PATHS, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.on_connect = on_connect
    client.on_message = on_message

    print("🚀 Connecting to AWS IoT...")
    client.connect(AWS_ENDPOINT, PORT, keepalive=60)
    client.loop_forever()

if __name__ == "__main__":
    main()
