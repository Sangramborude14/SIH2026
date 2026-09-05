import pytest
import math
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.models.weather_forecast import WeatherForecastSnapshot
from backend.app.engine.climatology import climatology_service, RainfallClimatologyService
from backend.app.ml.susceptibility import (
    static_susceptibility_model,
    StaticSusceptibilityModel,
    StaticGeospatialFactors,
    SusceptibilityStatus,
)
from backend.app.ml.types import (
    TemporalLeakageError,
    ForecastHorizon,
    ModelTier,
)
from backend.app.ml.features.pipeline_v2 import (
    ResearchFeaturePipelineV2,
    RESEARCH_FEATURE_NAMES,
    RESEARCH_FEATURE_SCHEMA_VERSION,
)
from backend.app.ml.features.pipeline import (
    LandslideFeaturePipeline,
    FEATURE_NAMES,
)
from backend.app.ml.features.feature_extractor import feature_extractor
from backend.app.ml.explainability.shap_explainer import shap_explainer, LandslideShapExplainer
from backend.app.ml.evaluation.sensitivity import LandslideSensitivityAnalyzer
from backend.app.schemas.ml_forecast import (
    LocationForecastResponse,
    MultiLocationForecastResponse,
    ForecastHorizonDetail,
    CurrentConditionSummary,
    EnvironmentalAnomalySummary,
)
from backend.app.services.landslide_inference_service import landslide_inference_service


# ---------------------------------------------------------------------
# 1. Climatology Normalized Rainfall Tests (Stanley et al. 2021)
# ---------------------------------------------------------------------
def test_rainfall_climatology_percentiles_and_ratios():
    loc_id = "NER-SIK-GANGTOK-01"
    clim = climatology_service.get_station_climatology(loc_id)
    assert clim.p99_24h > 0.0
    assert clim.p95_24h > 0.0
    assert clim.p99_24h >= clim.p95_24h >= clim.p90_24h

    # Test exact ratio calculations
    ratio_99, is_avail_99 = climatology_service.calculate_p99_ratio(clim.p99_24h, loc_id)
    assert is_avail_99 is True
    assert ratio_99 == pytest.approx(1.0, abs=1e-3)

    ratio_95, is_avail_95 = climatology_service.calculate_p95_ratio(clim.p95_24h * 0.5, loc_id)
    assert is_avail_95 is True
    assert ratio_95 == pytest.approx(0.5, abs=1e-3)

    # Test forecast ratio
    fc_ratio, _ = climatology_service.calculate_forecast_p99_ratio(clim.p99_24h * 1.5, loc_id)
    assert fc_ratio == pytest.approx(1.5, abs=1e-3)

    # Dynamic observation-based climatology calculation
    service = RainfallClimatologyService()
    observations = [float(x) for x in range(1, 101)]
    computed_clim = service.compute_percentiles_from_observations(
        location_id="DYNAMIC-LOC",
        station_name="Dynamic Station",
        daily_rainfall_samples=observations,
        min_samples=50,
    )
    assert computed_clim is not None
    assert computed_clim.p90_24h < computed_clim.p95_24h < computed_clim.p99_24h
    assert computed_clim.p99_24h == pytest.approx(np.percentile(observations, 99), abs=1e-2)


# ---------------------------------------------------------------------
# 2. Strict Temporal Leakage Rejection Tests (Khan et al. 2022)
# ---------------------------------------------------------------------
def test_temporal_leakage_observation_future():
    t_pred = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    future_obs_time = t_pred + timedelta(minutes=15)

    loc = Location(id="TEST-LOC-01", name="Test Station", slope_angle=35.0, elevation=1200.0)
    obs_future = WeatherObservation(location_id=loc.id, timestamp=future_obs_time, rainfall_24h=50.0)

    # Must raise TemporalLeakageError when an observation timestamp exceeds prediction timestamp
    with pytest.raises(TemporalLeakageError) as excinfo:
        feature_extractor.extract_features_v2(
            location=loc,
            current_obs=obs_future,
            prediction_time=t_pred,
        )
    assert "Temporal leakage violation" in str(excinfo.value)


