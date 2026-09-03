import pytest
from datetime import datetime, timezone, timedelta
from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.models.weather_forecast import WeatherForecastSnapshot
from backend.app.repositories.weather_repository import weather_repository
from backend.app.services.live_ingestion import LiveWeatherIngestionService, ingestion_tracker


@pytest.mark.asyncio
async def test_weather_repository_upsert_batch(db_session):
    """Verifies that upsert_batch prevents duplicate rows and updates values."""
    loc = Location(
        id="TEST-LOC-UPSERT",
        name="Test Station",
        state="Sikkim",
        district="East Sikkim",
        latitude=27.0,
        longitude=88.0,
        elevation=1500.0,
    )
    db_session.add(loc)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    obs1 = WeatherObservation(
        location_id=loc.id,
        timestamp=now,
        rainfall_1h=5.0,
        rainfall_24h=20.0,
        soil_moisture=50.0,
        source="TEST_SOURCE",
        observation_type="OBSERVED"
    )

    # First insert
    res1 = await weather_repository.upsert_batch(db_session, [obs1])
    assert res1["inserted"] == 1
    assert res1["updated"] == 0

    # Second insert with updated value
    obs2 = WeatherObservation(
        location_id=loc.id,
        timestamp=now,
        rainfall_1h=12.0,
        rainfall_24h=25.0,
        soil_moisture=55.0,
        source="TEST_SOURCE",
        observation_type="OBSERVED"
    )
    res2 = await weather_repository.upsert_batch(db_session, [obs2])
    assert res2["inserted"] == 0
    assert res2["updated"] == 1


@pytest.mark.asyncio
async def test_weather_forecast_snapshots_persistence(db_session):
    """Verifies that forecast predictions are archived separately into snapshots."""
    loc = Location(
        id="TEST-LOC-SNAP",
        name="Forecast Test",
        state="Sikkim",
        district="East Sikkim",
        latitude=27.0,
        longitude=88.0,
        elevation=1500.0,
    )
    db_session.add(loc)
    await db_session.flush()


    now = datetime.now(timezone.utc)
    snap = WeatherForecastSnapshot(
        location_id=loc.id,
        forecast_issued_at=now,
        forecast_valid_at=now + timedelta(hours=24),
        forecast_horizon_hours=24,
        precipitation_mm=45.0,
        source="OPEN_METEO",
    )

    saved = await weather_repository.save_forecast_snapshots(db_session, [snap])
    assert saved == 1


@pytest.mark.asyncio
async def test_ingestion_health_endpoint(client):
    """Verifies that GET /api/v1/system/ingestion-health returns valid telemetry metrics."""
    response = await client.get("/api/v1/system/ingestion-health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "ingestion" in data
    assert data["ingestion"]["provider"] == "OPEN_METEO"
    assert "cadence_seconds" in data["ingestion"]
