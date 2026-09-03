import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.ml.registry.model_registry import model_registry


@pytest_asyncio.fixture(scope="function")
async def setup_test_station(db_session: AsyncSession):
    loc = Location(
        id="LOC-TEST-API-01",
        name="Aizawl Ridge West",
        district="Aizawl",
        state="Mizoram",
        latitude=23.7271,
        longitude=92.7176,
        elevation=1132.0,
        slope_angle=38.0,
        susceptibility_score=0.78,
    )
    db_session.add(loc)
    obs = WeatherObservation(
        id="OBS-TEST-API-01",
        location_id=loc.id,
        rainfall_1h=25.0,
        rainfall_6h=80.0,
        rainfall_24h=145.0,
        soil_moisture=82.0,
        temperature=21.0,
        humidity=96.0,
    )
    db_session.add(obs)
    await db_session.commit()
    return loc


@pytest.mark.asyncio
async def test_api_ml_status(client: AsyncClient):
    response = await client.get("/api/v1/ml/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_active_model_trained_ml" in data
    assert "active_model_version" in data
    assert "feature_count" in data
    assert data["feature_count"] == 25



@pytest.mark.asyncio
async def test_api_location_forecast(client: AsyncClient, setup_test_station: Location):
    response = await client.get(f"/api/v1/ml/forecast/{setup_test_station.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["location_id"] == setup_test_station.id
    assert data["station_name"] == setup_test_station.name
    assert "current_condition" in data
    assert "environmental_anomaly" in data
    assert "forecast" in data
    assert "observed_drivers" in data

    if model_registry.is_trained_model_active():
        assert data["model_status"] == "READY"
        assert data["forecast_available"] is True
        assert "24h" in data["forecast"]
        p24 = data["forecast"]["24h"]["landslide_probability"]
        assert p24 is not None
        assert 0.0 <= p24 <= 1.0


@pytest.mark.asyncio
async def test_api_multi_location_forecast(client: AsyncClient, setup_test_station: Location):
    response = await client.get("/api/v1/ml/forecast")
    assert response.status_code == 200
    data = response.json()

    assert "generated_at" in data
    assert "locations_count" in data
    assert data["locations_count"] >= 1
    assert "forecasts" in data
    assert len(data["forecasts"]) >= 1


@pytest.mark.asyncio
async def test_api_gis_heatmap(client: AsyncClient, setup_test_station: Location):
    response = await client.get("/api/v1/ml/gis-heatmap")
    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert len(data["features"]) >= 1
    feat = data["features"][0]
    assert feat["type"] == "Feature"
    assert "geometry" in feat
    assert feat["geometry"]["type"] == "Point"
    assert "properties" in feat
    assert "landslide_probability_24h" in feat["properties"]
    assert "spatial_resolution_note" in data


@pytest.mark.asyncio
async def test_api_locations_map_enriched_fields(client: AsyncClient, setup_test_station: Location):
    response = await client.get("/api/v1/locations/map")
    assert response.status_code == 200
    items = response.json()

    matching = next((item for item in items if item["id"] == setup_test_station.id), None)
    assert matching is not None
    assert "forecast_probabilities" in matching
    assert "model_status" in matching
    assert "data_freshness" in matching
    assert "anomaly_score" in matching
    assert "anomaly_level" in matching

