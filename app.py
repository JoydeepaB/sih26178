from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS
import sqlite3
import os
import time
import random
import threading

app = Flask(__name__)
CORS(app)

DB_PATH = "environment.db"

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
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        node_id TEXT, 
        location_name TEXT, 
        water_cm REAL, 
        timestamp INTEGER,
        risk_level TEXT, 
        risk_score INTEGER, 
        lat REAL, 
        lon REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, node_id TEXT, 
        risk_level TEXT, message TEXT, timestamp INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sos_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, 
        latitude REAL, longitude REAL, timestamp INTEGER)""")
    db.commit()
    db.close()

def evaluate_risk(water_cm):
    if water_cm >= 80: return "CRITICAL", 9
    elif water_cm >= 60: return "HIGH", 6
    elif water_cm >= 40: return "MODERATE", 3
    else: return "LOW", 0

@app.route("/")
def index():
    dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    if os.path.exists(dashboard_path):
        return send_file(dashboard_path)
    return "DRISHTI AI Engine Live. (dashboard.html not found in server directory)"

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
        try:
            lt = float(item.get("latitude", 23.83))
            ln = float(item.get("longitude", 91.28))
            water = float(item.get("water_cm", 0))
        except (ValueError, TypeError):
            lt, ln, water = 23.83, 91.28, 0.0

        if "risk_override" in item:
            risk = item["risk_override"]
            score = {"CRITICAL": 9, "HIGH": 6, "MODERATE": 3}.get(risk, 0)
        else:
            risk, score = evaluate_risk(water)
            
        ts = int(item.get("timestamp", time.time()))
        
        cursor.execute("""INSERT INTO readings 
            (node_id, location_name, water_cm, timestamp, risk_level, risk_score, lat, lon)
            VALUES (?,?,?,?,?,?,?,?)""", (uid, loc, water, ts, risk, score, lt, ln))
            
        if risk in ("HIGH", "CRITICAL"):
            cursor.execute("""INSERT INTO alerts (node_id, risk_level, message, timestamp) 
                VALUES (?, ?, ?, ?)""", (uid, risk, f"{risk} risk detected at {loc}", ts))
    
    db.commit()
    return jsonify({"success": True}), 201

@app.route("/api/nodes")
def get_nodes():
    db = get_db()
    data = db.execute("SELECT * FROM readings WHERE id IN (SELECT MAX(id) FROM readings GROUP BY node_id)").fetchall()
    return jsonify({"success": True, "nodes": [dict(r) for r in data]})

@app.route("/api/statistics")
def get_stats():
    db = get_db()
    r = db.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    a = db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    return jsonify({"success": True, "statistics": {"total_readings": r, "total_alerts": a}})

@app.route("/api/alerts")
def get_alerts():
    db = get_db()
    data = db.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 50").fetchall()
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
    data = db.execute("SELECT * FROM sos_alerts ORDER BY timestamp DESC LIMIT 10").fetchall()
    return jsonify({"success": True, "alerts": [dict(r) for r in data], "sos": [dict(r) for r in data]})

@app.route("/api/nodes/<node_id>/history")
def get_history(node_id):
    db = get_db()
    data = db.execute("SELECT * FROM readings WHERE node_id=? ORDER BY timestamp ASC LIMIT 50", (node_id,)).fetchall()
    return jsonify({"success": True, "history": [dict(r) for r in data]})

# CWC & MHA 70-Year Flood History Matrix (1953 - 2023 from Official Records)
CWC_MHA_HISTORICAL_DATA = {
    "Assam": {"damage_crore": 23646.50, "human_lives": 3668, "houses_damaged": 4874911, "tier": "VERY HIGH", "base_score": 85},
    "Bihar": {"damage_crore": 21894.35, "human_lives": 11997, "houses_damaged": 10015880, "tier": "CRITICAL", "base_score": 95},
    "Uttar Pradesh": {"damage_crore": 22998.42, "human_lives": 19020, "houses_damaged": 14509918, "tier": "CRITICAL", "base_score": 90},
    "West Bengal": {"damage_crore": 79089.70, "human_lives": 11223, "houses_damaged": 19392696, "tier": "CRITICAL", "base_score": 92},
    "Gujarat": {"damage_crore": 14936.42, "human_lives": 10522, "houses_damaged": 2312155, "tier": "HIGH", "base_score": 78},
    "Himachal Pradesh": {"damage_crore": 17510.62, "human_lives": 5134, "houses_damaged": 268605, "tier": "HIGH", "base_score": 80},
    "Uttarakhand": {"damage_crore": 41048.24, "human_lives": 1853, "houses_damaged": 42560, "tier": "VERY HIGH", "base_score": 88},
    "Odisha": {"damage_crore": 19871.00, "human_lives": 2491, "houses_damaged": 4631364, "tier": "HIGH", "base_score": 75},
    "Kerala": {"damage_crore": 20700.82, "human_lives": 5035, "houses_damaged": 2304076, "tier": "HIGH", "base_score": 79},
    "Andhra Pradesh": {"damage_crore": 72297.04, "human_lives": 17028, "houses_damaged": 6806204, "tier": "CRITICAL", "base_score": 89},
    "Punjab": {"damage_crore": 4388.74, "human_lives": 3335, "houses_damaged": 2921761, "tier": "MODERATE", "base_score": 60},
    "Rajasthan": {"damage_crore": 36577.93, "human_lives": 3463, "houses_damaged": 1903557, "tier": "HIGH", "base_score": 72},
    "Delhi": {"damage_crore": 150.32, "human_lives": 126, "houses_damaged": 133566, "tier": "MODERATE", "base_score": 55},
    "Tamil Nadu": {"damage_crore": 34366.29, "human_lives": 4029, "houses_damaged": 5779738, "tier": "HIGH", "base_score": 76},
    "Tripura": {"damage_crore": 2423.06, "human_lives": 400, "houses_damaged": 409650, "tier": "MODERATE", "base_score": 65},
    "Maharashtra": {"damage_crore": 11378.52, "human_lives": 5866, "houses_damaged": 1328111, "tier": "HIGH", "base_score": 74},
    "Karnataka": {"damage_crore": 43806.98, "human_lives": 4171, "houses_damaged": 2009267, "tier": "HIGH", "base_score": 73}
}

@app.route("/api/nodes/<node_id>/prediction")
def get_prediction(node_id):
    db = get_db()
    rows = db.execute("SELECT * FROM readings WHERE node_id=? ORDER BY timestamp ASC", (node_id,)).fetchall()
    if not rows:
        return jsonify({"success": False, "message": "No data found"}), 404
        
    readings = [dict(r) for r in rows]
    current = readings[-1]
    curr_water = current["water_cm"]
    loc_name = current["location_name"]
    
    matched_state = "National"
    hist_stats = {"damage_crore": 510837.54, "human_lives": 121404, "houses_damaged": 83908274, "tier": "HIGH", "base_score": 75}
    for state, data in CWC_MHA_HISTORICAL_DATA.items():
        if state.lower() in loc_name.lower():
            matched_state = state
            hist_stats = data
            break
            
    if matched_state == "National":
        if "guwahati" in loc_name.lower() or "dibrugarh" in loc_name.lower():
            matched_state = "Assam"
            hist_stats = CWC_MHA_HISTORICAL_DATA["Assam"]
        elif "delhi" in loc_name.lower():
            matched_state = "Delhi"
            hist_stats = CWC_MHA_HISTORICAL_DATA["Delhi"]
        elif "patna" in loc_name.lower() or "supaul" in loc_name.lower():
            matched_state = "Bihar"
            hist_stats = CWC_MHA_HISTORICAL_DATA["Bihar"]
        elif "srinagar" in loc_name.lower():
            matched_state = "Himachal Pradesh"
            hist_stats = CWC_MHA_HISTORICAL_DATA["Himachal Pradesh"]
        elif "cuttack" in loc_name.lower() or "rourkela" in loc_name.lower():
            matched_state = "Odisha"
            hist_stats = CWC_MHA_HISTORICAL_DATA["Odisha"]
        elif "surat" in loc_name.lower():
            matched_state = "Gujarat"
            hist_stats = CWC_MHA_HISTORICAL_DATA["Gujarat"]
        elif "trichy" in loc_name.lower():
            matched_state = "Tamil Nadu"
            hist_stats = CWC_MHA_HISTORICAL_DATA["Tamil Nadu"]

    if len(readings) >= 2:
        dt = (readings[-1]["timestamp"] - readings[0]["timestamp"]) / 3600.0
        if dt > 0:
            rate_per_hr = round((readings[-1]["water_cm"] - readings[0]["water_cm"]) / dt, 2)
        else:
            rate_per_hr = 0.0
    else:
        rate_per_hr = 2.5

    if rate_per_hr < -10: rate_per_hr = -2.0
    
    pred_1h = max(5.0, round(curr_water + rate_per_hr * 1.0, 2))
    pred_2h = max(5.0, round(curr_water + rate_per_hr * 1.8, 2))
    pred_3h = max(5.0, round(curr_water + rate_per_hr * 2.5, 2))
    pred_6h = max(5.0, round(curr_water + rate_per_hr * 4.2, 2))

    danger_threshold = 80.0
    if rate_per_hr > 0 and curr_water < danger_threshold:
        lead_time = round((danger_threshold - curr_water) / rate_per_hr, 1)
    elif curr_water >= danger_threshold:
        lead_time = 0.0
    else:
        lead_time = 12.0

    surge_factor = min(30, max(0, rate_per_hr * 3))
    level_factor = min(50, (curr_water / 80.0) * 50)
    vuln_factor = (hist_stats["base_score"] / 100.0) * 20
    ai_risk_score = min(100, round(level_factor + surge_factor + vuln_factor))

    advisory = "Normal discharge conditions. Stable hydrological profile."
    if ai_risk_score >= 80 or curr_water >= 80:
        advisory = f"CRITICAL HAZARD: Current level ({curr_water} cm) surging rapidly (+{rate_per_hr} cm/hr). Danger breach window: {lead_time} hrs. Historical basin vulnerability: {matched_state} (₹{hist_stats['damage_crore']} Cr damage, {hist_stats['human_lives']} lives lost in past floods). Immediate Level-2 evacuation advised."
    elif ai_risk_score >= 55 or curr_water >= 50:
        advisory = f"ELEVATED RISK: Rising at +{rate_per_hr} cm/hr. Projected level in 3h: {pred_3h} cm. Warning threshold proximity detected. Alert downstream village panchayats."

    return jsonify({
        "success": True,
        "node_id": node_id,
        "location_name": loc_name,
        "state": matched_state,
        "current_water_cm": curr_water,
        "rate_per_hr": rate_per_hr,
        "pred_1h": pred_1h,
        "pred_2h": pred_2h,
        "pred_3h": pred_3h,
        "pred_6h": pred_6h,
        "lead_time_hours": lead_time,
        "ai_risk_score": ai_risk_score,
        "historical_stats": hist_stats,
        "advisory": advisory
    })

# -------------------------------------------------------------
# 🌊 BUILT-IN AUTOMATIC CLOUD SIMULATOR & SEEDER ENGINE
# (Runs 24/7 on the server so you never have to run VS Code scripts manually!)
# -------------------------------------------------------------

DEMO_STATIONS = [
    {"code": "DEMO_FLASH_FLOOD_ZONE", "name": "Guwahati River Bank, Assam", "lat": 26.14, "lon": 91.73, "base": 38.0},
    {"code": "CWC_001", "name": "Brahmaputra River, Dibrugarh, Assam", "lat": 27.47, "lon": 94.91, "base": 45.0},
    {"code": "CWC_002", "name": "Ganga River, Patna, Bihar", "lat": 25.59, "lon": 85.13, "base": 55.0},
    {"code": "CWC_003", "name": "Yamuna River, Delhi", "lat": 28.61, "lon": 77.20, "base": 32.0},
    {"code": "CWC_008", "name": "Mahanadi River, Cuttack, Odisha", "lat": 20.46, "lon": 85.88, "base": 50.0},
    {"code": "CWC_009", "name": "Cauvery River, Trichy, Tamil Nadu", "lat": 10.79, "lon": 78.70, "base": 30.0},
    {"code": "CWC_012", "name": "Jhelum River, Srinagar, Himachal Pradesh", "lat": 34.08, "lon": 74.79, "base": 42.0},
    {"code": "CWC_013", "name": "Kosi River, Supaul, Bihar", "lat": 26.12, "lon": 86.60, "base": 46.0},
    {"code": "CWC_014", "name": "Teesta River, Jalpaiguri, West Bengal", "lat": 26.52, "lon": 88.73, "base": 52.0}
]

def auto_seed_and_simulate_worker():
    """Background daemon thread to auto-seed initial history & stream live telemetry continuous in the cloud."""
    time.sleep(1) # wait for server boot
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Check if DB has historical data; if not, seed realistic 24-hour trends
    count = c.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    now = int(time.time())
    
    if count < 10:
        print("[DRISHTI Background Engine] Initializing database with 24-hr historical telemetry...")
        for station in DEMO_STATIONS:
            cur_lvl = station["base"]
            for h in range(24, 0, -1):
                cur_lvl = max(10.0, cur_lvl + random.uniform(-1.5, 2.2))
                risk, score = evaluate_risk(cur_lvl)
                ts = now - (h * 3600)
                c.execute("""INSERT INTO readings 
                    (node_id, location_name, water_cm, timestamp, risk_level, risk_score, lat, lon)
                    VALUES (?,?,?,?,?,?,?,?)""", 
                    (station["code"], station["name"], round(cur_lvl, 2), ts, risk, score, station["lat"], station["lon"]))
        conn.commit()
        print("[DRISHTI Background Engine] Database seeded successfully!")

    # 2. Continuous 24/7 background telemetry generator
    live_levels = {s["code"]: s["base"] + random.uniform(-2, 3) for s in DEMO_STATIONS}
    
    while True:
        try:
            now_ts = int(time.time())
            for s in DEMO_STATIONS:
                code = s["code"]
                # Natural hydrological rise & fall
                if code == "DEMO_FLASH_FLOOD_ZONE":
                    # Flash flood demo zone cycles up and down dynamically
                    live_levels[code] += random.uniform(0.5, 3.5)
                    if live_levels[code] > 88: 
                        live_levels[code] = 30.0 # reset cycle
                else:
                    live_levels[code] += random.uniform(-0.8, 1.2)
                    live_levels[code] = max(15.0, min(85.0, live_levels[code]))
                
                water_val = round(live_levels[code], 2)
                risk, score = evaluate_risk(water_val)
                
                c.execute("""INSERT INTO readings 
                    (node_id, location_name, water_cm, timestamp, risk_level, risk_score, lat, lon)
                    VALUES (?,?,?,?,?,?,?,?)""", 
                    (code, s["name"], water_val, now_ts, risk, score, s["lat"], s["lon"]))
                
                if risk in ("HIGH", "CRITICAL"):
                    c.execute("""INSERT INTO alerts (node_id, risk_level, message, timestamp) 
                        VALUES (?, ?, ?, ?)""", (code, risk, f"{risk} flood alert at {s['name']} ({water_val} cm)", now_ts))
            
            conn.commit()
        except Exception as err:
            print(f"[DRISHTI Simulator Error]: {err}")
        
        # Stream new telemetry point every 15 seconds
        time.sleep(15)

# Trigger Instant Flood Spike for live judge demonstration
@app.route("/api/demo-surge", methods=["GET", "POST"])
def demo_surge():
    """Instantly injects a critical flood surge for live demos."""
    db = get_db()
    now_ts = int(time.time())
    db.execute("""INSERT INTO readings 
        (node_id, location_name, water_cm, timestamp, risk_level, risk_score, lat, lon)
        VALUES (?,?,?,?,?,?,?,?)""", 
        ("DEMO_FLASH_FLOOD_ZONE", "Guwahati River Bank, Assam", 86.5, now_ts, "CRITICAL", 9, 26.14, 91.73))
    db.execute("""INSERT INTO alerts (node_id, risk_level, message, timestamp) 
        VALUES (?, ?, ?, ?)""", ("DEMO_FLASH_FLOOD_ZONE", "CRITICAL", "FLASH FLOOD WARNING: Water level spiked to 86.5 cm at Guwahati River Bank", now_ts))
    db.commit()
    return jsonify({"success": True, "message": "Critical Flash Flood Surge Injected Live!"})

init_db() 

# Start automatic continuous cloud simulator thread
sim_thread = threading.Thread(target=auto_seed_and_simulate_worker, daemon=True)
sim_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
