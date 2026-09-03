from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class WeatherForecastSnapshot(Base):
    """
    Archived multi-horizon weather forecast snapshots.
    Preserves what forecast was actually available at prediction time (T)
    for target windows (T + 6h, T + 12h, T + 24h) to avoid temporal leakage.
    Strictly isolated from observational data.
    """
    __tablename__ = "weather_forecast_snapshots"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    location_id = Column(String(64), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Forecast issuance and validity temporal bounds
    forecast_issued_at = Column(DateTime(timezone=True), nullable=False, index=True)
    forecast_valid_at = Column(DateTime(timezone=True), nullable=False, index=True)
    forecast_horizon_hours = Column(Integer, nullable=False)  # 6, 12, 24, 48, 72

    # Forecasted meteorological variables
    precipitation_mm = Column(Float, nullable=True, default=0.0)
    rain_mm = Column(Float, nullable=True, default=0.0)
    soil_moisture = Column(Float, nullable=True)  # Volumetric %
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    wind_speed = Column(Float, nullable=True)

    # Data Provenance
    source = Column(String(64), nullable=False, default="OPEN_METEO")
    model_name = Column(String(64), nullable=False, default="open-meteo-seamless")
    retrieved_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    location = relationship("Location")

    __table_args__ = (
        Index("idx_forecast_snap_loc_valid", "location_id", "forecast_valid_at"),
        Index("idx_forecast_snap_loc_issued", "location_id", "forecast_issued_at"),
        Index("idx_forecast_snap_horizon", "location_id", "forecast_horizon_hours", "forecast_valid_at"),
    )
