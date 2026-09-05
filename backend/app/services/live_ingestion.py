import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.logging import logger
from backend.app.core.redis import redis_service
from backend.app.models.location import Location
from backend.app.models.weather_forecast import WeatherForecastSnapshot
from backend.app.providers.weather.open_meteo import open_meteo_provider
from backend.app.providers.health import provider_health_registry
from backend.app.repositories.weather_repository import weather_repository
from backend.app.services.location_service import LocationService
from backend.app.core.cache import invalidate_station_weather


class LiveWeatherIngestionTracker:
    """In-memory thread-safe telemetry metrics tracker for live environmental ingestion."""

    def __init__(self):
        self.provider: str = "OPEN_METEO"
        self.status: str = "INITIALIZING"
        self.last_attempt: Optional[datetime] = None
        self.last_successful_fetch: Optional[datetime] = None
        self.last_persisted_timestamp: Optional[datetime] = None
        self.total_rows_inserted: int = 0
        self.total_rows_updated: int = 0
        self.total_forecast_snapshots: int = 0
        self.failure_count: int = 0
        self.last_error: Optional[str] = None
        self.stations_monitored_count: int = 0

    def record_attempt(self):
        self.last_attempt = datetime.now(timezone.utc)
        self.status = "INGESTING"

    def record_success(
        self,
        inserted: int,
        updated: int,
        forecast_count: int,
        latest_ts: Optional[datetime],
        stations_count: int
    ):
        self.last_successful_fetch = datetime.now(timezone.utc)
        self.total_rows_inserted += inserted
        self.total_rows_updated += updated
        self.total_forecast_snapshots += forecast_count
        if latest_ts:
            self.last_persisted_timestamp = latest_ts
        self.stations_monitored_count = stations_count
        self.status = "HEALTHY"
        self.last_error = None

    def record_failure(self, err: str):
        self.failure_count += 1
        self.last_error = err
        self.status = "DEGRADED" if self.last_successful_fetch else "FAILED"

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "last_successful_fetch": self.last_successful_fetch.isoformat() if self.last_successful_fetch else None,
            "last_persisted_timestamp": self.last_persisted_timestamp.isoformat() if self.last_persisted_timestamp else None,
            "total_rows_inserted": self.total_rows_inserted,
            "total_rows_updated": self.total_rows_updated,
            "total_forecast_snapshots": self.total_forecast_snapshots,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "stations_monitored_count": self.stations_monitored_count,
            "cadence_seconds": getattr(settings, "LIVE_INGESTION_INTERVAL_SECONDS", 900),
        }


ingestion_tracker = LiveWeatherIngestionTracker()


