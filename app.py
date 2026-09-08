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
    if db is not None: db.close()

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
    w = float(data.get("water_cm", 0))
    s = float(data.get("soil_pct", 0))
    r = float(data.get("rain_mm_hr", 0))
    score = 0
    if w > 75: score += 4
    elif w > 50: score += 2
    if s > 80: score += 3
    if r > 25: score += 4
    if trend > 1.5: score += 3
    
    current = get_risk_label(score)
    pred_score = score + (int(trend * 2) if trend > 0.5 else 0)
    return current, score, get_risk_label(pred_score)

@app.route("/")
def home():
    return jsonify({"status": "active", "info": "SIH26178 Network"})

@app.route("/api/sensor-data", methods=["POST"])
def ingest():
    payload = request.get_json(silent=True)
    if not payload: return jsonify({"success": False}), 400
    items = payload if isinstance(payload, list) else [payload]
    db = get_db()
    cursor = db.cursor()
    
    for item in items:
        uid = item["node_id"]
        loc = item.get("location_name", LOCATIONS.get(uid, "National Station"))
        lt = item.get("latitude", 23.83)
        ln = item.get("longitude", 91.28)
        
        cursor.execute("SELECT water_cm FROM readings WHERE node_id=? ORDER BY id DESC LIMIT 1", (uid,))
        prev = cursor.fetchone()
        trend = (float(item.get("water_cm", 0)) - prev[0]) if prev else 0
        
        curr_lvl, sc, pred_lvl = analyze_risk(item, trend)
        ts = int(item.get("timestamp", time.time()))
        
        cursor.execute("""INSERT INTO readings 
            (node_id, location_name, water_cm, soil_pct, rain_mm_hr, temp, humidity, timestamp, risk_level, risk_score, lat, lon)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", 
            (uid, loc, item.get("water_cm", 0), item.get("soil_pct", 0), item.get("rain_mm_hr", 0), 
             item.get("temp", 0), item.get("humidity", 0), ts, curr_lvl, sc, lt, ln))
        
        if curr_lvl in ["HIGH", "CRITICAL"]:
            cursor.execute("INSERT INTO alerts (node_id, risk_level, message, timestamp) VALUES (?,?,?,?)", 
                           (uid, curr_lvl, f"Flood Warning at {loc}", ts))
    db.commit()
    return jsonify({"success": True}), 201

@app.route("/api/nodes")
def get_nodes():
    db = get_db()
    data = db.execute("SELECT * FROM readings WHERE id IN (SELECT MAX(id) FROM readings GROUP BY node_id)").fetchall()
    output = []
    for row in data:
        item = dict(row)
        cursor = db.cursor()
        cursor.execute("SELECT water_cm FROM readings WHERE node_id=? AND id < ? ORDER BY id DESC LIMIT 1", (item["node_id"], item["id"]))
        prev = cursor.fetchone()
        diff = (item["water_cm"] - prev[0]) if prev else 0
        _, _, forecast = analyze_risk(item, diff)
        item["predicted_risk"] = forecast
        output.append(item)
    return jsonify({"success": True, "nodes": output})

@app.route("/api/statistics")
def get_stats():
    db = get_db()
    r = db.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    a = db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    return jsonify({"success": True, "statistics": {"total_readings": r, "total_alerts": a}})

@app.route("/api/sos", methods=["GET", "POST"])
def manage_sos():
    db = get_db()
    if request.method == "POST":
        req = request.get_json()
        db.execute("INSERT INTO sos_alerts (device_id, latitude, longitude, timestamp) VALUES (?,?,?,?)",
            (req["device_id"], req["lat"], req["lon"], int(time.time())))
        db.commit()
        return jsonify({"success": True})
    data = db.execute("SELECT * FROM sos_alerts ORDER BY timestamp DESC LIMIT 10").fetchall()
    return jsonify({"success": True, "sos": [dict(r) for r in data]})

@app.route("/api/nodes/<node_id>/history")
def get_history(node_id):
    db = get_db()
    data = db.execute("SELECT * FROM readings WHERE node_id=? ORDER BY timestamp ASC", (node_id,)).fetchall()
    return jsonify({"success": True, "history": [dict(r) for r in data]})

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
