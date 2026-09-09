import requests
import time

URL = "https://sih26178-1.onrender.com/api/sos"

def send():
    requests.post(URL, json={
        "device_id": "SIH_FIELD_USER_12", "lat": 23.835, "lon": 91.282
    })
    print("SOS Alert visible on dashboard now!")

if __name__ == "__main__":
    send()
