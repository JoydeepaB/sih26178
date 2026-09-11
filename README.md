# DRISHTI: AI-Powered Early Warning & Environmental Command Center

> **Smart India Hackathon (SIH 2026)**  
> **Problem Statement ID:** 26178  
> **Theme:** Disaster Management (Hardware Category)   

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Backend-Flask-green?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Leaflet](https://img.shields.io/badge/Mapping-Leaflet.js-brightgreen?logo=leaflet&logoColor=white)](https://leafletjs.com/)
[![Chart.js](https://img.shields.io/badge/Visuals-Chart.js-coral?logo=chartdotjs&logoColor=white)](https://www.chartjs.org/)
[![Status](https://img.shields.io/badge/Deployment-Render-violet?logo=render&logoColor=white)](https://sih26178-1.onrender.com)

---

## The Problem

CWC and NDMA already run national-scale flood monitoring, but their stations sit far apart on major rivers. Flash floods usually originate in local feeder streams and rural lowlands that have zero sensor coverage — and when a storm takes down cell towers, centralized alert systems go dark right when people need them most.

**DRISHTI** is a low-cost, edge-first sensor network designed to fill that last-mile gap: distributed nodes that classify flood risk locally, stay online through tiered connectivity, and push alerts to a live command dashboard.

---

## Executive Summary

Between 1953 and 2023, official government records (Ministry of Home Affairs & Central Water Commission) document that floods in India have caused:
- **1,21,404+** human casualties
- **71,28,400+** livestock lost
- **₹5,10,837+ Crore** in cumulative financial damages

The primary failure point of traditional flood management is **delayed last-mile alerting**. When cell towers lose power during severe storms, centralized warnings arrive after water has already reached villages.

**DRISHTI** bridges this gap through a modular, edge-resilient sensor mesh (costing ₹2,500–₹3,000 per node) that runs on solar power, uses **LoRa mesh-to-satellite tiered connectivity**, and leverages an **AI forecasting engine** trained on 70 years of national disaster telemetry.

---

## What's actually in this repository

This repo is the **software layer** of DRISHTI: the backend API, risk-scoring logic, and live dashboard. The physical sensor hardware (ESP32 nodes, LoRa mesh) is being built separately by our hardware team as part of the full system — this repo demonstrates and tests that pipeline using simulated and real government sensor data.

---

## Key Features

* **Real-Time Hydrological Situation Map:** Interactive Leaflet GIS dashboard tracking river basins and drainage tanks nationwide.
* **Dynamic Viewport Analytics:** Panning or zooming the map automatically filters and recalculates the regional risk status and pie chart distribution in real-time.
* **Dual-Series AI Trajectory Forecasting:** Projects future water levels for **+1h, +2h, +3h, and +6h** using rate-of-rise velocity ($\Delta h / \Delta t$).
* **70-Year CWC/MHA Historical Integration:** Automatically cross-references incoming telemetry with state-specific historical damage figures to compute a weighted disaster vulnerability score.
* **Instant Coordinate Risk Analysis:** Clicking any point on the map identifies the nearest river gauge, calculates proximity, and evaluates current flood safety.
* **Edge-First Resilience:** ESP32-based hardware nodes continue sensing and sounding local audio sirens even if internet connectivity drops.
* **One-Touch Emergency SOS:** Dedicated field-officer and citizen distress beacon system for targeted SDRF/NDRF dispatch.

---
### Designed, not yet built in software
- On-device (ESP32) local inference and LoRa mesh networking — hardware team deliverable
- Trained ML forecasting model (currently rule-based thresholds; a time-series model is the natural next step once enough real sensor history accumulates)
- SMS/voice alert delivery
- Historical CWC dataset correlation for region-specific risk weighting

We're being explicit about this split so the README doesn't claim more than the code does.

---
## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3, Flask, Flask-CORS |
| Database | SQLite |
| Frontend | Vanilla JavaScript, HTML5, CSS3 |
| Mapping | Leaflet.js + OpenStreetMap tiles |
| Charts | Chart.js |
| Deployment | Render |

---

## Repository Structure

```text
├── app.py              # Flask API — ingestion, risk scoring, alerts, SOS
├── dashboard.html       # Live situational dashboard (map, trends, alerts, SOS)
├── simulator.py         # Flood scenario generator for live demos
├── remote_seeder.py     # Seeds historical data for trend graphs
├── cwc_fetcher.py       # Pulls live data from India's public flood forecasting API
├── sos_simulator.py     # Sends a test SOS signal to the API
└── requirements.txt     # Python dependencies
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Health check / status |
| POST | `/api/sensor-data` | Submit one or more sensor readings |
| GET | `/api/nodes` | Latest reading per node |
| GET | `/api/nodes/<node_id>/history` | Full reading history for one node |
| GET | `/api/alerts` | Recent HIGH/CRITICAL alerts |
| GET | `/api/statistics` | Node, reading, and alert counts |
| POST | `/api/sos` | Submit an emergency SOS signal |
| GET | `/api/sos` | Recent SOS signals |

---

## Getting Started

### 1. Clone and install
```bash
git clone https://github.com/JoydeepaB/sih26178.git
cd sih26178
pip install -r requirements.txt
```

### 2. Run the backend
```bash
python app.py
```
Initializes `environment.db` and serves the API on `http://localhost:5000`.

### 3. Open the dashboard
```bash
python -m http.server 5500
```
Then visit `http://127.0.0.1:5500/dashboard.html`. Update the `API_URL` at the top of `dashboard.html` if you're pointing at a deployed backend instead of localhost.

---

## Demo Script

For a live walkthrough (what we run during presentations):

```bash
# 1. Seed some baseline history so the trend chart isn't empty
python remote_seeder.py

# 2. Pull in real government station data (where available)
python cwc_fetcher.py

# 3. Trigger a live flood scenario — watch the dashboard update in real time
python simulator.py
```

Watch the dashboard as `simulator.py` runs: water level climbs, node status flips to CRITICAL, and an alert appears in the feed automatically.

---

##  System Architecture

```mermaid
flowchart TD
    subgraph Edge Layer [River Banks & Bridges]
        N1[Upstream Node: Ultrasonic + Rain Gauge]
        N2[Midstream Node: Ultrasonic + Silt]
        N3[Downstream Node: Water Level]
        N1 -- LoRa Mesh --> N2
        N2 -- LoRa Mesh --> N3
    end

    subgraph Gateway Layer
        N3 -- LoRa / GSM Fallback --> GW[Field Gateway / Cloud Ingest]
    end

    subgraph Cloud & AI Engine
        GW --> API[Flask REST API - Render]
        CWC[CWC / IMD Historical Matrix 1953-2023] --> AI[AI Predictive Engine]
        API --> DB[(SQLite / Persistent DB)]
        DB --> AI
    end

    subgraph Command & Citizen Delivery
        AI --> DASH[DRISHTI Live Situation Dashboard]
        AI --> SOS[Automated Siren & Regional Voice Alerts]
        DASH --> AUTH[District Authorities / NDRF]
    end
---

## Live Deployment

Backend: [`sih26178-1.onrender.com`](https://sih26178-1.onrender.com)

---
