from typing import Optional, List, Dict, Any, Literal
from datetime import date, time, datetime
from pydantic import BaseModel, Field, field_validator


class LandslideInventoryRecord(BaseModel):
    """
    Validated historical landslide ground-truth event.
    """
    event_id: str = Field(..., description="Unique event identifier, e.g. GSI-NER-2022-001")
    latitude: float = Field(..., ge=20.0, le=32.0, description="WGS84 latitude within North Eastern Region corridor")
    longitude: float = Field(..., ge=87.0, le=98.0, description="WGS84 longitude within North Eastern Region corridor")
    event_date: date = Field(..., description="Date of slope failure event (YYYY-MM-DD)")
    event_time: Optional[time] = Field(None, description="Optional time of event if known")
    state: str = Field(..., description="State name in NER (Sikkim, Assam, Mizoram, etc.)")
    district: str = Field(..., description="District name")
    location_name: Optional[str] = Field(None, description="Optional locality or corridor description")
    source: str = Field("GSI_NLSM", description="Inventory source (GSI_NLSM, NASA_GLC, BRO, etc.)")
    confidence: Literal["CONFIRMED", "PROBABLE", "UNVERIFIED"] = "CONFIRMED"
    trigger_type: Optional[str] = Field("HEAVY_RAIN", description="Primary hazard trigger")
    landslide_size: Optional[str] = Field("MEDIUM", description="Estimated size / volume category")

    @field_validator("event_date", mode="before")
    @classmethod
    def parse_event_date(cls, v):
        if isinstance(v, str):
            return datetime.strptime(v.strip(), "%Y-%m-%d").date()
        return v

    @field_validator("event_time", mode="before")
    @classmethod
    def parse_event_time(cls, v):
        if v is None or v == "" or v == "None":
            return None
        if isinstance(v, str):
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(v.strip(), fmt).time()
                except ValueError:
                    continue
        return v


class LabeledSample(BaseModel):
    """
    A unified labeled training/testing instance representing spatial unit S at date/timestamp T.
    """
    sample_id: str
    location_id: str
    date: date
    timestamp: datetime
    label: int = Field(..., ge=0, le=1, description="1 for Landslide Event, 0 for Non-Landslide Negative Sample")
    is_hard_negative: bool = False
    spatial_features: Dict[str, float]
    temporal_features: Dict[str, float]
    soil_features: Dict[str, float]
    temporal_context: Dict[str, float]
    provenance_mode: str = "HISTORICAL_REANALYSIS"


class NegativeSamplingConfig(BaseModel):
    """
    Configuration for scientific background/negative sampling.
    """
    negative_to_positive_ratio: float = Field(5.0, ge=1.0, le=50.0, description="Ratio of negative to positive instances")
    hard_negative_pct: float = Field(0.60, ge=0.0, le=1.0, description="Proportion of negatives sampled from rainy/monsoon periods without failure")
    temporal_buffer_days: int = Field(3, ge=1, le=14, description="Exclusion window around positive events to prevent near-event leakage")
    min_rainfall_hard_negative_mm: float = Field(15.0, description="Minimum 24h rainfall to qualify as a hard negative")
    random_seed: int = 42
