import pytest
from datetime import datetime, timezone

from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.engine.base import TerrainProfile
from backend.app.ml.types import (
    DataProvenance,
    ForecastHorizon,
    AnomalyLevel,
    ModelTier,
)
from backend.app.ml.features.feature_extractor import feature_extractor
from backend.app.ml.anomaly.statistical import statistical_anomaly_detector
from backend.app.ml.prediction.baseline import deterministic_baseline_predictor
from backend.app.ml.registry.model_registry import model_registry
from backend.app.ml.evaluation.metrics import (
    compute_confusion_matrix,
    compute_brier_score,
    compute_roc_auc,
    compute_classification_metrics,
    compute_lead_time_distribution,
)


def test_feature_extraction_provenance():
    now = datetime.now(timezone.utc)
    loc = Location(
        id="NER-SIK-GANGTOK-01",
        name="Gangtok Ridge Sector",
        state="Sikkim",
        district="East Sikkim",
        latitude=27.3389,
        longitude=88.6065,
        elevation=1650.0,
        slope_angle=38.5,
        susceptibility_score=0.85,
    )
    obs = WeatherObservation(
        location_id=loc.id,
        timestamp=now,
        rainfall_1h=18.5,
        rainfall_6h=45.0,
        rainfall_24h=95.0,
        soil_moisture=72.0,
        source="TEST_SUITE",
    )
    history = [obs]

    vector = feature_extractor.extract_features(loc, obs, history, data_mode="LIVE")

    # Verify all 15 features are present
    flat = vector.to_flat_dict()
    assert len(flat) == 15
    assert flat["slope_angle"] == 38.5
    assert flat["elevation"] == 1650.0
    assert flat["rainfall_1h"] == 18.5
    assert flat["rainfall_24h"] == 95.0
    assert flat["soil_moisture_surface"] > 0.0

    # Verify provenance tagging is complete and explicit
    prov_summary = vector.get_provenance_summary()
    assert sum(prov_summary.values()) == 15
    assert DataProvenance.STATIC.value in prov_summary
    assert DataProvenance.OBSERVED.value in prov_summary
    assert DataProvenance.MODEL_DERIVED.value in prov_summary

    # When in simulation mode, provenance reflects simulation
    sim_vector = feature_extractor.extract_features(loc, obs, history, data_mode="SIMULATION")
    sim_summary = sim_vector.get_provenance_summary()
    assert sim_summary.get(DataProvenance.SIMULATED.value) == 15


def test_task_a_environmental_anomaly_separation():
    now = datetime.now(timezone.utc)
    loc = Location(
        id="NER-ASM-HAFLONG-01",
        name="Haflong Hill",
        state="Assam",
        district="Dima Hasao",
        elevation=850.0,
        slope_angle=34.0,
        susceptibility_score=0.80,
    )
    obs = WeatherObservation(
        location_id=loc.id,
        timestamp=now,
        rainfall_1h=32.0,      # extreme burst
        rainfall_24h=140.0,    # extreme cumulative
        soil_moisture=84.0,    # severe saturation
        source="TEST_SUITE",
    )
    # Provide normal baseline history so 140mm produces strong z-score departure
    history = [
        WeatherObservation(location_id=loc.id, timestamp=now, rainfall_1h=1.0, rainfall_24h=12.0, soil_moisture=42.0),
        WeatherObservation(location_id=loc.id, timestamp=now, rainfall_1h=0.5, rainfall_24h=10.0, soil_moisture=43.0),
        WeatherObservation(location_id=loc.id, timestamp=now, rainfall_1h=0.0, rainfall_24h=8.0, soil_moisture=41.0),
        WeatherObservation(location_id=loc.id, timestamp=now, rainfall_1h=1.5, rainfall_24h=15.0, soil_moisture=44.0),
        WeatherObservation(location_id=loc.id, timestamp=now, rainfall_1h=2.0, rainfall_24h=14.0, soil_moisture=45.0),
        obs,
    ]
    vector = feature_extractor.extract_features(loc, obs, history)

    anomaly_out = statistical_anomaly_detector.detect_anomaly(vector)

    assert 0.0 <= anomaly_out.anomaly_score <= 1.0
    assert anomaly_out.anomaly_level in [AnomalyLevel.SEVERE, AnomalyLevel.EXTREME]
    assert anomaly_out.rainfall_anomaly_score > 0.50
    assert anomaly_out.soil_wetness_anomaly_score > 0.50
    assert len(anomaly_out.primary_abnormal_factors) >= 1
    # Verify task contract: anomaly score is not a landslide probability
    assert hasattr(anomaly_out, "anomaly_score")
    assert not hasattr(anomaly_out, "landslide_probability")



