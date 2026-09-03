from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.weather import WeatherObservation
from backend.app.models.weather_forecast import WeatherForecastSnapshot
from backend.app.repositories.base import IRepository



class IWeatherRepository(IRepository[WeatherObservation]):
    """Repository interface for meteorological, precipitation, and soil moisture telemetry."""
    pass


class SqlAlchemyWeatherRepository(IWeatherRepository):
    """SQLAlchemy/PostgreSQL implementation of WeatherRepository."""

    async def get_by_id(self, session: AsyncSession, entity_id: str) -> Optional[WeatherObservation]:
        stmt = select(WeatherObservation).where(WeatherObservation.id == entity_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def list_all(self, session: AsyncSession) -> List[WeatherObservation]:
        stmt = select(WeatherObservation).order_by(WeatherObservation.timestamp.desc()).limit(100)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_location(
        self,
        session: AsyncSession,
        location_id: str
    ) -> Optional[WeatherObservation]:
        """Fetches the most recent observation for a location."""
        stmt = (
            select(WeatherObservation)
            .where(WeatherObservation.location_id == location_id)
            .order_by(WeatherObservation.timestamp.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_history_for_location(
        self,
        session: AsyncSession,
        location_id: str,
        limit: int = 48,
        since: Optional[datetime] = None
    ) -> List[WeatherObservation]:
        """Fetches time-series telemetry ordered chronologically for trend and anomaly calculations."""
        stmt = (
            select(WeatherObservation)
            .where(WeatherObservation.location_id == location_id)
        )
        if since:
            stmt = stmt.where(WeatherObservation.timestamp >= since)
        stmt = stmt.order_by(WeatherObservation.timestamp.asc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def save(self, session: AsyncSession, entity: WeatherObservation) -> WeatherObservation:
        session.add(entity)
        await session.flush()
        return entity

    async def save_batch(
        self,
        session: AsyncSession,
        entities: List[WeatherObservation]
    ) -> List[WeatherObservation]:
        session.add_all(entities)
        await session.flush()
        return entities

    async def upsert_batch(
        self,
        session: AsyncSession,
        entities: List[WeatherObservation]
    ) -> Dict[str, int]:
        """
        Idempotent bulk upsert for weather observations.
        Prevents duplicate rows on (location_id, timestamp, source, observation_type).
        Updates metrics if record exists, otherwise inserts new row.
        """
        if not entities:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        loc_ids = list({e.location_id for e in entities})
        timestamps = [e.timestamp for e in entities]
        min_ts = min(timestamps)
        max_ts = max(timestamps)

        stmt = (
            select(WeatherObservation)
            .where(WeatherObservation.location_id.in_(loc_ids))
            .where(WeatherObservation.timestamp >= min_ts)
            .where(WeatherObservation.timestamp <= max_ts)
        )
        existing_res = await session.execute(stmt)
        existing_map = {
            (o.location_id, o.timestamp, o.source, o.observation_type): o
            for o in existing_res.scalars().all()
        }

        inserted = 0
        updated = 0
        for e in entities:
            key = (e.location_id, e.timestamp, e.source, e.observation_type)
            if key in existing_map:
                curr = existing_map[key]
                if e.rainfall_1h is not None: curr.rainfall_1h = e.rainfall_1h

                if e.rainfall_6h is not None: curr.rainfall_6h = e.rainfall_6h
                if e.rainfall_24h is not None: curr.rainfall_24h = e.rainfall_24h
                if e.soil_moisture is not None: curr.soil_moisture = e.soil_moisture
                if e.temperature is not None: curr.temperature = e.temperature
                if e.humidity is not None: curr.humidity = e.humidity
                if e.pressure is not None: curr.pressure = e.pressure
                if e.wind_speed is not None: curr.wind_speed = e.wind_speed
                if e.wind_direction is not None: curr.wind_direction = e.wind_direction
                if e.quality_score is not None: curr.quality_score = e.quality_score
                if e.freshness_status is not None: curr.freshness_status = e.freshness_status
                if e.retrieved_at is not None: curr.retrieved_at = e.retrieved_at
                updated += 1

            else:
                session.add(e)
                existing_map[key] = e
                inserted += 1

        await session.flush()
        return {"inserted": inserted, "updated": updated, "skipped": 0}

    async def save_forecast_snapshots(
        self,
        session: AsyncSession,
        snapshots: List[WeatherForecastSnapshot]
    ) -> int:
        """Persists weather forecast snapshots."""
        if not snapshots:
            return 0
        session.add_all(snapshots)
        await session.flush()
        return len(snapshots)


    async def delete(self, session: AsyncSession, entity_id: str) -> bool:
        obs = await self.get_by_id(session, entity_id)
        if obs:
            await session.delete(obs)
            await session.flush()
            return True
        return False


weather_repository = SqlAlchemyWeatherRepository()
