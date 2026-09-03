from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_db
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
    """
    locations = await LocationService.get_all_locations(db)
    map_items: List[LocationMapItem] = []

    for loc in locations:
        risk_stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.location_id == loc.id)
            .order_by(RiskAssessment.timestamp.desc())
            .limit(1)
        )
        risk_res = await db.execute(risk_stmt)
        latest_risk = risk_res.scalars().first()

        if not latest_risk:
            assessment_out, _, _ = await disaster_engine.evaluate_location(db, loc)
            await db.commit()
            risk_res = await db.execute(risk_stmt)
            latest_risk = risk_res.scalars().first()

        event_stmt = (
            select(DisasterEvent)
            .where(and_(DisasterEvent.location_id == loc.id, DisasterEvent.status != "RESOLVED"))
            .order_by(DisasterEvent.detected_at.desc())
            .limit(1)
        )
        event_res = await db.execute(event_stmt)
        active_event = event_res.scalars().first()

        weather_stmt = (
            select(WeatherObservation)
            .where(WeatherObservation.location_id == loc.id)
            .order_by(WeatherObservation.timestamp.desc())
            .limit(1)
        )
        weather_res = await db.execute(weather_stmt)
        latest_weather = weather_res.scalars().first()

        # Query latest ML forecast records
        fc_stmt = (
            select(LandslideForecastRecord)
            .where(LandslideForecastRecord.location_id == loc.id)
            .order_by(LandslideForecastRecord.prediction_timestamp.desc())
            .limit(3)
        )
        fc_res = await db.execute(fc_stmt)
        fc_records = list(fc_res.scalars().all())

        forecast_probs: dict = {}
        model_version = "2.0.0"
        model_status = "READY" if model_registry.is_trained_model_active() else "NOT_TRAINED"
        data_freshness = "FRESH"
        for fc in fc_records:
            h_key = fc.forecast_horizon.lower()
            if fc.probability is not None:
                forecast_probs[h_key] = fc.probability
            model_version = fc.model_version
            model_status = fc.model_status
            data_freshness = fc.data_freshness

        # If no persisted forecast yet but trained model is active, generate now
        if not forecast_probs and model_registry.is_trained_model_active():
            from backend.app.services.landslide_inference_service import landslide_inference_service
            quick_fc = await landslide_inference_service.generate_forecast_for_location(
                session=db,
                location=loc,
                latest_obs=latest_weather,
                obs_history=[latest_weather] if latest_weather else [],
                deterministic_risk_score=latest_risk.risk_score if latest_risk else 10.0,
                deterministic_risk_level=latest_risk.risk_level if latest_risk else "LOW",
                persist=True,
            )
            for h_str, h_det in quick_fc.forecast.items():
                if h_det.landslide_probability is not None:
                    forecast_probs[h_str] = h_det.landslide_probability
            data_freshness = quick_fc.data_freshness
            model_status = quick_fc.model_status

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


