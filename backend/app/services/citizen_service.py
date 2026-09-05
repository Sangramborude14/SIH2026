import math
import random
import html
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from backend.app.models.citizen import CitizenSOS, CitizenReport
from backend.app.models.location import Location
from backend.app.models.event import DisasterEvent
from backend.app.models.public import SafetyPoint
from backend.app.models.risk import RiskAssessment
from backend.app.schemas.citizen import (
    CitizenRiskStatusResponse,
    ImmediateGuidanceItem,
    NearestShelterInfo,
    CitizenSOSCreate,
    CitizenSOSResponse,
    CitizenSOSStatusUpdate,
    CitizenReportResponse,
    CitizenGuidanceResponse,
    CitizenGuidanceSection,
    CitizenContactsResponse,
)
from backend.app.services.public_safety_service import PublicRiskService
from backend.app.services.storage_provider import get_storage_provider
from backend.app.core.config import settings
from backend.app.core.logging import logger


class CitizenService:
    """
    Core service delivering simple, mobile-friendly citizen safety intelligence,
    SOS distress beacon management with duplicate suppression, and community hazard reporting.
    Strictly filters out all scientific scores, ML internals, and technical jargon.
    """

    @staticmethod
    def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        return PublicRiskService.calculate_distance_km(lat1, lon1, lat2, lon2)

    @staticmethod
    async def evaluate_citizen_risk(
        session: AsyncSession,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_id: Optional[str] = None,
    ) -> CitizenRiskStatusResponse:
        """
        Translates physical & ML hazard intelligence into a clear citizen safety status,
        accompanied by 24h trend, immediate DOs/DONTs, and nearest safe shelter.
        """
        # 1. Resolve coordinates
        target_lat = latitude
        target_lon = longitude
        location_name = "Your Monitored Area"

        if location_id:
            loc = (await session.execute(select(Location).where(Location.id == location_id))).scalars().first()
            if loc:
                target_lat = loc.latitude
                target_lon = loc.longitude
                location_name = f"{loc.name}, {loc.district} ({loc.state})"
        elif target_lat is None or target_lon is None:
            # Fallback to premier NER station
            first_loc = (await session.execute(select(Location))).scalars().first()
            if first_loc:
                target_lat = first_loc.latitude
                target_lon = first_loc.longitude
                location_name = f"{first_loc.name}, {first_loc.district} ({first_loc.state})"

        # 2. Check for active disaster events nearby
        events_stmt = (
            select(DisasterEvent)
            .where(DisasterEvent.status != "RESOLVED")
            .order_by(DisasterEvent.updated_at.desc())
        )
        active_events = list((await session.execute(events_stmt)).scalars().all())

        closest_event: Optional[DisasterEvent] = None
        closest_loc: Optional[Location] = None
        min_dist_km: float = 9999.0

        loc_ids = [ev.location_id for ev in active_events if ev.location_id]
        loc_map: Dict[str, Location] = {}
        if loc_ids:
            loc_records = list((await session.execute(select(Location).where(Location.id.in_(loc_ids)))).scalars().all())
            loc_map = {l.id: l for l in loc_records}

        for ev in active_events:
            e_loc = loc_map.get(ev.location_id)
            if e_loc and target_lat is not None and target_lon is not None:
                d = CitizenService.calculate_distance_km(target_lat, target_lon, e_loc.latitude, e_loc.longitude)
                if d < min_dist_km:
                    min_dist_km = d
                    closest_event = ev
                    closest_loc = e_loc

        # 3. Determine safety level and plain-language interpretation
        safety_level = "LOW"
        safety_color = "green"
        headline = "Conditions Stable & Normal"
        summary = "No active landslide threat detected in your sector. Slopes and drainage remain stable."
        action_rec = "Normal daily activities may continue. Maintain standard monsoon weather awareness."
        trend_24h = "STABLE"
        trend_desc = "Slope moisture and rainfall patterns are projected to remain steady over the next 24 hours."

        if closest_event and closest_loc and min_dist_km <= 40.0:
            sev = closest_event.severity.upper()
            if sev == "CRITICAL" and min_dist_km <= 15.0:
                safety_level = "CRITICAL"
                safety_color = "red"
                headline = "URGENT: Severe Landslide Hazard in Your Sector"
                summary = (
                    f"Intense slope saturation and debris flow danger detected within {int(min_dist_km)} km of your location. "
                    "Hillside slopes and ravine bases are at immediate risk of sliding."
                )
                action_rec = "EVACUATE IMMEDIATELY: Move to designated community shelters or stable ridge ground away from slopes."
                trend_24h = "INCREASING"
                trend_desc = "Continuous rainfall and ground saturation indicate risk will remain elevated over the next 12 to 24 hours."
            elif (sev == "CRITICAL" and min_dist_km <= 35.0) or (sev == "HIGH" and min_dist_km <= 15.0):
                safety_level = "HIGH"
                safety_color = "orange"
                headline = "WARNING: High Landslide Danger in Sector"
                summary = (
                    f"Persistent heavy rainfall has weakened hillside soils within {int(min_dist_km)} km. "
                    "Risk of rockfalls, debris slides, and arterial road blockages is high."
                )
                action_rec = "Avoid non-essential travel on hillside and valley roads. Keep family emergency kit ready."
                trend_24h = "INCREASING"
                trend_desc = "Forecasted precipitation indicates slope instability may expand over the coming 24 hours."
            elif min_dist_km <= 30.0:
                safety_level = "MODERATE"
                safety_color = "yellow"
                headline = "WATCH: Elevated Slope Moisture Advisory"
                summary = (
                    f"Moderate weather activity detected in neighboring hills ({int(min_dist_km)} km away). "
                    "Ground conditions are damp with minor erosion potential."
                )
                action_rec = "Stay alert. Avoid parking vehicles near steep slopes or under high retaining walls."
                trend_24h = "STABLE"
                trend_desc = "Conditions are holding steady. Monitor district emergency bulletins."

        # 4. Immediate priority DOs and DONTs
        dos_donts = []
        if safety_level in ["CRITICAL", "HIGH"]:
            dos_donts.append(ImmediateGuidanceItem(
                category="DO",
                instruction="Move away from steep slopes, ravines, drainage gullies (jhoras), and cliff edges."
            ))
            dos_donts.append(ImmediateGuidanceItem(
                category="DO",
                instruction="Follow official instructions from local District Disaster Management authorities."
            ))
            dos_donts.append(ImmediateGuidanceItem(
                category="DONT",
                instruction="Do NOT attempt to drive or walk through mudflow, moving debris, or water-logged roads."
            ))
            dos_donts.append(ImmediateGuidanceItem(
                category="DONT",
                instruction="Do NOT return to an evacuated building until emergency officials inspect and clear it."
            ))
        else:
            dos_donts.append(ImmediateGuidanceItem(
                category="DO",
                instruction="Inspect house surroundings: clear leaves and debris from drainage channels."
            ))
            dos_donts.append(ImmediateGuidanceItem(
                category="DO",
                instruction="Keep a torch, drinking water, first aid, and charged mobile phone accessible."
            ))
            dos_donts.append(ImmediateGuidanceItem(
                category="DONT",
                instruction="Do NOT block natural rainwater runoff paths on hill slopes."
            ))

        # 5. Nearest Safe Shelter Point
        await PublicRiskService.seed_initial_safety_points(session)
        pts_stmt = select(SafetyPoint)
        all_pts = list((await session.execute(pts_stmt)).scalars().all())

        nearest_shelter: Optional[NearestShelterInfo] = None
        if all_pts and target_lat is not None and target_lon is not None:
            sorted_pts = sorted(
                all_pts,
                key=lambda p: CitizenService.calculate_distance_km(target_lat, target_lon, p.latitude, p.longitude)
            )
            top_pt = sorted_pts[0]
            dist = CitizenService.calculate_distance_km(target_lat, target_lon, top_pt.latitude, top_pt.longitude)
            nearest_shelter = NearestShelterInfo(
                name=top_pt.name,
                distance_km=dist,
                capacity=top_pt.capacity,
                availability=top_pt.availability,
                contact_number=top_pt.contact_number,
                latitude=top_pt.latitude,
                longitude=top_pt.longitude,
            )

        emergency_contacts = {
            "National Emergency": "112",
            "Disaster Management Helpline": "1070",
            "District Disaster Helpline": "1077",
            "Ambulance Service": "108",
            "Police Control": "100"
        }

        return CitizenRiskStatusResponse(
            safety_level=safety_level,
            safety_color=safety_color,
            safety_headline=headline,
            safety_summary=summary,
            trend_24h=trend_24h,
            trend_description=trend_desc,
            location_name=location_name,
            nearest_hazard_km=round(min_dist_km, 1) if min_dist_km < 9000 else None,
            action_recommendation=action_rec,
            immediate_dos_donts=dos_donts,
            nearest_shelter=nearest_shelter,
            emergency_contacts=emergency_contacts,
            timestamp=datetime.now(timezone.utc),
            data_mode=settings.DATA_MODE
        )

    @staticmethod
    async def create_sos(
        session: AsyncSession,
        sos_in: CitizenSOSCreate,
        user_id: Optional[str] = None,
    ) -> CitizenSOS:
        """
        Dispatches an emergency SOS distress beacon.
        Suppresses rapid duplicate dispatches within 120 seconds.
        Links user_id if authenticated, and generates an unguessable tracking_token.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=120)

        # Duplicate suppression by phone, fingerprint, or user_id
        filters = []
        if sos_in.contact_phone:
            filters.append(CitizenSOS.contact_phone == sos_in.contact_phone)
        if sos_in.device_fingerprint:
            filters.append(CitizenSOS.device_fingerprint == sos_in.device_fingerprint)
        if user_id:
            filters.append(CitizenSOS.user_id == user_id)

        if filters:
            dup_stmt = (
                select(CitizenSOS)
                .where(and_(
                    or_(*filters),
                    CitizenSOS.created_at >= cutoff_time,
                    CitizenSOS.status != "RESOLVED"
                ))
                .order_by(CitizenSOS.created_at.desc())
            )
            existing = (await session.execute(dup_stmt)).scalars().first()
            if existing:
                logger.info(f"Duplicate SOS suppressed for user={user_id} or contact={sos_in.contact_phone}; returning active SOS {existing.id}")
                return existing

        tracking_token = str(uuid.uuid4())
        new_sos = CitizenSOS(
            emergency_type=sos_in.emergency_type,
            status="RECEIVED",
            latitude=sos_in.latitude,
            longitude=sos_in.longitude,
            location_accuracy=sos_in.location_accuracy,
            location_name=html.escape(sos_in.location_name or "GPS Coordinates Captured"),
            contact_name=html.escape(sos_in.contact_name) if sos_in.contact_name else None,
            contact_phone=sos_in.contact_phone,
            num_people=sos_in.num_people,
            message=html.escape(sos_in.message) if sos_in.message else None,
            device_fingerprint=sos_in.device_fingerprint,
            user_id=user_id,
            tracking_token=tracking_token,
        )
        session.add(new_sos)
        await session.flush()
        logger.info(f"New Citizen SOS recorded: ID={new_sos.id}, Type={new_sos.emergency_type}, People={new_sos.num_people}")
        return new_sos

    @staticmethod
    async def get_sos_by_id(session: AsyncSession, sos_id: str) -> Optional[CitizenSOS]:
        stmt = select(CitizenSOS).where(CitizenSOS.id == sos_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def update_sos_status(
        session: AsyncSession,
        sos_id: str,
        update_in: CitizenSOSStatusUpdate
    ) -> Optional[CitizenSOS]:
        sos = await CitizenService.get_sos_by_id(session, sos_id)
        if not sos:
            return None
        sos.status = update_in.status
        if update_in.assigned_unit is not None:
            sos.assigned_unit = update_in.assigned_unit
        if update_in.responder_notes is not None:
            sos.responder_notes = update_in.responder_notes
        await session.flush()
        return sos

    @staticmethod
    async def create_citizen_report(
        session: AsyncSession,
        category: str,
        description: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_accuracy: Optional[float] = None,
        location_name: Optional[str] = None,
        contact_phone: Optional[str] = None,
        photo_file: Optional[UploadFile] = None,
        user_id: Optional[str] = None,
    ) -> CitizenReport:
        """
        Creates a citizen hazard report with optional photo attachment.
        Sanitizes text inputs against XSS and executes server-side image processing.
        """
        photo_storage_key = None
        thumbnail_storage_key = None
        photo_content_hash = None
        photo_url = None
        photo_size_bytes = 0.0
        mime_type = None

        if photo_file and photo_file.filename:
            storage = get_storage_provider()
            content = await photo_file.read()
            res = await storage.save_file(
                file_bytes=content,
                original_filename=photo_file.filename,
                content_type=photo_file.content_type or "image/jpeg",
                uploaded_by=user_id or contact_phone or "CITIZEN_ANONYMOUS"
            )
            photo_storage_key = res["storage_key"]
            thumbnail_storage_key = res.get("thumbnail_storage_key")
            photo_content_hash = res.get("content_hash")
            photo_url = res["url"]
            photo_size_bytes = float(res.get("file_size", len(content)))
            mime_type = res["mime_type"]

        # Generate unique report number
        current_year = datetime.now(timezone.utc).year
        random_suffix = random.randint(1000, 9999)
        report_number = f"REP-{current_year}-{random_suffix}"

        # XSS sanitization
        clean_desc = html.escape(description.strip())
        clean_loc = html.escape(location_name.strip()) if location_name else "User Landmark"

        report = CitizenReport(
            report_number=report_number,
            user_id=user_id,
            category=category,
            description=clean_desc,
            latitude=latitude,
            longitude=longitude,
            location_accuracy=location_accuracy,
            location_name=clean_loc,
            contact_phone=contact_phone,
            photo_storage_key=photo_storage_key,
            thumbnail_storage_key=thumbnail_storage_key,
            photo_content_hash=photo_content_hash,
            photo_url=photo_url,
            photo_size_bytes=photo_size_bytes,
            mime_type=mime_type,
            status="RECEIVED",
        )
        session.add(report)
        await session.flush()
        logger.info(f"New Citizen Report created: {report.report_number} ({report.category})")
        return report

    @staticmethod
    async def get_citizen_reports(
        session: AsyncSession,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CitizenReport], int]:
        """
        Returns paginated citizen reports.
        Restricts by user_id for citizen users to prevent IDOR data leaks.
        """
        base_query = select(CitizenReport)
        count_query = select(func.count(CitizenReport.id))

        filters = []
        if user_id:
            filters.append(CitizenReport.user_id == user_id)
        if status:
            filters.append(CitizenReport.status == status)

        if filters:
            base_query = base_query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        total_res = await session.execute(count_query)
        total = total_res.scalar() or 0

        offset = max(0, (page - 1) * page_size)
        items_query = base_query.order_by(CitizenReport.created_at.desc()).offset(offset).limit(page_size)
        items = list((await session.execute(items_query)).scalars().all())

        return items, total

    @staticmethod
    async def get_citizen_report_by_id(session: AsyncSession, report_id: str) -> Optional[CitizenReport]:
        stmt = select(CitizenReport).where(CitizenReport.id == report_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    def get_citizen_guidance() -> CitizenGuidanceResponse:
        """
        Returns structured Before, During, and After landslide instructions,
        tailored for North Eastern India mountain communities.
        """
        before_section = CitizenGuidanceSection(
            phase="BEFORE",
            title="Before a Landslide (Preparation & Prevention)",
            instructions=[
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="Familiarize yourself with your area's landslide history and identify local safer ridge zones."
                ),
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="Clear mud and debris from roadside culverts, drains, and roof runoff channels."
                ),
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="Prepare an emergency Go-Bag with torch, fresh water, battery bank, dry food, and essential medicines."
                ),
                ImmediateGuidanceItem(
                    category="DONT",
                    instruction="Do NOT construct unpermitted structures or dump excavated soil directly onto steep hill slopes."
                ),
                ImmediateGuidanceItem(
                    category="DONT",
                    instruction="Do NOT ignore new cracks in foundations, roads, retaining walls, or soil embankments."
                ),
            ]
        )

        during_section = CitizenGuidanceSection(
            phase="DURING",
            title="During a Landslide (Immediate Action)",
            instructions=[
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="If outdoors, quickly move away from the path of debris toward high, stable open ground."
                ),
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="If indoors and escape is impossible, curl into a tight ball under sturdy furniture and protect your head."
                ),
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="Listen for unusual sounds: cracking trees, rolling boulders, or sudden roaring torrents from hillside gullies."
                ),
                ImmediateGuidanceItem(
                    category="DONT",
                    instruction="Do NOT attempt to cross roads blocked by mudflows or active rockfalls. Turn back immediately."
                ),
                ImmediateGuidanceItem(
                    category="DONT",
                    instruction="Do NOT shelter in river valleys, ravines, or ground floor rooms facing unstable hill slopes."
                ),
            ]
        )

        after_section = CitizenGuidanceSection(
            phase="AFTER",
            title="After a Landslide (Recovery & Safety)",
            instructions=[
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="Stay away from the slide area. Secondary and tertiary slides often follow initial slope failures."
                ),
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="Check for injured or trapped neighbors without entering direct danger zones; notify 112/1070 immediately."
                ),
                ImmediateGuidanceItem(
                    category="DO",
                    instruction="Inspect utility lines (electric wires, gas, drinking water pipes) for damage and report hazards."
                ),
                ImmediateGuidanceItem(
                    category="DONT",
                    instruction="Do NOT drive over landslide-damaged roads until cleared and reinforced by highway engineers."
                ),
                ImmediateGuidanceItem(
                    category="DONT",
                    instruction="Do NOT spread unverified social media rumors. Rely strictly on district administration advisories."
                ),
            ]
        )

        warning_signs = [
            "Springs, seeps, or saturated ground appearing in areas that are usually dry.",
            "New cracks, fissures, or bulges appearing in the slope, road asphalt, or building foundations.",
            "Soil moving away from foundations, or fences, utility poles, and trees tilting downslope.",
            "Water in hillside streams suddenly turning intensely muddy or abruptly ceasing flow (indicating upstream blockage).",
            "Faint rumbling or roaring sounds that increase in volume over several seconds.",
        ]

        kit_checklist = [
            "High-power LED flashlight / torch with extra batteries",
            "Sealed drinking water (at least 3 liters per person)",
            "Non-perishable ready-to-eat dry food (biscuits, energy bars, dry fruit)",
            "First aid kit with antiseptic, bandages, scissors, and personal prescription medicines",
            "Fully charged power bank and mobile charging cables",
            "Emergency whistle to signal rescue teams if trapped",
            "Waterproof pouch with government photo IDs, bank passbooks, and property documents",
            "Sturdy footwear and rain ponchos / waterproof jackets",
        ]

        return CitizenGuidanceResponse(
            guidance_sections=[before_section, during_section, after_section],
            natural_warning_signs=warning_signs,
            emergency_kit_checklist=kit_checklist
        )

    @staticmethod
    def get_citizen_contacts() -> CitizenContactsResponse:
        ner_control_rooms = {
            "Sikkim State Disaster Control (Gangtok)": "03592-202461 / 1070",
            "Mizoram Disaster Control Room (Aizawl)": "0389-2342520 / 1070",
            "Nagaland State Disaster Authority (Kohima)": "0370-2291122 / 1070",
            "Meghalaya SDMA Emergency Center (Shillong)": "0364-2502098 / 1070",
            "Arunachal Pradesh Emergency Control (Itanagar)": "0360-2212222 / 1070",
            "Assam State Disaster Management (Guwahati)": "0361-2237221 / 1070",
            "Manipur Relief & Disaster Control (Imphal)": "0385-2443441 / 1070",
            "Tripura State Disaster Control (Agartala)": "0381-2416045 / 1070",
        }
        return CitizenContactsResponse(
            national_emergency="112",
            disaster_management_helpline="1070",
            district_disaster_helpline="1077",
            ambulance_service="108",
            police_helpline="100",
            fire_rescue="101",
            ner_state_control_rooms=ner_control_rooms
        )


citizen_service = CitizenService()
