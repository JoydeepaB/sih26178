import requests
import time
import random

ENDPOINT = "https://sih26178-1.onrender.com/api/sensor-data"
SENSORS = {
    "Drain_Zone_A": {"h": 30, "lat": 23.831, "lon": 91.286},
    "River_Bank_B": {"h": 45, "lat": 23.841, "lon": 91.279},
}

def simulate():
    while True:
        for key, val in SENSORS.items():
            val["h"] += random.uniform(-1, 4)
            val["h"] = max(20, min(100, val["h"]))
            packet = {
                "node_id": key,
                "water_cm": round(val["h"], 2),
                "soil_pct": 60,
                "rain_mm_hr": random.uniform(0, 15),
                "temp": 29,
                "humidity": 82,
                "latitude": val["lat"],
                "longitude": val["lon"]
            }
            try:
                requests.post(ENDPOINT, json=packet)
                print(f"IoT Broadcast: {key} @ {packet['water_cm']}cm")
            except: pass
        time.sleep(20)

if __name__ == "__main__":
    simulate()
