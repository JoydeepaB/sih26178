import requests
import time

SOURCE = "https://ffs.india-water.gov.in/api/v1/get-all-stations-current-level"
DEST = "https://sih26178-1.onrender.com/api/sensor-data"

def poll():
    try:
        print("Polling CWC River Stations...")
        r = requests.get(SOURCE, timeout=30)
        data = r.json()
        for s in data:
            if float(s['actual_level']) >= float(s['warning_level']):
                requests.post(DEST, json={
                    "node_id": f"CWC_{s['station_code']}",
                    "location_name": f"{s['station_name']}, {s['state_name']}",
                    "water_cm": float(s['actual_level']) * 100,
                    "soil_pct": 50.0, "rain_mm_hr": 0.0, "temp": 28.0, "humidity": 75.0,
                    "latitude": float(s['latitude']), "longitude": float(s['longitude'])
                })
                print(f"Danger at {s['station_name']}")
    except: print(" Govt server busy...")

if __name__ == "__main__":
    while True:
        poll()
        time.sleep(300)
