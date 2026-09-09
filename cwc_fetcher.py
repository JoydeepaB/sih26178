import requests
import time
import json

SOURCE = "https://ffs.india-water.gov.in/api/v1/get-all-stations-current-level"
DEST = "https://sih26178-1.onrender.com/api/sensor-data"

def poll():
    try:
        r = requests.get(SOURCE, timeout=30)
        raw = r.json()

    
        if isinstance(raw, dict):
            stations = None
            for key in ("data", "stations", "results", "station_list"):
                if key in raw and isinstance(raw[key], list):
                    stations = raw[key]
                    break
            if stations is None:
                print("Unexpected response shape -- top-level keys:", list(raw.keys()))
                return
        elif isinstance(raw, list):
            stations = raw
        else:
            print("Unexpected response type:", type(raw))
            return

        if not stations:
            print("API returned zero stations.")
            return

        # DEBUG: see the REAL field names before trusting the parsing below.
        print("Sample station record:")
        print(json.dumps(stations[0], indent=2))

        pushed, failed = 0, 0
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
                pushed += 1
            except Exception:
                failed += 1
                continue

        print(f"Pushed {pushed}, failed {failed} of {min(150, len(stations))}.")
        if pushed == 0:
            print("Zero parsed -- update the s['...'] keys above to match the sample record printed earlier.")
    except Exception as e:
        print(f"Server error: {e}")

if __name__ == "__main__":
    poll()
