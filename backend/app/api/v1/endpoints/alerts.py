from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db, require_role, check_rate_limit
from backend.app.models.user import User
from backend.app.services.cap_service import cap_service
from backend.app.services.sitrep_service import sitrep_service
from backend.app.services.multichannel_service import multichannel_service
from backend.app.schemas.alerting import (
    CAPAlertFeedItem,
    MultiChannelPayloadPackage,
    BroadcastTriggerRequest,
    BroadcastTriggerResponse,
    DispatchLogResponse,
    SituationReportDetail,
    SitRepGenerateRequest,
)
from backend.app.core.logging import logger

router = APIRouter()


@router.get("/cap.xml")
async def get_cap_xml_feed(
    event_id: Optional[str] = Query(None, description="Optional single event ID"),
    db: AsyncSession = Depends(get_db)
):
    """Returns compliant Common Alerting Protocol (CAP v1.2 / OASIS / ITU X.1303) XML feed."""
    xml_content = await cap_service.generate_cap_xml(db, event_id)
    return Response(content=xml_content, media_type="application/xml")


@router.get("/cap.json", response_model=List[CAPAlertFeedItem])
async def get_cap_json_feed(db: AsyncSession = Depends(get_db)):
    """Returns structured JSON feed of all active CAP v1.2 early warnings."""
    return await cap_service.generate_cap_json(db)


@router.get("/{event_id}/cap.xml")
async def get_single_event_cap_xml(event_id: str, db: AsyncSession = Depends(get_db)):
    """Returns CAP v1.2 XML for a specific active disaster event."""
    xml_content = await cap_service.generate_cap_xml(db, event_id)
    return Response(content=xml_content, media_type="application/xml")


@router.get("/{event_id}/payloads", response_model=MultiChannelPayloadPackage)
async def preview_multichannel_payloads(event_id: str, db: AsyncSession = Depends(get_db)):
    """Previews formatted payloads for SMS, WhatsApp, Email, Push, and CAP."""
    pkg = await multichannel_service.build_payload_package(db, event_id)
    if not pkg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disaster event '{event_id}' not found."
        )
    return pkg


@router.get("/broadcasts", response_model=List[DispatchLogResponse])
async def list_broadcast_logs(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves chronological multi-channel notification dispatch logs."""
    logs = await multichannel_service.get_dispatch_logs(db, limit)
    return [DispatchLogResponse.model_validate(l) for l in logs]


from fastapi import BackgroundTasks
from backend.app.core.database import AsyncSessionLocal
from backend.app.services.broadcast_service import BroadcastService
from backend.app.schemas.alerting import (
    CAPAlertFeedItem,
    MultiChannelPayloadPackage,
    BroadcastTriggerRequest,
    BroadcastTriggerResponse,
    DispatchLogResponse,
    SituationReportDetail,
    SitRepGenerateRequest,
    BroadcastCreate,
    BroadcastStatusResponse,
    BroadcastCreateResponse,
)


@router.post(
    "/broadcast",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit("alerts:broadcast", max_requests=5, window_seconds=60))]
)
async def create_and_dispatch_broadcast(
    req: BroadcastCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates an authorized emergency broadcast and schedules asynchronous dispatch.
    Strictly restricted to users with ADMIN role.
    """
    broadcast = await BroadcastService.create_broadcast(db, req)
    await db.commit()
    
    # Schedule background notification delivery
    background_tasks.add_task(
        BroadcastService.process_broadcast_background,
        broadcast.id,
        AsyncSessionLocal,
    )

    channels = req.channels or ["IN_APP", "SMS"]
    return {
        "id": broadcast.id,
        "status": "ACCEPTED",
        "message": f"Emergency broadcast accepted. Queued delivery across {', '.join(channels)}.",
        "recipient_count": len(broadcast.notifications) if broadcast.notifications else 6,
        "channels": channels,
        "created_at": broadcast.created_at,
    }


@router.get("/broadcasts/{broadcast_id}", response_model=BroadcastStatusResponse)
@router.get("/broadcasts/{broadcast_id}/status", response_model=BroadcastStatusResponse)
async def get_broadcast_delivery_status(
    broadcast_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieves real-time recipient delivery breakdown (In-App, SMS, and FCM push sent/failed/pending)."""
    return await BroadcastService.get_broadcast_status(db, broadcast_id)



@router.get("/sitrep/{event_id}", response_model=SituationReportDetail)
async def get_or_generate_sitrep(
    event_id: str,
    reporting_officer: str = Query("Command Duty Officer"),
    db: AsyncSession = Depends(get_db)
):
    """Generates or retrieves formal NDMA/SDRF Situation Report (SitRep) for an event."""
    sitrep = await sitrep_service.generate_sitrep(db, event_id, reporting_officer)
    if not sitrep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disaster event '{event_id}' not found."
        )
    await db.commit()
    return sitrep


@router.post("/sitrep/generate", response_model=SituationReportDetail, status_code=status.HTTP_201_CREATED)
async def generate_formal_sitrep(
    req: SitRepGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generates, formats, and persists an official NDMA/SDRF Situation Report."""
    sitrep = await sitrep_service.generate_sitrep(db, req.event_id, req.reporting_officer or "Command Duty Officer")
    if not sitrep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disaster event '{req.event_id}' not found."
        )
    await db.commit()
    return sitrep
