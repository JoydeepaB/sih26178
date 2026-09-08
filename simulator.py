import requests
import time
import random

ENDPOINT = "https://sih26178-1.onrender.com/api/sensor-data"
SENSORS = {
    "Drain_Zone_A": {"h": 30, "lat": 23.83, "lon": 91.28},
    "River_Bank_B": {"h": 45, "lat": 23.84, "lon": 91.27},
}

def simulate():
    while True:
        for key, val in SENSORS.items():
            val["h"] += random.uniform(-1, 5)
            requests.post(ENDPOINT, json={
                "node_id": key, "water_cm": round(val["h"], 2),
                "soil_pct": 60, "latitude": val["lat"], "longitude": val["lon"]
            })
            print(f"IoT {key} updated.")
        time.sleep(20)

if __name__ == "__main__":
    simulate()
