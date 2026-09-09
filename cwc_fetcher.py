import requests
import time

SOURCE = "https://ffs.india-water.gov.in/api/v1/get-all-stations-current-level"
DEST = "https://sih26178-1.onrender.com/api/sensor-data"

def poll():
    try:
        r = requests.get(SOURCE, timeout=30)
        stations = r.json()
        for s in stations[:150]:
            try:
                actual = float(s['actual_level'])
                warning = float(s['warning_level'])
                danger = float(s['danger_level'])
                
                risk = "LOW"
                if actual >= danger: risk = "CRITICAL"
                elif actual >= warning: risk = "HIGH"
                elif actual > (warning * 0.95): risk = "MODERATE"

                payload = {
                    "node_id": f"CWC_{s['station_code']}",
                    "location_name": f"{s['station_name']}, {s['state_name']}",
                    "water_cm": round(actual * 100, 2),
                    "latitude": float(s['latitude']),
                    "longitude": float(s['longitude']),
                    "risk_override": risk,
                    "timestamp": int(time.time())
                }
                requests.post(DEST, json=payload, timeout=5)
            except:
                continue
    except:
        pass

if __name__ == "__main__":
    poll()
