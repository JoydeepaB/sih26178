import requests
import time

URL = "https://sih26178-1.onrender.com/api/sos"

def trigger_emergency():
    msg = {
        "device_id": "FIELD_UNIT_ALPHA",
        "lat": 23.836,
        "lon": 91.284,
        "timestamp": int(time.time())
    }
    requests.post(URL, json=msg)
    print("SOS Signal Sent to Control Center.")

if __name__ == "__main__":
    trigger_emergency()
