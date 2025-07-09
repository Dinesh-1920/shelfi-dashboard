import json
import ssl
import time
import requests
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

# Firebase config
FIREBASE_URL = "https://shelfi-dashboard-default-rtdb.asia-southeast1.firebasedatabase.app/live_data.json"

def on_connect(client, userdata, flags, rc):
    print(f"Connected to AWS IoT with result code {rc}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print("MQTT →", payload)

        # Push to Firebase
        res = requests.put(FIREBASE_URL, json=payload)
        if res.status_code != 200:
            print("Failed to push to Firebase:", res.text)
    except Exception as e:
        print("Error:", e)

def main():
    client = mqtt.Client()
    client.tls_set(**CERT_PATHS, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.on_connect = on_connect
    client.on_message = on_message

    print("Connecting to AWS IoT...")
    client.connect(AWS_ENDPOINT, PORT, keepalive=60)

    client.loop_forever()

if __name__ == "__main__":
    main()
