# IMERG_INTEGRATION.md — NASA GPM IMERG Phase-2 Integration Architecture

## 1. Overview
The Integrated Multi-satellitE Retrievals for GPM (IMERG) algorithm combines precipitation estimates from all constellation satellites in the NASA/JAXA Global Precipitation Measurement (GPM) mission, geosynchronous infrared satellite estimates, and monthly surface precipitation gauge data.

For the North Eastern Region of India, IMERG represents a high-value Phase-2 spatial precipitation data source to overcome rain-gauge sparsity in steep mountain terrains where radar beam blockage is severe.

---

## 2. IMERG Product Comparison

| Product Name | Latency | Temporal Resolution | Spatial Resolution | Operational Suitability |
| :--- | :--- | :--- | :--- | :--- |
| **IMERG Early Run** | ~4 hours | Half-hourly ($30\text{ min}$) | $0.1^\circ \times 0.1^\circ$ (~$10\text{ km}$) | **Real-time Early Warning & Anomaly Detection** |
| **IMERG Late Run** | ~14 hours | Half-hourly ($30\text{ min}$) | $0.1^\circ \times 0.1^\circ$ (~$10\text{ km}$) | Daily situational reports & model retraining |
| **IMERG Final Run** | ~3.5 months | Monthly / Daily | $0.1^\circ \times 0.1^\circ$ (~$10\text{ km}$) | Official climatological research & GSI backtesting |

---

## 3. Phase-2 Integration Architecture

```text
NASA Earthdata GES DISC (OPeNDAP / HTTPS REST API)
                       ↓
   Token Authentication (EARTHDATA_TOKEN / .netrc)
                       ↓
     Spatial Bounding Box Subsetting (NER Polygon: 21.5°N - 29.5°N, 89.5°E - 97.5°E)
                       ↓
         NetCDF-4 / HDF5 Slice Decoder (xarray / h5py)
                       ↓
     IMERGProvider Adapter (converts precipitationCal mm/hr)
                       ↓
  Spatial Calibration Layer (Bridges station point observations with satellite grid)
```

---

## 4. Planned Requirements & Environment
* **Authentication**: NASA Earthdata Login account (`EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` or Bearer token).
* **Dependencies**: `xarray>=2024.0.0`, `netCDF4>=1.6.0`, `h5netcdf>=1.3.0`.
* **Deployment**: Deferred to Phase 2 to preserve lightweight, zero-binary deployment on standard student hardware. Current system relies on Open-Meteo's unified reanalysis and forecast API.
