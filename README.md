# SIH26001: AI/ML-Based Landslide Detection, Prediction & Early-Warning System for the North Eastern Region (NER) of India

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.115-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js_15_App_Router-black?style=flat&logo=next.js&logoColor=white)](https://nextjs.org)
[![CAP v1.2 Compliant](https://img.shields.io/badge/Standard-OASIS_CAP_v1.2-blue?style=flat)](https://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2.html)
[![Tests](https://img.shields.io/badge/Pytest-152_Passed-brightgreen?style=flat&logo=pytest&logoColor=white)](https://pytest.org)
[![Docker Ready](https://img.shields.io/badge/Deployment-Docker_Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com)

[![Engine Version](https://img.shields.io/badge/Engine_Version-prototype--v2.0-indigo?style=flat)](docs/core-engine-architecture.md)

---

## 1. Primary Problem & Technical Mission

The North Eastern Region (NER) of India accounts for over **70% of the nation's critical landslide susceptibility**, characterized by steep mountain slopes, complex geological shear zones, active seismicity, and torrential monsoonal precipitation.

### Primary Problem:
Detect abnormal environmental conditions associated with landslides, estimate current physical landslide risk, and use a genuinely trained AI/ML predictive analytics model to forecast the probability of an upcoming landslide across the North Eastern Region.

### The Two Major Technical Pillars:
1. **REAL-TIME GIS DASHBOARD AND LANDSLIDE RISK HEATMAPS**: Interactive geospatial risk mapping across NER station sectors, combining topographic geometry, multi-window rainfall accumulation, pore water pressure saturation, and geomorphological susceptibility.
2. **AI/ML-BASED PREDICTIVE ANALYTICS ENGINE FOR LANDSLIDE EARLY WARNING**: A modular predictive analytics architecture separating **Task A (Environmental Anomaly Detection)** from **Task B (Landslide Occurrence Probability Forecasting across 6h, 12h, and 24h horizons)**.

---

## 2. End-to-End Landslide Early-Warning Architecture

```text
                             DATA SOURCES
       (Live Open-Meteo API, In-Situ Sensors, Bhoonidhi Satellite)
                                  │
                                  ▼
                 DATA VALIDATION & PROVENANCE TAGGING
     (OBSERVED / FORECAST / SATELLITE / MODEL_DERIVED / STATIC / SIMULATED)
                                  │
                                  ▼
                 SPATIO-TEMPORAL FEATURE ENGINEERING
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
┌───────────────────────────────────────┐   ┌───────────────────────────────────────┐
│ TASK A: ENVIRONMENTAL ANOMALY MODEL   │   │ TASK B: LANDSLIDE PREDICTION MODEL    │
│                                       │   │                                       │
│ "Are environmental conditions         │   │ "P(landslide occurrence in location   │
│ statistically abnormal?"              │   │ during forecast window T + H)?"       │
│                                       │   │                                       │
│ Models: Rolling Z-Score Baseline &    │   │ Models: Logistic Regression, Random   │
│ Isolation Forest Multi-Signal         │   │ Forest, HistGradientBoosting (Platt)  │
│                                       │   │                                       │
│ Output: Anomaly Score (0.0 to 1.0)    │   │ Forecast Horizons:                    │
│ Anomaly Level (NORMAL / ELEVATED /    │   │ • 6-Hour Probability                  │
│ SEVERE / EXTREME)                     │   │ • 12-Hour Probability                 │
│                                       │   │ • 24-Hour Probability (Default Target)│
└──────────────────┬────────────────────┘   └──────────────────┬────────────────────┘
                   │                                           │
                   └─────────────────────┬─────────────────────┘
                                         │
                                         ▼
                     ┌───────────────────────────────────────┐
                     │ DETERMINISTIC SCIENTIFIC INDICATORS   │
                     │ (I-D Curves, API, Slope, Soil Sat.)   │
                     └───────────────────┬───────────────────┘
                                         │
                                         ▼
                     ┌───────────────────────────────────────┐
                     │ LANDSLIDE EARLY-WARNING DECISION      │
                     │ ENGINE (Synthesizes current risk,     │
                     │ future probability, & data quality)   │
                     └───────────────────┬───────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
GIS RISK HEATMAP (NER)         DECISION-SUPPORT DSS          CAP v1.2 / PUBLIC ALERTS
(Tactical Map & Perimeters)    (HQ Command & Field Units)    (Plain-Language Advisories)
```

### Critical Modeling Distinctions & Terminology
* **Current Conditions:** What is physically happening on the slope now?
* **Environmental Anomaly (Task A):** Are meteorological and soil saturation conditions statistically abnormal compared to normal behavior?
* **Current Landslide Risk:** How favorable are current physical terrain and moisture conditions for slope failure?
* **Forecast Landslide Probability (Task B):** What probability does the trained ML model assign to landslide occurrence during a future window?
* **Confidence / Data Quality:** How trustworthy is this assessment given sensor availability and model uncertainty?

---

## 3. The Four Core Interfaces

### A. Core Expert Disaster Intelligence Command Center (`/`)
* **GIS Landslide Prediction Map**: Multi-layer early warning GIS mapping (`24H ML Forecast`, `Current Landslide Risk`, `Environmental Anomaly`, `24h Rainfall`, `Soil Saturation`, `Susceptibility`) with station catchment perimeters, honest spatial disclosures (no fake 30m interpolation), and operational popups.
* **Forecast Progression Timeline**: Real-time chronological tracking showing `PAST (Observations)` &rarr; `NOW (Current Deterministic Risk 0-100)` &rarr; `FUTURE (24H ML Landslide Probability 0-100%)`.
* **Ranked Priority Table**: Sorted by calibrated 24h ML probability with anomaly status, risk tiers, and telemetry freshness.
* **Multi-Signal Factor Breakdown**: Real-time breakdown of 24h/72h rainfall, pore pressure soil saturation, slope gradient, and baseline susceptibility.
* **Active Event Lifecycle Queue**: Dual-signal escalation (Risk $\ge 50$ / $P(\text{landslide}) \ge 0.55$), de-escalation hysteresis buffer, and officer acknowledgment workflows.
* **API Endpoints**:
  - `GET /api/v1/ml/status`: Model provenance, training status, and feature schema.
  - `GET /api/v1/ml/forecast/{location_id}`: Consolidated station forecast (current condition, anomaly, probabilities, observed drivers, model attributions).
  - `GET /api/v1/ml/forecast`: Multi-station forecast across all monitored NER stations.
  - `GET /api/v1/ml/gis-heatmap`: Geospatially usable GeoJSON FeatureCollection.
  - `GET /api/v1/locations/map`: Enriched map data with live ML predictions.


### B. On-Ground Field Rescue Team Interface (`/field`)
* **Team Deployment Status**: Active team status tracking (`ON_SCENE`, `ASSISTING`, `EVACUATING`, `NEED_ASSISTANCE`).
* **Field Evidence Submission**: Submit ground reports for road blockages, mud flow observations, and structural fissures.
* **Emergency SOS Workflow**: One-tap emergency assistance dispatch to central HQ.
* **HQ Operational Broadcasts**: Real-time tactical directives received directly from the central command room.

### C. Public Disaster Alert & Safety Assistance Portal (`/public`)
* **Geofenced Risk Assessment**: Answers *Am I affected?*, *What is happening?*, *How serious is it?*, and *What should I do?*.
* **Public Safety Map**: Visualizes citizen GPS position relative to hazard perimeter and verified Safer Reference Points.
* **Conservative Safety Checklist**: Strict Landslide Do's and Don'ts avoiding speculation or AI hallucination.
* **Emergency Directory & Acknowledgment**: Instant calling (112, 1070) and `[ I UNDERSTAND ]` review logging.

### D. Historical Analytics, Disaster Playback & Model Calibration Studio (`/analytics`)
* **Forensic Disaster Replay**: Step-by-step 72-hour historical reconstruction (e.g. 2023 South Lhonak GLOF, 2022 Haflong Railway Collapse).
* **Authentic Model Verification**: Reads certified test cross-validation metrics directly from trained model artifacts (Brier score, PR-AUC, ROC-AUC, FAR, CSI), or displays `MODEL STATUS: NOT TRAINED` when operating on baseline physics.
* **Weight Tuning & Backtesting Sandbox**: Interactive parameter weight adjustments simulated on historical benchmark datasets.

---

## 4. AI/ML Landslide Model Training & Zero Fake Data Policy

SIH26001 enforces a strict **Zero Fake Data Policy**:
- No synthetic landslide events or demo scenarios are ever converted into fake training labels.
- Ground truth is sourced strictly from Geological Survey of India (GSI) National Landslide Susceptibility Mapping (NLSM) or NASA Global Landslide Catalog (GLC).
- If no trained model artifact exists, the engine reports `MODEL STATUS: NOT TRAINED` and falls back cleanly to the deterministic physics engine.

### Dataset Ingestion Contracts
- **Inventory Format**: CSV or GeoJSON conforming to `backend/app/ml/dataset/schemas.py`.
- **Templates**: Blank templates with zero fake observations are located in `data/landslide_inventory/`:
  - `data/landslide_inventory/template_inventory.csv`
  - `data/landslide_inventory/template_inventory.geojson`

### Training CLI Execution
To train, benchmark, calibrate, evaluate, and save versioned artifacts:
```bash
python -m backend.app.ml.training.train \
  --inventory <path_to_gsi_catalog.csv> \
  --telemetry <path_to_telemetry_archive.csv> \
  --output-dir backend/models/landslide \
  --horizon 24h \
  --seed 42
```
The CLI automatically:
1. Validates bounds ($21.5^\circ\text{N} \le \text{lat} \le 29.5^\circ\text{N}$, $89.5^\circ\text{E} \le \text{lon} \le 97.5^\circ\text{E}$) and checks timestamp precision.
2. Samples hard rainfall negatives ($\ge 15\text{mm}$) and baseline negatives outside $\pm 3$-day temporal exclusion windows.
3. Splits into Chronological Train/Val/Test or Spatial Group splits with temporal leakage assertion ($t_{\text{train\_max}} < t_{\text{val\_min}} \le t_{\text{val\_max}} < t_{\text{test\_min}}$).
4. Trains and compares Logistic Regression, Random Forest, and HistGradientBoosting classifiers.
5. Calibrates output probabilities using Platt/sigmoid calibration.
6. Computes comprehensive evaluation metrics (PR-AUC, ROC-AUC, Brier score, FAR, CSI, threshold sweeps).
7. Serializes 5 versioned artifacts (`model.joblib`, `pipeline.joblib`, `metadata.json`, `metrics.json`, `feature_schema.json`) for zero-downtime inference serving.


---

## 5. Multi-Channel Alerting & CAP v1.2 Standard

SIH26001 produces standardized **Common Alerting Protocol (OASIS CAP v1.2 / ITU X.1303)** feeds for integration with national disaster management aggregators:

* **CAP XML Feed**: `GET /api/v1/alerts/cap.xml`
* **CAP JSON Feed**: `GET /api/v1/alerts/cap.json`
* **NDMA / SDRF Situation Reports**: `GET /api/v1/alerts/sitrep/{event_id}`
* **Multilingual Warning Templates**: Automated SMS ($\le 160$ chars) and WhatsApp messages generated in English, Hindi, Assamese, Bengali, and Mizo.

---

## 6. Monitored North Eastern Region Monitoring Stations


| Location ID | Station Name | District | State | Latitude | Longitude | Slope Angle | Baseline Susceptibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `NER-SIK-GANGTOK-01` | Gangtok Ridge Sector | East Sikkim | Sikkim | 27.3389° N | 88.6065° E | 38.5° | 0.85 (High) |
| `NER-ASM-HAFLONG-01` | Haflong Hill Railway Zone | Dima Hasao | Assam | 25.1764° N | 93.0177° E | 34.0° | 0.80 (High) |
| `NER-MIZ-AIZAWL-01` | Aizawl Central Ridge | Aizawl | Mizoram | 23.7271° N | 92.7176° E | 42.0° | 0.90 (Very High) |
| `NER-MNP-IMPHAL-01` | Imphal-Noney Valley | Noney / Imphal West | Manipur | 24.8170° N | 93.9368° E | 29.5° | 0.70 (Moderate) |
| `NER-MEG-SHILLONG-01` | Shillong Peak Bypass | East Khasi Hills | Meghalaya | 25.5788° N | 91.8933° E | 31.0° | 0.75 (High) |
| `NER-ARU-ITANAGAR-01` | Itanagar Hill Corridor | Papum Pare | Arunachal Pradesh | 27.0844° N | 93.6053° E | 36.0° | 0.82 (High) |

---

## 7. Quick Start Guide

### Option A: Local Development Launch
```bash
# 1. Install Backend Dependencies
pip install -r backend/requirements.txt

# 2. Install Frontend Dependencies
cd frontend && npm install && cd ..

# 3. Seed Realistic Demo Database
python scripts/seed-demo.py

# 4. Start All Services
# On Windows PowerShell:
.\scripts\start-all.ps1

# On Linux / macOS:
chmod +x scripts/start-all.sh
./scripts/start-all.sh
```

### Option B: Docker Compose (Production Deployment)
```bash
docker-compose up --build -d
```

### Service Endpoints
* **Command Center**: [http://localhost:3000](http://localhost:3000)
* **Field Rescue Operations**: [http://localhost:3000/field](http://localhost:3000/field)
* **Public Safety Portal**: [http://localhost:3000/public](http://localhost:3000/public)
* **Calibration Studio**: [http://localhost:3000/analytics](http://localhost:3000/analytics)
* **OpenAPI Interactive Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Prometheus Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
* **CAP v1.2 XML Feed**: [http://localhost:8000/api/v1/alerts/cap.xml](http://localhost:8000/api/v1/alerts/cap.xml)

---

## 8. Automated Test Suite (141 Passing Tests)

```bash
python -m pytest backend/tests/ -v
```

```text
================= 141 passed, 5 skipped, 1 warning in 33.38s ==================
```


All scientific scoring calculations, anomaly detection algorithms, event hysteresis state transitions, agent guardrails, field rescue operations, public geofencing, CAP feeds, and disaster playback models are covered with automated test suites.
