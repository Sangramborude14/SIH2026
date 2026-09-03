# AGENTS.md — Authoritative Developer & AI Assistant Guide
## SIH26001: AI-Based Landslide Early-Warning & Continuous Telemetry System (NER India)

This is the canonical, authoritative specification for developers, contributors, and AI assistants working on the **SIH26001 North Eastern Region (NER) Landslide Decision Support System**.

---

### 1. PRIMARY MISSION
- **System**: SIH26001 Disaster Intelligence Command Center & Early Warning System.
- **Core Mission**: Detect abnormal hydrometeorological conditions associated with slope instability, estimate current geotechnical susceptibility, and deploy a genuinely trained, calibrated AI/ML model to forecast the probability of an upcoming landslide within a 24-hour window across the North Eastern Region of India.
- **Core Requirement**: This system is a deterministic and probabilistic early-warning engine. **It is NOT a chatbot.**

---

### 2. CORE ARCHITECTURE
```text
Live Data Sources (Open-Meteo, Bhoonidhi ISRO, Static DEM)
                     ↓
Dedicated Live Ingestion Scheduler (900s / 15m) → PostgreSQL (weather_observations, weather_forecast_snapshots)
                     ↓
Validation / Freshness Layer (DataValidator, FreshnessEvaluator)
                     ↓
Standardized Feature Engineering Pipeline (25 Topographic, Temporal, Hydrometeorological Features)
                     ↓
Dual-Engine Risk Evaluation (30s Cadence):
   ├─ A. Deterministic Physical Susceptibility Formula (0–100 Score, Infinite Lead Time)
   ├─ B. Statistical & Multivariate Environmental Anomaly Engine (0.00–1.00 Anomaly Index)
   └─ C. Trained & Calibrated Tabular ML Model (0.00–1.00 Landslide Probability P(T + 24h))
                     ↓
Dual-Threshold Escalation & Alert Lifecycle (P >= 0.55 WATCH, P >= 0.75 WARNING)
                     ↓
Real-Time GIS Command Center Dashboard (Interactive Prediction Heatmaps, Station Perimeters, Timelines)
                     ↓
Optional Downstream LLM (Gemini Natural Language Briefing Agent ONLY)
```

---

### 3. AI/ML VS LLM BOUNDARIES
- **Statistical / Multivariate Anomaly**: Measures whether current rainfall/soil moisture deviates from baseline.
- **Deterministic Current Risk**: Physics-based geotechnical factor of safety / susceptibility score ($0\text{--}100$).
- **Machine Learning Forecast**: Probabilistic tabular model estimating $P(\text{landslide in next 24 hours})$ ($0.00\text{--}1.00$).
- **Downstream LLM (Google Gemini)**:
  - Generates natural-language briefing summaries of already-computed assessments.
  - **GEMINI MUST NEVER**: Calculate or alter risk scores, modify factor weights, invent sensor measurements, issue warnings independently, or override deterministic/ML outputs.

---

### 4. MODEL LIFECYCLE
```text
[Raw Ground Truth / Synthetic Scenarios]
                   ↓
         [Canonical Importers]
                   ↓
       [Standardized Parquet/CSV]
                   ↓
      [Leakage-Safe Grouped Split]
                   ↓
       [Offline ML Training CLI]
                   ↓
   [Calibrated Model Artifact (.joblib)]
                   ↓
[Model Registry (artifacts/models/landslide_24h/)]
                   ↓
[Production Directory (backend/models/landslide/)]
                   ↓
    [FastAPI Startup: Artifact Load Only]
```

---

### 5. MODEL STATUS VALUES
The model registry strictly reports one of the following statuses via `GET /api/v1/ml/status` and `cli status`:
- `NOT_TRAINED`: No serialized model artifact found. Deterministic physics fallback is active.
- `READY_SYNTHETIC`: Model trained on high-volume synthetic scenarios with hard negatives; verified on held-out synthetic test split.
- `READY_HISTORICAL`: Model trained on official GSI/NASA historical events and retrospective weather archives.
- `READY_MIXED`: Model trained on composite historical inventory supplemented with synthetic scenario variations.
- `INCOMPATIBLE`: Artifact feature schema does not match current 25-feature schema specification.
- `FAILED`: Model file corrupted or unpickling failed. Fallback active.
- `STALE`: Model trained over 90 days ago without retraining on newly accumulated telemetry.

---

### 6. SYNTHETIC DATA POLICY
- High-volume scenario generation (`SyntheticLandslideDatasetGenerator`) is standard for pipeline benchmarking and offline training.
- **Formula Independence**: Ground truth must NOT simply be `label = risk_score > 70`. Ground truth is generated via a hidden geotechnical limit-equilibrium failure model with stochastic cohesion and root reinforcement noise.
- **Hard Negatives Required**:
  - Heavy rain ($180\text{--}250\text{mm}$) on low slope / valley ($< 18^\circ$) $\to$ Label = 0.
  - Steep slope ($> 40^\circ$) under dry antecedent conditions ($< 10\text{mm}$ rain, $< 30\%$ moisture) $\to$ Label = 0.
  - Saturated valley soil without slope $\to$ Label = 0.
