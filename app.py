#!/usr/bin/env python3
from flask import Flask, request, jsonify, g
import sqlite3
import os
import time
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ============================================================
# CONFIGURATION
# ============================================================
DATABASE = os.environ.get("DATABASE_PATH", "environment.db")

# Prototype configuration.
MAX_WATER_LEVEL_CM = 100.0

WATER_WARNING_CM = 40.0
WATER_HIGH_CM = 60.0
WATER_CRITICAL_CM = 80.0

SOIL_WARNING_PCT = 60.0
SOIL_HIGH_PCT = 75.0
SOIL_CRITICAL_PCT = 85.0

RAIN_WARNING_MM_HR = 5.0
RAIN_HIGH_MM_HR = 15.0
RAIN_CRITICAL_MM_HR = 30.0

# Timestamp allowances (seconds). Accept timestamps within +/- 7 days.
TIMESTAMP_ALLOWED_DRIFT = 7 * 24 * 3600

# Limits
NODE_ID_MAX_LENGTH = 64
DEVICE_ID_MAX_LENGTH = 64

# ============================================================
# DATABASE (per-request connection; teardown closes)
# ============================================================
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

def initialize_database():
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

    # Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_node_id ON readings(node_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sos_timestamp ON sos_alerts(timestamp)")

    db.commit()
    db.close()

# ============================================================
# RISK ENGINE
# ============================================================
def calculate_risk(data):
    water = float(data["water_cm"])
    soil = float(data["soil_pct"])
    rain = float(data["rain_mm_hr"])

    score = 0
    reasons = []

    # WATER
    if water >= WATER_CRITICAL_CM:
        score += 4
        reasons.append("Critical water level")
    elif water >= WATER_HIGH_CM:
        score += 3
        reasons.append("High water level")
    elif water >= WATER_WARNING_CM:
        score += 1
        reasons.append("Elevated water level")

    # SOIL
    if soil >= SOIL_CRITICAL_PCT:
        score += 4
        reasons.append("Critical soil moisture")
    elif soil >= SOIL_HIGH_PCT:
        score += 3
        reasons.append("High soil moisture")
    elif soil >= SOIL_WARNING_PCT:
        score += 1
        reasons.append("Elevated soil moisture")

    # RAIN
    if rain >= RAIN_CRITICAL_MM_HR:
        score += 4
        reasons.append("Very heavy rainfall")
    elif rain >= RAIN_HIGH_MM_HR:
        score += 3
        reasons.append("Heavy rainfall")
    elif rain >= RAIN_WARNING_MM_HR:
        score += 1
        reasons.append("Rainfall detected")

    # FINAL
    if score >= 9:
        risk_level = "CRITICAL"
    elif score >= 6:
        risk_level = "HIGH"
    elif score >= 3:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return risk_level, score, reasons

# ============================================================
# VALIDATION UTILITIES
# ============================================================
def is_reasonable_timestamp(ts, allowed_drift_seconds=TIMESTAMP_ALLOWED_DRIFT):
    now = int(time.time())
    return (now - allowed_drift_seconds) <= ts <= (now + allowed_drift_seconds)

