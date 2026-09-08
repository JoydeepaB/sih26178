import requests
import time

SOURCE = "https://ffs.india-water.gov.in/api/v1/get-all-stations-current-level"
DEST = "https://sih26178-1.onrender.com/api/sensor-data"

def poll_india():
    try:
        print("Polling All-India Stations...")
        r = requests.get(SOURCE, timeout=30)
        stations = r.json()
       
        for s in stations[:100]:
            try:
                requests.post(DEST, json={
                    "node_id": f"CWC_{s['station_code']}",
                    "location_name": f"{s['station_name']}, {s['state_name']}",
                    "water_cm": float(s['actual_level']) * 100,
                    "latitude": float(s['latitude']),
                    "longitude": float(s['longitude']),
                    "timestamp": int(time.time())
                }, timeout=5)
                print(f"Synced: {s['station_name']}")
            except: continue
        print("Batch sync complete.")
    except: print("Govt API Busy...")

if __name__ == "__main__":
    while True:
        poll_india()
        time.sleep(300)
