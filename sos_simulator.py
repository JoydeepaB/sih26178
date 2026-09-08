import requests
import time

URL = "https://sih26178-1.onrender.com/api/sos"

def trigger():
    requests.post(URL, json={
        "device_id": "RESCUE_TEAM_01",
        "lat": 23.834, "lon": 91.282,
        "timestamp": int(time.time())
    })
    print("SOS Dispatched.")

if __name__ == "__main__":
    trigger()
