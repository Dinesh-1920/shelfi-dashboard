import json, ssl
from datetime import datetime
import paho.mqtt.client as mqtt

def start_mqtt_listener(queue, endpoint, topic, certs):
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(topic)
            print("✅ Connected to", topic)
        else:
            print("❌ MQTT connect failed rc=", rc)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            weight = float(payload.get("weight", 0))
            ts = datetime.utcnow().strftime("%H:%M:%S")
            queue.put({"ts": ts, "weight": weight})
            print("Received:", payload)
        except Exception as e:
            print("Bad payload:", e)

    cli = mqtt.Client()
    cli.tls_set(
        str(certs["root"]), str(certs["cert"]), str(certs["key"]),
        tls_version=ssl.PROTOCOL_TLSv1_2
    )
    cli.on_connect = on_connect
    cli.on_message = on_message
    cli.connect(endpoint, 8883)
    cli.loop_forever()
