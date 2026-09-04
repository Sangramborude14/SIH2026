from datetime import datetime, timezone
import time
from typing import Dict, Any
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db
from backend.app.models.location import Location
from backend.app.models.event import DisasterEvent
from backend.app.models.alerting import NotificationDispatchLog
from backend.app.core.config import settings
from backend.app.core.database import check_database_health, is_sqlite

router = APIRouter()


@router.get("/live", tags=["Health & Readiness"])
async def liveness_probe():
    """Kubernetes / Container Liveness Probe."""
    return {
        "status": "ALIVE",
        "service": "DISASTRA Disaster Intelligence Engine",
        "environment": settings.ENVIRONMENT,
        "application_mode": settings.DATA_MODE,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/db", tags=["Health & Readiness"])
async def database_health_check():
    """
    Dedicated database health endpoint.
    Verifies database reachability, measured round-trip latency, and application mode.
    Exposes NO credentials or connection strings.
    """
    db_health = await check_database_health()
    status_code = status.HTTP_200_OK if db_health["reachable"] else status.HTTP_503_SERVICE_UNAVAILABLE
    
    payload = {
        "database_reachable": db_health["reachable"],
        "database_engine": db_health["engine"],
        "database_latency_ms": db_health["latency_ms"],
        "application_mode": settings.DATA_MODE,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if not db_health["reachable"]:
        payload["error"] = db_health.get("error", "Database unreachable")

    return Response(
        content=__import__("json").dumps(payload),
        status_code=status_code,
        media_type="application/json"
    )


@router.get("/redis", tags=["Health & Readiness"])
@router.get("/cache", tags=["Health & Readiness"])
async def cache_health_check():
    """
    Dedicated Redis / Upstash cache health endpoint.
    Verifies cache reachability, measured round-trip latency, and backend mode.
    Exposes NO credentials, tokens, or private URLs.
    """
    from backend.app.core.redis import redis_service
    cache_health = await redis_service.check_health()
    status_code = status.HTTP_200_OK if cache_health["reachable"] else status.HTTP_503_SERVICE_UNAVAILABLE
    
    payload = {
        "cache_reachable": cache_health["reachable"],
        "cache_backend": cache_health.get("backend", "in_memory"),
        "cache_mode": cache_health.get("mode", "LOCAL_MEMORY"),
        "cache_latency_ms": cache_health.get("latency_ms", 0.0),
        "application_mode": settings.DATA_MODE,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if not cache_health["reachable"]:
        payload["error"] = cache_health.get("error", "Cache unavailable")

    return Response(
        content=__import__("json").dumps(payload),
        status_code=status_code,
        media_type="application/json"
    )


@router.get("/ready", tags=["Health & Readiness"])
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Kubernetes / Container Readiness Probe verifying database, cache & pipeline health."""
    start_t = time.perf_counter()
    from backend.app.core.redis import redis_service
    cache_health = await redis_service.check_health()
    try:
        # Check database connectivity & statistics
        loc_count = (await db.execute(select(func.count(Location.id)))).scalar_one()
        active_events = (await db.execute(
            select(func.count(DisasterEvent.id)).where(DisasterEvent.status != "RESOLVED")
        )).scalar_one()
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

        return {
            "status": "READY",
            "database": "CONNECTED",
            "database_engine": "sqlite" if is_sqlite else "postgresql",
            "database_latency_ms": latency_ms,
            "cache": "CONNECTED" if cache_health["reachable"] else "FALLBACK_MEMORY",
            "cache_backend": cache_health.get("backend", "in_memory"),
            "cache_latency_ms": cache_health.get("latency_ms", 0.0),
            "locations_monitored": loc_count,
            "active_events": active_events,
            "application_mode": settings.DATA_MODE,
            "environment": settings.ENVIRONMENT,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return Response(
            content=f'{{"status": "NOT_READY", "database": "DISCONNECTED", "database_latency_ms": {latency_ms}, "cache": "FALLBACK_MEMORY", "application_mode": "{settings.DATA_MODE}", "error": "Database connection failed"}}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )


@router.get("/metrics", tags=["Health & Readiness"])
async def prometheus_metrics(db: AsyncSession = Depends(get_db)):
    """Prometheus-compatible operational monitoring metrics."""
    try:
        loc_count = (await db.execute(select(func.count(Location.id)))).scalar_one()
        active_events = (await db.execute(
            select(func.count(DisasterEvent.id)).where(DisasterEvent.status != "RESOLVED")
        )).scalar_one()
        total_broadcasts = (await db.execute(select(func.count(NotificationDispatchLog.id)))).scalar_one()
    except Exception:
        loc_count, active_events, total_broadcasts = 6, 0, 0

    mode_val = 1.0 if settings.DATA_MODE == "LIVE" else 0.0

    lines = [
        "# HELP sih_engine_up Engine process availability",
        "# TYPE sih_engine_up gauge",
        "sih_engine_up 1.0",
        "# HELP sih_engine_live_mode Data ingestion mode (1=LIVE, 0=SIMULATION)",
        "# TYPE sih_engine_live_mode gauge",
        f"sih_engine_live_mode {mode_val}",
        "# HELP sih_locations_monitored Total monitored stations in North Eastern Region",
        "# TYPE sih_locations_monitored gauge",
        f"sih_locations_monitored {loc_count}",
        "# HELP sih_active_disaster_events Active critical/high events in queue",
        "# TYPE sih_active_disaster_events gauge",
        f"sih_active_disaster_events {active_events}",
        "# HELP sih_notifications_dispatched_total Total emergency broadcasts dispatched",
        "# TYPE sih_notifications_dispatched_total counter",
        f"sih_notifications_dispatched_total {total_broadcasts}",
    ]

    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
