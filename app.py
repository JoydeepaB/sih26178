from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os
import time

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

DATABASE = os.environ.get("DATABASE_PATH", "environment.db")

# Prototype configuration.
# CHANGE THESE AFTER YOUR HARDWARE TEAM CALIBRATES THE SYSTEM.
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


# ============================================================
# DATABASE
# ============================================================

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def initialize_database():
    db = get_db()
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


# ============================================================
# RISK ENGINE
# ============================================================

def calculate_risk(data):

    water = float(data["water_cm"])
    soil = float(data["soil_pct"])
    rain = float(data["rain_mm_hr"])

    score = 0
    reasons = []

    # --------------------------------------------------------
    # WATER LEVEL
    # --------------------------------------------------------

    if water >= WATER_CRITICAL_CM:
        score += 4
        reasons.append("Critical water level")

    elif water >= WATER_HIGH_CM:
        score += 3
        reasons.append("High water level")

    elif water >= WATER_WARNING_CM:
        score += 1
        reasons.append("Elevated water level")

    # --------------------------------------------------------
    # SOIL MOISTURE
    # --------------------------------------------------------

    if soil >= SOIL_CRITICAL_PCT:
        score += 4
        reasons.append("Critical soil moisture")

    elif soil >= SOIL_HIGH_PCT:
        score += 3
        reasons.append("High soil moisture")

    elif soil >= SOIL_WARNING_PCT:
        score += 1
        reasons.append("Elevated soil moisture")

    # --------------------------------------------------------
    # RAINFALL
    # --------------------------------------------------------

    if rain >= RAIN_CRITICAL_MM_HR:
        score += 4
        reasons.append("Very heavy rainfall")

    elif rain >= RAIN_HIGH_MM_HR:
        score += 3
        reasons.append("Heavy rainfall")

    elif rain >= RAIN_WARNING_MM_HR:
        score += 1
        reasons.append("Rainfall detected")

    # --------------------------------------------------------
    # FINAL RISK
    # --------------------------------------------------------

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
# VALIDATION
# ============================================================

def validate_sensor_data(data):

    required_fields = [
        "node_id",
        "water_cm",
        "soil_pct",
        "rain_mm_hr",
        "temp",
        "humidity",
        "timestamp"
    ]

    missing = [
        field for field in required_fields
        if field not in data
    ]

    if missing:
        return False, f"Missing fields: {', '.join(missing)}"

    try:

        float(data["water_cm"])
        float(data["soil_pct"])
        float(data["rain_mm_hr"])
        float(data["temp"])
        float(data["humidity"])
        int(data["timestamp"])

    except (ValueError, TypeError):

        return False, "Sensor values contain invalid data types."

    # --------------------------------------------------------
    # BASIC RANGE CHECKS
    # --------------------------------------------------------

    if float(data["water_cm"]) < 0:
        return False, "water_cm cannot be negative."

    if not 0 <= float(data["soil_pct"]) <= 100:
        return False, "soil_pct must be between 0 and 100."

    if float(data["rain_mm_hr"]) < 0:
        return False, "rain_mm_hr cannot be negative."

    if not -50 <= float(data["temp"]) <= 70:
        return False, "Temperature value is outside expected range."

    if not 0 <= float(data["humidity"]) <= 100:
        return False, "Humidity must be between 0 and 100."

    return True, None


# ============================================================
# SAVE READING
# ============================================================

def save_reading(data, risk_level, risk_score):

    db = get_db()
    cursor = db.cursor()

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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["node_id"],
        float(data["water_cm"]),
        float(data["soil_pct"]),
        float(data["rain_mm_hr"]),
        float(data["temp"]),
        float(data["humidity"]),
        int(data["timestamp"]),
        risk_level,
        risk_score
    ))

    db.commit()
    db.close()


# ============================================================
# SAVE ALERT
# ============================================================

def save_alert(node_id, risk_level, message, timestamp):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO alerts (
            node_id,
            risk_level,
            message,
            timestamp
        )
        VALUES (?, ?, ?, ?)
    """, (
        node_id,
        risk_level,
        message,
        timestamp
    ))

    db.commit()
    db.close()


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "project": "SIH26178",
        "system": "AI-Powered Environmental Intelligence Network",
        "status": "online",
        "message": "Environmental monitoring backend is running."
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time())
    })


# ============================================================
# RECEIVE SENSOR DATA
# ============================================================

@app.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "error": "JSON body required."
        }), 400

    valid, error = validate_sensor_data(data)

    if not valid:

        return jsonify({
            "success": False,
            "error": error
        }), 400

    risk_level, risk_score, reasons = calculate_risk(data)

    save_reading(
        data,
        risk_level,
        risk_score
    )

    alert_created = False

    if risk_level in ["HIGH", "CRITICAL"]:

        message = (
            f"{risk_level} environmental risk detected "
            f"at node {data['node_id']}."
        )

        save_alert(
            data["node_id"],
            risk_level,
            message,
            int(data["timestamp"])
        )

        alert_created = True

    return jsonify({
        "success": True,
        "node_id": data["node_id"],
        "risk": {
            "level": risk_level,
            "score": risk_score,
            "reasons": reasons
        },
        "alert_created": alert_created,
        "processed_at": int(time.time())
    }), 201


# ============================================================
# GET LATEST DATA FROM ALL NODES
# ============================================================

@app.route("/api/nodes", methods=["GET"])
def get_nodes():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT r.*
        FROM readings r

        INNER JOIN (
            SELECT
                node_id,
                MAX(id) AS latest_id
            FROM readings
            GROUP BY node_id
        ) latest

        ON r.id = latest.latest_id

        ORDER BY r.node_id
    """)

    rows = cursor.fetchall()

    db.close()

    return jsonify({
        "success": True,
        "count": len(rows),
        "nodes": [dict(row) for row in rows]
    })


