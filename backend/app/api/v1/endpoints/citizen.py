from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import (
    get_db,
    get_current_user,
    get_current_user_optional,
    require_role,
    check_rate_limit,
)
from backend.app.models.user import User
from backend.app.services.citizen_service import citizen_service
from backend.app.services.public_safety_service import public_safety_service
from backend.app.schemas.citizen import (
    CitizenRiskStatusResponse,
    CitizenSOSCreate,
    CitizenSOSResponse,
    CitizenSOSStatusUpdate,
    CitizenReportResponse,
    CitizenGuidanceResponse,
    CitizenContactsResponse,
    NearestShelterInfo,
)
from backend.app.schemas.public import SafetyPointResponse
from backend.app.schemas.pagination import PaginatedResponse
from backend.app.core.logging import logger

router = APIRouter()


@router.get("/risk", response_model=CitizenRiskStatusResponse)
async def get_citizen_risk_status(
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0),
    location_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Answers: 'Am I currently safe?' and 'Is landslide risk increasing near me?'
    Strictly translates complex risk formulas and ML predictions into plain-language citizen status:
    LOW (Green), MODERATE (Yellow), HIGH (Orange), CRITICAL (Red).
    Exposes ZERO floating point probabilities, SHAP values, or technical model parameters.
    """
    return await citizen_service.evaluate_citizen_risk(
        session=db,
        latitude=latitude,
        longitude=longitude,
        location_id=location_id
    )


@router.get("/guidance", response_model=CitizenGuidanceResponse)
async def get_safety_guidance():
    """
    Answers: 'What should I do?'
    Returns actionable Before, During, and After landslide guidance,
    natural warning signs, and emergency Go-Bag supply checklists.
    """
    return citizen_service.get_citizen_guidance()


@router.get("/contacts", response_model=CitizenContactsResponse)
async def get_emergency_contacts():
    """
    Returns official emergency and disaster helpline directory for all 8 North Eastern Region states.
    """
    return citizen_service.get_citizen_contacts()


@router.get("/shelters", response_model=List[SafetyPointResponse])
async def list_safe_shelters(
    location_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns list of verified safe reference shelters, open grounds, and medical aid posts.
    """
    points = await public_safety_service.get_all_safety_points(db, location_id)
    return [SafetyPointResponse.model_validate(p) for p in points]


@router.post(
    "/sos",
    response_model=CitizenSOSResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit("citizen:sos", max_requests=10, window_seconds=120))]
)
async def create_sos_request(
    sos_in: CitizenSOSCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Dispatches an emergency SOS distress beacon.
    Suppresses rapid duplicates within a 120-second window.
    Supports authenticated citizens (linking user_id) or anonymous walk-ins (generating tracking_token).
    """
    user_id = current_user.id if current_user else None
    sos = await citizen_service.create_sos(db, sos_in, user_id=user_id)
    await db.commit()
    return CitizenSOSResponse.model_validate(sos)


@router.get("/sos/{sos_id}", response_model=CitizenSOSResponse)
async def get_sos_status(
    sos_id: str,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Tracks real-time progression of an SOS distress beacon.
    Enforces strict anti-IDOR authorization:
    - Allowed if caller presents valid X-SOS-Tracking-Token matching the beacon.
    - Allowed if authenticated user owns the beacon (user_id match).
    - Allowed if user has FIELD_RESPONDER, EXPERT, or ADMIN privileges.
    """
    sos = await citizen_service.get_sos_by_id(db, sos_id)
    if not sos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SOS beacon '{sos_id}' not found."
        )

    tracking_token = request.headers.get("X-SOS-Tracking-Token")
    is_authorized = False

    if tracking_token and sos.tracking_token and tracking_token == sos.tracking_token:
        is_authorized = True
    elif current_user:
        if sos.user_id and current_user.id == sos.user_id:
            is_authorized = True
        elif current_user.role.upper() in ["FIELD_RESPONDER", "EXPERT", "ADMIN"]:
            is_authorized = True

    if not is_authorized:
        logger.warning(f"IDOR attempt blocked: Unauthorized request for SOS {sos_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not authorized to view this emergency distress beacon."
        )

    return CitizenSOSResponse.model_validate(sos)


@router.patch("/sos/{sos_id}/status", response_model=CitizenSOSResponse)
async def update_sos_lifecycle_status(
    sos_id: str,
    update_in: CitizenSOSStatusUpdate,
    current_user: User = Depends(require_role(["FIELD_RESPONDER", "EXPERT", "ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates SOS lifecycle status.
    Strictly restricted to FIELD_RESPONDER, EXPERT, or ADMIN roles.
    """
    sos = await citizen_service.update_sos_status(db, sos_id, update_in)
    if not sos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SOS beacon '{sos_id}' not found."
        )
    await db.commit()
    logger.info(f"SOS {sos_id} status updated to {update_in.status} by User {current_user.id} ({current_user.role})")
    return CitizenSOSResponse.model_validate(sos)


@router.post(
    "/report",
    response_model=CitizenReportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit("citizen:report", max_requests=15, window_seconds=60))]
)
async def submit_citizen_report(
    category: str = Form(..., description="GROUND_CRACK, ROCKFALL, MUD_FLOW, LEANING_TREE_POLE, BLOCKED_ROAD_DRAIN, RUMBLING_SOUND, OTHER"),
    description: str = Form(..., min_length=5, max_length=2000),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    location_accuracy: Optional[float] = Form(None),
    location_name: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a community ground hazard observation with optional photo evidence.
    Enforces server-side signature checks, EXIF stripping, and thumbnail generation.
    Associates report with user profile if authenticated.
    """
    try:
        user_id = current_user.id if current_user else None
        report = await citizen_service.create_citizen_report(
            session=db,
            category=category,
            description=description,
            latitude=latitude,
            longitude=longitude,
            location_accuracy=location_accuracy,
            location_name=location_name,
            contact_phone=contact_phone,
            photo_file=photo,
            user_id=user_id,
        )
        await db.commit()
        return CitizenReportResponse.model_validate(report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit citizen report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while saving your report."
        )


@router.get("/reports", response_model=PaginatedResponse[CitizenReportResponse])
async def list_citizen_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists citizen hazard reports with pagination.
    Citizens only receive their own submitted reports.
    Field Responders, Experts, and Admins can view all community reports.
    """
    filter_user_id = current_user.id if current_user.role.upper() == "CITIZEN" else None

    reports, total = await citizen_service.get_citizen_reports(
        session=db,
        user_id=filter_user_id,
        status=status,
        page=page,
        page_size=page_size,
    )

    items = [CitizenReportResponse.model_validate(r) for r in reports]
    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/reports/{report_id}", response_model=CitizenReportResponse)
async def get_citizen_report_detail(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves verification status and details of a submitted citizen report.
    Validates resource ownership to prevent IDOR snooping.
    """
    report = await citizen_service.get_citizen_report_by_id(db, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found."
        )

    if current_user.role.upper() == "CITIZEN" and report.user_id != current_user.id:
        logger.warning(f"IDOR report access blocked: User {current_user.id} tried to read report {report_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only view your own submitted reports."
        )

    return CitizenReportResponse.model_validate(report)
