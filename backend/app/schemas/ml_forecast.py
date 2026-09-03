from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ForecastHorizonDetail(BaseModel):
    landslide_probability: Optional[float] = None
    risk_class: str = "LOW"  # "LOW", "MODERATE", "HIGH", "CRITICAL"
    target_window_start: datetime
    target_window_end: datetime
    decision_threshold: float = 0.50
    threshold_exceeded: bool = False


class CurrentConditionSummary(BaseModel):
    deterministic_risk_score: float
    risk_level: str


class EnvironmentalAnomalySummary(BaseModel):
    score: float
    status: str  # "NORMAL", "ELEVATED", "SEVERE", "EXTREME"
    rainfall_anomaly_score: float = 0.0
    soil_anomaly_score: float = 0.0
    is_statistically_anomalous: bool = False


class LocationForecastResponse(BaseModel):
    location_id: str
    station_name: str
    district: str
    state: str
    latitude: float
    longitude: float
    elevation: float
    slope_angle: float
    baseline_susceptibility: float
    generated_at: datetime
    data_timestamp: datetime
    data_freshness: str = "FRESH"  # "FRESH", "AGING", "STALE"
    model_version: str = "2.0.0"
    model_status: str = "READY"    # "READY", "NOT_TRAINED", "FALLBACK"
    forecast_available: bool = True
    current_condition: CurrentConditionSummary
    environmental_anomaly: EnvironmentalAnomalySummary
    forecast: Dict[str, ForecastHorizonDetail] = Field(default_factory=dict)
    observed_drivers: List[str] = Field(default_factory=list)
    model_contributions: List[Dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = ""


class MultiLocationForecastResponse(BaseModel):
    generated_at: datetime
    model_status: str
    model_version: str
    locations_count: int
    highest_forecast_probability: Optional[float] = None
    highest_risk_location: Optional[str] = None
    forecasts: List[LocationForecastResponse] = Field(default_factory=list)


class GISHeatmapFeature(BaseModel):
    type: str = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class GISHeatmapResponse(BaseModel):
    type: str = "FeatureCollection"
    generated_at: datetime
    forecast_horizon: str = "24H"
    spatial_resolution_note: str = (
        "Station-based observational & ML prediction sectors across North Eastern Region "
        "(Disclosed: Point telemetry & Voronoi catchment perimeters; no unverified 30m interpolation)."
    )
    features: List[GISHeatmapFeature] = Field(default_factory=list)
