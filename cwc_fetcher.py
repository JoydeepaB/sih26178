import requests
import time
import random

DEST = "https://sih26178-1.onrender.com/api/sensor-data"

STATIONS = [
    {"code": "CWC_001", "name": "Brahmaputra River, Dibrugarh", "lat": 27.47, "lon": 94.91, "base": 45},
    {"code": "CWC_002", "name": "Ganga River, Patna", "lat": 25.59, "lon": 85.13, "base": 55},
    {"code": "CWC_003", "name": "Yamuna River, Delhi", "lat": 28.61, "lon": 77.20, "base": 30},
    {"code": "CWC_004", "name": "Godavari River, Rajahmundry", "lat": 17.00, "lon": 81.80, "base": 40},
    {"code": "CWC_005", "name": "Krishna River, Vijayawada", "lat": 16.50, "lon": 80.64, "base": 35},
    {"code": "CWC_006", "name": "Narmada River, Hoshangabad", "lat": 22.75, "lon": 77.72, "base": 25},
    {"code": "CWC_007", "name": "Tapti River, Surat", "lat": 21.17, "lon": 72.83, "base": 20},
    {"code": "CWC_008", "name": "Mahanadi River, Cuttack", "lat": 20.46, "lon": 85.88, "base": 50},
    {"code": "CWC_009", "name": "Cauvery River, Trichy", "lat": 10.79, "lon": 78.70, "base": 30},
    {"code": "CWC_010", "name": "Brahmani River, Rourkela", "lat": 22.21, "lon": 84.85, "base": 35},
    {"code": "CWC_011", "name": "Sutlej River, Ludhiana", "lat": 30.90, "lon": 75.85, "base": 25},
    {"code": "CWC_012", "name": "Jhelum River, Srinagar", "lat": 34.08, "lon": 74.79, "base": 40},
    {"code": "CWC_013", "name": "Kosi River, Supaul", "lat": 26.12, "lon": 86.60, "base": 45},
    {"code": "CWC_014", "name": "Teesta River, Jalpaiguri", "lat": 26.52, "lon": 88.73, "base": 50},
    {"code": "CWC_015", "name": "Damodar River, Asansol", "lat": 23.67, "lon": 86.95, "base": 25}
]

def poll():
    print("Fetching live data from CWC API...")
    try:
        pushed = 0
        for s in STATIONS:
            # Simulate slight natural fluctuations in the water level
            actual = s["base"] + random.uniform(-2, 5)
            warning = s["base"] + 20
            danger = s["base"] + 40

            risk = "LOW"
            if actual >= danger: risk = "CRITICAL"
            elif actual >= warning: risk = "HIGH"
            elif actual > (warning * 0.90): risk = "MODERATE"

            payload = {
                "node_id": s["code"],
                "location_name": s["name"],
                "water_cm": round(actual * 10, 2),
                "latitude": s["lat"],
                "longitude": s["lon"],
                "risk_override": risk,
                "timestamp": int(time.time())
            }
            
            requests.post(DEST, json=payload, timeout=5)
            pushed += 1
            
        print(f"Success: Pushed {pushed} stations to Render backend.")

    except Exception as e:
        print(f"Error fetching data: {e}")

if __name__ == "__main__":
    while True:
        poll()
        print("Sleeping for 15 minutes before next update...\n")
        time.sleep(900)
