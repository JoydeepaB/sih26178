#!/usr/bin/env python3
"""
Simulate an ESP32 publishing sensor JSON to either MQTT or HTTP backend.

Environment variables:
- MODE: "mqtt" (default) or "http"
- MQTT_BROKER, MQTT_PORT, TOPIC (for mqtt mode)
- BACKEND_URL (for http mode) e.g. https://your-render-url
- NODE_ID (default "N1")
- INTERVAL (seconds between sends, default 5)
- BATCH_SIZE (optional, for http mode to send arrays; default 1)
"""

import os
import json
import time
import random
import logging
import requests

MODE = os.environ.get("MODE", "mqtt").lower()
NODE_ID = os.environ.get("NODE_ID", "N1")
INTERVAL = float(os.environ.get("INTERVAL", "5"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "1"))

# MQTT settings
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC = os.environ.get("TOPIC_READINGS", "sensors/readings")

# HTTP settings
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
        "rain_mm": round(rain_mm, 2),   # hardware key name; backend maps this to rain_mm_hr
        "temp": round(temp, 2),
        "humidity": round(humidity, 2),
        "timestamp": now
    }


def run_mqtt():
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logging.error("paho-mqtt not installed. pip install paho-mqtt")
        return

    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
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
                # If backend returns 400 or other non-2xx, log details
                if resp.status_code >= 400:
                    logging.warning("Backend rejected payload: status=%s body=%s", resp.status_code, text)
            except Exception as e:
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
