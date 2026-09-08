
import os
import json
import time
import random
import logging
import requests

MODE = os.environ.get("MODE", "http").lower()
NODE_ID = os.environ.get("NODE_ID", "Drain_Zone_A")
INTERVAL = float(os.environ.get("INTERVAL", "5"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "1"))

MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC = os.environ.get("TOPIC_READINGS", "sensors/readings")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000").rstrip("/")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def make_reading(node_id):
    now = int(time.time())
    water_cm = max(0.0, random.normalvariate(30, 10))
    soil_pct = max(0.0, min(100.0, random.normalvariate(50, 20)))
    rain_mm = max(0.0, random.choice([0.0, random.uniform(0, 40)]))
    temp = random.uniform(15, 35)
    humidity = random.uniform(30, 95)

    return {
        "node_id": node_id,
        "water_cm": round(water_cm, 2),
        "soil_pct": round(soil_pct, 2),
        "rain_mm_hr": round(rain_mm, 2),
        "temp": round(temp, 2),
        "humidity": round(humidity, 2),
        "timestamp": now
    }

def run_mqtt():
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logging.error("paho-mqtt not installed. Run: pip install paho-mqtt")
        return

    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception:
        logging.exception("Failed to connect to MQTT broker %s:%s", MQTT_BROKER, MQTT_PORT)
        return

    client.loop_start()
    logging.info("Publishing to MQTT %s:%s topic=%s every %s sec", MQTT_BROKER, MQTT_PORT, TOPIC, INTERVAL)

    try:
        while True:
            payload = make_reading(NODE_ID)
            client.publish(TOPIC, json.dumps(payload))
            logging.info("MQTT Published: %s", payload)
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        logging.info("Stopping mqtt publisher")
    finally:
        client.loop_stop()
        client.disconnect()

def run_http():
    url = f"{BACKEND_URL}/api/sensor-data"
    logging.info("Posting to HTTP %s every %s sec (batch_size=%s)", url, INTERVAL, BATCH_SIZE)

    session = requests.Session()
    try:
        while True:
            if BATCH_SIZE <= 1:
                payload = make_reading(NODE_ID)
            else:
                payload = [make_reading(f"{NODE_ID}-{i}") for i in range(BATCH_SIZE)]

            try:
                resp = session.post(url, json=payload, timeout=10)
                text = resp.text.strip()
                logging.info("HTTP POST status=%s response=%s", resp.status_code, text[:200])
                if resp.status_code >= 400:
                    logging.warning("Backend rejected payload: status=%s body=%s", resp.status_code, text)
            except Exception:
                logging.exception("Failed to POST to backend %s", url)

            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        logging.info("Stopping http publisher")

if __name__ == "__main__":
    logging.info("fake_publisher starting in MODE=%s", MODE)
    if MODE == "http":
        run_http()
    else:
        run_mqtt()
