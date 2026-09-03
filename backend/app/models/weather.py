from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    location_id = Column(String(64), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True, default=lambda: datetime.now(timezone.utc))

    # Meteorological & Atmospheric Metrics
    temperature = Column(Float, nullable=True)     # °C
    humidity = Column(Float, nullable=True)        # %
    pressure = Column(Float, nullable=True)        # hPa
    wind_speed = Column(Float, nullable=True)      # km/h
    wind_direction = Column(Float, nullable=True)  # degrees

    # Precipitation Metrics
    rainfall_1h = Column(Float, nullable=True, default=0.0)   # mm
    rainfall_6h = Column(Float, nullable=True, default=0.0)   # mm
    rainfall_24h = Column(Float, nullable=True, default=0.0)  # mm

    # Hydrological / Subsurface Metrics
    soil_moisture = Column(Float, nullable=True)   # % volumetric saturation

    # Data Provenance & Freshness Metadata
    source = Column(String(64), nullable=False, default="mock_multisignal_simulator", index=True)
    source_version = Column(String(32), nullable=False, default="v1")
    observation_type = Column(String(32), nullable=False, default="OBSERVED")  # OBSERVED, FORECAST, DERIVED, MODELLED, SATELLITE
    quality_score = Column(Float, nullable=False, default=1.0)
    retrieved_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    freshness_status = Column(String(32), nullable=False, default="FRESH")  # FRESH, AGING, STALE, UNKNOWN

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    location = relationship("Location", back_populates="observations")

    __table_args__ = (
        Index("idx_weather_loc_time", "location_id", "timestamp"),
        Index("idx_weather_loc_source", "location_id", "source"),
        UniqueConstraint("location_id", "timestamp", "source", "observation_type", name="uq_weather_loc_time_source_type"),
    )

