from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.app.schemas.location import LocationResponse
from backend.app.schemas.weather import WeatherObservationResponse
from backend.app.schemas.risk import RiskAssessmentResponse
from backend.app.schemas.event import DisasterEventResponse


class DashboardSummaryResponse(BaseModel):
    active_events_count: int
    critical_events_count: int
    high_risk_count: int
    moderate_risk_count: int
    low_risk_count: int
    total_monitored_locations: int
    highest_risk_score: float
    highest_risk_level: str
    last_engine_run: datetime
    data_sources_status: str = "OPERATIONAL (SIMULATED / NER SENSORS)"


class LocationMapItem(BaseModel):
    id: str
    name: str
    district: str
    state: str
    latitude: float
    longitude: float
    elevation: float
    slope_angle: float
    susceptibility_score: float
    risk_level: str
    risk_score: float
    confidence_score: float
    active_event: bool
    event_id: Optional[str] = None
    event_status: Optional[str] = None
    event_severity: Optional[str] = None
    rainfall_24h: Optional[float] = 0.0
    rainfall_1h: Optional[float] = 0.0
    soil_moisture: Optional[float] = None
    trend_direction: str = "UNKNOWN"
    last_updated: datetime
    anomaly_score: Optional[float] = None
    anomaly_level: Optional[str] = None
    forecast_probabilities: Dict[str, float] = Field(default_factory=dict)
    forecast_available: bool = False
    model_version: Optional[str] = None
    model_status: Optional[str] = None
    data_freshness: str = "FRESH"



class EventTimelineMilestone(BaseModel):
    timestamp: datetime
    time_label: str
    title: str
    description: str
    category: str  # 'info', 'anomaly', 'escalation', 'event', 'resolution'
    severity: Optional[str] = None


class LocationInvestigationResponse(BaseModel):
    location: LocationResponse
    latest_assessment: Optional[RiskAssessmentResponse] = None
    active_event: Optional[DisasterEventResponse] = None
    weather_history: List[WeatherObservationResponse] = Field(default_factory=list)
    risk_history: List[RiskAssessmentResponse] = Field(default_factory=list)
    event_timeline: List[EventTimelineMilestone] = Field(default_factory=list)