def test_temporal_leakage_forecast_issue_time_future():
    t_pred = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    loc = Location(id="TEST-LOC-01", name="Test Station", slope_angle=35.0, elevation=1200.0)
    obs_valid = WeatherObservation(location_id=loc.id, timestamp=t_pred, rainfall_24h=20.0)

    # Forecast snapshot issued into the future of prediction time
    fc_future_issue = WeatherForecastSnapshot(
        location_id=loc.id,
        forecast_issued_at=t_pred + timedelta(minutes=30),  # LEAKAGE!
        forecast_valid_at=t_pred + timedelta(hours=24),
        forecast_horizon_hours=24,
        precipitation_mm=45.0,
    )

    with pytest.raises(TemporalLeakageError) as excinfo:
        feature_extractor.extract_features_v2(
            location=loc,
            current_obs=obs_valid,
            forecast_snapshot=fc_future_issue,
            prediction_time=t_pred,
        )
    assert "Forecast issue leakage" in str(excinfo.value)


def test_temporal_leakage_forecast_validity_in_past():
    t_pred = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    loc = Location(id="TEST-LOC-01", name="Test Station", slope_angle=35.0, elevation=1200.0)
    obs_valid = WeatherObservation(location_id=loc.id, timestamp=t_pred, rainfall_24h=20.0)

    # Forecast snapshot whose validity window has already passed
    fc_past_valid = WeatherForecastSnapshot(
        location_id=loc.id,
        forecast_issued_at=t_pred - timedelta(hours=12),
        forecast_valid_at=t_pred - timedelta(hours=2),  # In the past!
        forecast_horizon_hours=24,
        precipitation_mm=45.0,
    )

    with pytest.raises(TemporalLeakageError) as excinfo:
        feature_extractor.extract_features_v2(
            location=loc,
            current_obs=obs_valid,
            forecast_snapshot=fc_past_valid,
            prediction_time=t_pred,
        )
    assert "Forecast validity violation" in str(excinfo.value)


def test_extract_features_v2_success_valid_temporal_bounds():
    t_pred = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    loc = Location(
        id="NER-SIK-GANGTOK-01",
        name="Gangtok",
        slope_angle=38.0,
        elevation=1650.0,
        susceptibility_score=0.75,
    )
    obs_valid = WeatherObservation(
        location_id=loc.id,
        timestamp=t_pred,
        rainfall_1h=15.0,
        rainfall_24h=80.0,
        soil_moisture=70.0,
    )
    fc_valid = WeatherForecastSnapshot(
        location_id=loc.id,
        forecast_issued_at=t_pred - timedelta(hours=1),
        forecast_valid_at=t_pred + timedelta(hours=23),
        forecast_horizon_hours=24,
        precipitation_mm=55.0,
    )

    feat_res = feature_extractor.extract_features_v2(
        location=loc,
        current_obs=obs_valid,
        forecast_snapshot=fc_valid,
        prediction_time=t_pred,
    )

    features = feat_res["features"]
    assert len(features) == 29
    assert "current_rainfall_p99_ratio" in features
    assert "forecast_rainfall_p99_ratio" in features
    assert "soil_moisture_delta_6h" in features
    assert "soil_moisture_delta_24h" in features
    assert "susceptibility_prior" in features
    assert features["forecast_precipitation_24h"] == 55.0