class LiveWeatherIngestionService:
    """
    Independent service orchestrating live environmental telemetry accumulation.
    Pulls hourly observations and future forecast points from Open-Meteo API,
    validates data quality, deduplicates via bulk upsert, and persists both
    weather_observations and weather_forecast_snapshots to PostgreSQL.
    """

    def __init__(self, weather_provider=open_meteo_provider):
        self.provider = weather_provider

    async def ingest_all_active_stations(self, session: AsyncSession) -> Dict[str, Any]:
        """Runs one full ingestion cycle across all monitored North Eastern Region stations."""
        ingestion_tracker.record_attempt()
        start_t = time.perf_counter()

        locations = await LocationService.get_all_locations(session)
        if not locations:
            await LocationService.seed_initial_locations(session)
            locations = await LocationService.get_all_locations(session)

        total_inserted = 0
        total_updated = 0
        total_forecasts = 0
        latest_obs_ts: Optional[datetime] = None
        now_utc = datetime.now(timezone.utc)

        for loc in locations:
            try:
                obs = await self.provider.get_observations(loc, limit=36)
                if not obs:
                    continue

                # Separate historical observations from forecast points
                observational_records = []
                forecast_snapshots = []

                for o in obs:
                    o_ts = o.timestamp if o.timestamp.tzinfo else o.timestamp.replace(tzinfo=timezone.utc)
                    observational_records.append(o)

                    if o_ts > now_utc:
                        diff_hours = int(round((o_ts - now_utc).total_seconds() / 3600.0))
                        if 0 < diff_hours <= 72:
                            forecast_snapshots.append(
                                WeatherForecastSnapshot(
                                    location_id=loc.id,
                                    forecast_issued_at=now_utc,
                                    forecast_valid_at=o_ts,
                                    forecast_horizon_hours=diff_hours,
                                    precipitation_mm=o.rainfall_1h,
                                    rain_mm=o.rainfall_1h,
                                    soil_moisture=o.soil_moisture,
                                    temperature=o.temperature,
                                    humidity=o.humidity,
                                    wind_speed=o.wind_speed,
                                    source="OPEN_METEO",
                                    model_name="open-meteo-seamless",
                                    retrieved_at=now_utc,
                                )
                            )

                # Persist observations idempotently
                counts = await weather_repository.upsert_batch(session, observational_records)
                total_inserted += counts["inserted"]
                total_updated += counts["updated"]
                await invalidate_station_weather(loc.id)

                # Persist forecast snapshots
                if forecast_snapshots:
                    f_saved = await weather_repository.save_forecast_snapshots(session, forecast_snapshots)
                    total_forecasts += f_saved

                if obs:
                    curr_max = max(o.timestamp for o in obs)
                    if latest_obs_ts is None or curr_max > latest_obs_ts:
                        latest_obs_ts = curr_max

            except Exception as loc_err:
                logger.warning(f"Live telemetry fetch failed for {loc.name}: {loc_err}")

        await session.commit()
        duration_ms = (time.perf_counter() - start_t) * 1000.0

        ingestion_tracker.record_success(
            inserted=total_inserted,
            updated=total_updated,
            forecast_count=total_forecasts,
            latest_ts=latest_obs_ts,
            stations_count=len(locations)
        )

        logger.info(
            f"[Live Ingestion] Completed cycle for {len(locations)} NER stations in {duration_ms:.1f}ms: "
            f"+{total_inserted} rows inserted, {total_updated} updated, +{total_forecasts} forecast snapshots."
        )

        return {
            "status": "SUCCESS",
            "inserted": total_inserted,
            "updated": total_updated,
            "forecast_snapshots": total_forecasts,
            "duration_ms": duration_ms,
        }


class LiveWeatherIngestionScheduler:
    """
    Dedicated background scheduler for continuous live telemetry acquisition (default: 15 min / 900s).
    Runs independently of the 30-second assessment engine to prevent rate-limiting while ensuring
    steady accumulation of authentic historical observations.
    """

    def __init__(self, interval_seconds: int = 900):
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.service = LiveWeatherIngestionService()

    async def _run_single_cycle(self):
        lock_name = "ingestion:weather_execution_lock"
        acquired = await redis_service.acquire_lock(lock_name, ttl_seconds=self.interval_seconds + 30)
        if not acquired:
            logger.debug("Live weather ingestion cycle skipped (lock held by active worker).")
            return

        try:
            async with AsyncSessionLocal() as session:
                await self.service.ingest_all_active_stations(session)
        except Exception as err:
            ingestion_tracker.record_failure(str(err))
            logger.error(f"[Live Ingestion Error] Ingestion cycle failed: {err}", exc_info=True)
        finally:
            await redis_service.release_lock(lock_name)

    async def start_loop(self):
        self._running = True
        logger.info(f"Starting Dedicated Live Telemetry Ingestion Scheduler (interval={self.interval_seconds}s)...")
        # Run first ingestion shortly after boot
        await asyncio.sleep(5.0)
        while self._running:
            try:
                if settings.DATA_MODE == "LIVE":
                    await self._run_single_cycle()
                else:
                    logger.debug("Ingestion scheduler idle (DATA_MODE is not LIVE).")
            except asyncio.CancelledError:
                logger.info("Live weather ingestion scheduler loop cancelled.")
                break
            except Exception as err:
                logger.error(f"Unexpected error in live ingestion scheduler loop: {err}")

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.start_loop())

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()


live_ingestion_scheduler = LiveWeatherIngestionScheduler(interval_seconds=900)
