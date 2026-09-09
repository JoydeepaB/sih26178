import requests
import time

SOURCE = "https://ffs.india-water.gov.in/api/v1/get-all-stations-current-level"
DEST = "https://sih26178-1.onrender.com/api/sensor-data"

def poll():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(SOURCE, headers=headers, timeout=30)
        raw = r.json()

        stations = None
        if isinstance(raw, dict):
            for key in ("data", "stations", "results", "station_list"):
                if key in raw and isinstance(raw[key], list):
                    stations = raw[key]
                    break
        elif isinstance(raw, list):
            stations = raw

        if not stations:
            return

        for s in stations:
            try:
                actual = float(s.get('actual_level', 0))
                warning = float(s.get('warning_level', 0))
                danger = float(s.get('danger_level', 0))

                risk = "LOW"
                if actual >= danger and danger > 0: risk = "CRITICAL"
                elif actual >= warning and warning > 0: risk = "HIGH"
                elif warning > 0 and actual > (warning * 0.90): risk = "MODERATE"

                payload = {
                    "node_id": f"CWC_{s.get('station_code', 'UNKNOWN')}",
                    "location_name": f"{s.get('station_name', 'Unknown')}, {s.get('state_name', 'Unknown')}",
                    "water_cm": round(actual * 100, 2),
                    "latitude": float(s.get('latitude', 0)),
                    "longitude": float(s.get('longitude', 0)),
                    "risk_override": risk,
                    "timestamp": int(time.time())
                }
                
                requests.post(DEST, json=payload, timeout=5)
            except Exception:
                continue

    except Exception:
        pass

if __name__ == "__main__":
    while True:
        poll()
        time.sleep(900)
