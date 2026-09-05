import pytest
import io
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_citizen_risk_evaluation(client: AsyncClient):
    """
    Verifies citizen risk translation answers 'Am I safe?' and 'Is risk increasing?',
    and strictly omits any ML floating point probabilities, SHAP values, or sensor internals.
    """
    # Test with Gangtok coordinates
    res = await client.get("/api/v1/citizen/risk?latitude=27.3389&longitude=88.6065")
    assert res.status_code == 200
    data = res.json()

    assert data["safety_level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    assert data["safety_color"] in ["green", "yellow", "orange", "red"]
    assert "safety_headline" in data
    assert "safety_summary" in data
    assert data["trend_24h"] in ["INCREASING", "STABLE", "DECREASING"]
    assert "trend_description" in data
    assert "immediate_dos_donts" in data
    assert len(data["immediate_dos_donts"]) >= 2
    assert "emergency_contacts" in data
    assert data["emergency_contacts"]["National Emergency"] == "112"

    # STRICT INVARIANT: Zero expert terminology or raw ML probabilities exposed
    forbidden_keys = [
        "probability", "p_value", "shap_values", "factor_of_safety",
        "feature_importance", "sensor_voltage", "station_id", "auc_pr", "brier_score"
    ]
    for k in forbidden_keys:
        assert k not in data, f"Forbidden technical key '{k}' exposed in citizen risk response!"


@pytest.mark.asyncio
async def test_citizen_guidance_and_contacts(client: AsyncClient):
    """
    Verifies structured Before, During, and After landslide guidance,
    natural warning signs, and official NER emergency numbers.
    """
    # 1. Guidance
    g_res = await client.get("/api/v1/citizen/guidance")
    assert g_res.status_code == 200
    g_data = g_res.json()
    assert len(g_data["guidance_sections"]) == 3
    phases = [s["phase"] for s in g_data["guidance_sections"]]
    assert "BEFORE" in phases
    assert "DURING" in phases
    assert "AFTER" in phases
    assert len(g_data["natural_warning_signs"]) >= 4
    assert len(g_data["emergency_kit_checklist"]) >= 5

    # 2. Contacts
    c_res = await client.get("/api/v1/citizen/contacts")
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert c_data["national_emergency"] == "112"
    assert c_data["disaster_management_helpline"] == "1070"
    assert "Sikkim State Disaster Control (Gangtok)" in c_data["ner_state_control_rooms"]


@pytest.mark.asyncio
async def test_citizen_shelters(client: AsyncClient):
    """
    Verifies listing of verified community shelters and safe points.
    """
    res = await client.get("/api/v1/citizen/shelters")
    assert res.status_code == 200
    shelters = res.json()
    assert len(shelters) >= 1
    assert "name" in shelters[0]
    assert "point_type" in shelters[0]


@pytest.mark.asyncio
async def test_citizen_sos_lifecycle_and_duplicate_suppression(client: AsyncClient):
    """
    Verifies SOS creation, status progression, and duplicate suppression.
    """
    sos_payload = {
        "emergency_type": "TRAPPED_BY_LANDSLIDE",
        "latitude": 27.3315,
        "longitude": 88.6138,
        "location_accuracy": 5.2,
        "location_name": "Near Paljor Stadium Ridge",
        "contact_name": "Tashi Dorji",
        "contact_phone": "+919876543210",
        "num_people": 3,
        "message": "Mudflow blocked road, 3 people sheltered inside vehicle",
        "device_fingerprint": "DEV-TEST-XYZ-123"
    }

    # 1. Initial SOS dispatch
    res1 = await client.post("/api/v1/citizen/sos", json=sos_payload)
    assert res1.status_code == 201
    sos1 = res1.json()
    assert sos1["status"] == "RECEIVED"
    assert sos1["num_people"] == 3
    sos_id = sos1["id"]

    # 2. Duplicate suppression test: Rapid second submission within 120s
    res2 = await client.post("/api/v1/citizen/sos", json=sos_payload)
    assert res2.status_code == 201
    sos2 = res2.json()
    assert sos2["id"] == sos_id, "Duplicate SOS was created instead of suppressing to existing record!"

    # 3. Read SOS status
    res3 = await client.get(f"/api/v1/citizen/sos/{sos_id}")
    assert res3.status_code == 200
    assert res3.json()["id"] == sos_id

    # 4. Update lifecycle status (e.g. by Rescue Command)
    patch_res = await client.patch(
        f"/api/v1/citizen/sos/{sos_id}/status",
        json={
            "status": "RESCUE_EN_ROUTE",
            "assigned_unit": "SDRF Unit Bravo",
            "responder_notes": "Team deployed via North Ridge route"
        }
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["status"] == "RESCUE_EN_ROUTE"
    assert patched["assigned_unit"] == "SDRF Unit Bravo"


@pytest.mark.asyncio
async def test_citizen_hazard_report(client: AsyncClient):
    """
    Verifies citizen abnormality hazard reporting with photo attachment.
    """
    # Create dummy image bytes (valid JPEG header)
    mock_jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 200

    form_data = {
        "category": "GROUND_CRACK",
        "description": "Fissure of 15cm width noticed across hillside road after continuous rainfall",
        "latitude": 27.3400,
        "longitude": 88.6100,
        "location_accuracy": 10.0,
        "location_name": "Tathangchen Ward Road",
        "contact_phone": "+919876543210"
    }

    files = {
        "photo": ("crack_evidence.jpg", io.BytesIO(mock_jpg_bytes), "image/jpeg")
    }

    res = await client.post("/api/v1/citizen/report", data=form_data, files=files)
    assert res.status_code == 201
    report_data = res.json()
    assert report_data["category"] == "GROUND_CRACK"
    assert report_data["status"] == "RECEIVED"
    assert report_data["report_number"].startswith("REP-")
    assert report_data["photo_url"] is not None

    report_id = report_data["id"]

    # Read back report
    get_res = await client.get(f"/api/v1/citizen/reports/{report_id}")
    assert get_res.status_code == 200
    assert get_res.json()["report_number"] == report_data["report_number"]

    # List reports
    list_res = await client.get("/api/v1/citizen/reports")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
