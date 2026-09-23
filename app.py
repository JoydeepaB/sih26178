from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS
import sqlite3
import os
import time
import math
import random
import threading
import json
import urllib.request

app = Flask(__name__)
CORS(app)

DB_PATH = "environment.db"

CWC_MHA_HISTORICAL_DATA = {
    "Assam": {
        "cwc_70yr_lives_lost": 3485,
        "cwc_70yr_damage_crores": 14210.5,
        "flood_prone_districts": 31,
        "major_river_basins": ["Brahmaputra", "Barak"],
        "critical_stations": ["Guwahati", "Dibrugarh", "Silchar"]
    },
    "Bihar": {
        "cwc_70yr_lives_lost": 10240,
        "cwc_70yr_damage_crores": 19450.8,
        "flood_prone_districts": 28,
        "major_river_basins": ["Ganga", "Kosi", "Gandak", "Bagmati"],
        "critical_stations": ["Patna", "Khagaria", "Darbhanga"]
    },
    "Uttar Pradesh": {
        "cwc_70yr_lives_lost": 12850,
        "cwc_70yr_damage_crores": 22100.2,
        "flood_prone_districts": 33,
        "major_river_basins": ["Ganga", "Yamuna", "Ghaghra", "Ramganga"],
        "critical_stations": ["Varanasi", "Prayagraj", "Ayodhya"]
    },
    "West Bengal": {
        "cwc_70yr_lives_lost": 6120,
        "cwc_70yr_damage_crores": 18230.0,
        "flood_prone_districts": 18,
        "major_river_basins": ["Ganga", "Teesta", "Damodar"],
        "critical_stations": ["Kolkata", "Jalpaiguri", "Malda"]
    },
    "Odisha": {
        "cwc_70yr_lives_lost": 3950,
        "cwc_70yr_damage_crores": 11840.4,
        "flood_prone_districts": 21,
        "major_river_basins": ["Mahanadi", "Brahmani", "Baitarani"],
        "critical_stations": ["Cuttack", "Sambalpur", "Bhadrak"]
    },
    "Kerala": {
        "cwc_70yr_lives_lost": 1890,
        "cwc_70yr_damage_crores": 26800.0,
        "flood_prone_districts": 14,
        "major_river_basins": ["Periyar", "Bharatpuzha", "Pamba"],
        "critical_stations": ["Kochi", "Aluva", "Chengannur"]
    },
    "Gujarat": {
        "cwc_70yr_lives_lost": 4120,
        "cwc_70yr_damage_crores": 9850.0,
        "flood_prone_districts": 16,
        "major_river_basins": ["Narmada", "Tapi", "Sabarmati"],
        "critical_stations": ["Bharuch", "Surat", "Ahmedabad"]
    },
    "Uttarakhand": {
        "cwc_70yr_lives_lost": 6890,
        "cwc_70yr_damage_crores": 12500.0,
        "flood_prone_districts": 13,
        "major_river_basins": ["Bhagirathi", "Alaknanda", "Mandakini"],
        "critical_stations": ["Haridwar", "Rishikesh", "Rudraprayag"]
    },
    "Himachal Pradesh": {
        "cwc_70yr_lives_lost": 2340,
        "cwc_70yr_damage_crores": 10400.0,
        "flood_prone_districts": 12,
        "major_river_basins": ["Beas", "Satluj", "Ravi"],
        "critical_stations": ["Mandi", "Kullu", "Shimla"]
    },
    "Jammu & Kashmir": {
        "cwc_70yr_lives_lost": 1450,
        "cwc_70yr_damage_crores": 8200.0,
        "flood_prone_districts": 10,
        "major_river_basins": ["Jhelum", "Chenab"],
        "critical_stations": ["Srinagar", "Sangam", "Baramulla"]
    },
    "Andhra Pradesh": {
        "cwc_70yr_lives_lost": 3200,
        "cwc_70yr_damage_crores": 9300.0,
        "flood_prone_districts": 15,
        "major_river_basins": ["Godavari", "Krishna"],
        "critical_stations": ["Vijayawada", "Rajahmundry"]
    },
    "Tamil Nadu": {
        "cwc_70yr_lives_lost": 1980,
        "cwc_70yr_damage_crores": 15600.0,
        "flood_prone_districts": 14,
        "major_river_basins": ["Cauvery", "Adyar", "Cooum"],
        "critical_stations": ["Hogenakkal", "Chennai", "Thanjavur"]
    }
}

