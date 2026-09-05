from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_db
from backend.app.core.cache import cache, CacheKeys
from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.models.risk import RiskAssessment
from backend.app.models.event import DisasterEvent
from backend.app.models.history import RiskAssessmentHistory
from backend.app.models.ml_forecast import LandslideForecastRecord
from backend.app.ml.registry.model_registry import model_registry

from backend.app.schemas.location import LocationResponse
from backend.app.schemas.weather import WeatherObservationResponse
from backend.app.schemas.risk import RiskAssessmentResponse
from backend.app.schemas.event import DisasterEventResponse
from backend.app.schemas.engine import EngineAssessmentResponse
from backend.app.schemas.dashboard import LocationMapItem, LocationInvestigationResponse, EventTimelineMilestone
from backend.app.schemas.scientific import (
    ScientificStationInvestigationResponse,
    RainfallAnalysisPackage,
    SoilMoistureAnalysisPackage,
    TimelineSeriesPoint,
)
from backend.app.services.location_service import LocationService
from backend.app.services.scientific_indicators_service import scientific_indicators_service
from backend.app.engine.pipeline import disaster_engine
from backend.app.engine.data_validator import data_validator

router = APIRouter()


@router.get("", response_model=List[LocationResponse])
async def list_locations(db: AsyncSession = Depends(get_db)):
    """
    List all monitored locations in the North Eastern Region.
    """
    locations = await LocationService.get_all_locations(db)
    return locations


