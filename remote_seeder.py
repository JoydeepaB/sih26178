import requests
import time
import random

URL = "https://sih26178-1.onrender.com/api/sensor-data"

def seed():
    nodes = ["Drain_Zone_A", "River_Bank_B"]
    for node in nodes:
        batch = []
        w = 20
        for i in range(24):
            w += random.uniform(-2, 5)
            batch.append({
                "node_id": node, "water_cm": round(max(10, w), 2),
                "timestamp": int(time.time()) - (i * 3600)
            })
        requests.post(URL, json=batch)
    print("Graphs populated with 24h history.")

if __name__ == "__main__":
    seed()