INDIAN_STATIONS = [
    {"node_id": "NODE_CWC_01", "name": "Brahmaputra - Guwahati (Assam)", "state": "Assam", "lat": 26.185, "lon": 91.750, "base_depth": 48.5, "danger_level": 49.68},
    {"node_id": "NODE_CWC_02", "name": "Ganga - Patna Dighaghat (Bihar)", "state": "Bihar", "lat": 25.632, "lon": 85.110, "base_depth": 47.8, "danger_level": 50.45},
    {"node_id": "NODE_CWC_03", "name": "Yamuna - Old Railway Bridge (Delhi)", "state": "Delhi", "lat": 28.665, "lon": 77.245, "base_depth": 204.2, "danger_level": 205.33},
    {"node_id": "NODE_CWC_04", "name": "Mahanadi - Cuttack Mundali (Odisha)", "state": "Odisha", "lat": 20.460, "lon": 85.875, "base_depth": 84.1, "danger_level": 88.50},
    {"node_id": "NODE_CWC_05", "name": "Godavari - Rajahmundry (AP)", "state": "Andhra Pradesh", "lat": 16.995, "lon": 81.780, "base_depth": 14.5, "danger_level": 17.50},
    {"node_id": "NODE_CWC_06", "name": "Periyar - Aluva (Kerala)", "state": "Kerala", "lat": 10.108, "lon": 76.353, "base_depth": 3.8, "danger_level": 5.50},
    {"node_id": "NODE_CWC_07", "name": "Narmada - Garudeshwar (Gujarat)", "state": "Gujarat", "lat": 21.880, "lon": 73.660, "base_depth": 28.5, "danger_level": 31.00},
    {"node_id": "NODE_CWC_08", "name": "Ganga - Haridwar (Uttarakhand)", "state": "Uttarakhand", "lat": 29.950, "lon": 78.160, "base_depth": 293.0, "danger_level": 294.00},
    {"node_id": "NODE_CWC_09", "name": "Jhelum - Ram Munshi Bagh (J&K)", "state": "Jammu & Kashmir", "lat": 34.070, "lon": 74.830, "base_depth": 15.2, "danger_level": 18.00},
    {"node_id": "NODE_CWC_10", "name": "Cauvery - Hogenakkal (Tamil Nadu)", "state": "Tamil Nadu", "lat": 12.115, "lon": 77.775, "base_depth": 11.2, "danger_level": 13.50}
]

weather_cache = {}

