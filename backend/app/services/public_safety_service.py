import math
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.public import (
    SafetyPoint,
    PublicUser,
    PublicAlertAcknowledgment,
)
from backend.app.models.location import Location
from backend.app.models.event import DisasterEvent
from backend.app.models.risk import RiskAssessment
from backend.app.schemas.public import (
    SafetyGuidanceItem,
    PublicAlertItem,
    PublicAlertDetailResponse,
    PublicRiskCheckResponse,
    SafetyPointResponse,
    PublicSystemStatusResponse,
)
from backend.app.core.config import settings
from backend.app.core.logging import logger


class SafetyGuidanceService:
    """
    Provides deterministic, conservative public safety guidance for landslide hazards.
    Strictly avoids speculative or hallucinated safety instructions.
    """

    @staticmethod
    def get_guidance_for_hazard(
        hazard_type: str = "LANDSLIDE",
        public_status: str = "ALERT"
    ) -> List[SafetyGuidanceItem]:
        if hazard_type.upper() != "LANDSLIDE":
            # Conservative fallback
            return [
                SafetyGuidanceItem(
                    category="DO",
                    title="Follow Official Instructions",
                    instruction="Comply immediately with directions issued by local disaster management authorities."
                ),
                SafetyGuidanceItem(
                    category="NOTICE",
                    title="Stay Informed",
                    instruction="Keep emergency communication channels active and monitor local warnings."
                )
            ]

        guidance: List[SafetyGuidanceItem] = []

        if public_status in ["URGENT", "ALERT"]:
            guidance.extend([
                SafetyGuidanceItem(
                    category="DO",
                    title="Move to Higher, Stable Ground",
                    instruction="Move away from steep hillside slopes, cliff bases, and known runoff ravines immediately."
                ),
                SafetyGuidanceItem(
                    category="DO",
                    title="Head Toward Designated Safer Reference Points",
                    instruction="Proceed cautiously along open ridge routes toward marked community assembly shelters."
                ),
                SafetyGuidanceItem(
                    category="DONT",
                    title="Do Not Cross Water-Logged Roads or Debris Chutes",
                    instruction="Never attempt to cross roads blocked by mudflow, falling rocks, or rising torrents."
                ),
                SafetyGuidanceItem(
                    category="DONT",
                    title="Avoid Hillside Basements and Ravines",
                    instruction="Do not shelter in valleys, hollows, or lower-story rooms facing unstable hillside embankments."
                ),
                SafetyGuidanceItem(
                    category="NOTICE",
                    title="Listen for Warning Signs",
                    instruction="Be alert for roaring sounds from slopes, cracking trees, tilting fence posts, or sudden muddy water discharges."
                )
            ])
        else:  # MONITORING or NO_ALERT
            guidance.extend([
                SafetyGuidanceItem(
                    category="DO",
                    title="Maintain Situational Awareness",
                    instruction="Heavy monsoon rains increase slope saturation. Monitor localized rainfall forecasts and road alerts."
                ),
                SafetyGuidanceItem(
                    category="DO",
                    title="Identify Family Assembly Zones",
                    instruction="Review local safer reference points and keep emergency kits (torch, water, first aid) accessible."
                ),
                SafetyGuidanceItem(
                    category="NOTICE",
                    title="Report Visible Slope Cracks",
                    instruction="Inform local disaster control rooms if new ground fissures or foundation cracks appear."
                )
            ])

        return guidance