- **Provenance Required**: Every synthetic row must specify `dataset_source="SYNTHETIC"`, `is_synthetic=True`, `scenario_id`, `seed`, and `generator_version`.

---

### 7. REAL DATA POLICY & HIERARCHY
1. **Priority A (GSI National Inventory / Bhusanket / Bhukosh)**: Primary official ground truth for India. Imported via manual workflow (`data/external/gsi/`). Automated scraping of protected government portals is strictly prohibited.
2. **Priority B (NASA Global Landslide Catalog)**: Supplementary global benchmark. Automated download script filters to NER bounding box ($21.5^\circ\text{N}\text{--}29.5^\circ\text{N}, 89.5^\circ\text{E}\text{--}97.5^\circ\text{E}$).
3. **Priority C (NRSC / ISRO Landslide Atlas)**: Marked `REFERENCE_ONLY`. Used for district vulnerability cross-validation; not scraped into synthetic coordinates.
4. **Retrospective Telemetry**: Open-Meteo Historical Weather Archive (`https://archive-api.open-meteo.com/v1/archive`).
5. **Phase-2 Satellite Precipitation**: NASA GPM IMERG architecture documented in `docs/ml/IMERG_INTEGRATION.md`.

---

### 8. EXACT TRAINING COMMANDS
All training is executed offline via the unified CLI:
```bash
# Environment & directory verification
python -m backend.app.ml.cli bootstrap

# One-command end-to-end synthetic demo training
python -m backend.app.ml.cli demo-train

# Generate synthetic dataset
python -m backend.app.ml.cli synthetic generate --samples 50000 --seed 42

# Full config-driven training
python -m backend.app.ml.cli train --config backend/app/ml/config/default.yaml

# Import GSI inventory
python -m backend.app.ml.cli dataset import-gsi --input data/external/gsi/landslides.csv

# Download & import NASA GLC
python -m backend.app.ml.cli dataset download-nasa-glc

# Backfill historical weather from Open-Meteo
python -m backend.app.ml.cli data backfill-weather --location all --start 2023-01-01 --end 2024-01-01
```

---

### 9. MODEL TRANSFER & PACKAGING
Export and import models without retraining:
```bash
# Export active model bundle with SHA-256 checksum
python -m backend.app.ml.cli model export --model v2.0.0 --output landslide-bundle.zip

# Import and activate on target server
python -m backend.app.ml.cli model import --file landslide-bundle.zip

# Switch active version
python -m backend.app.ml.cli model activate --version v2.0.0
```

---

### 10. PRODUCTION INFERENCE RULES
- **HARD INVARIANT**: `model.fit()` must **NEVER** be called during FastAPI startup, lifespan, or HTTP request handlers.
- Startup strictly loads existing artifacts via `model_registry.reload_artifacts()`.
- Inference latency must remain under $15\text{ms}$ per station.
- If model loading fails, the system logs a warning, sets status to `NOT_TRAINED`, and serves deterministic physics predictions without crashing.

---

### 11. FEATURE SCHEMA COMPATIBILITY
- Standardized 25-feature schema defined in `backend/app/ml/features/pipeline.py`.
- Shared identically between training and real-time inference.
- Schema mismatches raise `IncompatibleFeatureSchemaError` and trigger automatic graceful fallback.

---

### 12. DATA LEAKAGE RULES
- **Zero Future Leakage**: No observation recorded after prediction timestamp $T$ may enter features predicting $T + 24\text{h}$.
- **Grouped Scenario Splits**: All samples from a given `scenario_id` or `event_id` must reside entirely in either train, validation, or test split (`GroupShuffleSplit`).
- **Forecast Isolation**: Numerical forecast points are stored exclusively in `weather_forecast_snapshots`, never backfilled into `weather_observations`.

---

### 13. LIVE INGESTION ARCHITECTURE & CADENCE
- **Assessment Cadence**: `ENGINE_ASSESSMENT_INTERVAL_SECONDS = 30` (evaluates current station risk and feeds UI).
- **Live Ingestion Cadence**: `LIVE_INGESTION_INTERVAL_SECONDS = 900` ($15\text{ minutes}$).
- The live ingestion scheduler polls Open-Meteo, validates telemetry, and commits observations to PostgreSQL via bulk idempotent upsert on `(location_id, timestamp, source, observation_type)`.
- Health endpoint: `GET /api/v1/system/ingestion-health`.

---

### 14. DATABASE RULES
- **Production Database**: Supabase PostgreSQL (`DATABASE_URL`).
- **Connection**: Supabase Transaction Pooler (port 6543) with `statement_cache_size=0`.
- **Never**:
  - Hardcode database credentials.
  - Execute destructive migrations in production.
  - Insert duplicate telemetry rows (always use `weather_repository.upsert_batch`).