def normalize_and_validate_sensor_payload(data):
    # Accept 'rain_mm' from ESP32 firmware as synonym for rain_mm_hr
    if "rain_mm" in data and "rain_mm_hr" not in data:
        data["rain_mm_hr"] = data["rain_mm"]

    required_fields = [
        "node_id",
        "water_cm",
        "soil_pct",
        "rain_mm_hr",
        "temp",
        "humidity",
        "timestamp"
    ]

    missing = [f for f in required_fields if f not in data]
    if missing:
        return False, f"Missing fields: {', '.join(missing)}", None

    node_id = str(data["node_id"])
    if not (1 <= len(node_id) <= NODE_ID_MAX_LENGTH):
        return False, f"node_id must be 1..{NODE_ID_MAX_LENGTH} chars", None

    try:
        water = float(data["water_cm"])
        soil = float(data["soil_pct"])
        rain = float(data["rain_mm_hr"])
        temp = float(data["temp"])
        humidity = float(data["humidity"])
        ts = int(data["timestamp"])
    except (ValueError, TypeError):
        return False, "Sensor values contain invalid data types.", None

    if water < 0:
        return False, "water_cm cannot be negative.", None
    if not 0 <= soil <= 100:
        return False, "soil_pct must be between 0 and 100.", None
    if rain < 0:
        return False, "rain_mm_hr cannot be negative.", None
    if not -50 <= temp <= 70:
        return False, "temp is outside expected range.", None
    if not 0 <= humidity <= 100:
        return False, "humidity must be between 0 and 100.", None
    if not is_reasonable_timestamp(ts):
        return False, "timestamp is outside allowed range.", None

    normalized = {
        "node_id": node_id,
        "water_cm": water,
        "soil_pct": soil,
        "rain_mm_hr": rain,
        "temp": temp,
        "humidity": humidity,
        "timestamp": ts
    }
    return True, None, normalized

# ============================================================
# DB WRITE HELPERS
# ============================================================
def save_reading(data, risk_level, risk_score):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO readings (
                node_id,
                water_cm,
                soil_pct,
                rain_mm_hr,
                temp,
                humidity,
                timestamp,
                risk_level,
                risk_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["node_id"],
            data["water_cm"],
            data["soil_pct"],
            data["rain_mm_hr"],
            data["temp"],
            data["humidity"],
            data["timestamp"],
            risk_level,
            risk_score
        ))
        db.commit()
    except sqlite3.DatabaseError:
        db.rollback()
        app.logger.exception("Failed to save reading for node %s", data.get("node_id"))
        raise

def save_alert(node_id, risk_level, message, timestamp):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO alerts (node_id, risk_level, message, timestamp)
            VALUES (?, ?, ?, ?)
        """, (node_id, risk_level, message, timestamp))
        db.commit()
    except sqlite3.DatabaseError:
        db.rollback()
        app.logger.exception("Failed to save alert for node %s", node_id)
        raise

# ============================================================
# API: HOME / HEALTH
# ============================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "project": "SIH26178",
        "system": "AI-Powered Environmental Intelligence Network",
        "status": "online",
        "message": "Environmental monitoring backend is running."
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": int(time.time())})

# ============================================================
# API: RECEIVE SENSOR DATA (single OR batch)
# ============================================================
@app.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"success": False, "error": "JSON body required."}), 400

    results = []
    items = payload if isinstance(payload, list) else [payload]

    for item in items:
        ok, err, normalized = normalize_and_validate_sensor_payload(item)
        if not ok:
            results.append({"success": False, "error": err, "node_id": item.get("node_id")})
            continue

        try:
            risk_level, risk_score, reasons = calculate_risk(normalized)
            save_reading(normalized, risk_level, risk_score)

            alert_created = False
            if risk_level in ["HIGH", "CRITICAL"]:
                message = f"{risk_level} environmental risk detected at node {normalized['node_id']}."
                save_alert(normalized["node_id"], risk_level, message, normalized["timestamp"])
                alert_created = True

            results.append({
                "success": True,
                "node_id": normalized["node_id"],
                "risk": {"level": risk_level, "score": risk_score, "reasons": reasons},
                "alert_created": alert_created
            })
        except Exception:
            results.append({"success": False, "error": "Internal DB error.", "node_id": normalized["node_id"]})

    if not isinstance(payload, list):
        res = results[0]
        status = 201 if res.get("success") else 400
        return jsonify(res), status

    return jsonify({"success": True, "results": results}), 201

# ============================================================
# READ endpoints
# ============================================================
@app.route("/api/nodes", methods=["GET"])
def get_nodes():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT r.*
        FROM readings r
        INNER JOIN (
            SELECT node_id, MAX(id) AS latest_id
            FROM readings
            GROUP BY node_id
        ) latest ON r.id = latest.latest_id
        ORDER BY r.node_id
    """)
    rows = cursor.fetchall()
    return jsonify({"success": True, "count": len(rows), "nodes": [dict(row) for row in rows]})

