import asyncio
import time
from datetime import datetime, timezone
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.redis import redis_service
from backend.app.core.logging import logger
from backend.app.engine.pipeline import disaster_engine
from backend.app.engine.status import engine_status_tracker
from backend.app.services.location_service import LocationService


class BackgroundEngineScheduler:
    """
    Automated Background Assessment Engine Scheduler.
    Executes live multi-signal landslide assessments periodically (default: 30s)
    using Upstash Redis distributed locking to prevent duplicate concurrent runs across workers.
    """

    def __init__(self, interval_seconds: int = 30):
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: asyncio.Task = None

    async def _run_single_cycle(self):
        lock_name = "engine:execution_lock"
        acquired = await redis_service.acquire_lock(lock_name, ttl_seconds=self.interval_seconds + 15)
        if not acquired:
            logger.debug("Background engine scheduler cycle skipped (lock held by active worker).")
            return

        start_t = time.perf_counter()
        engine_status_tracker.mark_running()
        try:
            async with AsyncSessionLocal() as session:
                # 1. Ensure monitoring locations exist
                await LocationService.seed_initial_locations(session)

                # 2. Run multi-signal engine pipeline
                result = await disaster_engine.run_pipeline(session=session, force_fresh=False)
                await session.commit()

                duration_ms = (time.perf_counter() - start_t) * 1000.0
                engine_status_tracker.record_success(
                    locations_count=result.locations_evaluated,
                    active_events=result.active_events_count,
                    highest_score=result.highest_risk_score,
                    highest_level=result.highest_risk_level,
                    duration_ms=duration_ms
                )
                logger.info(
                    f"[Scheduled Engine] Evaluated {result.locations_evaluated} stations in {duration_ms:.1f}ms. "
                    f"Highest: {result.highest_risk_score} ({result.highest_risk_level}), Active Events: {result.active_events_count}"
                )
        except Exception as err:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            engine_status_tracker.record_error(str(err), duration_ms=duration_ms)
            logger.error(f"[Scheduled Engine Error] Cycle failed: {err}", exc_info=True)
        finally:
            await redis_service.release_lock(lock_name)

    async def start_loop(self):
        """Main scheduled execution loop."""
        self._running = True
        logger.info(f"Starting Background Disaster Engine Scheduler (interval={self.interval_seconds}s)...")
        # Run first cycle shortly after startup
        await asyncio.sleep(2.0)
        while self._running:
            try:
                await self._run_single_cycle()
            except asyncio.CancelledError:
                logger.info("Background Disaster Engine Scheduler loop cancelled.")
                break
            except Exception as err:
                logger.error(f"Unexpected error in background engine scheduler loop: {err}")

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


background_engine_scheduler = BackgroundEngineScheduler(
    interval_seconds=getattr(settings, "ENGINE_ASSESSMENT_INTERVAL_SECONDS", 30)
)
from backend.app.services.live_ingestion import live_ingestion_scheduler  # re-export
