from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any


class QualityStatus(str, Enum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    INVALID = "INVALID"


class TrendDirection(str, Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    UNKNOWN = "UNKNOWN"


class RiskTrajectory(str, Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventStatus(str, Enum):
    MONITORING = "MONITORING"
    WATCH = "WATCH"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    HIGH_RISK = "HIGH"
    CRITICAL = "CRITICAL"
    RESOLVING = "RESOLVING"
    RESOLVED = "RESOLVED"
    NORMAL = "MONITORING"


class AssessmentReasonCode(str, Enum):
    HEAVY_RAINFALL = "HEAVY_RAINFALL"
    RAINFALL_ANOMALY = "RAINFALL_ANOMALY"
    PERSISTENT_RAINFALL = "PERSISTENT_RAINFALL"
    SOIL_MOISTURE_ELEVATED = "SOIL_MOISTURE_ELEVATED"
    SOIL_MOISTURE_RISING = "SOIL_MOISTURE_RISING"
    HIGH_TERRAIN_SUSCEPTIBILITY = "HIGH_TERRAIN_SUSCEPTIBILITY"
    HISTORICAL_SUSCEPTIBILITY = "HISTORICAL_SUSCEPTIBILITY"
    MULTI_SIGNAL_AGREEMENT = "MULTI_SIGNAL_AGREEMENT"
    DATA_QUALITY_LOW = "DATA_QUALITY_LOW"
    RECOVERY_DRAINAGE = "RECOVERY_DRAINAGE"
    BASELINE_STABLE = "BASELINE_STABLE"


@dataclass
class DataQualityReport:
    status: QualityStatus
    completeness_score: float = 1.0  # 0.0 to 1.0 (ratio of non-null required fields)
    freshness_score: float = 1.0     # 0.0 to 1.0 (based on minutes since timestamp)
    missing_fields: List[str] = field(default_factory=list)
    invalid_fields: List[str] = field(default_factory=list)
    quality_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "completeness_score": round(self.completeness_score, 2),
            "freshness_score": round(self.freshness_score, 2),
            "missing_fields": self.missing_fields,
            "invalid_fields": self.invalid_fields,
            "quality_notes": self.quality_notes,
        }


@dataclass
class EnvironmentalState:
    """
    Internal normalized environmental domain state.
    Decoupled from database ORM models.
    """
    location_id: str
    timestamp: datetime
    rainfall_1h: float = 0.0
    rainfall_6h: float = 0.0
    rainfall_24h: float = 0.0
    rainfall_72h: float = 0.0
    soil_moisture: Optional[float] = None
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    data_quality: DataQualityReport = field(
        default_factory=lambda: DataQualityReport(QualityStatus.VALID, 1.0, 1.0)
    )


@dataclass
class TerrainProfile:
    location_id: str
    elevation: float
    slope_angle: float
    aspect: str = "SOUTH_EAST"
    terrain_susceptibility: float = 0.5  # 0.0 to 1.0
    geology_type: str = "Himalayan Phyllite & Gneiss"


@dataclass
class HistoricalRiskContext:
    location_id: str
    historical_landslide_events: int = 5
    susceptibility_score: float = 0.65
    data_period_years: int = 10
    monsoon_vulnerability_index: float = 0.70


@dataclass
class AnomalyResult:
    metric: str
    value: float
    baseline: float
    anomaly_score: float
    is_anomalous: bool
    description: Optional[str] = None


@dataclass
class TrendResult:
    metric: str
    direction: TrendDirection
    slope: float
    description: Optional[str] = None


@dataclass
class FactorScoreDetail:
    name: str
    raw_value: Any
    normalized_score: float  # 0.0 to 1.0
    weight: float           # 0.0 to 1.0
    contribution: float     # Points contributed to total 0-100 score
    status: str             # 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
    impact_type: str        # 'INCREASE_RISK', 'DECREASE_RISK', 'NEUTRAL', 'UNAVAILABLE'
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "raw_value": self.raw_value,
            "normalized_score": round(self.normalized_score, 3),
            "weight": round(self.weight, 3),
            "contribution": round(self.contribution, 2),
            "status": self.status,
            "impact_type": self.impact_type,
            "description": self.description,
        }


# Backward compatibility alias
FactorDetail = FactorScoreDetail


@dataclass
class SignalAgreementReport:
    agreement_score: float  # 0.0 to 1.0 (coherence across rainfall, soil, and terrain signals)
    coherent_signals_count: int
    conflicting_signals_count: int
    agreement_level: str    # 'STRONG', 'MODERATE', 'WEAK'
    details: str


@dataclass
class AssessmentOutput:
    location_id: str
    timestamp: datetime
    hazard_type: str
    risk_level: RiskLevel
    risk_score: float
    confidence_score: float
    reason: str
    trajectory: RiskTrajectory = RiskTrajectory.STABLE
    reason_codes: List[AssessmentReasonCode] = field(default_factory=list)
    factors: List[FactorScoreDetail] = field(default_factory=list)
    anomalies: List[AnomalyResult] = field(default_factory=list)
    trends: List[TrendResult] = field(default_factory=list)
    data_quality: DataQualityReport = field(
        default_factory=lambda: DataQualityReport(QualityStatus.VALID, 1.0, 1.0)
    )
    signal_agreement: Optional[SignalAgreementReport] = None
    is_persistent_rain: bool = False
    is_increasing_rain: bool = False
    engine_version: str = "1.0.0"
    forecast_probabilities: Dict[str, float] = field(default_factory=dict)
    forecast_available: bool = False
    ml_model_status: str = "NOT_TRAINED"
    ml_model_version: Optional[str] = None
    observed_drivers: List[str] = field(default_factory=list)


