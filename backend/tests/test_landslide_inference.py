import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.models.ml_forecast import LandslideForecastRecord
from backend.app.services.landslide_inference_service import landslide_inference_service
from backend.app.ml.registry.model_registry import model_registry
from backend.app.engine.event_manager import event_manager
from backend.app.engine.pipeline import disaster_engine
from backend.app.engine.base import EventStatus


@pytest.fixture
def mock_ner_location():
    return Location(
        id="LOC-NER-TEST-01",
        name="Guwahati Hills South",
        district="Kamrup Metropolitan",
        state="Assam",
        latitude=26.1445,
        longitude=91.7362,
        elevation=1150.0,
        slope_angle=36.5,
        susceptibility_score=0.72,
    )


@pytest.fixture
def mock_weather_observations():
    now = datetime.now(timezone.utc)
    obs = []
    for i in range(10):
        t = now - timedelta(hours=(10 - i))
        obs.append(
            WeatherObservation(
                id=f"OBS-TEST-{i}",
                location_id="LOC-NER-TEST-01",
                timestamp=t,
                rainfall_1h=15.0 + i * 2.0,
                rainfall_6h=60.0 + i * 5.0,
                rainfall_24h=120.0 + i * 3.0,
                soil_moisture=75.0 + i * 1.5,
                temperature=22.0,
                humidity=95.0,

            )
        )
    return obs


@pytest.mark.asyncio
async def test_inference_service_feature_building_and_prediction(mock_ner_location, mock_weather_observations):
    latest_obs = mock_weather_observations[-1]
    res = await landslide_inference_service.generate_forecast_for_location(
        session=None,
        location=mock_ner_location,
        latest_obs=latest_obs,
        obs_history=mock_weather_observations,
        deterministic_risk_score=68.5,
        deterministic_risk_level="HIGH",
        persist=False,
    )

    assert res.location_id == mock_ner_location.id
    assert res.station_name == mock_ner_location.name
    assert res.data_freshness == "FRESH"
    assert res.current_condition.deterministic_risk_score == 68.5
    assert res.current_condition.risk_level == "HIGH"
    assert res.environmental_anomaly.score >= 0.0
    assert len(res.observed_drivers) > 0

    if model_registry.is_trained_model_active():
        assert res.model_status == "READY"
        assert res.forecast_available is True
        assert "24h" in res.forecast
        p24 = res.forecast["24h"].landslide_probability
        assert p24 is not None
        assert 0.0 <= p24 <= 1.0
        assert res.forecast["24h"].risk_class in ["LOW", "MODERATE", "HIGH", "CRITICAL"]


@pytest.mark.asyncio
async def test_forecast_database_persistence(db_session: AsyncSession, mock_ner_location, mock_weather_observations):
    # Add location to db
    db_session.add(mock_ner_location)
    await db_session.flush()

    latest_obs = mock_weather_observations[-1]
    res = await landslide_inference_service.generate_forecast_for_location(
        session=db_session,
        location=mock_ner_location,
        latest_obs=latest_obs,
        obs_history=mock_weather_observations,
        deterministic_risk_score=72.0,
        deterministic_risk_level="HIGH",
        persist=True,
    )
    await db_session.flush()

    if model_registry.is_trained_model_active():
        stmt = select(LandslideForecastRecord).where(
            LandslideForecastRecord.location_id == mock_ner_location.id
        )
        saved_res = await db_session.execute(stmt)
        records = list(saved_res.scalars().all())

        assert len(records) > 0
        horizons = {r.forecast_horizon for r in records}
        assert "24H" in horizons
        rec = next(r for r in records if r.forecast_horizon == "24H")
        assert rec.probability is not None
        assert 0.0 <= rec.probability <= 1.0
        assert rec.model_version == "2.0.0"
        assert rec.data_freshness == "FRESH"
        assert rec.primary_features_compact is not None
        assert "slope_angle" in rec.primary_features_compact



@pytest.mark.asyncio
async def test_multi_location_and_gis_heatmap(db_session: AsyncSession, mock_ner_location, mock_weather_observations):
    db_session.add(mock_ner_location)
    for obs in mock_weather_observations:
        db_session.add(obs)
    await db_session.flush()

    multi_fc = await landslide_inference_service.generate_forecast_for_all_locations(
        session=db_session,
        locations=[mock_ner_location],
        persist=False,
    )
    assert multi_fc.locations_count == 1
    assert len(multi_fc.forecasts) == 1

    heatmap = landslide_inference_service.generate_gis_heatmap(multi_fc)
    assert heatmap.type == "FeatureCollection"
    assert len(heatmap.features) == 1
    feat = heatmap.features[0]
    assert feat.geometry["type"] == "Point"
    assert feat.properties["location_id"] == mock_ner_location.id
    assert "Disclosed: Point telemetry & Voronoi catchment perimeters" in heatmap.spatial_resolution_note


def test_event_manager_ml_probability_escalation():
    # 1. Standard low risk
    status, sev = event_manager.determine_event_status_and_severity(
        risk_score=15.0,
        forecast_probability=0.10
    )
    assert sev == "LOW"

    # 2. High forecast probability >= 0.55 escalates to HIGH even if deterministic score is moderate
    status_high, sev_high = event_manager.determine_event_status_and_severity(
        risk_score=35.0,
        forecast_probability=0.62
    )
    assert sev_high == "HIGH"

    # 3. Critical forecast probability >= 0.75 escalates to CRITICAL
    status_crit, sev_crit = event_manager.determine_event_status_and_severity(
        risk_score=40.0,
        forecast_probability=0.82
    )
    assert sev_crit == "CRITICAL"


@pytest.mark.asyncio
async def test_engine_pipeline_ml_integration(db_session: AsyncSession, mock_ner_location, mock_weather_observations):
    db_session.add(mock_ner_location)
    for obs in mock_weather_observations:
        db_session.add(obs)
    await db_session.flush()

    assessment_output, event, action = await disaster_engine.evaluate_location(
        session=db_session,
        location=mock_ner_location,
        force_fresh=False,
    )

    assert assessment_output.risk_score > 0
    if model_registry.is_trained_model_active():
        assert assessment_output.forecast_available is True
        assert "24h" in assessment_output.forecast_probabilities

    resp = disaster_engine.format_assessment_response(mock_ner_location, assessment_output, event)
    assert resp.location_id == mock_ner_location.id
    if model_registry.is_trained_model_active():
        assert resp.forecast_available is True
        assert "24h" in resp.forecast_probabilities


@pytest.mark.asyncio
async def test_ml_fallback_when_untrained(mock_ner_location, mock_weather_observations):
    orig_state = model_registry._is_trained_model_active
    try:
        model_registry._is_trained_model_active = False
        latest_obs = mock_weather_observations[-1]
        res = await landslide_inference_service.generate_forecast_for_location(
            session=None,
            location=mock_ner_location,
            latest_obs=latest_obs,
            obs_history=mock_weather_observations,
            deterministic_risk_score=55.0,
            deterministic_risk_level="HIGH",
            persist=False,
        )

        assert res.forecast_available is False
        assert res.model_status == "NOT_TRAINED"
        assert res.forecast == {}
        assert "ML FORECAST UNAVAILABLE" in res.disclaimer
        # Deterministic assessment is preserved completely
        assert res.current_condition.deterministic_risk_score == 55.0
        assert res.current_condition.risk_level == "HIGH"
    finally:
        model_registry._is_trained_model_active = orig_state

