#!/usr/bin/env python3
"""MQTT subscriber that forwards sensor JSON to the Flask backend.

Features / improvements:
- Uses a requests.Session with retries for backend POSTs.
- If a POST fails, message is persisted to disk (unsent_queue.jsonl) and retried periodically.
- Better logging and diagnostics for deployments.

Important deployment note:
- If you deploy this process on Render it must be able to reach your MQTT broker. For most setups it's
  simpler to run mqtt_ingest locally (near your MQTT broker) and point BACKEND_URL to the Render app.

Environment variables:
- MQTT_BROKER (default: localhost)
- MQTT_PORT (default: 1883)
- TOPIC_READINGS (default: sensors/readings)
- TOPIC_SOS (default: sensors/sos)
- BACKEND_URL (default: http://localhost:5000)
- QUEUE_FILE (default: unsent_queue.jsonl)
- FLUSH_INTERVAL (seconds; default: 10)
- SSL_VERIFY (true/false default: true) if your backend uses self-signed certs you can set false (not recommended)
"""
import os
import json
import time
import logging
import threading
from typing import Any

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC_READINGS = os.environ.get("TOPIC_READINGS", "sensors/readings")
TOPIC_SOS = os.environ.get("TOPIC_SOS", "sensors/sos")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000").rstrip("/")
QUEUE_FILE = os.environ.get("QUEUE_FILE", "unsent_queue.jsonl")
FLUSH_INTERVAL = int(os.environ.get("FLUSH_INTERVAL", "10"))
SSL_VERIFY = os.environ.get("SSL_VERIFY", "true").lower() not in ("0", "false")

# A small requests Session with retry adapter
session = requests.Session()
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retries = Retry(total=5, backoff_factor=1, status_forcelist=(500, 502, 503, 504))
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
except Exception:
    logging.warning("Retry adapter not available; proceeding without it.")

queue_lock = threading.Lock()


def persist_message(topic: str, payload: Any) -> None:
    """Append a failed message to the on-disk queue for retry later."""
    try:
        with queue_lock:
            with open(QUEUE_FILE, "a", encoding="utf-8") as f:
                record = {"topic": topic, "payload": payload}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logging.info("Persisted message to queue (%s)", QUEUE_FILE)
    except Exception:
        logging.exception("Failed to persist message to disk queue")


def flush_queue_once():
    """Attempt to deliver all queued messages. Rewrites the queue file with unsent messages."""
    if not os.path.exists(QUEUE_FILE):
        return

    with queue_lock:
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception:
            logging.exception("Failed to read queue file")
            return

        if not lines:
            return

        remaining = []
        for ln in lines:
            try:
                record = json.loads(ln)
                topic = record.get("topic")
                payload = record.get("payload")
                ok = forward_to_backend(topic, payload)
                if not ok:
                    remaining.append(ln)
            except Exception:
                logging.exception("Malformed queue line, skipping")

        # write back remaining
        try:
            if remaining:
                with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(remaining) + "\n")
            else:
                # remove file when empty
                try:
                    os.remove(QUEUE_FILE)
                except OSError:
                    pass
        except Exception:
            logging.exception("Failed to rewrite queue file")


def periodic_flush_loop():
    logging.info("Starting periodic queue flusher every %s seconds", FLUSH_INTERVAL)
    while True:
        try:
            flush_queue_once()
        except Exception:
            logging.exception("Error while flushing queue")
        time.sleep(FLUSH_INTERVAL)


def forward_to_backend(topic: str, payload: Any) -> bool:
    """Send payload to the backend. Returns True on success, False on failure.

    topic parameter is used to choose the API path (readings vs sos). We forward the payload JSON as-is; the backend
    does the sensor normalization.
    """
    if topic == TOPIC_SOS:
        path = "/api/sos"
    else:
        # default to sensor-data for readings
        path = "/api/sensor-data"

    url = BACKEND_URL + path
    try:
        resp = session.post(url, json=payload, timeout=10, verify=SSL_VERIFY)
        text = resp.text.strip()
        logging.info("Forwarded to %s: status=%s", url, resp.status_code)
        if resp.status_code >= 200 and resp.status_code < 300:
            return True
        else:
            logging.warning("Backend rejected payload: status=%s body=%s", resp.status_code, text[:200])
            return False
    except requests.RequestException:
        logging.exception("Failed to POST to backend %s", url)
        return False


# MQTT handling

def on_connect(client, userdata, flags, rc):
    logging.info("Connected to MQTT broker %s:%s (rc=%s). Subscribing to topics...", MQTT_BROKER, MQTT_PORT, rc)
    try:
        client.subscribe(TOPIC_READINGS)
        client.subscribe(TOPIC_SOS)
    except Exception:
        logging.exception("Failed to subscribe to MQTT topics")


def on_message(client, userdata, msg):
    payload_text = msg.payload.decode("utf-8", errors="ignore")
    logging.info("MQTT message topic=%s payload=%s", msg.topic, payload_text[:500])
    try:
        data = json.loads(payload_text)
    except Exception:
        logging.warning("Received non-JSON payload on %s, ignoring", msg.topic)
        return

    # Try to forward immediately. If it fails, persist for later flushing.
    ok = forward_to_backend(msg.topic, data)
    if not ok:
        persist_message(msg.topic, data)


def run_mqtt_client():
    try:
        import paho.mqtt.client as mqtt
    except Exception:
        logging.exception("paho-mqtt is not installed. Please pip install paho-mqtt")
        return

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception:
        logging.exception("Failed to connect to MQTT broker %s:%s", MQTT_BROKER, MQTT_PORT)
        return

    # Start background flusher thread
    flusher = threading.Thread(target=periodic_flush_loop, daemon=True)
    flusher.start()

    logging.info("Starting MQTT client loop (broker=%s:%s)", MQTT_BROKER, MQTT_PORT)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("MQTT client stopped by user")
    except Exception:
        logging.exception("MQTT loop terminated unexpectedly")


if __name__ == "__main__":
    logging.info("mqtt_ingest starting. BACKEND_URL=%s, MQTT_BROKER=%s:%s", BACKEND_URL, MQTT_BROKER, MQTT_PORT)
    run_mqtt_client()