class PublicAlertPolicy:
    """
    Evaluates scientific disaster event severity and user distance to calculate public alert levels.
    """

    @staticmethod
    def evaluate_policy(
        severity: str,
        event_status: str,
        distance_km: float
    ) -> Tuple[bool, str, str, str, str]:
        """
        Returns (should_alert, public_status, user_zone, title, summary)
        """
        if event_status == "RESOLVED":
            return (
                False,
                "NO_ALERT",
                "SAFE_ZONE",
                "Incident Resolved",
                "Previous hazard condition has subsided. Area is under routine baseline monitoring."
            )

        sev = severity.upper()

        if sev == "CRITICAL":
            if distance_km <= 12.0:
                return (
                    True,
                    "URGENT",
                    "CRITICAL_ZONE",
                    "URGENT: Critical Landslide Risk Detected",
                    "Severe slope saturation and high debris flow risk in your immediate sector. Move to safer ground."
                )
            elif distance_km <= 25.0:
                return (
                    True,
                    "URGENT",
                    "AFFECTED_ZONE",
                    "URGENT: Landslide Danger in Sector",
                    "Active critical hazard in neighboring hillside sector. Avoid arterial transit routes."
                )
            elif distance_km <= 45.0:
                return (
                    True,
                    "ALERT",
                    "WATCH_ZONE",
                    "Advisory: Regional Landslide Threat",
                    "Critical hazard detected within 45km. Stay alert for secondary road blockages."
                )
            else:
                return (
                    False,
                    "MONITORING",
                    "SAFE_ZONE",
                    "Regional Hazard Monitoring",
                    "Event is beyond your immediate perimeter. Regular monitoring active."
                )

        elif sev == "HIGH":
            if distance_km <= 15.0:
                return (
                    True,
                    "ALERT",
                    "AFFECTED_ZONE",
                    "ALERT: High Landslide Risk in Area",
                    "Persistent rainfall and high slope susceptibility detected. Exercise caution."
                )
            elif distance_km <= 30.0:
                return (
                    True,
                    "MONITORING",
                    "WATCH_ZONE",
                    "Advisory: Elevated Regional Risk",
                    "High risk active in nearby sector. Monitor updates."
                )
            else:
                return (
                    False,
                    "NO_ALERT",
                    "SAFE_ZONE",
                    "No Current Alert",
                    "Area operating within stable limits."
                )

        elif sev == "MODERATE":
            if distance_km <= 10.0:
                return (
                    False,
                    "MONITORING",
                    "WATCH_ZONE",
                    "Monitoring: Moderate Slope Caution",
                    "Moderate rainfall observed. Ground conditions stable but warrant monitoring."
                )
            else:
                return (
                    False,
                    "NO_ALERT",
                    "SAFE_ZONE",
                    "No Current Alert",
                    "No active warnings in your sector."
                )

        return (
            False,
            "NO_ALERT",
            "SAFE_ZONE",
            "No Current Alert",
            "No active disaster events detected."
        )


