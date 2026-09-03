# SIH26001 — Portable Landslide ML Pipeline & Telemetry Engine

Welcome to the machine-learning and continuous telemetry engineering subsystem for the **SIH26001 AI-Based Landslide Decision Support System (NER India)**.

This subsystem provides a reproducible, CPU-friendly tabular ML training pipeline, multi-signal scenario generation, official ground-truth importers, and continuous live telemetry collection into PostgreSQL.

---

## 1. Quickstart: 3-Command Setup & Training

Clone the repository and run:

```bash
# Step 1: Bootstrap directory layout and verify dependencies
python -m backend.app.ml.cli bootstrap

# Step 2: Run end-to-end demo training (synthetic generation, baseline benchmarking, calibration & activation)
python -m backend.app.ml.cli demo-train

# Step 3: Inspect active model registry status and authentic metrics
python -m backend.app.ml.cli status
```

---

## 2. CLI Command Reference

The unified CLI tool `backend/app/ml/cli.py` controls all ML operations across Windows, Linux, and macOS:

| Command | Purpose | Example |
| :--- | :--- | :--- |
| `bootstrap` | Verifies directories, packages, and environment | `python -m backend.app.ml.cli bootstrap` |
| `demo-train` | One-command end-to-end synthetic demo training | `python -m backend.app.ml.cli demo-train` |
| `status` | Shows active model status, tier, and metrics | `python -m backend.app.ml.cli status` |
| `synthetic generate` | Generates configurable synthetic scenario datasets | `python -m backend.app.ml.cli synthetic generate --samples 50000 --seed 42` |
| `dataset import-gsi` | Imports manually downloaded GSI landslide CSV | `python -m backend.app.ml.cli dataset import-gsi --input data/external/gsi/landslides.csv` |
| `dataset download-nasa-glc` | Downloads & normalizes NASA Global Landslide Catalog for NER | `python -m backend.app.ml.cli dataset download-nasa-glc` |
| `data backfill-weather` | Backfills historical reanalysis from Open-Meteo | `python -m backend.app.ml.cli data backfill-weather --location all --start 2023-01-01 --end 2024-01-01` |
| `train` | Config-driven offline training across all baseline models | `python -m backend.app.ml.cli train --config backend/app/ml/config/default.yaml` |
| `model export` | Bundles active model artifact into portable `.zip` with SHA-256 | `python -m backend.app.ml.cli model export --model v2.0.0 --output landslide-bundle.zip` |
| `model import` | Verifies SHA-256 checksum, unpacks, and activates model | `python -m backend.app.ml.cli model import --file landslide-bundle.zip` |
| `model activate` | Activates a specific versioned artifact directory | `python -m backend.app.ml.cli model activate --version v2.0.0` |

---

## 3. Data Ingestion Architecture & PostgreSQL Accumulation

The application separates real-time decision-making from telemetry accumulation:

1. **Assessment Engine Scheduler (`30s` interval)**:
   - Evaluates current sensor state and produces immediate landslide probability, anomaly levels, and GIS heatmaps.
   - Evaluates the freshest available database records between ingestion cycles.
2. **Dedicated Live Telemetry Ingestion Scheduler (`900s` / `15 min` interval)**:
   - Hits Open-Meteo REST API for all active NER monitoring stations.
   - Idempotently upserts hourly observations into PostgreSQL table `weather_observations` on `(location_id, timestamp, source, observation_type)`.
   - Isolates and preserves numerical forecast points into `weather_forecast_snapshots` (preventing forecast pollution in historical records).
   - Ingestion health can be queried at `GET /api/v1/system/ingestion-health`.

---

## 4. Ground-Truth Data Strategy

* **Priority A (Official Indian Ground Truth)**: Geological Survey of India (GSI) Bhusanket / Bhukosh / NGDR. Manual import workflow documented in `data/external/gsi/README.md` and detailed in `docs/ml/DATASET_RESEARCH.md`.
* **Priority B (Supplementary Global Benchmark)**: NASA Global Landslide Catalog (GLC). Automated download and NER bounding-box filtering script (`21.5°N - 29.5°N, 89.5°E - 97.5°E`).
* **Priority C (Reference Only)**: NRSC / ISRO Landslide Atlas of India. Marked `REFERENCE_ONLY` for spatial validation; not scraped into fake points.
* **Level 1 (Synthetic Scenarios)**: 18+ varied meteorological & geotechnical scenarios, with explicit hard negatives (heavy rain on flat slope, steep dry slopes) and stochastic limit-equilibrium failure mechanics.

---

## 5. Machine Learning Models & Evaluation

The training pipeline evaluates three CPU-friendly baseline classifiers:
1. **Logistic Regression** (`class_weight="balanced"`)
2. **Random Forest Classifier** (`100` estimators, `max_depth=8`, `balanced_subsample`)
3. **HistGradientBoostingClassifier** (`max_iter=100`, `max_depth=6`, `balanced`)

The winning candidate is automatically calibrated via isotonic or sigmoid probability calibration (`CalibratedClassifierCV`) and evaluated on a held-out test split:
- **ROC-AUC & PR-AUC** (primary discrimination metrics)
- **Brier Score** (calibration quality)
- **F1-Score, Precision, Recall** (tuned at optimal decision threshold)
- **Confusion Matrix** (tracking false positives and false negatives)

All metrics are authentic held-out results written to `artifacts/models/landslide_24h/<version>/metrics.json`.

---

## 6. Model Artifact Portability

A trained model can be packaged and transferred to any environment without retraining:

```bash
# On training machine:
python -m backend.app.ml.cli model export --model v2.0.0 --output landslide-bundle.zip

# Transfer landslide-bundle.zip and landslide-bundle.zip.sha256 to target machine

# On deployment machine:
python -m backend.app.ml.cli model import --file landslide-bundle.zip
```

FastAPI server startup (`backend/app/main.py`) **never calls `model.fit()`**. It strictly loads existing artifacts in `< 50ms`. If no artifact exists, it safely falls back to deterministic physical susceptibility calculations.
