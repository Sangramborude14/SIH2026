from datetime import datetime, timezone, date
import enum
import uuid
from typing import Optional
from sqlalchemy import Column, String, Float, DateTime, Date, Enum as SqlEnum, Index, JSON
from backend.app.core.database import Base


class TimePrecision(str, enum.Enum):
    EXACT_TIME = "EXACT_TIME"
    HOUR = "HOUR"
    DATE_ONLY = "DATE_ONLY"
    APPROXIMATE = "APPROXIMATE"
    UNKNOWN = "UNKNOWN"


class LandslideEvent(Base):
    """
    Canonical Ground-Truth Landslide Event Catalog.
    Normalizes official inventories (GSI Bhusanket/Bhukosh, NASA GLC, NRSC)
    with strict temporal precision flags to prevent temporal leakage during ML training.
    """
    __tablename__ = "landslide_events"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(64), nullable=False, index=True)  # GSI, NASA_GLC, NRSC, FIELD_VERIFIED, SYNTHETIC
    external_id = Column(String(128), nullable=True, index=True)

    # Geographical coordinates
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)

    # Administrative geography
    state = Column(String(64), nullable=False, index=True)
    district = Column(String(64), nullable=False, index=True)
    location_name = Column(String(256), nullable=True)

    # Occurrence timing and precision
    occurrence_timestamp = Column(DateTime(timezone=True), nullable=True, index=True)
    occurrence_date = Column(Date, nullable=False, index=True)
    time_precision = Column(
        SqlEnum(TimePrecision),
        nullable=False,
        default=TimePrecision.DATE_ONLY,
        index=True
    )

    # Classification and trigger
    landslide_type = Column(String(64), nullable=False, default="RAINFALL_TRIGGERED_SLIDE")
    trigger = Column(String(128), nullable=True, default="HEAVY_RAINFALL")

    # Quality and provenance
    verification_status = Column(String(64), nullable=False, default="FIELD_VALIDATED")
    source_confidence = Column(Float, nullable=False, default=1.0)
    original_source = Column(String(256), nullable=True)
    source_metadata = Column(JSON, nullable=True)

    ingested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    dataset_version = Column(String(32), nullable=False, default="v1.0")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_landslide_source_ext", "source", "external_id"),
        Index("idx_landslide_geo_date", "latitude", "longitude", "occurrence_date"),
        Index("idx_landslide_state_district", "state", "district"),
    )