@router.get("/map", response_model=List[LocationMapItem])
async def get_locations_for_map(db: AsyncSession = Depends(get_db)):
    """
    Returns all monitored stations enriched with current risk score,
    latest weather readings, and active disaster events for GIS map rendering.
    Cached under 'sih:gis:map' (TTL 30s) with consolidated batch queries.
    """
    cache_key = CacheKeys.gis_map()
    cached_map = await cache.get(cache_key)
    if cached_map and isinstance(cached_map, list):
        try:
            return [LocationMapItem(**item) for item in cached_map]
        except Exception:
            pass

    locations = await LocationService.get_all_locations(db)
    if not locations:
        return []

    loc_ids = [loc.id for loc in locations]

    # 1. Batch load latest active events
    active_events_stmt = (
        select(DisasterEvent)
        .where(and_(DisasterEvent.location_id.in_(loc_ids), DisasterEvent.status != "RESOLVED"))
        .order_by(DisasterEvent.detected_at.desc())
    )
    all_active_events = list((await db.execute(active_events_stmt)).scalars().all())
    event_map = {}
    for ev in all_active_events:
        if ev.location_id not in event_map:
            event_map[ev.location_id] = ev

    # 2. Batch load latest risk assessments
    subq_r = (
        select(RiskAssessment.location_id, func.max(RiskAssessment.timestamp).label("max_ts"))
        .where(RiskAssessment.location_id.in_(loc_ids))
        .group_by(RiskAssessment.location_id)
        .subquery()
    )
    latest_risks_stmt = (
        select(RiskAssessment)
        .join(subq_r, and_(RiskAssessment.location_id == subq_r.c.location_id, RiskAssessment.timestamp == subq_r.c.max_ts))
    )
    all_latest_risks = list((await db.execute(latest_risks_stmt)).scalars().all())
    risk_map = {r.location_id: r for r in all_latest_risks}

    # 3. Batch load latest weather observations
    subq_w = (
        select(WeatherObservation.location_id, func.max(WeatherObservation.timestamp).label("max_ts"))
        .where(WeatherObservation.location_id.in_(loc_ids))
        .group_by(WeatherObservation.location_id)
        .subquery()
    )
    latest_weather_stmt = (
        select(WeatherObservation)
        .join(subq_w, and_(WeatherObservation.location_id == subq_w.c.location_id, WeatherObservation.timestamp == subq_w.c.max_ts))
    )
    all_latest_weather = list((await db.execute(latest_weather_stmt)).scalars().all())
    weather_map = {w.location_id: w for w in all_latest_weather}

    # 4. Batch load recent ML forecasts
    fc_stmt = (
        select(LandslideForecastRecord)
        .where(LandslideForecastRecord.location_id.in_(loc_ids))
        .order_by(LandslideForecastRecord.prediction_timestamp.desc())
    )
    all_fc = list((await db.execute(fc_stmt)).scalars().all())
    fc_map = {}
    for fc in all_fc:
        if fc.location_id not in fc_map:
            fc_map[fc.location_id] = []
        if len(fc_map[fc.location_id]) < 3:
            fc_map[fc.location_id].append(fc)

    map_items: List[LocationMapItem] = []
    is_trained = model_registry.is_trained_model_active()

    for loc in locations:
        latest_risk = risk_map.get(loc.id)
        active_event = event_map.get(loc.id)
        latest_weather = weather_map.get(loc.id)
        fc_records = fc_map.get(loc.id, [])

        forecast_probs: dict = {}
        model_version = "2.0.0"
        model_status = "READY" if is_trained else "NOT_TRAINED"
        data_freshness = "FRESH"
        for fc in fc_records:
            h_key = fc.forecast_horizon.lower()
            if fc.probability is not None:
                forecast_probs[h_key] = fc.probability
            model_version = fc.model_version
            model_status = fc.model_status
            data_freshness = fc.data_freshness

        item = LocationMapItem(
            id=loc.id,
            name=loc.name,
            district=loc.district,
            state=loc.state,
            latitude=loc.latitude,
            longitude=loc.longitude,
            elevation=loc.elevation,
            slope_angle=loc.slope_angle,
            susceptibility_score=loc.susceptibility_score,
            risk_level=latest_risk.risk_level if latest_risk else "LOW",
            risk_score=latest_risk.risk_score if latest_risk else 10.0,
            confidence_score=latest_risk.confidence_score if latest_risk else 0.85,
            active_event=active_event is not None,
            event_id=active_event.id if active_event else None,
            event_status=active_event.status if active_event else None,
            event_severity=active_event.severity if active_event else None,
            rainfall_24h=latest_weather.rainfall_24h if latest_weather else 0.0,
            rainfall_1h=latest_weather.rainfall_1h if latest_weather else 0.0,
            soil_moisture=latest_weather.soil_moisture if latest_weather else 30.0,
            trend_direction="INCREASING" if (latest_weather and (latest_weather.rainfall_1h or 0) > 10) else "STABLE",
            last_updated=latest_risk.timestamp if latest_risk else datetime.now(timezone.utc),
            anomaly_score=round(min(1.0, (latest_weather.rainfall_24h or 0.0) / 150.0), 3) if latest_weather else 0.05,
            anomaly_level="SEVERE" if (latest_weather and (latest_weather.rainfall_24h or 0) >= 120) else ("ELEVATED" if (latest_weather and (latest_weather.rainfall_24h or 0) >= 60) else "NORMAL"),
            forecast_probabilities=forecast_probs,
            forecast_available=bool(forecast_probs),
            model_version=model_version,
            model_status=model_status,
            data_freshness=data_freshness,
        )
        map_items.append(item)

    try:
        await cache.set(cache_key, [item.model_dump(mode="json") for item in map_items], ttl_seconds=30)
    except Exception as e:
        logger.debug(f"Cache write error for map: {e}")

    return map_items



