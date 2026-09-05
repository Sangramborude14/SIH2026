from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db, require_role
from backend.app.models.user import User
from backend.app.services.field_service import field_service, FieldOperationsService
from backend.app.schemas.field import (
    FieldTeamResponse,
    TeamStatusUpdateRequest,
    FieldReportCreate,
    FieldReportUpdate,
    FieldReportResponse,
    AssistanceRequestCreate,
    AssistanceRequestUpdate,
    AssistanceRequestResponse,
    OperationalMessageCreate,
    OperationalMessageResponse,
    FieldAssignmentResponse,
    FieldOperationsSummary,
    NearbyIncidentItem,
)
from backend.app.core.logging import logger

router = APIRouter()


@router.get("/summary", response_model=FieldOperationsSummary)
async def get_field_operations_summary(db: AsyncSession = Depends(get_db)):
    """Retrieves operational overview of all field teams, unacknowledged reports, and SOS assistance requests."""
    return await field_service.get_operations_summary(db)


@router.get("/assignments", response_model=FieldAssignmentResponse)
async def get_field_assignment(
    callsign: str = Query("ALPHA-1", description="Field team callsign or ID"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves high-priority tactical assignment, immediate conditions, and nearby hazards for a field team."""
    briefing = await field_service.get_assignment_briefing(db, callsign)
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field unit '{callsign}' not found."
        )
    return briefing


@router.get("/assignments/{team_id}", response_model=FieldAssignmentResponse)
async def get_field_assignment_by_id(
    team_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieves tactical assignment briefing for a specific field unit ID or callsign."""
    briefing = await field_service.get_assignment_briefing(db, team_id)
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field unit '{team_id}' not found."
        )
    return briefing


@router.patch("/assignments/{team_id}/status", response_model=FieldTeamResponse)
async def update_assignment_status(
    team_id: str,
    status_in: TeamStatusUpdateRequest,
    current_user: User = Depends(require_role(["FIELD_RESPONDER", "ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    """Updates unit deployment lifecycle status and GPS coordinates."""
    try:
        updated = await field_service.update_team_status(
            session=db,
            team_id=team_id,
            status=status_in.status,
            latitude=status_in.latitude,
            longitude=status_in.longitude
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field unit '{team_id}' not found."
        )
    await db.commit()
    return FieldTeamResponse.model_validate(updated)


@router.get("/nearby-events", response_model=List[NearbyIncidentItem])
async def get_nearby_field_events(
    latitude: float = Query(27.3389, ge=-90.0, le=90.0),
    longitude: float = Query(88.6065, ge=-180.0, le=180.0),
    radius_km: float = Query(150.0, ge=1.0, le=1000.0),
    db: AsyncSession = Depends(get_db)
):
    """Calculates active hazard events within distance radius of current field GPS coordinates."""
    all_teams = await field_service.get_all_teams(db)
    target_team = all_teams[0] if all_teams else None
    if not target_team:
        return []
    briefing = await field_service.get_assignment_briefing(db, target_team.callsign)
    return briefing.nearby_incidents if briefing else []


@router.get("/teams", response_model=List[FieldTeamResponse])
async def list_field_teams(db: AsyncSession = Depends(get_db)):
    """Lists all registered disaster response field units and deployment statuses."""
    teams = await field_service.get_all_teams(db)
    return [FieldTeamResponse.model_validate(t) for t in teams]


@router.patch("/teams/{team_id}/status", response_model=FieldTeamResponse)
async def update_team_status(
    team_id: str,
    status_in: TeamStatusUpdateRequest,
    current_user: User = Depends(require_role(["FIELD_RESPONDER", "ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    """Updates unit deployment lifecycle status and GPS coordinates."""
    try:
        updated = await field_service.update_team_status(
            session=db,
            team_id=team_id,
            status=status_in.status,
            latitude=status_in.latitude,
            longitude=status_in.longitude
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field unit '{team_id}' not found."
        )
    await db.commit()
    return FieldTeamResponse.model_validate(updated)



from fastapi import UploadFile, File, Response
from backend.app.services.storage_provider import get_storage_provider


@router.post("/upload-image")
async def upload_field_report_image(
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = Query(None, description="Reporter name or callsign"),
    current_user: User = Depends(require_role(["FIELD_RESPONDER", "EXPERT", "ADMIN"]))
):
    """
    Securely uploads a field report evidence image (JPEG, PNG, WEBP).
    Validates MIME type, enforces size limits (10MB), and returns safe storage metadata.
    """
    storage = get_storage_provider()
    content = await file.read()
    res = await storage.save_file(
        file_bytes=content,
        original_filename=file.filename or "report.jpg",
        content_type=file.content_type or "image/jpeg",
        uploaded_by=uploaded_by or current_user.email,
    )
    return res


@router.get("/media/{storage_key}")
async def get_report_media_file(storage_key: str):
    """Retrieves securely stored image media for field and citizen reports."""
    storage = get_storage_provider()
    file_bytes, mime_type = await storage.get_file(storage_key)
    return Response(content=file_bytes, media_type=mime_type)


@router.get("/reports", response_model=List[FieldReportResponse])
async def list_field_reports(
    location_id: Optional[str] = None,
    event_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves chronological field observations submitted by rescue units."""
    reports = await field_service.get_field_reports(db, location_id, event_id, status, limit)
    return [FieldOperationsService.format_report_response(r) for r in reports]


@router.post("/reports", response_model=FieldReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_field_report(
    report_in: FieldReportCreate,
    current_user: User = Depends(require_role(["FIELD_RESPONDER", "ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    """Submits a structured ground observation report from a field operator."""
    report = await field_service.submit_field_report(db, report_in)
    await db.commit()
    return FieldOperationsService.format_report_response(report)


@router.patch("/reports/{report_id}", response_model=FieldReportResponse)
async def update_report_status(
    report_id: str,
    update_in: FieldReportUpdate,
    current_user: User = Depends(require_role(["EXPERT", "ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    """Command Center officer acknowledges, reviews, or incorporates a field observation."""
    report = await field_service.update_report_status(db, report_id, update_in)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field report '{report_id}' not found."
        )
    await db.commit()
    return FieldOperationsService.format_report_response(report)


@router.get("/assistance", response_model=List[AssistanceRequestResponse])
async def list_assistance_requests(
    event_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Lists SOS assistance requests dispatched by field units."""
    requests = await field_service.get_assistance_requests(db, event_id, limit)
    return [AssistanceRequestResponse.model_validate(r) for r in requests]


@router.post("/assistance", response_model=AssistanceRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_assistance_request(
    req_in: AssistanceRequestCreate,
    db: AsyncSession = Depends(get_db)
):
    """Dispatches an urgent SOS assistance request from an on-ground rescue team."""
    req = await field_service.request_assistance(db, req_in)
    await db.commit()
    return AssistanceRequestResponse.model_validate(req)


@router.patch("/assistance/{request_id}", response_model=AssistanceRequestResponse)
async def update_assistance_request(
    request_id: str,
    update_in: AssistanceRequestUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Updates assistance request lifecycle status (e.g. ASSIGNED, RESOLVED)."""
    req = await field_service.update_assistance_status(db, request_id, update_in)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistance request '{request_id}' not found."
        )
    await db.commit()
    return AssistanceRequestResponse.model_validate(req)


@router.get("/messages", response_model=List[OperationalMessageResponse])
async def list_operational_messages(
    callsign: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves operational broadcasts and urgent command directives."""
    messages = await field_service.get_operational_messages(db, callsign, limit)
    return [OperationalMessageResponse.model_validate(m) for m in messages]


@router.post("/messages", response_model=OperationalMessageResponse, status_code=status.HTTP_201_CREATED)
async def broadcast_operational_message(
    msg_in: OperationalMessageCreate,
    db: AsyncSession = Depends(get_db)
):
    """Central Command officer broadcasts an operational directive to field units."""
    msg = await field_service.send_operational_message(db, msg_in)
    await db.commit()
    return OperationalMessageResponse.model_validate(msg)


@router.post("/messages/{message_id}/acknowledge", response_model=OperationalMessageResponse)
async def acknowledge_operational_message(
    message_id: str,
    acknowledged_by: str = Query("Team Alpha Leader"),
    db: AsyncSession = Depends(get_db)
):
    """Field operator acknowledges receipt of an urgent operational message."""
    msg = await field_service.acknowledge_operational_message(db, message_id, acknowledged_by)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operational message '{message_id}' not found."
        )
    await db.commit()
    return OperationalMessageResponse.model_validate(msg)
