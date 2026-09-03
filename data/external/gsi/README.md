# GSI External Inventory Import Directory

Place manually downloaded Geological Survey of India (GSI) Bhusanket / Bhukosh / NGDR CSV or GeoJSON files in this directory.

### To import:
```bash
python -m backend.app.ml.cli dataset import-gsi --input data/external/gsi/landslides.csv
```
