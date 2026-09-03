# DATASET_RESEARCH.md — Landslide & Environmental Datasets for SIH26001

## Executive Summary
This document provides an authoritative, scientific, and legal evaluation of candidate landslide inventory databases, Earth observation missions, and retrospective hydrometeorological archives for training and evaluating machine learning models in the North Eastern Region (NER) of India.

In accordance with strict system rules:
- **No scraping of protected government systems** requiring interactive authentication or CAPTCHAs.
- **No fabrication of ground-truth events or APIs**.
- **No conflation of remote-sensing segmentation masks with 24-hour temporal early-warning labels**.

---

## 1. Candidate Source Evaluations

### Priority A: Geological Survey of India (GSI) National Landslide Inventory / Bhusanket / Bhukosh / NGDR
* **Organization**: Geological Survey of India (GSI), Ministry of Mines, Government of India.
* **Official Sources**:
  - Bhusanket Portal: `https://bhusanket.gsi.gov.in/`
  - Bhukosh Geoscience Portal: `https://bhukosh.gsi.gov.in/`
  - National Geoscience Data Repository (NGDR): `https://ngdr.gsi.gov.in/`
* **Dataset Purpose**: National field-validated landslide inventory under the National Landslide Susceptibility Mapping (NLSM) programme.
* **Geographic Coverage**: Entire Himalayas, Western Ghats, and North Eastern Region of India.
* **NER Coverage**: Exceptional coverage across all 8 NER states (Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim, Tripura). Over 60,000+ field-validated landslide polygons and points nationwide.
* **Event Count**: ~80,000+ national records (estimated ~25,000+ in North Eastern Region).
* **Date Range**: 1950–Present (accelerated field mapping post-2014).
* **Fields / Schema**:
  - Spatial: `Latitude`, `Longitude`, `Geometry (Polygon/Point)`, `State`, `District`, `Toposheet No.`
  - Geomorphological: `Landslide Type` (debris slide, rockfall, slump, mud flow), `Geological Formation`, `Slope Angle`, `Aspect`, `Material`
  - Temporal: `Date of Occurrence` (frequently available), `Time of Occurrence` (rarely exact, mostly date-only or unknown)
  - Trigger: `Rainfall Triggered`, `Anthropogenic / Road Cut`, `Tectonic / Seismic`
  - Validation: `Field Validated By Geologist`, `High Confidence`
* **Spatial Precision**: High (GPS field surveyed, 1:50,000 scale to GPS point).
* **Temporal Precision**: `DATE_ONLY` in 85%+ of records; `APPROXIMATE` or `UNKNOWN` in older historical records; `EXACT_TIME` in fewer than 5% of records.
* **Download Mechanism**: Manual export through Bhukosh / NGDR web GIS interface (WFS/WMS/Shapefile/GeoJSON/CSV).
* **API Availability**: No public unauthenticated REST API exists. Access is restricted to registered authenticated sessions and GIS export tools.
* **Authentication**: Indian government mobile OTP / registration required for bulk download via NGDR portal.
* **License / Usage Terms**: Government of India National Data Sharing and Accessibility Policy (NDSAP) / GSI terms of use. Permitted for academic research and hackathons with attribution; automated scraping strictly disallowed.
* **Machine-Readable Format**: CSV, ESRI Shapefile, GeoJSON, KML.
* **Automated Download**: **NO**. Must be imported manually via documented workflow.
* **Suitability for Forecasting Labels**: **PRIMARY GROUND TRUTH**. Field-validated ground truth in the target geography. Requires models to respect `DATE_ONLY` target window definitions.
* **Limitations**: Temporal resolution is predominantly daily rather than hourly; exact trigger timestamps must not be hallucinated.
* **Integration Status**: **SUPPORTED VIA MANUAL IMPORTER** (`python -m backend.app.ml.cli dataset import-gsi --input data/external/gsi/landslides.csv`).

---

### Priority B: NASA Global Landslide Catalog (GLC)
* **Organization**: National Aeronautics and Space Administration (NASA) Goddard Space Flight Center.
* **Official Source**: `https://data.nasa.gov/Earth-Science/Global-Landslide-Catalog-Export/dd9e-wu2v` / NASA Cooperative Open Online Landslide Repository (COOLR).
* **Dataset Purpose**: Compiles rainfall-triggered landslide events globally reported in online media, disaster reports, and government communiques.
* **Geographic Coverage**: Global ($180^\circ\text{W}$ to $180^\circ\text{E}$, $60^\circ\text{S}$ to $70^\circ\text{N}$).
* **NER Coverage**: Moderate (~300–800 documented events across Assam, Sikkim, Meghalaya, and Manipur corridors along national highways).
* **Event Count**: ~11,000+ events globally.
* **Date Range**: 2007–2018 (with sporadic updates).
* **Fields / Schema**:
  - `event_id`, `event_title`, `event_description`, `event_date`, `event_time`
  - `location_description`, `location_accuracy` (e.g. 5km, 25km, 100km)
  - `latitude`, `longitude`, `country_name`, `admin_division_name`
  - `landslide_category` (mudslide, rockfall, debris flow, complex)
  - `landslide_trigger` (downpour, continuous rain, monsoon, flood)
  - `landslide_size` (small, medium, large, very large)
  - `fatality_count`, `injury_count`