# ============================================================
# GET ONE NODE
# ============================================================

@app.route("/api/nodes/<node_id>", methods=["GET"])
def get_node(node_id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM readings
        WHERE node_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (node_id,))

    row = cursor.fetchone()

    db.close()

    if row is None:

        return jsonify({
            "success": False,
            "error": "Node not found."
        }), 404

    return jsonify({
        "success": True,
        "node": dict(row)
    })


# ============================================================
# GET NODE HISTORY
# ============================================================

@app.route("/api/nodes/<node_id>/history", methods=["GET"])
def get_node_history(node_id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            id,
            node_id,
            water_cm,
            soil_pct,
            rain_mm_hr,
            temp,
            humidity,
            timestamp,
            risk_level,
            risk_score
        FROM readings
        WHERE node_id = ?
        ORDER BY timestamp ASC
    """, (node_id,))

    rows = cursor.fetchall()

    db.close()

    return jsonify({
        "success": True,
        "node_id": node_id,
        "count": len(rows),
        "history": [dict(row) for row in rows]
    })


# ============================================================
# GET ALERTS
# ============================================================

@app.route("/api/alerts", methods=["GET"])
def get_alerts():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM alerts
        ORDER BY timestamp DESC
        LIMIT 100
    """)

    rows = cursor.fetchall()

    db.close()

    return jsonify({
        "success": True,
        "count": len(rows),
        "alerts": [dict(row) for row in rows]
    })


# ============================================================
# GET SYSTEM STATISTICS
# ============================================================

@app.route("/api/statistics", methods=["GET"])
def get_statistics():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS total_readings
        FROM readings
    """)

    total_readings = cursor.fetchone()["total_readings"]

    cursor.execute("""
        SELECT COUNT(*) AS total_alerts
        FROM alerts
    """)

    total_alerts = cursor.fetchone()["total_alerts"]

    cursor.execute("""
        SELECT COUNT(DISTINCT node_id) AS total_nodes
        FROM readings
    """)

    total_nodes = cursor.fetchone()["total_nodes"]

    cursor.execute("""
        SELECT
            risk_level,
            COUNT(*) AS count
        FROM readings
        GROUP BY risk_level
    """)

    risk_distribution = {
        row["risk_level"]: row["count"]
        for row in cursor.fetchall()
    }

    db.close()

    return jsonify({
        "success": True,
        "statistics": {
            "total_nodes": total_nodes,
            "total_readings": total_readings,
            "total_alerts": total_alerts,
            "risk_distribution": risk_distribution
        }
    })


# ============================================================
# SOS ALERT
# ============================================================

@app.route("/api/sos", methods=["POST"])
def receive_sos():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "error": "JSON body required."
        }), 400

    required_fields = [
        "device_id",
        "lat",
        "lon",
        "timestamp"
    ]

    missing = [
        field
        for field in required_fields
        if field not in data
    ]

    if missing:

        return jsonify({
            "success": False,
            "error": f"Missing fields: {', '.join(missing)}"
        }), 400

    try:

        device_id = str(data["device_id"])
        latitude = float(data["lat"])
        longitude = float(data["lon"])
        timestamp = int(data["timestamp"])

    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "error": "Invalid SOS data."
        }), 400

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO sos_alerts (
            device_id,
            latitude,
            longitude,
            timestamp
        )
        VALUES (?, ?, ?, ?)
    """, (
        device_id,
        latitude,
        longitude,
        timestamp
    ))

    db.commit()
    db.close()

    return jsonify({
        "success": True,
        "type": "SOS",
        "device_id": device_id,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp": timestamp,
        "message": "SOS alert received."
    }), 201


# ============================================================
# GET SOS ALERTS
# ============================================================

@app.route("/api/sos", methods=["GET"])
def get_sos_alerts():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM sos_alerts
        ORDER BY timestamp DESC
        LIMIT 50
    """)

    rows = cursor.fetchall()

    db.close()

    return jsonify({
        "success": True,
        "count": len(rows),
        "alerts": [dict(row) for row in rows]
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "success": False,
        "error": "API endpoint not found."
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):

    return jsonify({
        "success": False,
        "error": "HTTP method not allowed."
    }), 405


@app.errorhandler(500)
def server_error(error):

    return jsonify({
        "success": False,
        "error": "Internal server error."
    }), 500


# ============================================================
# START APPLICATION
# ============================================================

initialize_database()


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