# ---------------------------------------------------------------------
# 3. Static Geotechnical Susceptibility Tests (Mihu et al. 2026)
# ---------------------------------------------------------------------
def test_static_susceptibility_model_non_fabrication():
    loc = Location(
        id="NER-ASM-GUWAHATI-01",
        name="Guwahati Hills",
        slope_angle=28.0,
        elevation=150.0,
        susceptibility_score=0.45,
    )
    # Evaluate station with only terrain topography available
    eval_res = static_susceptibility_model.evaluate_station(loc)

    assert 0.0 <= eval_res.susceptibility_score <= 1.0
    assert eval_res.status == SusceptibilityStatus.DETERMINISTIC_PHYSICS_FALLBACK
    assert "lithology_strength" in eval_res.features_missing
    assert "lineament_density_km_km2" in eval_res.features_missing
    assert "distance_to_active_fault_km" in eval_res.features_missing
    assert "slope_angle" in eval_res.features_available
    assert "elevation" in eval_res.features_available
    assert "Zero synthetic data fabrication" in eval_res.disclaimer


# ---------------------------------------------------------------------
# 4. Feature Pipeline v2 & Monotonicity Constraints Spec
# ---------------------------------------------------------------------
def test_pipeline_v2_spec_and_monotonic_constraints():
    pipeline = ResearchFeaturePipelineV2()
    assert len(pipeline.FEATURE_NAMES) == 29
    assert pipeline.SCHEMA_VERSION == "2.0.0-research"

    constraints = pipeline.get_monotonic_constraints_tuple()
    assert len(constraints) == 29

    # Trigger and steep topography features must have positive constraint (+1)
    slope_idx = pipeline.FEATURE_NAMES.index("slope_angle")
    r24_idx = pipeline.FEATURE_NAMES.index("current_rainfall_p99_ratio")
    fc_idx = pipeline.FEATURE_NAMES.index("forecast_rainfall_p99_ratio")
    road_idx = pipeline.FEATURE_NAMES.index("distance_to_road")

    assert constraints[slope_idx] == 1
    assert constraints[r24_idx] == 1
    assert constraints[fc_idx] == 1
    # Distance to road / fault stabilizes slope when larger, so constraint must be negative (-1)
    assert constraints[road_idx] == -1


# ---------------------------------------------------------------------
# 5. TreeSHAP Attribution Tests
# ---------------------------------------------------------------------
def test_treeshap_explainer_structure():
    explainer = LandslideShapExplainer()
    feature_names = RESEARCH_FEATURE_NAMES[:5]
    X_sample = np.array([[35.0, 1500.0, 0.5, 0.5, 80.0]])

    class DummyModel:
        def predict_proba(self, X):
            return np.array([[0.2, 0.8]])

    # Should safely fallback to permutation/heuristic attributions without crashing
    attributions = explainer.explain_instance(
        model=DummyModel(),
        X_arr=X_sample,
        feature_names=feature_names,
        top_k=3,
    )
    assert len(attributions) <= 3
    for attr in attributions:
        assert "feature" in attr
        assert "importance_score" in attr
        assert "method" in attr


# ---------------------------------------------------------------------
# 6. Physical Sensitivity Analyzer Tests
# ---------------------------------------------------------------------
def test_sensitivity_analyzer_checks():
    analyzer = LandslideSensitivityAnalyzer(
        feature_names=RESEARCH_FEATURE_NAMES,
        schema_version="2.0.0-research",
    )

    class MonotonicMockModel:
        def predict_proba(self, X):
            # Monotonically non-decreasing with rainfall
            # X shape is (N, 29)
            probs = np.full(X.shape[0], 0.25)
            return np.column_stack([1.0 - probs, probs])

    results = analyzer.run_all_checks(MonotonicMockModel())
    assert "checks" in results
    assert "rainfall_monotonicity" in results["checks"]
    assert "low_slope_invariant" in results["checks"]
    assert results["checks"]["low_slope_invariant"]["passed"] is True


