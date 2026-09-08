import requests
import time
import random

URL = "https://sih26178-1.onrender.com/api/sensor-data"
NODES = ["Drain_Zone_A", "River_Bank_B", "Lowland_Zone_C"]

def seed():
    now = int(time.time())
    for node in NODES:
        batch = []
        val = 25
        for i in range(24):
            val += random.uniform(-2, 6)
            batch.append({
                "node_id": node, "water_cm": round(max(20, val), 2),
                "soil_pct": 50, "rain_mm_hr": 2, "temp": 28, "humidity": 75,
                "timestamp": now - (i * 3600)
            })
        requests.post(URL, json=batch)
    print("History Pushed.")

if __name__ == "__main__":
    seed()
