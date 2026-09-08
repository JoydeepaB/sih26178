from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
import os
import time
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

DATABASE = os.environ.get("DATABASE_PATH", "environment.db")

WATER_WARN, WATER_HIGH, WATER_CRIT = 40.0, 60.0, 80.0
SOIL_WARN, SOIL_HIGH, SOIL_CRIT = 60.0, 75.0, 85.0
RAIN_WARN, RAIN_HIGH, RAIN_CRIT = 5.0, 15.0, 30.0

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            water_cm REAL NOT NULL,
            soil_pct REAL NOT NULL,
            rain_mm_hr REAL NOT NULL,
            temp REAL NOT NULL,
            humidity REAL NOT NULL,
            timestamp INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            risk_score INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sos_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp INTEGER NOT NULL
        )
    """)
    db.commit()
    db.close()

def evaluate_risk(data):
    water = float(data["water_cm"])
    soil = float(data["soil_pct"])
    rain = float(data["rain_mm_hr"])
    
    score = 0
    reasons = []

    if water >= WATER_CRIT:
        score += 4
        reasons.append("Critical water level")
    elif water >= WATER_HIGH:
        score += 3
        reasons.append("High water level")
    elif water >= WATER_WARN:
        score += 1
        reasons.append("Elevated water level")

    if soil >= SOIL_CRIT:
        score += 4
        reasons.append("Critical soil moisture")
    elif soil >= SOIL_HIGH:
        score += 3
        reasons.append("High soil moisture")
    elif soil >= SOIL_WARN:
        score += 1
        reasons.append("Elevated soil moisture")

    if rain >= RAIN_CRIT:
        score += 4
        reasons.append("Very heavy rainfall")
    elif rain >= RAIN_HIGH:
        score += 3
        reasons.append("Heavy rainfall")
    elif rain >= RAIN_WARN:
        score += 1
        reasons.append("Rainfall detected")

    if score >= 9:
        level = "CRITICAL"
    elif score >= 6:
        level = "HIGH"
    elif score >= 3:
        level = "MODERATE"
    else:
        level = "LOW"

    return level, score, reasons

@app.route("/")
def index():
    return jsonify({"status": "active", "message": "Backend server is running smoothly."})

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "time": int(time.time())})

@app.route("/api/sensor-data", methods=["POST"])
def post_sensor_data():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"success": False, "error": "No JSON payload provided"}), 400

    items = payload if isinstance(payload, list) else [payload]
    results = []

    for item in items:
        if "rain_mm" in item and "rain_mm_hr" not in item:
            item["rain_mm_hr"] = item["rain_mm"]

        required = ["node_id", "water_cm", "soil_pct", "rain_mm_hr", "temp", "humidity", "timestamp"]
        if not all(k in item for k in required):
            results.append({"success": False, "error": "Missing fields", "node_id": item.get("node_id")})
            continue

        try:
            node_id = str(item["node_id"])
            water = float(item["water_cm"])
            soil = float(item["soil_pct"])
            rain = float(item["rain_mm_hr"])
            temp = float(item["temp"])
            humidity = float(item["humidity"])
            ts = int(item["timestamp"])
        except ValueError:
            results.append({"success": False, "error": "Invalid data types", "node_id": item.get("node_id")})
            continue

        risk_level, risk_score, reasons = evaluate_risk(item)
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO readings (node_id, water_cm, soil_pct, rain_mm_hr, temp, humidity, timestamp, risk_level, risk_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (node_id, water, soil, rain, temp, humidity, ts, risk_level, risk_score))
        
        if risk_level in ["HIGH", "CRITICAL"]:
            msg = f"{risk_level} risk detected at node {node_id}"
            cursor.execute("INSERT INTO alerts (node_id, risk_level, message, timestamp) VALUES (?, ?, ?, ?)",
                           (node_id, risk_level, msg, ts))
        
        db.commit()
        results.append({"success": True, "node_id": node_id, "risk": {"level": risk_level, "score": risk_score, "reasons": reasons}})

    return jsonify({"success": True, "results": results if isinstance(payload, list) else results[0]}), 201

@app.route("/api/nodes", methods=["GET"])
def get_nodes():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT r.* FROM readings r
        WHERE r.id IN (SELECT MAX(id) FROM readings GROUP BY node_id)
        ORDER BY r.node_id
    """)
    rows = cursor.fetchall()
    return jsonify({"success": True, "count": len(rows), "nodes": [dict(r) for r in rows]})

@app.route("/api/nodes/<node_id>/history", methods=["GET"])
def get_history(node_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM readings WHERE node_id = ? ORDER BY timestamp ASC", (node_id,))
    rows = cursor.fetchall()
    return jsonify({"success": True, "node_id": node_id, "history": [dict(r) for r in rows]})

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 50")
    rows = cursor.fetchall()
    return jsonify({"success": True, "alerts": [dict(r) for r in rows]})

@app.route("/api/statistics", methods=["GET"])
def get_stats():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) AS total_readings FROM readings")
    total_readings = cursor.fetchone()["total_readings"]
    cursor.execute("SELECT COUNT(*) AS total_alerts FROM alerts")
    total_alerts = cursor.fetchone()["total_alerts"]
    cursor.execute("SELECT COUNT(DISTINCT node_id) AS total_nodes FROM readings")
    total_nodes = cursor.fetchone()["total_nodes"]
    return jsonify({
        "success": True,
        "statistics": {
            "total_nodes": total_nodes,
            "total_readings": total_readings,
            "total_alerts": total_alerts
        }
    })

@app.route("/api/sos", methods=["POST"])
def post_sos():
    data = request.get_json(silent=True)
    if not data or not all(k in data for k in ["device_id", "lat", "lon", "timestamp"]):
        return jsonify({"success": False, "error": "Missing SOS fields"}), 400
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO sos_alerts (device_id, latitude, longitude, timestamp) VALUES (?, ?, ?, ?)",
                   (str(data["device_id"]), float(data["lat"]), float(data["lon"]), int(data["timestamp"])))
    db.commit()
    return jsonify({"success": True, "message": "SOS recorded"}), 201

@app.route("/api/sos", methods=["GET"])
def get_sos():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM sos_alerts ORDER BY timestamp DESC LIMIT 50")
    rows = cursor.fetchall()
    return jsonify({"success": True, "alerts": [dict(r) for r in rows]})

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
