import requests

URL = "https://sih26178-1.onrender.com/api/sos"

def send():
    try:
        requests.post(URL, json={
            "device_id": "SIH_FIELD_USER_12", 
            "lat": 23.835, 
            "lon": 91.282
        }, timeout=5)
        print("SOS Sent")
    except Exception:
        pass

if __name__ == "__main__":
    send()