# ---------------------------------------------------------------------
# 7. Backward Compatibility: v1 Feature Pipeline & Predictor
# ---------------------------------------------------------------------
def test_backward_compatibility_v1_pipeline():
    pipeline_v1 = LandslideFeaturePipeline()
    assert len(pipeline_v1.FEATURE_NAMES) == 25
    assert pipeline_v1.SCHEMA_VERSION == "1.0.0"

    # Verify extraction of v1 vector succeeds
    now = datetime.now(timezone.utc)
    loc = Location(id="TEST-01", name="Test Loc", slope_angle=30.0, elevation=800.0)
    obs = WeatherObservation(location_id=loc.id, timestamp=now, rainfall_24h=40.0, soil_moisture=60.0)
    v1_vector = feature_extractor.extract_features(loc, obs, [obs])

    flat_dict = v1_vector.to_flat_dict()
    X_arr = pipeline_v1.transform_single_dict(flat_dict)
    assert X_arr.shape == (1, 25)


# ---------------------------------------------------------------------
# 8. GIS Heatmap Feature Properties Test
# ---------------------------------------------------------------------
def test_gis_heatmap_feature_properties():
    now = datetime.now(timezone.utc)
    fc_detail = ForecastHorizonDetail(
        landslide_probability=0.72,
        risk_class="CRITICAL",
        target_window_start=now,
        target_window_end=now + timedelta(hours=24),
        decision_threshold=0.50,
        threshold_exceeded=True,
    )
    loc_fc = LocationForecastResponse(
        location_id="NER-SIK-GANGTOK-01",
        station_name="Gangtok Ridge Sector",
        district="East Sikkim",
        state="Sikkim",
        latitude=27.3389,
        longitude=88.6065,
        elevation=1650.0,
        slope_angle=38.5,
        baseline_susceptibility=0.85,
        generated_at=now,
        data_timestamp=now,
        data_freshness="FRESH",
        model_version="2.1.0-research",
        model_status="READY_SYNTHETIC",
        forecast_available=True,
        current_condition=CurrentConditionSummary(
            deterministic_risk_score=75.0,
            risk_level="HIGH",
        ),
        environmental_anomaly=EnvironmentalAnomalySummary(
            score=0.85,
            status="SEVERE",
            rainfall_anomaly_score=0.90,
            soil_anomaly_score=0.80,
            is_statistically_anomalous=True,
        ),
        forecast={"24h": fc_detail},
        observed_drivers=["24h Rainfall: 110mm (Extreme monsoonal deluge)"],
        model_contributions=[{"feature": "rainfall_24h_p99_ratio", "importance_score": 0.35, "method": "TREESHAP"}],
        static_susceptibility_score=0.82,
        susceptibility_model_version="1.0.0-geotechnical-dibang-valley",
        current_rainfall_p99_ratio=1.25,
        forecast_rainfall_p99_ratio=0.85,
        antecedent_rainfall_48h=45.0,
        soil_moisture_trend_6h=3.5,
        soil_moisture_trend_24h=12.0,
        shap_attributions=[{"feature": "rainfall_24h_p99_ratio", "importance_score": 0.35, "method": "TREESHAP"}],
    )

    multi_fc = MultiLocationForecastResponse(
        generated_at=now,
        model_status="READY_SYNTHETIC",
        model_version="2.1.0-research",
        locations_count=1,
        highest_forecast_probability=0.72,
        highest_risk_location="Gangtok Ridge Sector",
        forecasts=[loc_fc],
    )

    gis_res = landslide_inference_service.generate_gis_heatmap(multi_fc)
    assert gis_res.type == "FeatureCollection"
    assert len(gis_res.features) == 1
    props = gis_res.features[0].properties

    # Verify all research fields are present
    assert props["location_id"] == "NER-SIK-GANGTOK-01"
    assert props["forecast_probability_24h"] == 0.72
    assert props["static_susceptibility"] == 0.82
    assert props["current_rainfall_p99_ratio"] == 1.25
    assert props["forecast_rainfall_p99_ratio"] == 0.85
    assert props["antecedent_rainfall_48h"] == 45.0
    assert props["soil_moisture_trend_6h"] == 3.5
    assert props["soil_moisture_trend_24h"] == 12.0
    assert len(props["top_contributing_factors"]) == 1
