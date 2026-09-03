from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.event import DisasterEvent
from backend.app.models.location import Location
from backend.app.engine.base import AssessmentOutput, RiskLevel, EventStatus, RiskTrajectory
from backend.app.core.config import settings
from backend.app.core.logging import logger


class EventManager:
    """
    Manages the lifecycle, debounced state transitions, hysteresis buffers,
    and evolution metrics (initial_risk, peak_risk, peak_severity, trajectory) of DisasterEvents.
    Prevents alert flapping caused by single noisy observations.
    """

    def determine_event_status_and_severity(
        self,
        risk_score: float,
        current_event: Optional[DisasterEvent] = None,
        forecast_probability: Optional[float] = None
    ) -> Tuple[str, str]:
        """
        Maps deterministic risk score and/or ML forecast probability to EventStatus and severity
        with hysteresis buffering against noisy score fluctuations on downgrades.
        Does NOT blend scores into a fake composite number: checks dual operational thresholds.
        """
        buffer = settings.HYSTERESIS_DOWNGRADE_BUFFER  # e.g., 4.0 pts

        # Escalation checks ALWAYS take precedence
        # Critical if deterministic score >= 75.0 OR ML forecast probability >= 0.75
        if risk_score >= settings.THRESHOLD_CRITICAL or (forecast_probability is not None and forecast_probability >= 0.75):
            return EventStatus.CRITICAL.value, "CRITICAL"

        # If existing event is in higher state, check downgrade hysteresis buffer
        if current_event and current_event.status != "RESOLVED":
            curr_sev = current_event.severity.upper()

            # Hysteresis for CRITICAL -> HIGH
            if curr_sev == "CRITICAL":
                if risk_score >= (settings.THRESHOLD_CRITICAL - buffer) or (forecast_probability is not None and forecast_probability >= 0.70):
                    return EventStatus.CRITICAL.value, "CRITICAL"
                elif risk_score >= settings.THRESHOLD_HIGH or (forecast_probability is not None and forecast_probability >= 0.55):
                    return EventStatus.HIGH.value, "HIGH"

            # Hysteresis for HIGH -> ELEVATED
            if curr_sev == "HIGH":
                if risk_score >= settings.THRESHOLD_HIGH or (forecast_probability is not None and forecast_probability >= 0.55):
                    return EventStatus.HIGH.value, "HIGH"
                elif risk_score >= (settings.THRESHOLD_HIGH - buffer) or (forecast_probability is not None and forecast_probability >= 0.50):
                    return EventStatus.HIGH.value, "HIGH"
                elif risk_score >= settings.THRESHOLD_ELEVATED or (forecast_probability is not None and forecast_probability >= 0.35):
                    return EventStatus.ELEVATED.value, "MODERATE"

        # Standard Threshold Mapping
        # High if deterministic score >= 50.0 OR ML probability >= 0.55
        if risk_score >= settings.THRESHOLD_HIGH or (forecast_probability is not None and forecast_probability >= 0.55):
            return EventStatus.HIGH.value, "HIGH"
        elif risk_score >= settings.THRESHOLD_ELEVATED or (forecast_probability is not None and forecast_probability >= 0.35):
            return EventStatus.ELEVATED.value, "MODERATE"
        elif risk_score >= settings.THRESHOLD_WATCH or (forecast_probability is not None and forecast_probability >= 0.20):
            return EventStatus.WATCH.value, "LOW"
        elif current_event and current_event.status != "RESOLVED" and risk_score >= (settings.THRESHOLD_WATCH - buffer):
            return EventStatus.RESOLVING.value, "LOW"
        else:
            return EventStatus.MONITORING.value, "LOW"

    async def get_active_event(
        self,
        session: AsyncSession,
        location_id: str,
        event_type: str = "LANDSLIDE"
    ) -> Optional[DisasterEvent]:
        """
        Fetches an active non-resolved disaster event for the specified location.
        """
        query = select(DisasterEvent).where(
            and_(
                DisasterEvent.location_id == location_id,
                DisasterEvent.event_type == event_type,
                DisasterEvent.status != EventStatus.RESOLVED.value
            )
        ).order_by(DisasterEvent.detected_at.desc())

        result = await session.execute(query)
        return result.scalars().first()

    async def process_assessment_event(
        self,
        session: AsyncSession,
        location: Location,
        assessment: AssessmentOutput,
        forecast_probability: Optional[float] = None
    ) -> Tuple[Optional[DisasterEvent], str]:
        """
        Processes risk assessment against the event lifecycle state machine.
        Returns: (event_instance_or_none, lifecycle_action_string)
        Actions: 'created', 'escalated', 'deescalated', 'updated', 'resolving', 'resolved', 'none'
        """
        active_event = await self.get_active_event(session, location.id, assessment.hazard_type)
        new_status, new_severity = self.determine_event_status_and_severity(
            assessment.risk_score,
            current_event=active_event,
            forecast_probability=forecast_probability
        )

        now = datetime.now(timezone.utc)

        # Case 1: Risk is low (< 21 after buffer)
        if new_status in (EventStatus.MONITORING.value, EventStatus.NORMAL.value):
            if active_event:
                # Active event has fully subsided -> transition to RESOLVED
                active_event.status = EventStatus.RESOLVED.value
                active_event.risk_score = assessment.risk_score
                active_event.confidence_score = assessment.confidence_score
                active_event.trajectory = assessment.trajectory.value
                active_event.updated_at = now
                active_event.summary = (
                    f"Resolved: Landslide hazard at {location.name} returned to baseline "
                    f"(Score: {assessment.risk_score:.1f}, Peak: {active_event.peak_risk:.1f})."
                )
                logger.info(f"Resolved DisasterEvent {active_event.id} for location {location.name}")
                return active_event, "resolved"
            else:
                return None, "none"

        # Case 2: Resolving state (in transition buffer)
        if new_status == EventStatus.RESOLVING.value and active_event:
            active_event.status = EventStatus.RESOLVING.value
            active_event.risk_score = assessment.risk_score
            active_event.confidence_score = assessment.confidence_score
            active_event.trajectory = assessment.trajectory.value
            active_event.updated_at = now
            active_event.summary = (
                f"Resolving: Environmental indicators subsiding at {location.name} "
                f"(Current Risk: {assessment.risk_score:.1f}, Peak: {active_event.peak_risk:.1f})."
            )
            return active_event, "resolving"

        # Case 3: Risk elevated (>= 25) but NO active event currently exists -> Create new event
        if not active_event:
            est_peak = now + timedelta(hours=12) if assessment.is_increasing_rain else now + timedelta(hours=6)
            est_start = now if assessment.risk_score >= settings.THRESHOLD_HIGH else now + timedelta(hours=3)

            summary = (
                f"Active {new_status} alert: Emerging landslide activity detected at {location.name}, "
                f"{location.district}, {location.state}. Risk Score: {assessment.risk_score:.1f}/100. {assessment.reason}"
            )

            new_event = DisasterEvent(
                event_type=assessment.hazard_type,
                location_id=location.id,
                status=new_status,
                severity=new_severity,
                risk_score=assessment.risk_score,
                initial_risk=assessment.risk_score,
                peak_risk=assessment.risk_score,
                peak_severity=new_severity,
                confidence_score=assessment.confidence_score,
                trajectory=assessment.trajectory.value,
                detected_at=now,
                updated_at=now,
                expected_start=est_start,
                expected_peak=est_peak,
                affected_area=f"{location.name} and surrounding {location.district} hill slopes",
                summary=summary
            )
            session.add(new_event)
            await session.flush()
            logger.info(f"Created new DisasterEvent {new_event.id} [{new_status}] for location {location.name}")
            return new_event, "created"

        # Case 4: Active event ALREADY exists -> Update evolution metrics
        prev_score = active_event.risk_score
        active_event.updated_at = now
        active_event.risk_score = assessment.risk_score
        active_event.confidence_score = assessment.confidence_score
        active_event.trajectory = assessment.trajectory.value

        # Update peak risk & peak severity
        if assessment.risk_score > active_event.peak_risk:
            active_event.peak_risk = assessment.risk_score
            active_event.peak_severity = new_severity

        # Determine escalation / de-escalation action
        if assessment.risk_score > prev_score + 3.0:
            action = "escalated"
            active_event.status = new_status
            active_event.severity = new_severity
            active_event.summary = (
                f"ESCALATED to {new_status}: Landslide hazard increasing at {location.name} "
                f"(Risk: {prev_score:.1f} -> {assessment.risk_score:.1f}, Peak: {active_event.peak_risk:.1f}). {assessment.reason}"
            )
            logger.info(f"Escalated DisasterEvent {active_event.id} for {location.name} to {new_status}")
        elif assessment.risk_score < prev_score - 3.0:
            action = "deescalated"
            active_event.status = new_status
            active_event.severity = new_severity
            active_event.summary = (
                f"De-escalated to {new_status}: Landslide hazard decreasing at {location.name} "
                f"(Risk: {prev_score:.1f} -> {assessment.risk_score:.1f}, Peak: {active_event.peak_risk:.1f})."
            )
            logger.info(f"De-escalated DisasterEvent {active_event.id} for {location.name} to {new_status}")
        else:
            action = "updated"
            active_event.status = new_status
            active_event.severity = new_severity
            logger.debug(f"Updated DisasterEvent {active_event.id} for {location.name}")

        return active_event, action


event_manager = EventManager()
