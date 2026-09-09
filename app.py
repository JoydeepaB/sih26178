from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
import os
import time

app = Flask(__name__)
CORS(app)

DB_PATH = "environment.db"
RISK_SCORES = {"CRITICAL": 9, "HIGH": 6, "MODERATE": 3, "LOW": 0}

def evaluate_risk(water_cm):
    if water_cm >= 80: return "CRITICAL", 9
    elif water_cm >= 60: return "HIGH", 6
    elif water_cm >= 40: return "MODERATE", 3
    else: return "LOW", 0

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
        id INTEGER PRIMARY KEY AUTOINCREMENT, node_id TEXT, location_name TEXT, 
        water_cm REAL, timestamp INTEGER, risk_level TEXT, risk_score INTEGER, lat REAL, lon REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, node_id TEXT, risk_level TEXT, message TEXT, timestamp INTEGER)""")
    db.commit()
    db.close()

@app.route("/")
def index():
    return "DRISHTI System Live."

@app.route("/api/sensor-data", methods=["POST"])
def ingest():
    payload = request.get_json(silent=True)
    if not payload: return jsonify({"success": False}), 400
    items = payload if isinstance(payload, list) else [payload]
    db = get_db()
    cursor = db.cursor()

    for item in items:
        uid = item["node_id"]
        loc = item.get("location_name", "National Station")
        lt = float(item.get("latitude", 23.83))
        ln = float(item.get("longitude", 91.28))
        water = float(item.get("water_cm", 0))
        ts = int(item.get("timestamp", time.time()))

        if "risk_override" in item:
            risk = item["risk_override"]
            score = RISK_SCORES.get(risk, 0)
        else:
            risk, score = evaluate_risk(water)

        cursor.execute("""INSERT INTO readings
            (node_id, location_name, water_cm, timestamp, risk_level, risk_score, lat, lon)
            VALUES (?,?,?,?,?,?,?,?)""", (uid, loc, water, ts, risk, score, lt, ln))

    db.commit()
    return jsonify({"success": True}), 201

@app.route("/api/nodes")
def get_nodes():
    db = get_db()
    data = db.execute("SELECT * FROM readings WHERE id IN (SELECT MAX(id) FROM readings GROUP BY node_id)").fetchall()
    return jsonify({"success": True, "nodes": [dict(r) for r in data]})

@app.route("/api/nodes/<node_id>/history")
def get_history(node_id):
    db = get_db()
    data = db.execute("SELECT * FROM readings WHERE node_id=? ORDER BY timestamp ASC LIMIT 50", (node_id,)).fetchall()
    return jsonify({"success": True, "history": [dict(r) for r in data]})

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
