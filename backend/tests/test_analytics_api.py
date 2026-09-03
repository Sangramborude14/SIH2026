import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analytics_api_endpoints(client):
    # 1. GET /api/v1/analytics/incidents
    inc_res = await client.get("/api/v1/analytics/incidents")
    assert inc_res.status_code == 200
    incidents = inc_res.json()
    assert len(incidents) >= 4
    inc_id = incidents[0]["id"]

    # 2. GET /api/v1/analytics/incidents/{id}/playback
    pb_res = await client.get(f"/api/v1/analytics/incidents/{inc_id}/playback")
    assert pb_res.status_code == 200
    pb_data = pb_res.json()
    assert "playback_frames" in pb_data
    assert len(pb_data["playback_frames"]) >= 4

    # 3. GET /api/v1/analytics/metrics
    met_res = await client.get("/api/v1/analytics/metrics")
    assert met_res.status_code == 200
    met_data = met_res.json()
    assert met_data["model_status"] in ["READY", "NOT_TRAINED"]
    assert "model_name" in met_data
    if met_data.get("is_trained"):
        assert "confusion_matrix" in met_data
        assert met_data["brier_score"] is not None
    else:
        assert met_data["precision"] is None


    # 4. POST /api/v1/analytics/backtest
    bt_res = await client.post(
        "/api/v1/analytics/backtest",
        json={
            "run_name": "API Weight Test",
            "weights": {
                "rainfall_24h": 0.40,
                "rainfall_72h": 0.10,
                "soil_moisture": 0.20,
                "slope_angle": 0.15,
                "susceptibility": 0.15
            },
            "warning_threshold_score": 70.0
        }
    )
    assert bt_res.status_code == 201
    bt_data = bt_res.json()
    assert bt_data["f1_score"] > 0.80

    # 5. GET /api/v1/analytics/history
    hist_res = await client.get("/api/v1/analytics/history")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1
