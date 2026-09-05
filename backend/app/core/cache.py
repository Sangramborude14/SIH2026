"""
Cache facade and compatibility layer.
Re-exports the unified RedisService instance, standardized namespaced cache keys (sih:*),
and granular selective invalidation functions.
"""

from typing import Optional, Any
from backend.app.core.redis import redis_service, RedisService, InMemoryTTLCache, rate_limiter
from backend.app.core.logging import logger

# Global singleton alias
cache: RedisService = redis_service


class CacheKeys:
    """Standardized Redis cache key generators using 'sih:' namespace."""

    @staticmethod
    def weather_latest(location_id: str) -> str:
        return f"sih:weather:{location_id}:latest"

    @staticmethod
    def weather_live(location_id: str) -> str:
        # Backward compatibility alias
        return f"sih:weather:{location_id}:latest"

    @staticmethod
    def weather_coords(lat: float, lon: float) -> str:
        return f"sih:weather:coords:{lat:.4f}:{lon:.4f}"

    @staticmethod
    def weather_forecast(location_id: str) -> str:
        return f"sih:weather:forecast:{location_id}"

    @staticmethod
    def risk_station_24h(location_id: str) -> str:
        return f"sih:risk:station:{location_id}:24h"

    @staticmethod
    def gis_summary() -> str:
        return "sih:gis:summary"

    @staticmethod
    def gis_map() -> str:
        return "sih:gis:map"

    @staticmethod
    def alerts_summary() -> str:
        return "sih:alerts:summary"

    @staticmethod
    def citizen_risk(lat: Optional[float] = None, lon: Optional[float] = None, location_id: Optional[str] = None) -> str:
        if location_id:
            return f"sih:citizen:risk:loc:{location_id}"
        if lat is not None and lon is not None:
            return f"sih:citizen:risk:coords:{lat:.3f}:{lon:.3f}"
        return "sih:citizen:risk:default"

    @staticmethod
    def model_status() -> str:
        return "sih:model:status"

    @staticmethod
    def provider_health() -> str:
        return "sih:provider:health"

    @staticmethod
    def bhoonidhi_auth_token(user_id: str) -> str:
        return f"sih:bhoonidhi:auth_token:{user_id}"

    @staticmethod
    def bhoonidhi_scenes(collection: str, location_id: str, limit: int) -> str:
        return f"sih:bhoonidhi:scenes:{collection}:{location_id}:{limit}"

    @staticmethod
    def terrain_static(location_id: str) -> str:
        return f"sih:terrain:static:{location_id}"

    @staticmethod
    def historical_incident(incident_id: str) -> str:
        return f"sih:historical:incident:{incident_id}"

    @staticmethod
    def ai_explanation(location_id: str, assessment_id: str, agent_type: str) -> str:
        return f"sih:ai:explanation:{location_id}:{assessment_id}:{agent_type}"


async def invalidate_station_risk(location_id: str) -> None:
    """
    Granularly invalidates risk-affected cache entries for a station.
    Strictly avoids global cache flushes (FLUSHALL/FLUSHDB).
    """
    try:
        await cache.delete(CacheKeys.risk_station_24h(location_id))
        await cache.delete(CacheKeys.gis_summary())
        await cache.delete(CacheKeys.gis_map())
        await cache.delete(CacheKeys.alerts_summary())
        await cache.delete(f"sih:citizen:risk:loc:{location_id}")
        logger.debug(f"Granular risk cache invalidated for station {location_id}")
    except Exception as e:
        logger.warning(f"Error during granular risk cache invalidation for {location_id}: {e}")


async def invalidate_station_weather(location_id: str) -> None:
    """
    Granularly invalidates weather cache entries for a station when fresh telemetry arrives.
    """
    try:
        await cache.delete(CacheKeys.weather_latest(location_id))
        await cache.delete(CacheKeys.weather_forecast(location_id))
        logger.debug(f"Granular weather cache invalidated for station {location_id}")
    except Exception as e:
        logger.warning(f"Error during granular weather cache invalidation for {location_id}: {e}")


__all__ = [
    "cache",
    "redis_service",
    "RedisService",
    "InMemoryTTLCache",
    "rate_limiter",
    "CacheKeys",
    "invalidate_station_risk",
    "invalidate_station_weather",
]
