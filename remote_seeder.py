import requests
import time
import random

URL = "https://sih26178-1.onrender.com/api/sensor-data"

def seed_graph_data():
    node = "DEMO_FLASH_FLOOD_ZONE"
    batch = []
    
    w = 20 
    for i in range(24, 0, -1):
        w += random.uniform(-2, 3)
        batch.append({
            "node_id": node, 
            "location_name": "Guwahati River Bank",
            "water_cm": round(max(10, w), 2),
            "latitude": 26.14, 
            "longitude": 91.73,
            "timestamp": int(time.time()) - (i * 3600)
        })
        
    requests.post(URL, json=batch)

if __name__ == "__main__":
    seed_graph_data()
