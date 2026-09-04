import requests
import time
import random

API_URL = "http://127.0.0.1:5000/api/sensor-data"

NODES = {
    "Drain_Zone_A": {
        "water_cm": 30,
        "soil_pct": 50,
        "rain_mm_hr": 0,
        "temp": 29,
        "humidity": 72
    },
    "River_Bank_B": {
        "water_cm": 45,
        "soil_pct": 65,
        "rain_mm_hr": 0,
        "temp": 28,
        "humidity": 78
    },
    "Lowland_Zone_C": {
        "water_cm": 55,
        "soil_pct": 72,
        "rain_mm_hr": 0,
        "temp": 29,
        "humidity": 80
    }
}

INTERVAL = 5


def send_data(node_id, data):
    payload = {
        "node_id": node_id,
        "water_cm": round(data["water_cm"], 2),
        "soil_pct": round(data["soil_pct"], 2),
        "rain_mm_hr": round(data["rain_mm_hr"], 2),
        "temp": round(data["temp"], 2),
        "humidity": round(data["humidity"], 2),
        "timestamp": int(time.time())
    }

    try:
        response = requests.post(API_URL, json=payload)

        if response.status_code == 201:
            result = response.json()

            print(
                node_id,
                "| Water:", payload["water_cm"],
                "| Soil:", payload["soil_pct"],
                "| Rain:", payload["rain_mm_hr"],
                "| Risk:", result["risk"]["level"],
                "| Score:", result["risk"]["score"]
            )

            if result["risk"]["reasons"]:
                print("Reasons:", ", ".join(result["risk"]["reasons"]))

            if result["alert_created"]:
                print("Alert created")

        else:
            print(node_id, "API error:", response.status_code)

    except requests.exceptions.ConnectionError:
        print("Could not connect to the server")


def update_environment(step):

    if step < 10:
        phase = "normal"
    elif step < 20:
        phase = "rain"
    elif step < 35:
        phase = "heavy_rain"
    elif step < 45:
        phase = "storm"
    else:
        phase = "recovery"

    for node_id, data in NODES.items():

        data["temp"] += random.uniform(-0.3, 0.3)
        data["humidity"] += random.uniform(-1, 1)

        if phase == "normal":
            data["rain_mm_hr"] += random.uniform(-0.5, 0.5)

        elif phase == "rain":
            data["rain_mm_hr"] += random.uniform(1, 3)

        elif phase == "heavy_rain":
            data["rain_mm_hr"] += random.uniform(2, 5)

        elif phase == "storm":
            data["rain_mm_hr"] += random.uniform(1, 4)

        elif phase == "recovery":
            data["rain_mm_hr"] -= random.uniform(2, 4)

        if phase in ["rain", "heavy_rain", "storm"]:
            data["water_cm"] += data["rain_mm_hr"] * random.uniform(0.08, 0.18)
            data["soil_pct"] += random.uniform(0.5, 2)

        elif phase == "recovery":
            data["water_cm"] -= random.uniform(1, 3)
            data["soil_pct"] -= random.uniform(0.2, 0.8)

        data["water_cm"] += random.uniform(-1, 1)
        data["soil_pct"] += random.uniform(-0.5, 0.5)

        data["water_cm"] = max(0, min(100, data["water_cm"]))
        data["soil_pct"] = max(0, min(100, data["soil_pct"]))
        data["rain_mm_hr"] = max(0, min(100, data["rain_mm_hr"]))
        data["humidity"] = max(0, min(100, data["humidity"]))
        data["temp"] = max(10, min(50, data["temp"]))


def main():

    print("Starting environmental data simulation")
    print("Nodes:", ", ".join(NODES.keys()))

    step = 0

    while True:

        update_environment(step)

        for node_id, data in NODES.items():
            send_data(node_id, data)
            time.sleep(0.5)

        step += 1
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