@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(location_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed station metadata.
    """
    location = await LocationService.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID '{location_id}' not found."
        )
    return location


@router.get("/{location_id}/assessment", response_model=EngineAssessmentResponse)
async def get_location_latest_assessment(location_id: str, db: AsyncSession = Depends(get_db)):
    """
    Evaluates or retrieves the latest structured risk assessment for a specific location.
    """
    location = await LocationService.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID '{location_id}' not found."
        )

    assessment_out, event, _ = await disaster_engine.evaluate_location(db, location)
    await db.commit()
    return disaster_engine.format_assessment_response(location, assessment_out, event)


@router.get("/{location_id}/assessment/history", response_model=List[RiskAssessmentResponse])
async def get_location_assessment_history(
    location_id: str,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves chronological assessment audit history for a specific station.
    """
    stmt = (
        select(RiskAssessment)
        .where(RiskAssessment.location_id == location_id)
        .order_by(RiskAssessment.timestamp.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/{location_id}/environment", response_model=List[WeatherObservationResponse])
async def get_location_environmental_series(
    location_id: str,
    limit: int = Query(48, ge=1, le=168),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves validated meteorological and pore water sensor series for a station.
    """
    stmt = (
        select(WeatherObservation)
        .where(WeatherObservation.location_id == location_id)
        .order_by(WeatherObservation.timestamp.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/{location_id}/investigate", response_model=LocationInvestigationResponse)
async def investigate_location(location_id: str, db: AsyncSession = Depends(get_db)):
    """
    360-degree investigation payload for a specific monitoring station.
    """
    location = await LocationService.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID '{location_id}' not found."
        )

    # 1. Latest Risk Assessment
    risk_stmt = (
        select(RiskAssessment)
        .where(RiskAssessment.location_id == location_id)
        .order_by(RiskAssessment.timestamp.desc())
        .limit(1)
    )
    risk_res = await db.execute(risk_stmt)
    latest_risk = risk_res.scalars().first()

    if not latest_risk:
        await disaster_engine.evaluate_location(db, location)
        await db.commit()
        risk_res = await db.execute(risk_stmt)
        latest_risk = risk_res.scalars().first()

    # 2. Active Event
    event_stmt = (
        select(DisasterEvent)
        .where(and_(DisasterEvent.location_id == location_id, DisasterEvent.status != "RESOLVED"))
        .order_by(DisasterEvent.detected_at.desc())
        .limit(1)
    )
    event_res = await db.execute(event_stmt)
    active_event = event_res.scalars().first()

    # 3. Weather History (past 48 points)
    weather_stmt = (
        select(WeatherObservation)
        .where(WeatherObservation.location_id == location_id)
        .order_by(WeatherObservation.timestamp.asc())
        .limit(48)
    )
    weather_res = await db.execute(weather_stmt)
    weather_history = list(weather_res.scalars().all())

    # 4. Risk History (past 30 assessments)
    hist_stmt = (
        select(RiskAssessment)
        .where(RiskAssessment.location_id == location_id)
        .order_by(RiskAssessment.timestamp.asc())
        .limit(30)
    )
    hist_res = await db.execute(hist_stmt)
    risk_history = list(hist_res.scalars().all())

    # 5. Build Chronological Milestones
    milestones: List[EventTimelineMilestone] = []
    if weather_history:
        first_time = weather_history[0].timestamp
        milestones.append(
            EventTimelineMilestone(
                timestamp=first_time,
                time_label=first_time.strftime("%H:%M"),
                title="Continuous Telemetry Ingestion Online",
                description=f"Sensors active at {location.name} ({location.elevation:.0f}m elev, {location.slope_angle:.0f}° slope).",
                category="info"
            )
        )

    if latest_risk and latest_risk.risk_score >= 25.0:
        milestones.append(
            EventTimelineMilestone(
                timestamp=latest_risk.timestamp,
                time_label=latest_risk.timestamp.strftime("%H:%M"),
                title="Hazard Anomaly & Saturation Flagged",
                description=latest_risk.reason,
                category="anomaly",
                severity=latest_risk.risk_level
            )
        )

    if active_event:
        milestones.append(
            EventTimelineMilestone(
                timestamp=active_event.detected_at,
                time_label=active_event.detected_at.strftime("%H:%M"),
                title=f"Disaster Event Incident Created [{active_event.status}]",
                description=active_event.summary,
                category="event",
                severity=active_event.severity
            )
        )

    return LocationInvestigationResponse(
        location=LocationResponse.model_validate(location),
        latest_assessment=RiskAssessmentResponse.model_validate(latest_risk) if latest_risk else None,
        active_event=DisasterEventResponse.model_validate(active_event) if active_event else None,
        weather_history=[WeatherObservationResponse.model_validate(w) for w in weather_history],
        risk_history=[RiskAssessmentResponse.model_validate(r) for r in risk_history],
        event_timeline=milestones
    )


from backend.app.schemas.scientific import (
    ScientificStationInvestigationResponse,
    RainfallAnalysisPackage,
    SoilMoistureAnalysisPackage,
    TimelineSeriesPoint,
    CanonicalAssessmentObject,
)


@router.get(
    "/{location_id}/scientific-analysis",
    response_model=ScientificStationInvestigationResponse,
    tags=["Station 360 & Scientific Analytics"]
)
@router.get(
    "/{location_id}/scientific-investigation",
    response_model=ScientificStationInvestigationResponse,
    tags=["Station 360 & Scientific Analytics"]
)
async def get_scientific_station_investigation(
    location_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Comprehensive scientific hydro-meteorological, rainfall accumulation,
    soil moisture profile, intensity-duration, triggers/conditioning separation,
    uncertainty analysis, and data quality matrix.
    """
    payload = await scientific_indicators_service.build_investigation_response(db, location_id)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID '{location_id}' not found."
        )
    return payload


@router.get("/{location_id}/canonical-assessment", response_model=CanonicalAssessmentObject)
async def get_canonical_engine_assessment(
    location_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Canonical Core Engine Assessment Object stamped with engine version prototype-v0.3.
    Standardized payload consumed downstream by expert command, field ops, alerts, and AI agents.
    """
    canonical = await scientific_indicators_service.generate_canonical_assessment(db, location_id)
    if not canonical:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID '{location_id}' not found."
        )
    return canonical


@router.get("/{location_id}/rainfall-analysis", response_model=RainfallAnalysisPackage)
async def get_station_rainfall_analysis(
    location_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Specialized rainfall analysis: intensity rates, rolling accumulation table,
    persistence spells, antecedent wetness, anomaly deviation, and I-D curve comparison.
    """
    location = await LocationService.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Location '{location_id}' not found.")

    obs_stmt = select(WeatherObservation).where(WeatherObservation.location_id == location.id).order_by(WeatherObservation.timestamp.asc()).limit(72)
    obs = list((await db.execute(obs_stmt)).scalars().all())
    return scientific_indicators_service.calculate_rainfall_metrics(obs, location)


@router.get("/{location_id}/soil-analysis", response_model=SoilMoistureAnalysisPackage)
async def get_station_soil_analysis(
    location_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Specialized subsurface moisture analysis: multi-depth vertical profile,
    temporal trend rate of change, and historical seasonal percentile.
    """
    location = await LocationService.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Location '{location_id}' not found.")

    obs_stmt = select(WeatherObservation).where(WeatherObservation.location_id == location.id).order_by(WeatherObservation.timestamp.asc()).limit(72)
    obs = list((await db.execute(obs_stmt)).scalars().all())
    return scientific_indicators_service.calculate_soil_metrics(obs, location)


@router.get("/{location_id}/risk-timeline", response_model=List[TimelineSeriesPoint])
async def get_station_risk_timeline(
    location_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Aligned multi-series timeline: rainfall rate, 24h cumulative rainfall,
    soil moisture, risk score, confidence, and milestone event markers.
    """
    location = await LocationService.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Location '{location_id}' not found.")

    obs_stmt = select(WeatherObservation).where(WeatherObservation.location_id == location.id).order_by(WeatherObservation.timestamp.asc()).limit(72)
    obs = list((await db.execute(obs_stmt)).scalars().all())

    risk_stmt = select(RiskAssessment).where(RiskAssessment.location_id == location.id).order_by(RiskAssessment.timestamp.desc()).limit(30)
    risks = list((await db.execute(risk_stmt)).scalars().all())

    return scientific_indicators_service.build_multi_series_timeline(obs, risks)


@router.get("/{location_id}/field-reports", tags=["Station 360 & Scientific Analytics"])
async def get_station_field_reports(
    location_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves chronological on-ground field observations and evidence submitted by response units for this station.
    """
    location = await LocationService.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Location '{location_id}' not found.")

    from backend.app.services.field_service import field_service, FieldOperationsService
    reports = await field_service.get_field_reports(db, location_id=location_id, limit=limit)
    return [FieldOperationsService.format_report_response(r) for r in reports]