---

### 15. DATA PROVENANCE
Every observation, feature vector, and forecast record tracks its provenance:
`OBSERVED`, `DERIVED`, `FORECAST`, `HISTORICAL_REANALYSIS`, `SIMULATED`.

---

### 16. NO FAKE METRICS RULE
- Calibration metrics, accuracy scores, ROC-AUC, and PR-AUC must be computed strictly from genuine held-out evaluation splits.
- Hardcoded dictionaries disguised as empirical test results are strictly forbidden.
- The `ModelCalibrationService.run_backtest()` is explicitly designated as `DETERMINISTIC WEIGHT SANDBOX / SIMULATED BENCHMARK`.

---

### 17. PRIORITY EVALUATION METRICS
1. **PR-AUC (Precision-Recall AUC)**: Primary selection metric under extreme class imbalance.
2. **ROC-AUC**: Secondary discrimination metric across all thresholds.
3. **Brier Score**: Evaluates probability calibration quality ($\le 0.05$ target).
4. **False Negative Rate**: Critical safety threshold ($\le 5\%$ missed landslides at alert threshold).

---

### 18. DETERMINISTIC FALLBACK INVARIANCE
If the ML predictor is unavailable, disabled, or uncalibrated:
1. `ml_forecast_available = false`
2. `ml_landslide_probability = null`
3. Engine serves physical susceptibility risk score ($0\text{--}100$).
4. System remains $100\%$ functional; zero UI crashes or HTTP 500 errors.

---

### 19. REPOSITORY DIRECTORY MAP
```text
backend/
  app/
    api/v1/endpoints/     # REST Endpoints (ml, locations, system, field)
    core/                 # Config, database, cache, logging
    engine/               # Deterministic risk engine, pipeline, schedulers
    ml/
      cli.py              # Unified CLI for training, bootstrap, export
      config/default.yaml # ML hyperparameters & schema config
      dataset/            # GSI, NASA, and Open-Meteo backfill adapters
      evaluation/         # Authentic held-out metrics & confusion matrix
      explainability/     # Feature importance & SHAP approximation
      features/           # Shared 25-feature extraction pipeline
      prediction/         # Baselines (Logistic, RF, HistGB) & calibrator
      registry/           # Model loading, discovery, and fallback
      synthetic/          # High-volume scenario generator with hard negatives
    models/               # SQLAlchemy models (landslide_events, forecasts)
    repositories/         # Repository pattern with idempotent upserts
    services/             # Ingestion, inference, and data services
  alembic/versions/       # Database schema migrations
data/
  external/gsi/           # Place manual GSI CSV exports here
  raw/                    # Cached Open-Meteo and NASA GLC downloads (gitignored)
  processed/              # Generated Parquet datasets (gitignored)
artifacts/models/         # Versioned model artifact repository
frontend/src/             # Next.js 15 GIS Command Center Dashboard
docs/ml/                  # Dataset research, README, and IMERG architecture
```

---

### 20. PORTABLE DEVELOPMENT
- **Paths**: All file operations use Python `pathlib.Path` relative to project root.
- **Environment Overrides**: `ML_DATA_DIR`, `ML_ARTIFACT_DIR`, `ML_ACTIVE_MODEL_PATH`.
- **Cross-Platform**: Tested on Windows 11, Ubuntu Linux, and macOS. CPU-only training standard; no CUDA or C++ compiler required.

---

### 21. TESTING REQUIREMENTS
- **Unit Tests**: Offline-safe, no live network dependencies (`pytest backend/tests -m "not integration"`).
- **Integration Tests**: Isolated in `backend/tests/` with graceful skipping when credentials are absent.
- **Minimum Test Suite Target**: 160+ passing tests across ML pipeline, synthetic generator, data importers, live ingestion, and REST endpoints.

---

### 22. DEPLOYMENT
- **Frontend Target**: Vercel (`npm run build`).
- **Backend Target**: Render / Docker Container (`docker build -f Dockerfile.backend .`).
- **Health Probes**:
  - `GET /health` (Aggregated health probe)
  - `GET /ready` (Readiness probe)
  - `GET /api/v1/ml/status` (ML model registry status)
  - `GET /api/v1/system/ingestion-health` (Continuous telemetry collection health)

---

### 23. RESEARCH RULE
Always record dataset access mechanisms, licensing terms, and limitations in `docs/ml/DATASET_RESEARCH.md` before writing data adapters.

---

### 24. PRE-COMMIT CHECKLIST
Before pushing any commit:
1. **Backend Tests**: `python -m pytest backend/tests -v` (160+ passing)
2. **Frontend Build**: `npm run build` inside `frontend/` (12/12 routes passing)
3. **Environment Check**: `python -m backend.app.core.env_check`
4. **Secret Audit**: Verify `git status` contains no `.env` or credential files.
5. **No Localhost in Prod**: Verify no hardcoded `localhost` URLs in production paths.
