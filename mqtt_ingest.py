#!/usr/bin/env python3
"""
MQTT subscriber that forwards sensor JSON to the Flask backend.
Subscribe to:
  - sensors/readings  (payload: JSON object or JSON array)
  - sensors/sos       (payload: SOS JSON object)
"""
import json
import os
import logging
import requests
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO)
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC_READINGS = os.environ.get("TOPIC_READINGS", "sensors/readings")
TOPIC_SOS = os.environ.get("TOPIC_SOS", "sensors/sos")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000")

def forward_to_backend(path, payload):
    url = BACKEND_URL.rstrip("/") + path
    try:
        resp = requests.post(url, json=payload, timeout=5)
        logging.info("Forwarded to %s: status=%s", url, resp.status_code)
    except Exception as e:
        logging.exception("Failed to forward to backend %s: %s", url, e)

def on_connect(client, userdata, flags, rc):
    logging.info("Connected to MQTT broker (rc=%s). Subscribing to topics...", rc)
    client.subscribe(TOPIC_READINGS)
    client.subscribe(TOPIC_SOS)

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="ignore")
    logging.info("MQTT msg topic=%s payload=%s", msg.topic, payload[:200])
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logging.warning("Invalid JSON received on topic %s", msg.topic)
        return

    if msg.topic == TOPIC_READINGS:
        forward_to_backend("/api/sensor-data", data)
    elif msg.topic == TOPIC_SOS:
        forward_to_backend("/api/sos", data)

def run():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    run()
