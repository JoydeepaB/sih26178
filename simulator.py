import requests
import time
import random

API = "https://sih26178-1.onrender.com/api/sensor-data"
SENSORS = {
    "Drain_Zone_A": {"h": 30, "lat": 23.831, "lon": 91.286},
    "River_Bank_B": {"h": 45, "lat": 23.841, "lon": 91.279},
}

def simulate():
    while True:
        for key, val in SENSORS.items():
            val["h"] += random.uniform(-1, 5)
            val["h"] = max(20, min(100, val["h"]))
            requests.post(API, json={
                "node_id": key, "water_cm": round(val["h"], 2),
                "soil_pct": 65, "rain_mm_hr": random.uniform(0, 10),
                "temp": 30, "humidity": 80, "latitude": val["lat"], "longitude": val["lon"]
            })
            print(f" IoT: {key} @ {val['h']}cm")
        time.sleep(15)

if __name__ == "__main__":
    simulate()
