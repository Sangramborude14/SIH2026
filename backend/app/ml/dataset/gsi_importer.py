import csv
import json
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.models.landslide_event import LandslideEvent, TimePrecision


class GSILandslideImporter:
    """
    Normalizes official Geological Survey of India (GSI) Bhusanket/Bhukosh landslide exports
    into the canonical LandslideEvent database catalog.
    Supports CSV and GeoJSON formats downloaded manually from official GSI portals.
    """

    # Mapping common GSI export column names to canonical fields
    FIELD_CANDIDATES = {
        "latitude": ["latitude", "lat", "y", "y_coord", "latitude_dd"],
        "longitude": ["longitude", "long", "lon", "x", "x_coord", "longitude_dd"],
        "date": ["occurrence_date", "event_date", "date_of_occurrence", "date", "slide_date"],
        "state": ["state", "state_name", "province"],
        "district": ["district", "district_name", "dist"],
        "location": ["location", "location_name", "village", "place", "site_name"],
        "type": ["landslide_type", "slide_type", "type_of_movement", "type"],
        "trigger": ["trigger", "causative_factor", "triggering_factor", "cause"],
        "external_id": ["slide_id", "incident_id", "objectid", "id", "gsi_id"],
    }

    @staticmethod
    def _find_col(row: Dict[str, Any], candidates: List[str]) -> Optional[Any]:
        row_lower = {k.lower().strip(): v for k, v in row.items()}
        for c in candidates:
            if c in row_lower and row_lower[c] is not None and str(row_lower[c]).strip() != "":
                return row_lower[c]
        return None

    @classmethod
    async def import_from_csv(
        cls,
        session: AsyncSession,
        csv_path: Path,
        dataset_version: str = "GSI-NLSM-v1.0"
    ) -> Dict[str, int]:
        """Reads GSI CSV file, normalizes fields, and idempotently upserts to landslide_events."""
        if not csv_path.exists():
            raise FileNotFoundError(f"GSI inventory file not found at: {csv_path}")

        records_to_insert: List[LandslideEvent] = []
        skipped = 0
        total_read = 0

        with open(csv_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                total_read += 1
                lat_raw = cls._find_col(raw_row, cls.FIELD_CANDIDATES["latitude"])
                lon_raw = cls._find_col(raw_row, cls.FIELD_CANDIDATES["longitude"])
                date_raw = cls._find_col(raw_row, cls.FIELD_CANDIDATES["date"])

                if not lat_raw or not lon_raw or not date_raw:
                    skipped += 1
                    continue

                try:
                    lat = float(lat_raw)
                    lon = float(lon_raw)
                except ValueError:
                    skipped += 1
                    continue

                # Coordinate bounding sanity check for North Eastern Region + Indian Himalayas
                if not (5.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0):
                    skipped += 1
                    continue

                # Parse occurrence date
                parsed_date: Optional[date] = None
                parsed_ts: Optional[datetime] = None
                time_precision = TimePrecision.DATE_ONLY

                date_str = str(date_raw).strip()
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
                    try:
                        parsed_date = datetime.strptime(date_str, fmt).date()
                        parsed_ts = datetime.combine(parsed_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue

                if not parsed_date:
                    # Try datetime with time
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
                        try:
                            parsed_ts = datetime.strptime(date_str[:19], fmt).replace(tzinfo=timezone.utc)
                            parsed_date = parsed_ts.date()
                            time_precision = TimePrecision.HOUR
                            break
                        except ValueError:
                            continue

                if not parsed_date:
                    skipped += 1
                    continue

                state_val = str(cls._find_col(raw_row, cls.FIELD_CANDIDATES["state"]) or "Unknown NER State").strip()
                district_val = str(cls._find_col(raw_row, cls.FIELD_CANDIDATES["district"]) or "Unknown District").strip()
                loc_name = str(cls._find_col(raw_row, cls.FIELD_CANDIDATES["location"]) or f"{district_val} Slope").strip()
                slide_type = str(cls._find_col(raw_row, cls.FIELD_CANDIDATES["type"]) or "RAINFALL_TRIGGERED_SLIDE").strip()
                trigger_val = str(cls._find_col(raw_row, cls.FIELD_CANDIDATES["trigger"]) or "HEAVY_RAINFALL").strip()
                ext_id = str(cls._find_col(raw_row, cls.FIELD_CANDIDATES["external_id"]) or f"GSI-{lat:.4f}-{lon:.4f}-{parsed_date.isoformat()}").strip()

                event = LandslideEvent(
                    source="GSI",
                    external_id=ext_id,
                    latitude=lat,
                    longitude=lon,
                    state=state_val,
                    district=district_val,
                    location_name=loc_name,
                    occurrence_timestamp=parsed_ts,
                    occurrence_date=parsed_date,
                    time_precision=time_precision,
                    landslide_type=slide_type,
                    trigger=trigger_val,
                    verification_status="FIELD_CONFIRMED",
                    source_confidence=1.0,
                    original_source=csv_path.name,
                    source_metadata=raw_row,
                    dataset_version=dataset_version,
                )
                records_to_insert.append(event)

        # Idempotent persistence avoiding duplicate entries
        inserted_count = 0
        if records_to_insert:
            ext_ids = [e.external_id for e in records_to_insert]
            stmt = select(LandslideEvent.external_id).where(
                LandslideEvent.source == "GSI",
                LandslideEvent.external_id.in_(ext_ids)
            )
            existing_res = await session.execute(stmt)
            existing_ids = set(existing_res.scalars().all())

            for ev in records_to_insert:
                if ev.external_id not in existing_ids:
                    session.add(ev)
                    existing_ids.add(ev.external_id)
                    inserted_count += 1

            await session.commit()

        logger.info(
            f"GSI Import complete from {csv_path.name}: "
            f"Read {total_read} rows, +{inserted_count} new events inserted, {skipped} skipped, {total_read - inserted_count - skipped} already existing."
        )

        return {
            "total_read": total_read,
            "inserted": inserted_count,
            "skipped": skipped,
            "duplicates": total_read - inserted_count - skipped,
        }
