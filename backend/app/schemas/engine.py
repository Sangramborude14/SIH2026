from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AnomalyReport(BaseModel):
    metric: str
    value: float
    baseline: float
    anomaly_score: float
    is_anomalous: bool
    description: Optional[str] = None


class TrendReport(BaseModel):
    metric: str
    direction: str  # INCREASING, DECREASING, STABLE, UNKNOWN
    slope: float
    description: Optional[str] = None


class DataQualityReportSchema(BaseModel):
    status: str
    completeness_score: float
    freshness_score: float
    missing_fields: List[str] = Field(default_factory=list)
    invalid_fields: List[str] = Field(default_factory=list)
    quality_notes: Optional[str] = None


class SignalAgreementSchema(BaseModel):
    agreement_score: float
    coherent_signals_count: int
    conflicting_signals_count: int
    agreement_level: str
    details: str


class EngineRunRequest(BaseModel):
    location_id: Optional[str] = Field(None, description="Optional target location ID. If omitted, runs for all locations.")
    force_fresh_fetch: bool = Field(False, description="Whether to trigger fresh ingestion before assessment")


class EngineAssessmentResponse(BaseModel):
    location_id: str
    location: str
    state: str
    hazard: str = "LANDSLIDE"
    risk_level: str
    risk_score: float
    confidence: float
    trajectory: str = "STABLE"
    trend: str = "UNKNOWN"
    active_event: bool
    event_id: Optional[str] = None
    event_status: Optional[str] = None
    event_severity: Optional[str] = None
    initial_risk: Optional[float] = None
    peak_risk: Optional[float] = None
    reason_codes: List[str] = Field(default_factory=list)
    anomalies: List[AnomalyReport] = Field(default_factory=list)
    trends: List[TrendReport] = Field(default_factory=list)
    factors: List[Dict[str, Any]] = Field(default_factory=list)
    data_quality: Optional[Dict[str, Any]] = None
    signal_agreement: Optional[Dict[str, Any]] = None
    summary: str
    timestamp: datetime
    engine_version: str = "1.0.0"
    forecast_probabilities: Dict[str, float] = Field(default_factory=dict)
    forecast_available: bool = False
    ml_model_status: str = "NOT_TRAINED"
    ml_model_version: Optional[str] = None
    observed_drivers: List[str] = Field(default_factory=list)



class MultiLocationEngineResponse(BaseModel):
    executed_at: datetime
    locations_evaluated: int
    active_events_count: int
    highest_risk_score: float
    highest_risk_level: str
    engine_version: str = "1.0.0"
    assessments: List[EngineAssessmentResponse]

