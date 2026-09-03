import pytest
from datetime import datetime, timezone
import pandas as pd
from backend.app.ml.synthetic.generator import SyntheticLandslideDatasetGenerator


def test_synthetic_generator_reproducibility():
    """Verifies that the same seed produces identical dataset rows and labels."""
    gen1 = SyntheticLandslideDatasetGenerator(random_seed=123)
    df1, manifest1 = gen1.generate_dataset(num_samples=100)

    gen2 = SyntheticLandslideDatasetGenerator(random_seed=123)
    df2, manifest2 = gen2.generate_dataset(num_samples=100)

    assert len(df1) == 100
    assert len(df2) == 100
    assert manifest1["positive_count"] == manifest2["positive_count"]
    pd.testing.assert_series_equal(df1["landslide_within_24h"], df2["landslide_within_24h"])


def test_synthetic_generator_provenance_and_schema():
    """Verifies all required provenance columns and target horizons exist."""
    gen = SyntheticLandslideDatasetGenerator(random_seed=42)
    df, manifest = gen.generate_dataset(num_samples=50)

    required_cols = [
        "landslide_within_24h",
        "landslide_within_12h",
        "landslide_within_6h",
        "dataset_source",
        "is_synthetic",
        "scenario_id",
        "scenario_type",
        "location_id",
        "timestamp",
        "generator_version",
        "seed",
        "slope_angle",
        "rainfall_24h",
        "soil_moisture_surface",
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column {col}"

    assert (df["dataset_source"] == "SYNTHETIC").all()
    assert (df["is_synthetic"] == True).all()
    assert manifest["is_synthetic"] is True


def test_hard_negatives_low_slope():
    """Verifies that flat terrain (< 18 deg) never triggers a landslide, even in heavy rain."""
    gen = SyntheticLandslideDatasetGenerator(random_seed=999)
    # Filter station profiles to low slope
    flat_station = {"id": "TEST-FLAT", "name": "Flat Basin", "state": "Assam", "lat": 26.0, "lon": 91.0, "elev": 50.0, "slope": 10.0, "susc": 0.1}

    # Generate 20 heavy rain scenarios on flat station
    for _ in range(20):
        obs, slide, _ = gen._generate_scenario_timeseries(
            station=flat_station,
            scenario="heavy_rain_low_slope",
            start_time=datetime.now(timezone.utc),
            num_hours=48
        )
        assert slide is False, "Hard negative violated: flat terrain must not fail under rain"
