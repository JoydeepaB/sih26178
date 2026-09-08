import requests
import time
import random

TARGET = "https://sih26178-1.onrender.com/api/sensor-data"
NODES = ["Drain_Zone_A", "River_Bank_B", "Lowland_Zone_C"]

def push_history():
    now = int(time.time())
    for node in NODES:
        stack = []
        level = 30
        for i in range(24):
            ts = now - (i * 3600)
            level += random.uniform(-2, 5)
            stack.append({
                "node_id": node,
                "water_cm": round(max(20, level), 2),
                "soil_pct": 45, "rain_mm_hr": 2,
                "temp": 27, "humidity": 75, "timestamp": ts
            })
        requests.post(TARGET, json=stack)
    print("Database seeding successful.")

if __name__ == "__main__":
    push_history()