@app.route("/api/nodes/<node_id>", methods=["GET"])
def get_node(node_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM readings WHERE node_id = ? ORDER BY id DESC LIMIT 1", (node_id,))
    row = cursor.fetchone()
    if row is None:
        return jsonify({"success": False, "error": "Node not found."}), 404
    return jsonify({"success": True, "node": dict(row)})

@app.route("/api/nodes/<node_id>/history", methods=["GET"])
def get_node_history(node_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT id, node_id, water_cm, soil_pct, rain_mm_hr, temp, humidity, timestamp, risk_level, risk_score
        FROM readings WHERE node_id = ? ORDER BY timestamp ASC
    """, (node_id,))
    rows = cursor.fetchall()
    return jsonify({"success": True, "node_id": node_id, "count": len(rows), "history": [dict(row) for row in rows]})

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 100")
    rows = cursor.fetchall()
    return jsonify({"success": True, "count": len(rows), "alerts": [dict(row) for row in rows]})

@app.route("/api/statistics", methods=["GET"])
def get_statistics():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) AS total_readings FROM readings")
    total_readings = cursor.fetchone()["total_readings"]
    cursor.execute("SELECT COUNT(*) AS total_alerts FROM alerts")
    total_alerts = cursor.fetchone()["total_alerts"]
    cursor.execute("SELECT COUNT(DISTINCT node_id) AS total_nodes FROM readings")
    total_nodes = cursor.fetchone()["total_nodes"]
    cursor.execute("SELECT risk_level, COUNT(*) AS count FROM readings GROUP BY risk_level")
    risk_distribution = {row["risk_level"]: row["count"] for row in cursor.fetchall()}
    return jsonify({"success": True, "statistics": {
        "total_nodes": total_nodes,
        "total_readings": total_readings,
        "total_alerts": total_alerts,
        "risk_distribution": risk_distribution
    }})

# ============================================================
# SOS endpoints
# ============================================================
@app.route("/api/sos", methods=["POST"])
def receive_sos():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "JSON body required."}), 400

    required_fields = ["device_id", "lat", "lon", "timestamp"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"success": False, "error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        device_id = str(data["device_id"])
        if not (1 <= len(device_id) <= DEVICE_ID_MAX_LENGTH):
            return jsonify({"success": False, "error": f"device_id must be 1..{DEVICE_ID_MAX_LENGTH} chars"}), 400
        latitude = float(data["lat"])
        longitude = float(data["lon"])
        timestamp = int(data["timestamp"])
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid SOS data."}), 400

    if not is_reasonable_timestamp(timestamp):
        return jsonify({"success": False, "error": "timestamp is outside allowed range."}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO sos_alerts (device_id, latitude, longitude, timestamp) VALUES (?, ?, ?, ?)",
                       (device_id, latitude, longitude, timestamp))
        db.commit()
    except sqlite3.DatabaseError:
        db.rollback()
        app.logger.exception("Failed to save SOS alert for device %s", device_id)
        return jsonify({"success": False, "error": "Internal DB error."}), 500

    return jsonify({"success": True, "type": "SOS", "device_id": device_id, "latitude": latitude, "longitude": longitude, "timestamp": timestamp, "message": "SOS alert received."}), 201

@app.route("/api/sos", methods=["GET"])
def get_sos_alerts():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM sos_alerts ORDER BY timestamp DESC LIMIT 50")
    rows = cursor.fetchall()
    return jsonify({"success": True, "count": len(rows), "alerts": [dict(row) for row in rows]})

# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "API endpoint not found."}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"success": False, "error": "HTTP method not allowed."}), 405

@app.errorhandler(500)
def server_error(error):
    return jsonify({"success": False, "error": "Internal server error."}), 500

# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    initialize_database()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
