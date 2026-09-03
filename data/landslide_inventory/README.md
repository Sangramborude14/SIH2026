# Landslide Inventory Dataset Specification (SIH26001)

This directory is the designated ingestion drop-point for authentic historical landslide inventories for the North Eastern Region (NER) of India.

---

## 1. Scientific Principles & Zero Fake Data Policy

* **Authentic Sources Only**: Do not inject fabricated records. Ground truth events must originate from verified sources such as:
  * **Geological Survey of India (GSI)** — National Landslide Susceptibility Mapping (NLSM) & Disaster Inventory.
  * **NASA Global Landslide Catalog (GLC)**.
  * **Border Roads Organisation (BRO)** & State Disaster Management Authorities (SDMA).
* **Target Definition**:
  * Because catalog inventories typically record **event dates** (`YYYY-MM-DD`) rather than exact sub-hourly strike times, the standard supervised model target is formulated as:
    $$\text{Daily Landslide Occurrence } P(Y_{\text{date}} = 1 \mid \mathbf{X})$$
  * If sub-daily timestamps (`HH:MM:SS`) are validated in the input data, sub-daily horizons ($6\text{h}$, $12\text{h}$, $24\text{h}$) are enabled.
* **Un-trained Safety**: If no verified dataset is present in this directory, the AI/ML model registry explicitly declares `MODEL_STATUS: NOT_TRAINED` and routes predictions safely to the deterministic baseline physics engine.

---

## 2. Expected Dataset Schema

### CSV Format (`*.csv`)
A CSV file containing the following column headers:

| Header | Type | Mandatory? | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `event_id` | String | Yes | Unique incident identifier | `GSI-NER-2022-0142` |
| `latitude` | Float | Yes | WGS84 latitude coordinate ($21.5^\circ\text{N} - 29.5^\circ\text{N}$) | `27.3389` |
| `longitude` | Float | Yes | WGS84 longitude coordinate ($89.5^\circ\text{E} - 97.5^\circ\text{E}$) | `88.6065` |
| `event_date` | String | Yes | Incident date (`YYYY-MM-DD`) | `2022-06-18` |
| `event_time` | String | No | Incident time (`HH:MM:SS`, UTC or IST) | `14:30:00` |
| `state` | String | Yes | Indian State (Sikkim, Assam, Mizoram, etc.) | `Sikkim` |
| `district` | String | Yes | District name | `East Sikkim` |
| `location_name` | String | No | Local sector / highway identifier | `Gangtok Ridge Corridor` |
| `source` | String | Yes | Reporting agency | `GSI_NLSM` |
| `confidence` | String | Yes | Confidence tier (`CONFIRMED`, `PROBABLE`, `UNVERIFIED`) | `CONFIRMED` |
| `trigger_type` | String | No | Primary hazard trigger (`HEAVY_RAIN`, `MONSOON`, etc.) | `HEAVY_RAIN` |
| `landslide_size` | String | No | Magnitude (`SMALL`, `MEDIUM`, `LARGE`, `VERY_LARGE`) | `LARGE` |

### GeoJSON Format (`*.geojson`)
Standard RFC 7946 FeatureCollection where each Feature has:
* `geometry`: Point with `[longitude, latitude]`.
* `properties`: Matching the dictionary keys from the CSV schema above.

---

## 3. Template Files
* `template_inventory.csv`: Ready-to-use CSV template containing exact headers and column comments.
* `template_inventory.geojson`: Ready-to-use GeoJSON template.

---

## 4. Running Model Training

Once real inventory data is placed in this directory, execute the reproducible training CLI:
```bash
python -m backend.app.ml.training.train \
  --inventory data/landslide_inventory/your_inventory.csv \
  --output-dir backend/models/landslide \
  --horizon 24h \
  --seed 42
```
