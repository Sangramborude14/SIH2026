from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_db
from backend.app.models.location import Location
from backend.app.models.event import DisasterEvent
from backend.app.models.risk import RiskAssessment
from backend.app.schemas.dashboard import DashboardSummaryResponse
from backend.app.engine.pipeline import disaster_engine
from backend.app.core.config import settings
from backend.app.core.cache import cache, CacheKeys
from backend.app.core.logging import logger

router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    Get consolidated KPI counters and situational overview for the Central Command Center.
    Cached under 'sih:gis:summary' (TTL 30s) with subquery batch execution to eliminate N+1 overhead.
    """
    cache_key = CacheKeys.gis_summary()
    cached_data = await cache.get(cache_key)
    if cached_data and isinstance(cached_data, dict):
        try:
            return DashboardSummaryResponse(**cached_data)
        except Exception:
            pass

    # 1. Total Locations
    loc_count_res = await db.execute(select(func.count(Location.id)))
    total_locations = loc_count_res.scalar() or 0

    if total_locations == 0:
        from backend.app.services.location_service import LocationService
        await LocationService.seed_initial_locations(db)
        loc_count_res = await db.execute(select(func.count(Location.id)))
        total_locations = loc_count_res.scalar() or 0

    # 2. Active & Critical Events
    active_events_query = select(DisasterEvent).where(DisasterEvent.status != "RESOLVED")
    active_res = await db.execute(active_events_query)
    active_events = list(active_res.scalars().all())
    active_events_count = len(active_events)
    critical_events_count = sum(1 for e in active_events if e.status == "CRITICAL" or e.severity == "CRITICAL")

    # 3. Retrieve latest risk assessments across all locations in a SINGLE query
    subq = (
        select(
            RiskAssessment.location_id,
            func.max(RiskAssessment.timestamp).label("max_ts")
        )
        .group_by(RiskAssessment.location_id)
        .subquery()
    )
    stmt = (
        select(RiskAssessment)
        .join(
            subq,
            and_(
                RiskAssessment.location_id == subq.c.location_id,
                RiskAssessment.timestamp == subq.c.max_ts
            )
        )
    )
    latest_risks = list((await db.execute(stmt)).scalars().all())

    highest_score = 0.0
    highest_level = "LOW"
    high_count = 0
    mod_count = 0
    low_count = 0
    latest_ts = datetime.now(timezone.utc)

    evaluated_locations = set()
    for risk in latest_risks:
        evaluated_locations.add(risk.location_id)
        risk_ts = risk.timestamp
        if risk_ts.tzinfo is None:
            risk_ts = risk_ts.replace(tzinfo=timezone.utc)
        if latest_ts is None or risk_ts > latest_ts:
            latest_ts = risk_ts
        score = risk.risk_score
        level = risk.risk_level.upper()

        if score > highest_score:
            highest_score = score
            highest_level = level

        if level in ["CRITICAL", "HIGH"]:
            high_count += 1
        elif level == "MODERATE":
            mod_count += 1
        else:
            low_count += 1

    # Remaining un-evaluated locations counted as LOW
    low_count += max(0, total_locations - len(evaluated_locations))

    response_obj = DashboardSummaryResponse(
        active_events_count=active_events_count,
        critical_events_count=critical_events_count,
        high_risk_count=high_count,
        moderate_risk_count=mod_count,
        low_risk_count=low_count,
        total_monitored_locations=total_locations,
        highest_risk_score=round(highest_score, 1),
        highest_risk_level=highest_level,
        last_engine_run=latest_ts,
        data_sources_status="OPERATIONAL (SIMULATED / NER STATIONS)"
    )

    # Cache response for 30s
    try:
        await cache.set(cache_key, response_obj.model_dump(mode="json"), ttl_seconds=30)
    except Exception as e:
        logger.debug(f"Cache write error for summary: {e}")

    return response_obj
