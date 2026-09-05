from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.providers.health import provider_health_registry
from backend.app.core.config import settings
from backend.app.api.deps import get_db, require_role
from backend.app.models.user import User
from backend.app.services.data_retention_service import data_retention_service

router = APIRouter()


@router.get("/data-sources")
async def get_data_sources_health() -> Dict[str, Any]:
    """
    Returns runtime operational health, latency metrics, and data provenance
    for all registered environmental, DEM terrain, and historical data providers.
    """
    providers = [p.to_dict() for p in provider_health_registry.get_all_health()]

    return {
        "data_mode": settings.DATA_MODE,
        "engine_version": settings.ENGINE_VERSION,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "providers": providers,
        "caching": {
            "status": "OPERATIONAL",
            "type": "REDIS_OR_IN_MEMORY_TTL",
            "ttl_seconds": settings.WEATHER_CACHE_TTL_SECONDS
        },
        "freshness_policy": {
            "weather_max_minutes": settings.DATA_FRESHNESS_WEATHER_MINUTES,
            "soil_moisture_max_minutes": settings.DATA_FRESHNESS_SOIL_MOISTURE_MINUTES,
        }
    }


@router.get("/ingestion-health")
async def get_ingestion_health() -> Dict[str, Any]:
    """
    Returns continuous live environmental data ingestion health metrics:
    provider, last attempt, last success, last persisted timestamp, rows inserted/updated,
    forecast snapshots saved, and failure counts.
    """
    from backend.app.services.live_ingestion import ingestion_tracker
    return {
        "status": "success",
        "ingestion": ingestion_tracker.get_metrics(),
        "data_mode": settings.DATA_MODE,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/ingestion/trigger")
async def trigger_manual_live_ingestion(
    current_user: User = Depends(require_role(["EXPERT", "ADMIN"]))
):
    """
    Manually triggers an on-demand live environmental ingestion cycle across all NER stations.
    Restricted to EXPERT or ADMIN roles.
    """
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.services.live_ingestion import LiveWeatherIngestionService

    service = LiveWeatherIngestionService()
    async with AsyncSessionLocal() as session:
        result = await service.ingest_all_active_stations(session)

    return {
        "message": "Manual live ingestion cycle completed successfully",
        "triggered_by": current_user.email,
        "result": result
    }


@router.post("/maintenance/retention")
async def trigger_retention_policy_cleanup(
    current_user: User = Depends(require_role(["ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes automated database retention pruning:
    - Prunes revoked/expired refresh tokens > 7 days
    - Prunes stale AI audit logs > 90 days
    - Prunes old dispatch notification logs > 180 days
    - Prunes old alert acknowledgments > 90 days
    Historical environmental observations are strictly preserved for ML retraining.
    Restricted to ADMIN role.
    """
    result = await data_retention_service.execute_retention_policy(db)
    return {
        "status": "success",
        "message": "Data retention policy executed successfully.",
        "executed_by": current_user.email,
        "details": result,
    }