* **Spatial Precision**: Variable ($1\text{km}$ to $25\text{km}$ depending on reporting source).
* **Temporal Precision**: `DATE_ONLY` to `HOUR` (some events have estimated hour of occurrence from news reports).
* **Download Mechanism**: Direct public CSV/JSON download from NASA Open Data Portal.
* **API Availability**: Socrata Open Data API (SODA API) available (`https://data.nasa.gov/resource/dd9e-wu2v.json`).
* **Authentication**: None required for public bulk CSV export.
* **License / Usage Terms**: NASA Open Data Policy (Public Domain / CC0).
* **Machine-Readable Format**: CSV, GeoJSON.
* **Automated Download**: **YES**. Fully scriptable via standard HTTP client.
* **Suitability for Forecasting Labels**: **SUPPLEMENTARY BENCHMARK**. Excellent for validating pipeline mechanics and international cross-comparison, but has known media-reporting bias (only slides blocking major roads or causing casualties get logged).
* **Limitations**: Catalog ends primarily in 2018; spatial accuracy is coarse compared to GSI field surveys.
* **Integration Status**: **AUTOMATED DOWNLOADER IMPLEMENTED** (`python -m backend.app.ml.cli dataset download-nasa-glc`).

---

### Priority C: NRSC / ISRO Landslide Atlas of India
* **Organization**: National Remote Sensing Centre (NRSC), Indian Space Research Organisation (ISRO).
* **Official Source**: `https://www.nrsc.gov.in/` (Landslide Atlas of India, February 2023).
* **Dataset Purpose**: Pan-India landslide database created from high-resolution Indian Remote Sensing (IRS) satellites (Cartosat, Resourcesat).
* **Geographic Coverage**: 17 states and 2 Union Territories in India (Himalayas and Western Ghats).
* **NER Coverage**: Comprehensive coverage across all 8 NER states; ranks districts by landslide vulnerability (e.g., Rudraprayag, Tehri Garhwal, Subansiri, West Sikkim).
* **Event Count**: 80,000+ landslide scars mapped between 1998 and 2022.
* **Fields / Schema**: Published primarily as an atlas with county/district-level risk indices and aggregated spatial heatmaps.
* **Spatial Precision**: High in raster format ($1\text{m}$ to $10\text{m}$ imagery-derived).
* **Temporal Precision**: Decadal/multi-year aggregations (1998–2022); event occurrence timestamp is not published as an open tabular dataset.
* **Download Mechanism**: PDF Atlas document and interactive Bhoonidhi/Bhuvan web viewers.
* **API Availability**: No open tabular REST API for raw point-event occurrence time-series.
* **Authentication**: Restricted.
* **License / Usage Terms**: ISRO / NRSC Proprietary Copyright.
* **Machine-Readable Format**: Web maps (Bhuvan OGC services) and PDF tables.
* **Automated Download**: **NO**.
* **Suitability for Forecasting Labels**: **REFERENCE ONLY**. We must NOT parse PDF pages into fake ground-truth points. It serves as authoritative ground truth for regional district vulnerability rankings, not daily binary training labels.
* **Integration Status**: **MARKED REFERENCE_ONLY**.

---

### Priority D: Landslide4Sense (Benchmark Dataset)
* **Organization**: IEEE GRSS / Technical University of Munich (TUM).
* **Official Source**: `https://landslide4sense.comp.hkbu.edu.hk/` (2022).
* **Dataset Purpose**: Deep learning benchmark for semantic segmentation of landslide boundaries from multi-spectral Sentinel-2 satellite imagery, ALOS PALSAR DEM, and slope data.
* **Geographic Coverage**: Globally distributed sample patches (including Himalayas).
* **NER Coverage**: Patch-based.
* **Event Count**: 3,799 image patches ($128 \times 128$ pixels across 14 spectral bands).
* **Fields / Schema**: Multi-band GeoTIFF rasters (B1–B12 Sentinel-2, DEM, Slope) + binary segmentation mask.
* **Spatial Precision**: $10\text{m}$ pixel resolution.
* **Temporal Precision**: Static post-disaster satellite acquisitions. Zero continuous temporal weather sequence.
* **Download Mechanism**: Requires registration on competition platform.
* **Suitability for Forecasting Labels**: **NOT SUITABLE FOR 24H RISK FORECASTING**. Landslide4Sense solves "Find where a landslide already occurred in this satellite image," which is distinct from "Forecast if a landslide will occur in the next 24 hours given incoming rainfall."
* **Integration Status**: **MARKED OPTIONAL FUTURE REMOTE-SENSING SUBMODEL**.

---

## 2. Retrospective Environmental Data Sources

| Source | Variables | Time Step | Latency | Automated Access | Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Open-Meteo Historical Weather API** | Precipitation, Rain, 4 Soil Moisture depths, Pressure, Humidity, Temp, Wind | Hourly | ERA5 / Seamless Reanalysis | **YES** (Free, unauthenticated) | **Primary Retrospective Telemetry** |
| **Open-Meteo Historical Forecast API** | Archival numerical weather predictions (ECMWF, GFS) issued before target time | Hourly | Historical archive | **YES** (Free, unauthenticated) | **Forecast Feature Backtesting** |
| **NASA GPM IMERG** | Multi-satellite precipitation estimation (half-hourly, daily) | 30-min / Daily | ~4 hours | Requires Earthdata Login | **Phase-2 Spatial Calibration** |

---

## 3. Dataset Hierarchy for Model Maturity

```text
LEVEL 0: Physics / Deterministic Geotechnical Baseline (Infinite lead time, 0 labels needed)
   ↓
LEVEL 1: Synthetic Scenario Dataset (High volume, diverse hard negatives, pipeline proof)
   ↓
LEVEL 2: NASA GLC Public Historical Labels (External international baseline validation)
   ↓
LEVEL 3: GSI Field-Validated NER Historical Inventory (Official Indian ground truth)
   ↓
LEVEL 4: Prospective Live Field / Telemetry Validation (Real-time operational verification)
```
