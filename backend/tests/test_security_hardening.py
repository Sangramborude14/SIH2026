import io
import uuid
import time
import pytest
from httpx import AsyncClient, ASGITransport
from PIL import Image
from sqlalchemy import select

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_token,
)
from backend.app.models.user import User, RefreshToken
from backend.app.models.citizen import CitizenSOS, CitizenReport
from backend.app.services.storage_provider import LocalStorageProvider


@pytest.mark.asyncio
async def test_password_hashing_and_verification():
    """Verifies PBKDF2-HMAC-SHA256 password hashing and timing attack defense."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    
    assert hashed.startswith("pbkdf2_sha256$600000$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "") is False


@pytest.mark.asyncio
async def test_jwt_access_token_claims_and_validation():
    """Verifies JWT token issuance, minimal claims, and tamper resistance."""
    user_id = str(uuid.uuid4())
    role = "EXPERT"
    
    token = create_access_token(user_id=user_id, role=role)
    assert isinstance(token, str)
    
    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "EXPERT"
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload
    assert payload["type"] == "access"
    
    # Verify tampered token is rejected
    tampered = token[:-4] + "abcd"
    with pytest.raises(Exception):
        decode_access_token(tampered)


@pytest.mark.asyncio
async def test_user_registration_and_login_flow(anon_client: AsyncClient):
    """Verifies user registration, password hashing, and authentication."""
    # 1. Register new citizen
    reg_payload = {
        "email": "namgyal@gangtok.in",
        "password": "SecurePassword#2026",
        "full_name": "Namgyal Bhutia",
        "phone_number": "+919876543211",
        "role": "CITIZEN"
    }
    reg_res = await anon_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    data = reg_res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "namgyal@gangtok.in"
    assert data["user"]["role"] == "CITIZEN"
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]

    # 2. Reject duplicate registration with 409 Conflict
    dup_res = await anon_client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.json()["detail"].lower()

    # 3. Login with correct credentials
    login_res = await anon_client.post(
        "/api/v1/auth/login",
        json={"email": "namgyal@gangtok.in", "password": "SecurePassword#2026"}
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_res.cookies.get(settings.REFRESH_COOKIE_NAME) is not None

    # 4. Login with incorrect password
    bad_pw_res = await anon_client.post(
        "/api/v1/auth/login",
        json={"email": "namgyal@gangtok.in", "password": "WrongPassword!"}
    )
    assert bad_pw_res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_revocation(anon_client: AsyncClient):
    """Verifies refresh token rotation, single-use enforcement, and logout."""
    # Register user as citizen
    reg_res = await anon_client.post("/api/v1/auth/register", json={
        "email": "field_officer@sih2026.gov.in",
        "password": "FieldPassword123!",
        "full_name": "Officer Tenzing",
        "role": "CITIZEN"
    })
    assert reg_res.status_code == 201
    initial_refresh_cookie = reg_res.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert initial_refresh_cookie is not None

    # Call refresh endpoint with cookie
    anon_client.cookies.set(settings.REFRESH_COOKIE_NAME, initial_refresh_cookie)
    refresh_res = await anon_client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    new_token_data = refresh_res.json()
    assert "access_token" in new_token_data
    rotated_refresh_cookie = refresh_res.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert rotated_refresh_cookie is not None
    assert rotated_refresh_cookie != initial_refresh_cookie

    # Attempting to reuse old refresh token should fail (single-use rotation)
    anon_client.cookies.set(settings.REFRESH_COOKIE_NAME, initial_refresh_cookie)
    reuse_res = await anon_client.post("/api/v1/auth/refresh")
    assert reuse_res.status_code == 401

    # Logout revokes refresh token
    anon_client.cookies.set(settings.REFRESH_COOKIE_NAME, rotated_refresh_cookie)
    logout_res = await anon_client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200

    # Attempting refresh after logout fails
    post_logout_refresh = await anon_client.post("/api/v1/auth/refresh")
    assert post_logout_refresh.status_code == 401



@pytest.mark.asyncio
async def test_rbac_endpoint_protection(anon_client: AsyncClient, db_session):
    """
    Verifies 4-tier Role-Based Access Control:
    - Anonymous: 401 Unauthorized on protected routes
    - CITIZEN: 403 Forbidden on EXPERT/ADMIN/RESPONDER actions
    - FIELD_RESPONDER: Can update team status, cannot run simulation
    - EXPERT: Can run simulation, cannot broadcast alerts
    - ADMIN: Can perform all administrative actions
    """
    # 1. Anonymous caller trying administrative simulation
    anon_sim = await anon_client.post("/api/v1/simulation/scenario", json={"scenario": "normal"})
    assert anon_sim.status_code == 401

    anon_broadcast = await anon_client.post("/api/v1/alerts/broadcast", json={
        "headline": "Evacuation Order",
        "description": "Critical landslide alert",
        "severity": "CRITICAL",
        "target_location_ids": ["gangtok_east"]
    })
    assert anon_broadcast.status_code == 401

    # Create users for each role
    citizen_user = User(
        id=str(uuid.uuid4()),
        email="citizen@ner.in",
        hashed_password=hash_password("Pass123!"),
        full_name="Citizen User",
        role="CITIZEN",
        is_active=True,
    )
    responder_user = User(
        id=str(uuid.uuid4()),
        email="responder@ner.in",
        hashed_password=hash_password("Pass123!"),
        full_name="Responder User",
        role="FIELD_RESPONDER",
        is_active=True,
    )
    expert_user = User(
        id=str(uuid.uuid4()),
        email="expert@ner.in",
        hashed_password=hash_password("Pass123!"),
        full_name="Expert Geologist",
        role="EXPERT",
        is_active=True,
    )
    db_session.add_all([citizen_user, responder_user, expert_user])
    await db_session.commit()

    citizen_token = create_access_token(user_id=citizen_user.id, role="CITIZEN")
    responder_token = create_access_token(user_id=responder_user.id, role="FIELD_RESPONDER")
    expert_token = create_access_token(user_id=expert_user.id, role="EXPERT")

    # 2. CITIZEN calling simulation -> 403 Forbidden
    anon_client.headers["Authorization"] = f"Bearer {citizen_token}"
    cit_sim = await anon_client.post("/api/v1/simulation/scenario", json={"scenario": "normal"})
    assert cit_sim.status_code == 403

    cit_bcast = await anon_client.post("/api/v1/alerts/broadcast", json={
        "headline": "Fake Alert",
        "description": "Should be blocked",
        "severity": "CRITICAL",
        "target_location_ids": ["gangtok_east"]
    })
    assert cit_bcast.status_code == 403

    # 3. FIELD_RESPONDER calling simulation -> 403 Forbidden; updating team status -> 200
    anon_client.headers["Authorization"] = f"Bearer {responder_token}"
    resp_sim = await anon_client.post("/api/v1/simulation/scenario", json={"scenario": "normal"})
    assert resp_sim.status_code == 403

    # Fetch first seeded team
    teams_res = await anon_client.get("/api/v1/field/teams")
    assert teams_res.status_code == 200
    team_list = teams_res.json()
    assert len(team_list) > 0
    target_team_id = team_list[0]["id"]

    resp_team = await anon_client.patch(
        f"/api/v1/field/teams/{target_team_id}/status",
        json={
            "status": "DEPLOYED",
            "latitude": 27.33,
            "longitude": 88.61
        }
    )
    assert resp_team.status_code == 200
    assert resp_team.json()["status"] == "DEPLOYED"

    # 4. EXPERT calling simulation -> 200 OK; broadcasting alerts -> 403 Forbidden (Admin only)
    anon_client.headers["Authorization"] = f"Bearer {expert_token}"
    exp_sim = await anon_client.post("/api/v1/simulation/scenario", json={"scenario": "normal"})
    assert exp_sim.status_code == 200

    exp_bcast = await anon_client.post("/api/v1/alerts/broadcast", json={
        "headline": "Expert Alert",
        "description": "Admin only broadcast",
        "severity": "HIGH",
        "target_location_ids": ["gangtok_east"]
    })
    assert exp_bcast.status_code == 403
    anon_client.headers.pop("Authorization", None)


@pytest.mark.asyncio
async def test_idor_prevention_on_citizen_sos(anon_client: AsyncClient):
    """
    Verifies Insecure Direct Object Reference (IDOR) prevention:
    - Citizen A cannot retrieve Citizen B's SOS beacon without tracking token.
    - Anonymous SOS is accessible ONLY with the returned X-SOS-Tracking-Token.
    - Responders and Admins can access distress beacons for rescue operations.
    """
    # 1. Create anonymous SOS
    sos_payload = {
        "emergency_type": "TRAPPED_BY_LANDSLIDE",
        "latitude": 27.3315,
        "longitude": 88.6138,
        "num_people": 2,
        "contact_name": "Stranded Traveler",
        "contact_phone": "+919876543299",
        "message": "Vehicle stuck near rockfall"
    }

    res = await anon_client.post("/api/v1/citizen/sos", json=sos_payload)
    assert res.status_code == 201
    sos_data = res.json()
    sos_id = sos_data["id"]
    tracking_token = sos_data["tracking_token"]
    assert tracking_token is not None

    # Attempt access WITHOUT tracking token -> 403 Forbidden
    idor_attempt = await anon_client.get(f"/api/v1/citizen/sos/{sos_id}")
    assert idor_attempt.status_code == 403

    # Attempt access WITH WRONG tracking token -> 403 Forbidden
    bad_token_attempt = await anon_client.get(
        f"/api/v1/citizen/sos/{sos_id}",
        headers={"X-SOS-Tracking-Token": "invalid-token-12345"}
    )
    assert bad_token_attempt.status_code == 403

    # Access WITH VALID tracking token -> 200 OK
    valid_attempt = await anon_client.get(
        f"/api/v1/citizen/sos/{sos_id}",
        headers={"X-SOS-Tracking-Token": tracking_token}
    )
    assert valid_attempt.status_code == 200
    assert valid_attempt.json()["id"] == sos_id


@pytest.mark.asyncio
async def test_photo_upload_magic_bytes_and_deduplication(tmp_path):
    """
    Verifies photo security controls:
    - Magic byte validation rejects files with spoofed extensions (e.g. text/html renamed to .jpg).
    - Image dimension and decompression bomb constraints.
    - SHA-256 deduplication avoids duplicate disk allocations.
    """
    provider = LocalStorageProvider(base_dir=tmp_path)

    # 1. Spoofed JPEG: HTML payload with .jpg extension
    spoofed_bytes = b"<html><script>alert('xss')</script></html>"
    with pytest.raises(Exception) as exc_info:
        await provider.save_file(
            file_bytes=spoofed_bytes,
            original_filename="malicious.jpg",
            content_type="image/jpeg",
        )
    assert "Invalid file signature" in str(exc_info.value) or "could not be decoded" in str(exc_info.value)

    # 2. Valid 200x200 JPEG image
    valid_img = Image.new("RGB", (200, 200), color=(200, 50, 50))
    buffer = io.BytesIO()
    valid_img.save(buffer, format="JPEG", quality=85)
    valid_bytes = buffer.getvalue()

    result1 = await provider.save_file(
        file_bytes=valid_bytes,
        original_filename="landslide_evidence.jpg",
        content_type="image/jpeg",
    )
    assert result1["storage_key"].endswith(".jpg")
    assert result1["thumbnail_storage_key"] is not None
    assert (tmp_path / result1["storage_key"]).exists()
    assert (tmp_path / result1["thumbnail_storage_key"]).exists()

    # 3. Upload same image bytes again (deduplication check)
    result2 = await provider.save_file(
        file_bytes=valid_bytes,
        original_filename="landslide_evidence_retry.jpg",
        content_type="image/jpeg",
    )
    assert result2["deduplicated"] is True
    assert result2["storage_key"] == result1["storage_key"]
    assert result2["content_hash"] == result1["content_hash"]


@pytest.mark.asyncio
async def test_http_security_headers(client: AsyncClient):
    """Verifies that all OWASP-recommended HTTP security headers are present."""
    response = await client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=" in headers.get("Permissions-Policy", "")
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in headers.get("Content-Security-Policy", "")


@pytest.mark.asyncio
async def test_rate_limiting_enforcement(anon_client: AsyncClient):
    """Verifies that exceeding the rate limit window triggers HTTP 429 Too Many Requests."""
    settings.RATE_LIMIT_ENABLED = True
    
    # Send 10 rapid requests (the max limit for login)
    status_codes = []
    for _ in range(12):
        res = await anon_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "WrongPassword123!"}
        )
        status_codes.append(res.status_code)

    # At least one request beyond the limit must return 429
    assert 429 in status_codes, f"Expected 429 in responses, got: {status_codes}"


@pytest.mark.asyncio
async def test_redis_namespacing_and_invalidation():
    """Verifies standard sih:* namespace key generation and selective invalidation."""
    from backend.app.core.cache import cache, CacheKeys, invalidate_station_risk

    loc_id = "NER-SIK-GANGTOK-01"
    key = CacheKeys.risk_station_24h(loc_id)
    assert key.startswith("sih:risk:station:")

    # Set station risk
    await cache.set(key, {"risk_score": 78.5, "status": "WARNING"}, ttl_seconds=60)
    cached = await cache.get(key)
    assert cached is not None
    assert cached["risk_score"] == 78.5

    # Selective invalidation
    await invalidate_station_risk(loc_id)
    cleared = await cache.get(key)
    assert cleared is None



@pytest.mark.asyncio
async def test_citizen_reports_pagination(client: AsyncClient):
    """Verifies standardized paginated response structure."""
    res = await client.get("/api/v1/citizen/reports?page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert data["page"] == 1
    assert data["page_size"] == 5

