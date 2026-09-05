from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ImmediateGuidanceItem(BaseModel):
    category: str  # DO or DONT
    instruction: str


class NearestShelterInfo(BaseModel):
    name: str
    distance_km: Optional[float] = None
    capacity: Optional[int] = None
    availability: str = "OPEN"
    contact_number: Optional[str] = None
    latitude: float
    longitude: float


class CitizenRiskStatusResponse(BaseModel):
    safety_level: str  # LOW, MODERATE, HIGH, CRITICAL
    safety_color: str  # green, yellow, orange, red
    safety_headline: str
    safety_summary: str
    trend_24h: str  # INCREASING, STABLE, DECREASING
    trend_description: str
    location_name: str
    nearest_hazard_km: Optional[float] = None
    action_recommendation: str
    immediate_dos_donts: List[ImmediateGuidanceItem]
    nearest_shelter: Optional[NearestShelterInfo] = None
    emergency_contacts: Dict[str, str]
    timestamp: datetime
    data_mode: str = "LIVE"


class CitizenSOSCreate(BaseModel):
    emergency_type: str = Field(..., description="TRAPPED_BY_LANDSLIDE, ROAD_BLOCKED_STRANDED, MEDICAL_EMERGENCY, EVACUATION_NEEDED, SHELTER_NEEDED, OTHER")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    location_accuracy: Optional[float] = None
    location_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    num_people: int = Field(default=1, ge=1, le=500)
    message: Optional[str] = None
    device_fingerprint: Optional[str] = None


class CitizenSOSStatusUpdate(BaseModel):
    status: str  # SENT, RECEIVED, ASSIGNED, RESCUE_EN_ROUTE, RESOLVED
    assigned_unit: Optional[str] = None
    responder_notes: Optional[str] = None


class CitizenSOSResponse(BaseModel):
    id: str
    emergency_type: str
    status: str
    latitude: float
    longitude: float
    location_accuracy: Optional[float] = None
    location_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    num_people: int
    message: Optional[str] = None
    assigned_unit: Optional[str] = None
    responder_notes: Optional[str] = None
    user_id: Optional[str] = None
    tracking_token: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitizenReportCreate(BaseModel):
    category: str = Field(..., description="GROUND_CRACK, ROCKFALL, MUD_FLOW, LEANING_TREE_POLE, BLOCKED_ROAD_DRAIN, RUMBLING_SOUND, OTHER")
    description: str = Field(..., min_length=5, max_length=2000)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    location_accuracy: Optional[float] = None
    location_name: Optional[str] = None
    contact_phone: Optional[str] = None


class CitizenReportResponse(BaseModel):
    id: str
    report_number: str
    category: str
    description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy: Optional[float] = None
    location_name: Optional[str] = None
    photo_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    user_id: Optional[str] = None
    status: str  # RECEIVED, UNDER_REVIEW, VERIFIED, REJECTED, DUPLICATE
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitizenGuidanceSection(BaseModel):
    phase: str  # BEFORE, DURING, AFTER
    title: str
    instructions: List[ImmediateGuidanceItem]


class CitizenGuidanceResponse(BaseModel):
    guidance_sections: List[CitizenGuidanceSection]
    natural_warning_signs: List[str]
    emergency_kit_checklist: List[str]


class CitizenContactsResponse(BaseModel):
    national_emergency: str = "112"
    disaster_management_helpline: str = "1070"
    district_disaster_helpline: str = "1077"
    ambulance_service: str = "108"
    police_helpline: str = "100"
    fire_rescue: str = "101"
    ner_state_control_rooms: Dict[str, str]