def test_task_b_landslide_prediction_horizons():
    now = datetime.now(timezone.utc)
    loc = Location(
        id="NER-MIZ-AIZAWL-01",
        name="Aizawl Central Ridge",
        state="Mizoram",
        district="Aizawl",
        elevation=1132.0,
        slope_angle=42.0,
        susceptibility_score=0.90,
    )
    obs = WeatherObservation(
        location_id=loc.id,
        timestamp=now,
        rainfall_1h=12.0,
        rainfall_24h=80.0,
        soil_moisture=68.0,
        source="TEST_SUITE",
    )
    vector = feature_extractor.extract_features(loc, obs, [obs])

    pred = deterministic_baseline_predictor.predict(vector)

    assert pred.is_trained_ml_model is False
    assert pred.model_tier == ModelTier.BASELINE_DETERMINISTIC
    assert "disclaimer" in pred.model_dump()
    assert "uncalibrated deterministic baseline" in pred.disclaimer

    # Verify all 3 forecast horizons are present
    assert ForecastHorizon.HORIZON_6H in pred.horizons
    assert ForecastHorizon.HORIZON_12H in pred.horizons
    assert ForecastHorizon.HORIZON_24H in pred.horizons

    for h in [ForecastHorizon.HORIZON_6H, ForecastHorizon.HORIZON_12H, ForecastHorizon.HORIZON_24H]:
        hp = pred.horizons[h]
        assert 0.0 <= hp.probability <= 1.0
        assert hp.confidence_interval_low <= hp.probability <= hp.confidence_interval_high
        assert hp.risk_tier in ["LOW", "MODERATE", "HIGH", "CRITICAL"]


def test_model_registry_status():
    status = model_registry.get_registry_status()
    assert status["registry_version"] == "1.0.0"
    assert status["active_model_tier"] in [
        ModelTier.BASELINE_DETERMINISTIC.value,
        ModelTier.TABULAR_ML_LOGISTIC.value,
        ModelTier.TABULAR_ML_RANDOM_FOREST.value,
        ModelTier.TABULAR_ML_GRADIENT_BOOST.value,
    ]
    assert status["feature_count"] >= 15

    assert len(status["registered_models"]) >= 1
    assert status["operational_status"] in ["READY", "READY_BASELINE_OPERATIONAL", "NOT_TRAINED"]


    pred = model_registry.get_active_predictor()
    assert pred is not None
    det = model_registry.get_active_anomaly_detector()
    assert det is not None


def test_authentic_evaluation_metrics():
    # 1. Perfect Classification Test
    y_true = [1, 1, 1, 0, 0, 0]
    y_probs = [0.95, 0.88, 0.76, 0.12, 0.05, 0.22]

    metrics = compute_classification_metrics(y_true, y_probs, threshold=0.5)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["accuracy"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["brier_score"] < 0.05

    cm = metrics["confusion_matrix"]
    assert cm["true_positives"] == 3
    assert cm["true_negatives"] == 3
    assert cm["false_positives"] == 0
    assert cm["false_negatives"] == 0

    # 2. Inverted Ranking Test (AUC should be 0.0)
    y_true_inv = [1, 1, 0, 0]
    y_probs_inv = [0.1, 0.2, 0.8, 0.9]
    auc_inv = compute_roc_auc(y_true_inv, y_probs_inv)
    assert auc_inv == 0.0

    # 3. Lead Time Distribution Test
    lead_times = [6.5, 12.0, 18.5, 22.0, 26.0]
    lt_dist = compute_lead_time_distribution(lead_times)
    assert lt_dist["mean_lead_time_hours"] == 17.0
    assert lt_dist["min_lead_time_hours"] == 6.5
    assert lt_dist["max_lead_time_hours"] == 26.0
    assert lt_dist["hist_bins"]["6-12h"] == 1
    assert lt_dist["hist_bins"]["12-18h"] == 1
    assert lt_dist["hist_bins"]["18-24h"] == 2
    assert lt_dist["hist_bins"][">24h"] == 1



@pytest.mark.asyncio
async def test_ml_api_endpoints(client, db_session):
    # 1. Status endpoint
    status_resp = await client.get("/api/v1/ml/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["active_model_tier"] in [
        "BASELINE_DETERMINISTIC",
        "TABULAR_ML_LOGISTIC",
        "TABULAR_ML_RANDOM_FOREST",
        "TABULAR_ML_GRADIENT_BOOST",
    ]
    assert status_data["feature_count"] >= 15


    # 2. Features endpoint for seeded station
    loc_id = "NER-SIK-GANGTOK-01"
    feat_resp = await client.get(f"/api/v1/ml/features/{loc_id}")
    assert feat_resp.status_code == 200
    feat_data = feat_resp.json()
    assert feat_data["location_id"] == loc_id
    assert "features" in feat_data
    assert "slope_angle" in feat_data["features"]
    assert feat_data["features"]["slope_angle"]["provenance"] in ["STATIC", "SIMULATED"]

    # 3. Anomaly endpoint (Task A)
    anomaly_resp = await client.post(f"/api/v1/ml/anomaly/{loc_id}")
    assert anomaly_resp.status_code == 200
    anomaly_data = anomaly_resp.json()
    assert 0.0 <= anomaly_data["anomaly_score"] <= 1.0
    assert anomaly_data["anomaly_level"] in ["NORMAL", "ELEVATED", "SEVERE", "EXTREME"]

    # 4. Predict endpoint (Task B)
    pred_resp = await client.post(f"/api/v1/ml/predict/{loc_id}")
    assert pred_resp.status_code == 200
    pred_data = pred_resp.json()
    assert pred_data["location_id"] == loc_id
    assert ("6H" in pred_data["horizons"]) or ("24H" in pred_data["horizons"])
    if "12H" in pred_data["horizons"]:
        assert 0.0 <= pred_data["horizons"]["12H"]["probability"] <= 1.0
    elif "24H" in pred_data["horizons"]:
        assert 0.0 <= pred_data["horizons"]["24H"]["probability"] <= 1.0
    assert "disclaimer" in pred_data

