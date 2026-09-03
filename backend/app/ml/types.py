from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class DataProvenance(str, Enum):
    """
    Explicit provenance classification for all input telemetry and model features.
    Guarantees no synthetic demo values are ever misrepresented as live observations.
    """
    OBSERVED = "OBSERVED"              # Direct measurement from physical sensor or live station telemetry
    FORECAST = "FORECAST"              # Numerical weather prediction model forecast (e.g. Open-Meteo GFS/ECMWF)
    SATELLITE = "SATELLITE"            # Remote sensing Earth Observation (ISRO Bhoonidhi / Sentinel / Landsat)
    MODEL_DERIVED = "MODEL_DERIVED"    # Mathematically derived physical indicator (e.g. API, rolling slope)
    STATIC = "STATIC"                  # Static geospatial raster/survey metadata (DEM slope, elevation, lithology)
    SIMULATED = "SIMULATED"            # Synthetic test fixture injected during simulation/testing mode


class ForecastHorizon(str, Enum):
    """
    Standardized forecast lead-time horizons for landslide occurrence probability.
    """
    HORIZON_6H = "6H"
    HORIZON_12H = "12H"
    HORIZON_24H = "24H"


class AnomalyLevel(str, Enum):
    """
    Operational categorization for Task A: Environmental Anomaly.
    Answers: 'Are environmental conditions statistically unusual?'
    """
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    SEVERE = "SEVERE"
    EXTREME = "EXTREME"


class ModelTier(str, Enum):
    """
    Identifies the algorithmic tier of the prediction provider.
    """
    BASELINE_DETERMINISTIC = "BASELINE_DETERMINISTIC"
    TABULAR_ML_LOGISTIC = "TABULAR_ML_LOGISTIC"
    TABULAR_ML_RANDOM_FOREST = "TABULAR_ML_RANDOM_FOREST"
    TABULAR_ML_GRADIENT_BOOST = "TABULAR_ML_GRADIENT_BOOST"


class TaggedFeatureValue(BaseModel):
    """
    A numerical feature value coupled with its strict data provenance.
    """
    name: str
    value: float
    unit: str
    provenance: DataProvenance
    source_name: str
    timestamp: datetime
    is_missing: bool = False


class LandslideFeatureVector(BaseModel):
    """
    Canonical standardized feature vector passed into Task A (Anomaly) and Task B (Prediction).
    """
    location_id: str
    station_name: str
    timestamp: datetime
    
    # Static Geospatial Features
    slope_angle: TaggedFeatureValue
    elevation: TaggedFeatureValue
    baseline_susceptibility: TaggedFeatureValue
    
    # Dynamic Meteorological Telemetry
    rainfall_1h: TaggedFeatureValue
    rainfall_6h: TaggedFeatureValue
    rainfall_24h: TaggedFeatureValue
    rainfall_72h: TaggedFeatureValue
    
    # Dynamic Soil Moisture Telemetry
    soil_moisture_surface: TaggedFeatureValue   # 0-7 cm
    soil_moisture_middle: TaggedFeatureValue    # 7-28 cm
    soil_moisture_deep: TaggedFeatureValue      # 28-100 cm
    
    # Derived Physical & Statistical Indicators
    antecedent_precipitation_index: TaggedFeatureValue
    consecutive_wet_hours: TaggedFeatureValue
    rainfall_z_score_24h: TaggedFeatureValue
    soil_moisture_trend_slope: TaggedFeatureValue
    id_curve_ratio: TaggedFeatureValue          # Current intensity / critical intensity

    def to_flat_dict(self) -> Dict[str, float]:
        """Returns numerical values for tabular ML inference."""
        return {
            "slope_angle": self.slope_angle.value,
            "elevation": self.elevation.value,
            "baseline_susceptibility": self.baseline_susceptibility.value,
            "rainfall_1h": self.rainfall_1h.value,
            "rainfall_6h": self.rainfall_6h.value,
            "rainfall_24h": self.rainfall_24h.value,
            "rainfall_72h": self.rainfall_72h.value,
            "soil_moisture_surface": self.soil_moisture_surface.value,
            "soil_moisture_middle": self.soil_moisture_middle.value,
            "soil_moisture_deep": self.soil_moisture_deep.value,
            "antecedent_precipitation_index": self.antecedent_precipitation_index.value,
            "consecutive_wet_hours": self.consecutive_wet_hours.value,
            "rainfall_z_score_24h": self.rainfall_z_score_24h.value,
            "soil_moisture_trend_slope": self.soil_moisture_trend_slope.value,
            "id_curve_ratio": self.id_curve_ratio.value,
        }

    def get_provenance_summary(self) -> Dict[str, int]:
        """Counts features by provenance category for audit trails."""
        summary: Dict[str, int] = {}
        for f in [
            self.slope_angle, self.elevation, self.baseline_susceptibility,
            self.rainfall_1h, self.rainfall_6h, self.rainfall_24h, self.rainfall_72h,
            self.soil_moisture_surface, self.soil_moisture_middle, self.soil_moisture_deep,
            self.antecedent_precipitation_index, self.consecutive_wet_hours,
            self.rainfall_z_score_24h, self.soil_moisture_trend_slope, self.id_curve_ratio
        ]:
            key = f.provenance.value
            summary[key] = summary.get(key, 0) + 1
        return summary


class EnvironmentalAnomalyOutput(BaseModel):
    """
    Task A Output: Detection of abnormal environmental / hydrologic conditions.
    NOTE: Anomaly DOES NOT equal landslide occurrence probability.
    """
    location_id: str
    timestamp: datetime
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Normalized environmental anomaly score (0-1)")
    anomaly_level: AnomalyLevel
    rainfall_anomaly_score: float
    soil_wetness_anomaly_score: float
    atmospheric_anomaly_score: float
    primary_abnormal_factors: List[str]
    is_statistically_anomalous: bool
    summary: str


class HorizonProbability(BaseModel):
    """
    Landslide occurrence probability for a specific future window.
    """
    horizon: ForecastHorizon
    probability: float = Field(..., ge=0.0, le=1.0, description="P(landslide within horizon)")
    confidence_interval_low: float = Field(..., ge=0.0, le=1.0)
    confidence_interval_high: float = Field(..., ge=0.0, le=1.0)
    risk_tier: str  # LOW, MODERATE, HIGH, CRITICAL


class LandslidePredictionOutput(BaseModel):
    """
    Task B Output: Model-estimated probability of landslide occurrence over future windows.
    """
    location_id: str
    station_name: str
    timestamp: datetime
    model_tier: ModelTier
    model_version: str
    is_trained_ml_model: bool
    data_provenance_summary: Dict[str, int]
    horizons: Dict[ForecastHorizon, HorizonProbability]
    primary_contributing_features: List[Dict[str, Any]]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    disclaimer: str


class ModelMetadata(BaseModel):
    """
    Manifest describing a registered model, training dataset, and validation metrics.
    """
    model_id: str
    model_name: str
    model_tier: ModelTier
    version: str
    is_trained: bool
    is_active: bool
    training_dataset_name: Optional[str] = None
    training_samples_count: Optional[int] = None
    positive_events_count: Optional[int] = None
    negative_samples_count: Optional[int] = None
    training_timestamp: Optional[datetime] = None
    feature_names: List[str]
    validation_roc_auc: Optional[float] = None
    validation_f1_score: Optional[float] = None
    validation_brier_score: Optional[float] = None
    status_note: str
