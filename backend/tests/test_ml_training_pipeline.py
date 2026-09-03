import json
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pytest

from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.ml.features.pipeline import LandslideFeaturePipeline, IncompatibleFeatureSchemaError
from backend.app.ml.features.feature_extractor import feature_extractor
from backend.app.ml.anomaly.isolation_forest import IsolationForestAnomalyDetector
from backend.app.ml.evaluation.evaluator import LandslideModelEvaluator
from backend.app.ml.prediction.calibrator import LandslideProbabilityCalibrator
from backend.app.ml.training.train import run_training_pipeline
from backend.app.ml.registry.model_registry import LandslideModelRegistry
from backend.app.ml.types import ForecastHorizon


def test_feature_pipeline_schema_validation():
    pipe = LandslideFeaturePipeline()

    # Valid feature dictionary with all features
    valid_features = {spec["name"]: spec["default"] for spec in pipe.FEATURE_SCHEMA}
    valid_features["slope_angle"] = 42.0
    valid_features["rainfall_24h"] = 120.0

    cleaned = pipe.validate_features_dict(valid_features)
    assert cleaned["slope_angle"] == 42.0
    assert cleaned["rainfall_24h"] == 120.0

    # Incompatible dictionary missing required variables without fallback
    incomplete = {"slope_angle": 30.0}
    with pytest.raises(IncompatibleFeatureSchemaError):
        pipe.validate_features_dict(incomplete, allow_missing_with_default=False)

    # Allow missing with default fills defaults
    filled = pipe.validate_features_dict(incomplete, allow_missing_with_default=True)
    assert filled["rainfall_24h"] == 0.0


def test_isolation_forest_anomaly_detector():
    detector = IsolationForestAnomalyDetector(contamination=0.10, random_state=42)

    # Baseline normal data (15 rows of moderate rain)
    X_normal = np.random.uniform(low=0.0, high=20.0, size=(30, len(detector.ANOMALY_FEATURE_NAMES)))
    detector.fit(X_normal)
    assert detector.is_fitted is True

    # Test normal observation vector
    now = datetime.now(timezone.utc)
    loc = Location(
        id="NER-SIK-GANGTOK-01",
        name="Gangtok Ridge",
        state="Sikkim",
        district="East Sikkim",
        elevation=1650.0,
        slope_angle=38.5,
        susceptibility_score=0.85,
    )
    normal_obs = WeatherObservation(
        location_id=loc.id,
        timestamp=now,
        rainfall_1h=2.0,
        rainfall_24h=15.0,
        soil_moisture=40.0,
    )
    vector = feature_extractor.extract_features(loc, normal_obs, [normal_obs])
    out = detector.detect_anomaly(vector)

    assert 0.0 <= out.anomaly_score <= 1.0
    assert hasattr(out, "anomaly_level")
    assert hasattr(out, "is_statistically_anomalous")


def test_evaluator_threshold_sweep():
    y_true = np.array([1, 1, 1, 0, 0, 0, 0, 0])
    y_probs = np.array([0.9, 0.8, 0.4, 0.3, 0.2, 0.1, 0.05, 0.25])

    res = LandslideModelEvaluator.evaluate_model(y_true, y_probs, selected_threshold=0.50)
    assert res["total_samples"] == 8
    assert res["positive_events"] == 3
    assert res["roc_auc"] > 0.70
    assert res["pr_auc"] > 0.50
    assert len(res["threshold_sweep"]) == 5


def test_end_to_end_training_and_inference_integration(tmp_path):
    inv_file = Path("backend/tests/fixtures/ml/fixture_inventory.csv")
    telem_file = Path("backend/tests/fixtures/ml/fixture_telemetry.csv")
    out_dir = tmp_path / "model_out"

    metadata = run_training_pipeline(
        inventory_path=str(inv_file),
        telemetry_path=str(telem_file),
        output_dir=str(out_dir),
        horizon="24h",
        random_seed=42,
        dry_run=False,
    )

    assert (out_dir / "model.joblib").exists()
    assert (out_dir / "pipeline.joblib").exists()
    assert (out_dir / "metadata.json").exists()
    assert (out_dir / "metrics.json").exists()
    assert (out_dir / "feature_schema.json").exists()

    assert metadata["model_version"] == "2.0.0"
    assert metadata["training_samples_count"] > 0

    # Test loading artifacts into ModelRegistry pointing to tmp_path
    registry = LandslideModelRegistry()
    registry.ARTIFACTS_DIR = out_dir
    success = registry.reload_artifacts()
    assert success is True
    assert registry.is_trained_model_active() is True

    active_predictor = registry.get_active_predictor()
    assert active_predictor is not None

    # Perform real-time inference using the active trained predictor
    now = datetime.now(timezone.utc)
    loc = Location(
        id="NER-SIK-GANGTOK-01",
        name="Gangtok Ridge",
        state="Sikkim",
        district="East Sikkim",
        elevation=1650.0,
        slope_angle=38.5,
        susceptibility_score=0.85,
    )
    obs = WeatherObservation(
        location_id=loc.id,
        timestamp=now,
        rainfall_1h=25.0,
        rainfall_6h=65.0,
        rainfall_24h=140.0,
        soil_moisture=88.0,
    )
    vector = feature_extractor.extract_features(loc, obs, [obs])

    pred_output = active_predictor.predict(vector)
    assert pred_output.is_trained_ml_model is True
    assert pred_output.location_id == loc.id
    assert len(pred_output.horizons) >= 1
    assert len(pred_output.primary_contributing_features) > 0
    assert ForecastHorizon.HORIZON_24H in pred_output.horizons
    p24 = pred_output.horizons[ForecastHorizon.HORIZON_24H].probability
    assert 0.0 <= p24 <= 1.0