class PublicRiskService:
    """
    Public safety intelligence orchestration and geofenced risk checks.
    """

    @staticmethod
    def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(r * c, 2)

    @staticmethod
    async def seed_initial_safety_points(session: AsyncSession):
        stmt = select(SafetyPoint)
        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            return

        points = [
            SafetyPoint(
                id="SAFE-SIK-GANGTOK-01",
                name="Paljor Stadium Open Ground Assembly Zone",
                location_id="NER-SIK-GANGTOK-01",
                latitude=27.3315,
                longitude=88.6138,
                point_type="ASSEMBLY_POINT",
                capacity=1500,
                availability="OPEN",
                source="Sikkim SDMA Demo Profile",
                contact_number="03592-202461 / 1070",
                is_simulated=True
            ),
            SafetyPoint(
                id="SAFE-SIK-GANGTOK-02",
                name="Tadong Government College Relief Center",
                location_id="NER-SIK-GANGTOK-01",
                latitude=27.3160,
                longitude=88.5990,
                point_type="SHELTER",
                capacity=600,
                availability="OPEN",
                source="Sikkim SDMA Demo Profile",
                contact_number="03592-202461 / 112",
                is_simulated=True
            ),
            SafetyPoint(
                id="SAFE-MIZ-AIZAWL-01",
                name="Aizawl AR Ground Safe Shelter Point",
                location_id="NER-MIZ-AIZAWL-01",
                latitude=23.7310,
                longitude=92.7150,
                point_type="SAFE_ZONE",
                capacity=1200,
                availability="OPEN",
                source="Mizoram Disaster Management Authority",
                contact_number="0389-2335837 / 1070",
                is_simulated=True
            ),
            SafetyPoint(
                id="SAFE-NAG-KOHIMA-01",
                name="Kohima Local Ground Community Assembly Zone",
                location_id="NER-NAG-KOHIMA-01",
                latitude=25.6690,
                longitude=94.1030,
                point_type="ASSEMBLY_POINT",
                capacity=800,
                availability="OPEN",
                source="Nagaland SDMA Demo Profile",
                contact_number="0370-2291122 / 112",
                is_simulated=True
            ),
        ]
        for p in points:
            session.add(p)
        await session.flush()
        logger.info("Successfully seeded North Eastern Region Safer Reference Points.")

    @staticmethod
    async def get_public_system_status(session: AsyncSession) -> PublicSystemStatusResponse:
        alerts = await PublicRiskService.get_active_public_alerts(session)
        return PublicSystemStatusResponse(
            system_status="OPERATIONAL",
            active_public_alerts_count=len(alerts),
            data_mode=settings.DATA_MODE,
            timestamp=datetime.now(timezone.utc)
        )

    @staticmethod
    async def get_active_public_alerts(session: AsyncSession) -> List[PublicAlertItem]:
        stmt = (
            select(DisasterEvent)
            .where(
                and_(
                    DisasterEvent.status != "RESOLVED",
                    DisasterEvent.severity.in_(["HIGH", "CRITICAL"])
                )
            )
            .order_by(DisasterEvent.updated_at.desc())
        )
        events = list((await session.execute(stmt)).scalars().all())
        results: List[PublicAlertItem] = []

        for ev in events:
            loc = (await session.execute(select(Location).where(Location.id == ev.location_id))).scalars().first()
            if not loc:
                continue

            public_status = "URGENT" if ev.severity == "CRITICAL" else "ALERT"
            title = f"URGENT: High Landslide Risk in {loc.district}" if ev.severity == "CRITICAL" else f"ALERT: Landslide Warning in {loc.district}"

            results.append(
                PublicAlertItem(
                    alert_id=f"PUB-ALERT-{ev.id[:8]}",
                    event_id=ev.id,
                    location_id=loc.id,
                    location_name=loc.name,
                    district=loc.district,
                    state=loc.state,
                    hazard_type=ev.event_type,
                    public_status=public_status,
                    message_title=title,
                    message_summary=ev.summary,
                    affected_radius_km=25.0 if ev.severity == "CRITICAL" else 15.0,
                    detected_at=ev.detected_at,
                    updated_at=ev.updated_at,
                    data_mode=settings.DATA_MODE
                )
            )
        return results

    @staticmethod
    async def get_public_alert_detail(
        session: AsyncSession,
        event_id: str,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None
    ) -> Optional[PublicAlertDetailResponse]:
        await PublicRiskService.seed_initial_safety_points(session)

        ev = (await session.execute(select(DisasterEvent).where(DisasterEvent.id == event_id))).scalars().first()
        if not ev:
            return None

        loc = (await session.execute(select(Location).where(Location.id == ev.location_id))).scalars().first()
        if not loc:
            return None

        # Distance calculation
        u_lat = user_lat or loc.latitude
        u_lon = user_lon or loc.longitude
        dist_km = PublicRiskService.calculate_distance_km(u_lat, u_lon, loc.latitude, loc.longitude)

        _, public_status, user_zone, title, summary = PublicAlertPolicy.evaluate_policy(
            ev.severity, ev.status, dist_km
        )

        alert_item = PublicAlertItem(
            alert_id=f"PUB-ALERT-{ev.id[:8]}",
            event_id=ev.id,
            location_id=loc.id,
            location_name=loc.name,
            district=loc.district,
            state=loc.state,
            hazard_type=ev.event_type,
            public_status=public_status,
            message_title=title,
            message_summary=summary,
            affected_radius_km=25.0 if ev.severity == "CRITICAL" else 15.0,
            detected_at=ev.detected_at,
            updated_at=ev.updated_at,
            data_mode=settings.DATA_MODE
        )

        guidance = SafetyGuidanceService.get_guidance_for_hazard(ev.event_type, public_status)

        # Retrieve nearest safety points
        pts_stmt = select(SafetyPoint).where(SafetyPoint.location_id == loc.id)
        pts = list((await session.execute(pts_stmt)).scalars().all())
        if not pts:
            pts = list((await session.execute(select(SafetyPoint))).scalars().all())

        safety_points_resp: List[SafetyPointResponse] = []
        for p in pts:
            p_dist = PublicRiskService.calculate_distance_km(u_lat, u_lon, p.latitude, p.longitude)
            resp_p = SafetyPointResponse.model_validate(p)
            resp_p.distance_km = p_dist
            safety_points_resp.append(resp_p)

        safety_points_resp.sort(key=lambda x: x.distance_km or 999.0)

        emergency_contacts = {
            "National Emergency Helpline": "112",
            "Disaster Management Helpline": "1070",
            "State Disaster Control Room": "03592-202461" if "SIK" in loc.id else "0370-2291122",
            "Ambulance Service": "108"
        }

        provenance = {
            "source_engine": "DISASTRA Disaster Intelligence Engine",
            "assessment_time": ev.updated_at.isoformat(),
            "data_mode": settings.DATA_MODE,
            "notice": "Demonstration Early Warning System. Verify with official district administration advisories."
        }

        return PublicAlertDetailResponse(
            alert=alert_item,
            user_zone=user_zone,
            user_distance_km=dist_km,
            guidance=guidance,
            safer_reference_points=safety_points_resp[:3],
            emergency_contacts=emergency_contacts,
            data_provenance=provenance
        )

    @staticmethod
    async def evaluate_user_location(
        session: AsyncSession,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_id: Optional[str] = None
    ) -> PublicRiskCheckResponse:
        await PublicRiskService.seed_initial_safety_points(session)

        # Resolve target anchor coordinates
        target_lat = latitude
        target_lon = longitude
        target_name = "User Location"

        if location_id:
            loc = (await session.execute(select(Location).where(Location.id == location_id))).scalars().first()
            if loc:
                target_lat = loc.latitude
                target_lon = loc.longitude
                target_name = loc.name
        elif target_lat is None or target_lon is None:
            # Default to Gangtok station
            loc = (await session.execute(select(Location))).scalars().first()
            if loc:
                target_lat = loc.latitude
                target_lon = loc.longitude
                target_name = loc.name

        # Find closest active critical/high disaster event
        stmt = (
            select(DisasterEvent)
            .where(DisasterEvent.status != "RESOLVED")
            .order_by(DisasterEvent.updated_at.desc())
        )
        events = list((await session.execute(stmt)).scalars().all())

        closest_event: Optional[DisasterEvent] = None
        closest_loc: Optional[Location] = None
        min_dist = 9999.0

        for ev in events:
            e_loc = (await session.execute(select(Location).where(Location.id == ev.location_id))).scalars().first()
            if e_loc and target_lat is not None and target_lon is not None:
                d = PublicRiskService.calculate_distance_km(target_lat, target_lon, e_loc.latitude, e_loc.longitude)
                if d < min_dist:
                    min_dist = d
                    closest_event = ev
                    closest_loc = e_loc

        if closest_event and closest_loc and min_dist <= 50.0:
            should_alert, public_status, user_zone, title, summary = PublicAlertPolicy.evaluate_policy(
                closest_event.severity, closest_event.status, min_dist
            )

            active_alert_item = PublicAlertItem(
                alert_id=f"PUB-ALERT-{closest_event.id[:8]}",
                event_id=closest_event.id,
                location_id=closest_loc.id,
                location_name=closest_loc.name,
                district=closest_loc.district,
                state=closest_loc.state,
                hazard_type=closest_event.event_type,
                public_status=public_status,
                message_title=title,
                message_summary=summary,
                affected_radius_km=25.0 if closest_event.severity == "CRITICAL" else 15.0,
                detected_at=closest_event.detected_at,
                updated_at=closest_event.updated_at,
                data_mode=settings.DATA_MODE
            )

            guidance = SafetyGuidanceService.get_guidance_for_hazard(closest_event.event_type, public_status)
        else:
            should_alert = False
            public_status = "NO_ALERT"
            user_zone = "SAFE_ZONE"
            active_alert_item = None
            guidance = SafetyGuidanceService.get_guidance_for_hazard("LANDSLIDE", "NO_ALERT")
            min_dist = None

        # Nearest safe point
        pts = list((await session.execute(select(SafetyPoint))).scalars().all())
        nearest_safe: Optional[SafetyPointResponse] = None
        if pts and target_lat is not None and target_lon is not None:
            sorted_pts = sorted(
                pts,
                key=lambda p: PublicRiskService.calculate_distance_km(target_lat, target_lon, p.latitude, p.longitude)
            )
            nearest_p = sorted_pts[0]
            nearest_dist = PublicRiskService.calculate_distance_km(target_lat, target_lon, nearest_p.latitude, nearest_p.longitude)
            nearest_safe = SafetyPointResponse.model_validate(nearest_p)
            nearest_safe.distance_km = nearest_dist

        return PublicRiskCheckResponse(
            is_affected=should_alert,
            public_status=public_status,
            user_zone=user_zone,
            location_name=target_name,
            nearest_hazard_km=min_dist,
            active_alert=active_alert_item,
            guidance=guidance,
            nearest_safe_point=nearest_safe,
            data_mode=settings.DATA_MODE,
            timestamp=datetime.now(timezone.utc)
        )

    @staticmethod
    async def get_all_safety_points(session: AsyncSession, location_id: Optional[str] = None) -> List[SafetyPoint]:
        await PublicRiskService.seed_initial_safety_points(session)
        stmt = select(SafetyPoint)
        if location_id:
            stmt = stmt.where(SafetyPoint.location_id == location_id)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def record_acknowledgment(
        session: AsyncSession,
        event_id: str,
        location_id: str,
        user_id: Optional[str] = None
    ) -> PublicAlertAcknowledgment:
        ack = PublicAlertAcknowledgment(
            event_id=event_id,
            location_id=location_id,
            user_id=user_id or "ANONYMOUS_CITIZEN"
        )
        session.add(ack)
        await session.flush()
        logger.info(f"Public alert acknowledged for event {event_id} at location {location_id}")
        return ack


public_safety_service = PublicRiskService()