def get_live_weather(lat, lon):
    key = f"{round(lat, 2)},{round(lon, 2)}"
    now = time.time()
    
    if key in weather_cache:
        data, cached_at = weather_cache[key]
        if now - cached_at < 600:
            return data

    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation,rain,temperature_2m&timezone=Asia%2FKolkata"
        req = urllib.request.Request(url, headers={"User-Agent": "DRISHTI-WaterMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            current = raw.get("current", {})
            rain = float(current.get("rain", current.get("precipitation", 0.0)))
            temp = float(current.get("temperature_2m", 28.0))
            result = {"rain_mm": rain, "temp_c": temp, "live": True}
            weather_cache[key] = (result, now)
            return result
    except Exception:
        return {"rain_mm": 0.0, "temp_c": 28.0, "live": False}

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        node_id TEXT, 
        location_name TEXT, 
        water_cm REAL, 
        timestamp INTEGER,
        risk_level TEXT, 
        risk_score INTEGER, 
        lat REAL, 
        lon REAL,
        rainfall_mm REAL DEFAULT 0.0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        node_id TEXT, 
        risk_level TEXT, 
        message TEXT, 
        timestamp INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT)""")
    db.commit()
    db.close()

surge_state = {"active": False, "node_id": None, "expires_at": 0}

def background_telemetry_loop():
    time.sleep(2)
    while True:
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cursor = conn.cursor()
            now = int(time.time())

            is_surge = surge_state["active"] and (now < surge_state["expires_at"])
            target = surge_state["node_id"]

            for stn in INDIAN_STATIONS:
                weather = get_live_weather(stn["lat"], stn["lon"])
                rain_mm = weather["rain_mm"]
                
                diurnal = math.sin((now % 86400) / 86400.0 * 2 * math.pi) * 0.15
                rain_run_off = rain_mm * 0.12
                noise = random.uniform(-0.04, 0.05)
                
                current_depth = round(stn["base_depth"] + diurnal + rain_run_off + noise, 2)

                if is_surge and (target == "ALL" or target == stn["node_id"]):
                    current_depth = round(stn["danger_level"] + random.uniform(0.4, 1.1), 2)
                    rain_mm = max(rain_mm, random.uniform(50.0, 90.0))

                danger = stn["danger_level"]
                warning = danger * 0.95

                if current_depth >= danger:
                    risk_level = "CRITICAL"
                    risk_score = min(100, int(85 + ((current_depth - danger) / (danger * 0.05) * 15)))
                elif current_depth >= warning:
                    risk_level = "WARNING"
                    risk_score = int(60 + ((current_depth - warning) / (danger - warning) * 24))
                else:
                    risk_level = "NORMAL"
                    risk_score = max(5, int((current_depth / warning) * 55))

                cursor.execute("""
                    INSERT INTO readings (node_id, location_name, water_cm, timestamp, risk_level, risk_score, lat, lon, rainfall_mm)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (stn["node_id"], stn["name"], current_depth, now, risk_level, risk_score, stn["lat"], stn["lon"], rain_mm))

                if risk_level in ["CRITICAL", "WARNING"]:
                    msg = f"{stn['name']} water level reached {current_depth}m (Danger mark: {danger}m). Local rain: {rain_mm:.1f} mm/hr."
                    cursor.execute("""
                        INSERT INTO alerts (node_id, risk_level, message, timestamp)
                        VALUES (?, ?, ?, ?)
                    """, (stn["node_id"], risk_level, msg, now))

            cursor.execute("DELETE FROM readings WHERE id NOT IN (SELECT id FROM readings ORDER BY timestamp DESC LIMIT 600)")
            cursor.execute("DELETE FROM alerts WHERE id NOT IN (SELECT id FROM alerts ORDER BY timestamp DESC LIMIT 100)")
            
            conn.commit()
            conn.close()

            if not is_surge and surge_state["active"]:
                surge_state["active"] = False

        except Exception as err:
            print("Background telemetry loop error:", err)

        time.sleep(15)

# Serve the dashboard HTML directly at the root URL
@app.route("/", methods=["GET"])
def index():
    if os.path.exists("dashboard.html"):
        return send_file("dashboard.html")
    return jsonify({
        "status": "online",
        "service": "DRISHTI Early Warning Command",
        "stations": len(INDIAN_STATIONS)
    })

@app.route("/api/status", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "service": "DRISHTI Early Warning Command",
        "stations": len(INDIAN_STATIONS)
    })

@app.route("/api/live", methods=["GET"])
def live_readings():
    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT r.* FROM readings r
        INNER JOIN (
            SELECT node_id, MAX(timestamp) as max_ts
            FROM readings
            GROUP BY node_id
        ) latest ON r.node_id = latest.node_id AND r.timestamp = latest.max_ts
        ORDER BY r.risk_score DESC
    """)
    rows = c.fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/history", methods=["GET"])
def reading_history():
    node_id = request.args.get("node_id")
    limit = int(request.args.get("limit", 60))
    db = get_db()
    c = db.cursor()
    if node_id:
        c.execute("SELECT * FROM readings WHERE node_id = ? ORDER BY timestamp DESC LIMIT ?", (node_id, limit))
    else:
        c.execute("SELECT * FROM readings ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    return jsonify([dict(row) for row in reversed(rows)])

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 50")
    rows = c.fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/cwc-historical", methods=["GET"])
def historical_data():
    return jsonify({
        "source": "Central Water Commission & MHA (1953-2023)",
        "data": CWC_MHA_HISTORICAL_DATA
    })

@app.route("/api/demo-surge", methods=["POST"])
def trigger_surge():
    payload = request.get_json(silent=True) or {}
    node_id = payload.get("node_id", "ALL")
    duration = int(payload.get("duration_seconds", 90))
    
    surge_state["active"] = True
    surge_state["node_id"] = node_id
    surge_state["expires_at"] = int(time.time()) + duration
    
    return jsonify({
        "status": "ok",
        "target": node_id,
        "expires_in": duration
    })

init_db()
worker = threading.Thread(target=background_telemetry_loop, daemon=True)
worker.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
