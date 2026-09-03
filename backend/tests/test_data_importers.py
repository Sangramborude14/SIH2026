import csv
import pytest
from pathlib import Path
from backend.app.ml.dataset.gsi_importer import GSILandslideImporter
from backend.app.ml.dataset.nasa_glc_importer import NASAGLCLandslideImporter
from backend.app.models.landslide_event import LandslideEvent


@pytest.mark.asyncio
async def test_gsi_importer_csv(db_session, tmp_path):
    """Tests GSI CSV parsing, schema normalization, and deduplication."""
    csv_file = tmp_path / "gsi_mock.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["SLIDE_ID", "LATITUDE", "LONGITUDE", "OCCURRENCE_DATE", "STATE_NAME", "DISTRICT_NAME", "LANDSLIDE_TYPE"])
        writer.writerow(["GSI-NER-001", "27.33", "88.60", "2024-07-15", "Sikkim", "East Sikkim", "Debris Flow"])
        writer.writerow(["GSI-NER-002", "25.27", "91.73", "2024-08-01", "Meghalaya", "East Khasi Hills", "Rockfall"])

    # First import
    res1 = await GSILandslideImporter.import_from_csv(db_session, csv_file)
    assert res1["inserted"] == 2
    assert res1["duplicates"] == 0

    # Second import should deduplicate idempotently
    res2 = await GSILandslideImporter.import_from_csv(db_session, csv_file)
    assert res2["inserted"] == 0
    assert res2["duplicates"] == 2


@pytest.mark.asyncio
async def test_nasa_glc_importer_filtering(db_session, tmp_path):
    """Tests NASA GLC parsing and geographical NER bounding box filtering."""
    csv_file = tmp_path / "nasa_mock.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "latitude", "longitude", "event_date", "country_name", "admin_division_name", "landslide_category"])
        # Inside NER: lat ~27, lon ~88
        writer.writerow(["NASA-001", "27.35", "88.62", "07/12/2016 12:00:00 AM", "India", "Sikkim", "mudslide"])
        # Outside NER (e.g. USA): lat ~45, lon ~-120
        writer.writerow(["NASA-002", "45.10", "-120.50", "08/15/2016 12:00:00 AM", "United States", "Oregon", "rock_fall"])

    res = await NASAGLCLandslideImporter.import_to_database(db_session, csv_file, filter_ner_only=True)
    assert res["total_rows_parsed"] == 2
    assert res["ner_candidates_matched"] == 1
    assert res["inserted"] == 1
