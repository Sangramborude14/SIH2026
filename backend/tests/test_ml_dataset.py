import pytest
from datetime import date
from pathlib import Path
import pandas as pd

from backend.app.ml.dataset.schemas import LandslideInventoryRecord, NegativeSamplingConfig
from backend.app.ml.dataset.inventory_loader import LandslideInventoryLoader
from backend.app.ml.dataset.negative_sampler import ScientificNegativeSampler
from backend.app.ml.dataset.splitter import LandslideDatasetSplitter


def test_inventory_record_validation():
    # Valid record
    rec = LandslideInventoryRecord(
        event_id="GSI-NER-2022-001",
        latitude=27.3389,
        longitude=88.6065,
        event_date="2022-06-18",
        state="Sikkim",
        district="East Sikkim",
        confidence="CONFIRMED",
    )
    assert rec.event_date == date(2022, 6, 18)
    assert rec.latitude == 27.3389

    # Out-of-bounds latitude should fail validation
    with pytest.raises(Exception):
        LandslideInventoryRecord(
            event_id="GSI-INVALID-001",
            latitude=12.5,  # South India, outside NER
            longitude=88.6,
            event_date="2022-06-18",
            state="Kerala",
            district="Wayanad",
        )


def test_inventory_loader_csv():
    fixture_path = Path("backend/tests/fixtures/ml/fixture_inventory.csv")
    records, summary = LandslideInventoryLoader.load_from_file(fixture_path)
    assert len(records) >= 6
    assert summary["total_rows_read"] >= 6
    assert summary["valid_records_count"] >= 6
    assert summary["rejected_records_count"] == 0
    assert "Sikkim" in summary["unique_states"]


def test_scientific_negative_sampling():
    fixture_inv = Path("backend/tests/fixtures/ml/fixture_inventory.csv")
    fixture_telem = Path("backend/tests/fixtures/ml/fixture_telemetry.csv")

    positives, _ = LandslideInventoryLoader.load_from_file(fixture_inv)
    telem_df = pd.read_csv(fixture_telem)
    telem_df["date"] = pd.to_datetime(telem_df["date"]).dt.date
    telem_records = telem_df.to_dict(orient="records")

    cfg = NegativeSamplingConfig(
        negative_to_positive_ratio=2.0,
        hard_negative_pct=0.50,
        temporal_buffer_days=2,
        min_rainfall_hard_negative_mm=10.0,
        random_seed=42,
    )
    sampler = ScientificNegativeSampler(cfg)
    negatives, stats = sampler.sample_negatives(positives, telem_records)

    assert len(negatives) > 0
    assert all(n["label"] == 0 for n in negatives)
    assert stats["actual_negatives_sampled"] == len(negatives)
    assert stats["hard_negatives_count"] >= 0


def test_temporal_split_zero_leakage():
    data = [
        {"date": date(2020, 1, 1), "val": 1},
        {"date": date(2020, 6, 1), "val": 2},
        {"date": date(2021, 1, 1), "val": 3},
        {"date": date(2021, 6, 1), "val": 4},
        {"date": date(2022, 1, 1), "val": 5},
        {"date": date(2022, 6, 1), "val": 6},
        {"date": date(2023, 1, 1), "val": 7},
        {"date": date(2023, 6, 1), "val": 8},
        {"date": date(2024, 1, 1), "val": 9},
        {"date": date(2024, 6, 1), "val": 10},
    ]
    df = pd.DataFrame(data)

    train_df, val_df, test_df = LandslideDatasetSplitter.temporal_split(
        df=df,
        date_column="date",
        test_ratio=0.20,
        val_ratio=0.20,
    )

    # Train date strictly before Val date strictly before Test date
    assert train_df["date"].max() < val_df["date"].min()
    assert val_df["date"].max() < test_df["date"].min()

    # Verify leakage checker passes
    LandslideDatasetSplitter.verify_temporal_leakage_absence(train_df, val_df, test_df, "date")

    # Deliberate leakage test
    leaky_train = df[df["date"] >= date(2023, 1, 1)]
    with pytest.raises(ValueError, match="Temporal leakage detected"):
        LandslideDatasetSplitter.verify_temporal_leakage_absence(leaky_train, val_df, test_df, "date")


def test_spatial_group_split_disjoint():
    data = [
        {"location_id": "STA-A", "val": 1},
        {"location_id": "STA-A", "val": 2},
        {"location_id": "STA-B", "val": 3},
        {"location_id": "STA-C", "val": 4},
        {"location_id": "STA-D", "val": 5},
        {"location_id": "STA-E", "val": 6},
    ]
    df = pd.DataFrame(data)

    train_df, val_df, test_df = LandslideDatasetSplitter.spatial_group_split(
        df=df,
        group_column="location_id",
        test_group_ratio=0.33,
        val_group_ratio=0.33,
        random_seed=42,
    )

    train_groups = set(train_df["location_id"].unique())
    val_groups = set(val_df["location_id"].unique())
    test_groups = set(test_df["location_id"].unique())

    assert len(train_groups.intersection(val_groups)) == 0
    assert len(train_groups.intersection(test_groups)) == 0
    assert len(val_groups.intersection(test_groups)) == 0
