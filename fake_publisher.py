#!/usr/bin/env python3
"""
Simulate an ESP32 publishing sensor JSON to MQTT.
Each message uses the JSON shape you defined:
{"node_id": "N1", "water_cm": 42.5, "soil_pct": 78, "rain_mm": 12, "temp": 27.3, "humidity": 88, "timestamp": 1725436800}
"""
import json
import time
import random
import os
import paho.mqtt.client as mqtt

MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPIC = os.environ.get("TOPIC_READINGS", "sensors/readings")

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

node_id = os.environ.get("NODE_ID", "N1")
try:
    while True:
        now = int(time.time())
        # Simulate sensors
        water_cm = max(0.0, random.normalvariate(30, 10))
        soil_pct = max(0.0, min(100.0, random.normalvariate(50, 20)))
        rain_mm = max(0.0, random.choice([0.0, random.uniform(0, 40)]))
        temp = random.uniform(15, 35)
        humidity = random.uniform(30, 95)

        payload = {
            "node_id": node_id,
            "water_cm": round(water_cm, 2),
            "soil_pct": round(soil_pct, 2),
            "rain_mm": round(rain_mm, 2),   # hardware key name
            "temp": round(temp, 2),
            "humidity": round(humidity, 2),
            "timestamp": now
        }

        client.publish(TOPIC, json.dumps(payload))
        print("Published:", payload)
        time.sleep(5)
except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()
