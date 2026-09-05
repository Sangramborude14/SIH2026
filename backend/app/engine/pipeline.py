from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.models.risk import RiskAssessment
from backend.app.models.event import DisasterEvent
from backend.app.models.history import RiskAssessmentHistory

from backend.app.engine.base import AssessmentOutput, RiskLevel, EnvironmentalState
from backend.app.engine.anomaly_detector import AnomalyDetector
from backend.app.engine.trend_analyzer import TrendAnalyzer
from backend.app.engine.landslide_risk_analyzer import landslide_risk_analyzer
from backend.app.engine.risk_aggregator import RiskAggregator
from backend.app.engine.event_manager import event_manager
from backend.app.services.environmental_data_service import (
    environmental_data_service,
    EnvironmentalDataService,
    EnvironmentalStatePackage,
)

from backend.app.services.landslide_inference_service import (
    landslide_inference_service,
    LandslideInferenceService,
)
from backend.app.schemas.engine import (
    AnomalyReport,
    TrendReport,
    EngineAssessmentResponse,
    MultiLocationEngineResponse,
)
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.cache import invalidate_station_risk


class DisasterIntelligenceEngine:
    """
    Upgraded Multi-Signal Disaster Intelligence Pipeline.
    Strictly separated from data collection.
    Consumes validated EnvironmentalStatePackage from EnvironmentalDataService
    and executes deterministic anomaly detection, trend calculation,
    multi-signal factor scoring, signal agreement, real-time ML future landslide inference,
    debounced event transitions, and audit trail persistence.
    """

    def __init__(
        self,
        data_service: Optional[EnvironmentalDataService] = None,
        inference_service: Optional[LandslideInferenceService] = None,
    ):
        self.data_service = data_service or environmental_data_service
        self.inference_service = inference_service or landslide_inference_service
        self.anomaly_detector = AnomalyDetector()
        self.trend_analyzer = TrendAnalyzer()
        self.risk_analyzer = landslide_risk_analyzer
        self.risk_aggregator = RiskAggregator()
        self.event_manager = event_manager


    async def evaluate_location(
        self,
        session: AsyncSession,
        location: Location,
        force_fresh: bool = False
    ) -> Tuple[AssessmentOutput, Optional[DisasterEvent], str]:
        """
        Runs the multi-signal assessment pipeline on a monitored location.
        """
        # 1. Collect and validate full environmental package from ingestion service
        pkg: EnvironmentalStatePackage = await self.data_service.collect_environmental_package(
            session=session,
            location=location,
            force_fresh=force_fresh
        )

        observations = pkg.observations
        historical_obs = observations[:-1] if len(observations) > 1 else observations
        latest_raw = observations[-1] if observations else WeatherObservation(location_id=location.id, timestamp=datetime.now(timezone.utc))

        # 2. Stage 3: Statistical Anomaly Detection
        anomalies = self.anomaly_detector.detect_anomalies(latest_raw, historical_obs)

        # 3. Stage 4: Temporal Trend & Persistence Analysis
        trends, is_persistent, is_increasing = self.trend_analyzer.analyze_trends(observations)

        # 4. Fetch recent historical risk assessments for trajectory analysis
        recent_assess_stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.location_id == location.id)
            .order_by(RiskAssessment.timestamp.asc())
            .limit(10)
        )
        recent_assess_res = await session.execute(recent_assess_stmt)
        recent_assessments = list(recent_assess_res.scalars().all())

        # 5. Stage 6, 7 & 8: Landslide Risk Calculation, Signal Agreement, Confidence, Reasons, Trajectory
        assessment_output = self.risk_analyzer.assess_risk(
            location=location,
            env_state=pkg.latest_env,
            terrain=pkg.terrain,
            historical=pkg.historical,
            anomalies=anomalies,
            trends=trends,
            is_persistent_rain=is_persistent,
            is_increasing_rain=is_increasing,
            recent_assessments=recent_assessments,
            historical_points_count=len(observations)
        )

        # 6. Persist Risk Assessment Record
        db_assessment = RiskAssessment(
            location_id=location.id,
            timestamp=assessment_output.timestamp,
            hazard_type=assessment_output.hazard_type,
            risk_level=assessment_output.risk_level.value,
            risk_score=assessment_output.risk_score,
            confidence_score=assessment_output.confidence_score,
            reason=assessment_output.reason,
            factors=[f.to_dict() for f in assessment_output.factors],
            assessment_version=settings.ENGINE_VERSION
        )
        session.add(db_assessment)

        # 7. Stage 8.5: Real-Time ML Future Landslide Inference (Task B)
        forecast_res = await self.inference_service.generate_forecast_for_location(
            session=session,
            location=location,
            latest_obs=latest_raw,
            obs_history=observations,
            deterministic_risk_score=assessment_output.risk_score,
            deterministic_risk_level=assessment_output.risk_level.value,
            persist=True,
        )

        p24 = None
        if forecast_res.forecast_available and "24h" in forecast_res.forecast:
            p24 = forecast_res.forecast["24h"].landslide_probability

        assessment_output.forecast_probabilities = {
            h: detail.landslide_probability
            for h, detail in forecast_res.forecast.items()
            if detail.landslide_probability is not None
        }
        assessment_output.forecast_available = forecast_res.forecast_available
        assessment_output.ml_model_status = forecast_res.model_status
        assessment_output.ml_model_version = forecast_res.model_version
        assessment_output.observed_drivers = forecast_res.observed_drivers

        # 8. Stage 9: Process Event Lifecycle State Machine (Dual-Signal: Risk Score + ML Probability)
        event, action = await self.event_manager.process_assessment_event(
            session=session,
            location=location,
            assessment=assessment_output,
            forecast_probability=p24,
        )

        # 9. Persist Detailed Assessment History for Auditing & Trend Analysis

        history_record = RiskAssessmentHistory(
            event_id=event.id if event else None,
            location_id=location.id,
            timestamp=assessment_output.timestamp,
            risk_score=assessment_output.risk_score,
            risk_level=assessment_output.risk_level.value,
            confidence=assessment_output.confidence_score,
            trajectory=assessment_output.trajectory.value,
            factors_json=[f.to_dict() for f in assessment_output.factors],
            reasons_json=[c.value for c in assessment_output.reason_codes],
            quality_json=assessment_output.data_quality.to_dict(),
            engine_version=settings.ENGINE_VERSION
        )
        session.add(history_record)

        await session.flush()
        await invalidate_station_risk(location.id)
        return assessment_output, event, action

    def format_assessment_response(
        self,
        location: Location,
        assessment: AssessmentOutput,
        event: Optional[DisasterEvent]
    ) -> EngineAssessmentResponse:
        """Formats internal assessment into a comprehensive API response schema."""
        return EngineAssessmentResponse(
            location_id=location.id,
            location=location.name,
            state=location.state,
            hazard=assessment.hazard_type,
            risk_level=assessment.risk_level.value,
            risk_score=assessment.risk_score,
            confidence=assessment.confidence_score,
            trajectory=assessment.trajectory.value,
            trend=next((t.direction.value for t in assessment.trends if t.metric == "rainfall_1h"), "UNKNOWN"),
            active_event=event is not None and event.status != "RESOLVED",
            event_id=event.id if event else None,
            event_status=event.status if event else None,
            event_severity=event.severity if event else None,
            initial_risk=event.initial_risk if event else None,
            peak_risk=event.peak_risk if event else None,
            reason_codes=[c.value for c in assessment.reason_codes],
            anomalies=[
                AnomalyReport(
                    metric=a.metric,
                    value=a.value,
                    baseline=a.baseline,
                    anomaly_score=a.anomaly_score,
                    is_anomalous=a.is_anomalous,
                    description=a.description
                )
                for a in assessment.anomalies
            ],
            trends=[
                TrendReport(
                    metric=t.metric,
                    direction=t.direction.value,
                    slope=t.slope,
                    description=t.description
                )
                for t in assessment.trends
            ],
            factors=[f.to_dict() for f in assessment.factors],
            data_quality=assessment.data_quality.to_dict(),
            signal_agreement={
                "agreement_score": assessment.signal_agreement.agreement_score,
                "coherent_signals_count": assessment.signal_agreement.coherent_signals_count,
                "conflicting_signals_count": assessment.signal_agreement.conflicting_signals_count,
                "agreement_level": assessment.signal_agreement.agreement_level,
                "details": assessment.signal_agreement.details,
            } if assessment.signal_agreement else None,
            summary=assessment.reason,
            timestamp=assessment.timestamp,
            engine_version=assessment.engine_version,
            forecast_probabilities=assessment.forecast_probabilities,
            forecast_available=assessment.forecast_available,
            ml_model_status=assessment.ml_model_status,
            ml_model_version=assessment.ml_model_version,
            observed_drivers=assessment.observed_drivers,
        )


    async def run_pipeline(
        self,
        session: AsyncSession,
        target_location_id: Optional[str] = None,
        force_fresh: bool = False
    ) -> MultiLocationEngineResponse:
        """
        Executes engine run across all locations or a targeted location.
        """
        now = datetime.now(timezone.utc)

        if target_location_id:
            query = select(Location).where(Location.id == target_location_id)
        else:
            query = select(Location)

        result = await session.execute(query)
        locations = list(result.scalars().all())

        if not locations:
            logger.warning("No locations found in database for engine execution.")
            return MultiLocationEngineResponse(
                executed_at=now,
                locations_evaluated=0,
                active_events_count=0,
                highest_risk_score=0.0,
                highest_risk_level="LOW",
                engine_version=settings.ENGINE_VERSION,
                assessments=[]
            )

        assessments_res: List[EngineAssessmentResponse] = []
        raw_assessments: List[AssessmentOutput] = []

        for loc in locations:
            assessment_out, event, _ = await self.evaluate_location(session, loc, force_fresh=force_fresh)
            raw_assessments.append(assessment_out)
            formatted = self.format_assessment_response(loc, assessment_out, event)
            assessments_res.append(formatted)

        agg = self.risk_aggregator.aggregate_assessments(raw_assessments)
        active_events = sum(1 for a in assessments_res if a.active_event)

        logger.info(
            f"Disaster Engine [{settings.ENGINE_VERSION}] run completed for {len(locations)} stations. "
            f"Highest risk: {agg['highest_risk_score']} ({agg['highest_risk_level']}), Active events: {active_events}"
        )

        return MultiLocationEngineResponse(
            executed_at=now,
            locations_evaluated=len(locations),
            active_events_count=active_events,
            highest_risk_score=agg["highest_risk_score"],
            highest_risk_level=agg["highest_risk_level"],
            engine_version=settings.ENGINE_VERSION,
            assessments=assessments_res
        )


disaster_engine = DisasterIntelligenceEngine()
