from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
import os
import time

app = Flask(__name__)
CORS(app)

DB_PATH = "environment.db"

LOCATIONS = {
    "Drain_Zone_A": "Akhaura Road Drain",
    "River_Bank_B": "Howrah River Bank",
    "Lowland_Zone_C": "Battala Lowland Area",
    "N1": "Indranagar Sector 2"
}

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
        id INTEGER PRIMARY KEY AUTOINCREMENT, node_id TEXT, 
        location_name TEXT, water_cm REAL, soil_pct REAL, rain_mm_hr REAL,
        temp REAL, humidity REAL, timestamp INTEGER,
        risk_level TEXT, risk_score INTEGER, lat REAL, lon REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, node_id TEXT, 
        risk_level TEXT, message TEXT, timestamp INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sos_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, 
        latitude REAL, longitude REAL, timestamp INTEGER)""")
    db.commit()
    db.close()

def get_risk_label(score):
    if score >= 9: return "CRITICAL"
    if score >= 6: return "HIGH"
    if score >= 3: return "MODERATE"
    return "LOW"

def analyze_risk(data, trend):
    w, s, r = float(data["water_cm"]), float(data["soil_pct"]), float(data["rain_mm_hr"])
    score = 0
    reasons = []
    
    if w > 75: 
        score += 4
        reasons.append("Flood Threshold")
    elif w > 50: 
        score += 2
        reasons.append("High Water")
    
    if s > 80: 
        score += 3
        reasons.append("Saturated Soil")
    
    if r > 25: 
        score += 4
        reasons.append("Heavy Downpour")
    
    if trend > 1.5: 
        score += 3
        reasons.append("Rapid Rise")

    current_lvl = get_risk_label(score)
    
    pred_score = score
    if trend > 0.5:
        pred_score += int(trend * 2)
    elif trend < -0.5:
        pred_score -= 1

    pred_lvl = get_risk_label(pred_score)
    
    return current_lvl, score, pred_lvl, reasons

@app.route("/api/sensor-data", methods=["POST"])
def ingest_data():
    payload = request.get_json(silent=True)
    if not payload: return jsonify({"success": False}), 400
    
    data_list = payload if isinstance(payload, list) else [payload]
    db = get_db()
    cursor = db.cursor()
    responses = []

    for item in data_list:
        uid = item["node_id"]
        place = item.get("location_name", LOCATIONS.get(uid, "Remote Node"))
        lt = item.get("latitude", 23.83)
        ln = item.get("longitude", 91.28)

        cursor.execute("SELECT water_cm FROM readings WHERE node_id=? ORDER BY id DESC LIMIT 1", (uid,))
        last = cursor.fetchone()
        diff = (float(item["water_cm"]) - last[0]) if last else 0
        
        cur_status, val, next_status, alerts = analyze_risk(item, diff)
        now = int(item.get("timestamp", time.time()))
        
        cursor.execute("""INSERT INTO readings 
            (node_id, location_name, water_cm, soil_pct, rain_mm_hr, temp, humidity, timestamp, risk_level, risk_score, lat, lon)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", 
            (uid, place, item["water_cm"], item["soil_pct"], item["rain_mm_hr"], item["temp"], item["humidity"], now, cur_status, val, lt, ln))
        
        if cur_status in ["HIGH", "CRITICAL"]:
            msg = f"{cur_status}: " + " & ".join(alerts)
            cursor.execute("INSERT INTO alerts (node_id, risk_level, message, timestamp) VALUES (?,?,?,?)", (uid, cur_status, msg, now))
        
        db.commit()
        responses.append({"id": uid, "status": cur_status, "predicted": next_status})
        
    return jsonify({"success": True, "data": responses}), 201

@app.route("/api/nodes")
def fetch_nodes():
    db = get_db()
    data = db.execute("""
        SELECT r.* FROM readings r 
        WHERE id IN (SELECT MAX(id) FROM readings GROUP BY node_id)
    """).fetchall()
    
    output = []
    for row in data:
        item = dict(row)
        cursor = db.cursor()
        cursor.execute("SELECT water_cm FROM readings WHERE node_id=? AND id < ? ORDER BY id DESC LIMIT 1", (item["node_id"], item["id"]))
        prev = cursor.fetchone()
        change = (item["water_cm"] - prev[0]) if prev else 0
        _, _, forecast, _ = analyze_risk(item, change)
        item["predicted_risk"] = forecast
        output.append(item)
        
    return jsonify({"success": True, "nodes": output})

@app.route("/api/alerts")
def fetch_alerts():
    db = get_db()
    data = db.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 15").fetchall()
    return jsonify({"success": True, "alerts": [dict(r) for r in data]})

@app.route("/api/sos", methods=["GET", "POST"])
def manage_sos():
    db = get_db()
    if request.method == "POST":
        req = request.get_json()
        db.execute("INSERT INTO sos_alerts (device_id, latitude, longitude, timestamp) VALUES (?,?,?,?)",
            (req["device_id"], req["lat"], req["lon"], int(time.time())))
        db.commit()
        return jsonify({"success": True})
    data = db.execute("SELECT * FROM sos_alerts ORDER BY timestamp DESC LIMIT 15").fetchall()
    return jsonify({"success": True, "sos": [dict(r) for r in data]})

@app.route("/api/statistics")
def fetch_stats():
    db = get_db()
    readings = db.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    warnings = db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    return jsonify({"success": True, "statistics": {"total_readings": readings, "total_alerts": warnings}})

@app.route("/api/nodes/<node_id>/history")
def fetch_history(node_id):
    db = get_db()
    data = db.execute("SELECT * FROM readings WHERE node_id=? ORDER BY timestamp ASC", (node_id,)).fetchall()
    return jsonify({"success": True, "history": [dict(r) for r in data]})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
