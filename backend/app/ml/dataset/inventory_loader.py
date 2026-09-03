import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
from backend.app.ml.dataset.schemas import LandslideInventoryRecord

logger = logging.getLogger(__name__)


class LandslideInventoryLoader:
    """
    Ingests and validates historical landslide ground-truth inventories
    from CSV, GeoJSON, and Parquet formats.
    """

    NER_LAT_MIN = 20.0
    NER_LAT_MAX = 32.0
    NER_LON_MIN = 87.0
    NER_LON_MAX = 98.0

    @classmethod
    def load_from_file(
        cls,
        filepath: str | Path,
        confidence_filter: Optional[List[str]] = None,
        drop_out_of_bounds: bool = True,
    ) -> Tuple[List[LandslideInventoryRecord], Dict[str, Any]]:
        """
        Loads and validates inventory events from a file.
        Returns (validated_records, metadata_summary).
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Landslide inventory file not found at: {path}")

        ext = path.suffix.lower()
        if ext == ".csv":
            raw_records = cls._load_csv(path)
        elif ext in [".json", ".geojson"]:
            raw_records = cls._load_geojson(path)
        elif ext == ".parquet":
            raw_records = cls._load_parquet(path)
        else:
            raise ValueError(f"Unsupported inventory file extension '{ext}'. Use .csv, .geojson, or .parquet.")

        validated: List[LandslideInventoryRecord] = []
        rejected: List[Dict[str, Any]] = []
        has_subdaily_timestamps = False

        for idx, row in enumerate(raw_records):
            try:
                rec = LandslideInventoryRecord.model_validate(row)

                # Geographic bounds check for NER corridor
                if drop_out_of_bounds:
                    if not (cls.NER_LAT_MIN <= rec.latitude <= cls.NER_LAT_MAX and
                            cls.NER_LON_MIN <= rec.longitude <= cls.NER_LON_MAX):
                        rejected.append({"row_index": idx, "reason": "Outside NER geographic bounds", "data": row})
                        continue

                # Confidence tier filter
                if confidence_filter and rec.confidence not in confidence_filter:
                    continue

                if rec.event_time is not None:
                    has_subdaily_timestamps = True

                validated.append(rec)
            except Exception as e:
                rejected.append({"row_index": idx, "reason": str(e), "data": row})

        summary = {
            "file_path": str(path),
            "total_rows_read": len(raw_records),
            "valid_records_count": len(validated),
            "rejected_records_count": len(rejected),
            "rejected_samples": rejected[:5],
            "has_subdaily_timestamps": has_subdaily_timestamps,
            "recommended_target_horizon": "6H_OR_12H" if has_subdaily_timestamps else "DAILY_24H",
            "unique_states": list(set(r.state for r in validated)),
            "date_range": {
                "min": min((r.event_date for r in validated), default=None),
                "max": max((r.event_date for r in validated), default=None),
            } if validated else None,
        }

        logger.info(
            f"Loaded {len(validated)} validated landslide records from {path.name} "
            f"({len(rejected)} rejected). Target horizon: {summary['recommended_target_horizon']}"
        )
        return validated, summary

    @classmethod
    def _load_csv(cls, path: Path) -> List[Dict[str, Any]]:
        records = []
        with open(path, "r", encoding="utf-8-sig") as f:
            lines = [line for line in f if line.strip() and not line.strip().startswith("#")]
            reader = csv.DictReader(lines)
            for row in reader:
                # Clean keys and string values
                clean_row = {k.strip(): (v.strip() if v else None) for k, v in row.items() if k}
                records.append(clean_row)
        return records


    @classmethod
    def _load_geojson(cls, path: Path) -> List[Dict[str, Any]]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        records = []
        for feature in data.get("features", []):
            props = feature.get("properties", {}) or {}
            geom = feature.get("geometry", {}) or {}
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                # GeoJSON coordinates are [longitude, latitude]
                props["longitude"] = coords[0]
                props["latitude"] = coords[1]
            records.append(props)
        return records

    @classmethod
    def _load_parquet(cls, path: Path) -> List[Dict[str, Any]]:
        df = pd.read_parquet(path)
        return df.to_dict(orient="records")


inventory_loader = LandslideInventoryLoader()
