from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from backend.app.ml.types import (
    DataProvenance,
    ForecastHorizon,
    AnomalyLevel,
    ModelTier,
    TaggedFeatureValue,
    HorizonProbability,
)


class TaggedFeatureValueSchema(BaseModel):
    name: str
    value: float
    unit: str
    provenance: DataProvenance
    source_name: str
    timestamp: datetime
    is_missing: bool = False


class StationFeaturesResponse(BaseModel):
    location_id: str
    station_name: str
    timestamp: datetime
    features: Dict[str, TaggedFeatureValueSchema]
    provenance_summary: Dict[str, int]
    flat_vector: Dict[str, float]


class EnvironmentalAnomalyResponse(BaseModel):
    location_id: str
    timestamp: datetime
    anomaly_score: float
    anomaly_level: AnomalyLevel
    rainfall_anomaly_score: float
    soil_wetness_anomaly_score: float
    atmospheric_anomaly_score: float
    primary_abnormal_factors: List[str]
    is_statistically_anomalous: bool
    summary: str


class LandslidePredictionResponse(BaseModel):
    location_id: str
    station_name: str
    timestamp: datetime
    model_tier: ModelTier
    model_version: str
    is_trained_ml_model: bool
    data_provenance_summary: Dict[str, int]
    horizons: Dict[str, HorizonProbability]
    primary_contributing_features: List[Dict[str, Any]]
    confidence_score: float
    disclaimer: str


class ModelRegistryStatusResponse(BaseModel):
    registry_version: str
    active_model_id: str
    active_model_tier: str
    is_active_model_trained_ml: bool
    models_count: int
    feature_count: int
    features_monitored: List[str]
    registered_models: List[Dict[str, Any]]
    operational_status: str
    training_pipeline_status: str
    model_status: Optional[str] = "READY"
    active_model_version: Optional[str] = "2.0.0"

