import requests
import time
import random

ENDPOINT = "https://sih26178-1.onrender.com/api/sensor-data"

SENSORS = {
    "DEMO_FLASH_FLOOD_ZONE": {"h": 35, "lat": 26.14, "lon": 91.73, "name": "Guwahati River Bank"}
}

def simulate_flash_flood():
    while True:
        for key, val in SENSORS.items():
            val["h"] += random.uniform(5, 12) 
            
            payload = {
                "node_id": key,
                "location_name": val["name"],
                "water_cm": round(val["h"], 2),
                "latitude": val["lat"],
                "longitude": val["lon"]
            }
            
            requests.post(ENDPOINT, json=payload)
            
            if val["h"] >= 80:
                print(f"CRITICAL: {val['name']} level {round(val['h'], 2)} cm")
            elif val["h"] >= 60:
                print(f"HIGH: {val['name']} level {round(val['h'], 2)} cm")
            elif val["h"] >= 40:
                print(f"MODERATE: {val['name']} level {round(val['h'], 2)} cm")
            else:
                print(f"NORMAL: {val['name']} level {round(val['h'], 2)} cm")
                
        time.sleep(5)

if __name__ == "__main__":
    simulate_flash_flood()
