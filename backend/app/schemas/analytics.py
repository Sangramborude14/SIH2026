from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# --- Playback Schemas ---
class PlaybackFrame(BaseModel):
    step_offset_hours: int  # e.g. -72, -48, -24, -12, -6, 0, +12, +24
    timestamp_str: str
    rainfall_1h_mm: float
    rainfall_24h_mm: float
    soil_moisture_pct: float
    simulated_risk_score: float
    simulated_risk_level: str
    engine_state: str  # NORMAL, MONITORING, WATCH, WARNING, CRITICAL_EMERGENCY
    ground_evidence: Optional[str] = None
    early_warning_issued: bool = False


class HistoricalIncidentSummary(BaseModel):
    id: str
    name: str
    location_id: Optional[str] = None
    state: str
    district: str
    event_date: datetime
    incident_type: str
    actual_impact_summary: str
    casualties: int
    infrastructure_loss: Optional[str] = None
    recorded_lead_time_hours: float
    peak_rainfall_mm: float

    model_config = ConfigDict(from_attributes=True)


class DisasterPlaybackResponse(BaseModel):
    incident: HistoricalIncidentSummary
    total_frames: int
    playback_frames: List[PlaybackFrame]
    model_performance_summary: Dict[str, Any]


# --- Model Calibration & Validation Schemas ---
class ConfusionMatrix(BaseModel):
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    total_evaluations: int


class LeadTimeDistribution(BaseModel):
    mean_lead_time_hours: float
    median_lead_time_hours: float
    min_lead_time_hours: float
    max_lead_time_hours: float
    hist_bins: Dict[str, int]  # e.g. {"<6h": 5, "6-12h": 14, "12-24h": 22, ">24h": 8}


class CalibrationMetricsResponse(BaseModel):
    model_name: str = "NER Multi-Signal Landslide Predictive Model"
    dataset_name: str = "GSI NLSM / NASA GLC Regional Catalog"
    is_trained: bool = False
    model_status: str = "NOT_TRAINED"
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    brier_score: Optional[float] = None
    confusion_matrix: Optional[ConfusionMatrix] = None
    lead_time_distribution: Optional[LeadTimeDistribution] = None
    current_factor_weights: Optional[Dict[str, float]] = None
    verified_disaster_events_count: int = 0
    is_simulated: bool = False
    data_mode: str = "AUTHENTIC_VALIDATION"
    disclaimer: str = "Model status: NOT_TRAINED. Awaiting training on regional ground-truth dataset."



# --- Backtest Sandbox Schemas ---
class BacktestWeightConfig(BaseModel):
    rainfall_24h: float = Field(0.35, ge=0.0, le=1.0)
    rainfall_72h: float = Field(0.15, ge=0.0, le=1.0)
    soil_moisture: float = Field(0.20, ge=0.0, le=1.0)
    slope_angle: float = Field(0.15, ge=0.0, le=1.0)
    susceptibility: float = Field(0.15, ge=0.0, le=1.0)


class BacktestRequest(BaseModel):
    run_name: str = "Custom Weight Optimization Experiment"
    weights: BacktestWeightConfig
    warning_threshold_score: float = Field(70.0, ge=40.0, le=90.0)


class BacktestResponse(BaseModel):
    run_id: str
    run_name: str
    weights_applied: Dict[str, float]
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    mean_lead_time_hours: float
    confusion_matrix: ConfusionMatrix
    comparison_with_baseline: Dict[str, Any]
    recommendation: str
    is_simulated: bool = True
    data_mode: str = "DEMO_SIMULATED"

