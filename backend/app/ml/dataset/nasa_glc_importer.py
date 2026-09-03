import csv
import hashlib
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.models.landslide_event import LandslideEvent, TimePrecision


class NASAGLCLandslideImporter:
    """
    Downloader and importer for the official NASA Global Landslide Catalog (GLC).
    Filters events geographically to the North Eastern Region (NER) bounding corridor:
    Latitude: 21.5°N - 29.5°N, Longitude: 89.5°E - 97.5°E.
    """

    NASA_GLC_CSV_URL = "https://data.nasa.gov/api/views/dd9e-wu2v/rows.csv?accessType=DOWNLOAD"

    # NER geographical bounding polygon (covering all 8 NER states from Sikkim to Arunachal Pradesh)
    NER_LAT_MIN = 21.5
    NER_LAT_MAX = 29.5
    NER_LON_MIN = 88.0
    NER_LON_MAX = 97.5


    @classmethod
    async def download_catalog(cls, target_dir: Path) -> Path:
        """Downloads the official NASA GLC CSV export to a local raw directory with hash verification."""
        target_dir.mkdir(parents=True, exist_ok=True)
        cached_file = target_dir / "nasa_global_landslide_catalog.csv"

        if cached_file.exists() and cached_file.stat().st_size > 100_000:
            logger.info(f"Using cached NASA GLC file at: {cached_file}")
            return cached_file

        logger.info(f"Downloading NASA Global Landslide Catalog from {cls.NASA_GLC_CSV_URL}...")
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            resp = await client.get(cls.NASA_GLC_CSV_URL)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to download NASA GLC (HTTP {resp.status_code}): {resp.text[:120]}")

            content = resp.content
            with open(cached_file, "wb") as f:
                f.write(content)

            sha256 = hashlib.sha256(content).hexdigest()
            logger.info(f"NASA GLC downloaded successfully ({len(content)} bytes, SHA256: {sha256[:12]}...)")
            return cached_file

    @classmethod
    async def import_to_database(
        cls,
        session: AsyncSession,
        csv_path: Path,
        filter_ner_only: bool = True,
        dataset_version: str = "NASA-GLC-2018"
    ) -> Dict[str, Any]:
        """Parses NASA GLC CSV, filters to NER region, and idempotently inserts canonical events."""
        if not csv_path.exists():
            raise FileNotFoundError(f"NASA GLC file not found: {csv_path}")

        records: List[LandslideEvent] = []
        total_rows = 0
        ner_matched = 0
        skipped = 0

        with open(csv_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                total_rows += 1
                row = {k.lower().strip(): v for k, v in raw_row.items()}

                lat_str = row.get("latitude")
                lon_str = row.get("longitude")
                date_str = row.get("event_date") or row.get("date")

                if not lat_str or not lon_str or not date_str:
                    skipped += 1
                    continue

                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                except ValueError:
                    skipped += 1
                    continue

                # Filter geographically to NER region
                if filter_ner_only:
                    if not (cls.NER_LAT_MIN <= lat <= cls.NER_LAT_MAX and cls.NER_LON_MIN <= lon <= cls.NER_LON_MAX):
                        continue

                ner_matched += 1

                # Parse date
                parsed_date: Optional[date] = None
                parsed_ts: Optional[datetime] = None
                time_precision = TimePrecision.DATE_ONLY

                # NASA date formats: e.g. "08/14/2015 12:00:00 AM", "2015-08-14"
                for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(str(date_str).strip()[:22], fmt)
                        parsed_date = dt.date()
                        parsed_ts = dt.replace(tzinfo=timezone.utc)
                        if " " in date_str and (":" in date_str):
                            time_precision = TimePrecision.HOUR
                        break
                    except ValueError:
                        continue

                if not parsed_date:
                    skipped += 1
                    continue

                ext_id = row.get("event_id") or f"NASA-{lat:.4f}-{lon:.4f}-{parsed_date.isoformat()}"
                state_val = row.get("admin_division_name") or row.get("state") or "North Eastern Region"
                district_val = row.get("gazeteer_closest_point") or row.get("district") or "NER Sector"
                loc_name = row.get("event_title") or row.get("location_description") or f"NER Landslide ({lat:.2f}, {lon:.2f})"
                slide_cat = row.get("landslide_category") or "Landslide"
                trigger_val = row.get("landslide_trigger") or "Rain"

                event = LandslideEvent(
                    source="NASA_GLC",
                    external_id=str(ext_id).strip(),
                    latitude=lat,
                    longitude=lon,
                    state=str(state_val).strip()[:64],
                    district=str(district_val).strip()[:64],
                    location_name=str(loc_name).strip()[:256],
                    occurrence_timestamp=parsed_ts,
                    occurrence_date=parsed_date,
                    time_precision=time_precision,
                    landslide_type=str(slide_cat).upper(),
                    trigger=str(trigger_val).upper(),
                    verification_status="REPORTED_MEDIA",
                    source_confidence=0.85,
                    original_source="NASA Global Landslide Catalog",
                    source_metadata={
                        "raw_id": ext_id,
                        "location_accuracy": row.get("location_accuracy"),
                        "fatalities": row.get("fatality_count"),
                        "landslide_size": row.get("landslide_size"),
                    },
                    dataset_version=dataset_version,
                )
                records.append(event)

        inserted_count = 0
        if records:
            ext_ids = [e.external_id for e in records]
            stmt = select(LandslideEvent.external_id).where(
                LandslideEvent.source == "NASA_GLC",
                LandslideEvent.external_id.in_(ext_ids)
            )
            existing_res = await session.execute(stmt)
            existing_ids = set(existing_res.scalars().all())

            for ev in records:
                if ev.external_id not in existing_ids:
                    session.add(ev)
                    existing_ids.add(ev.external_id)
                    inserted_count += 1

            await session.commit()

        logger.info(
            f"NASA GLC Import: Parsed {total_rows} global records, "
            f"found {ner_matched} in NER bounding box, inserted +{inserted_count} new events."
        )

        return {
            "total_rows_parsed": total_rows,
            "ner_candidates_matched": ner_matched,
            "inserted": inserted_count,
            "already_existing": ner_matched - inserted_count,
        }
