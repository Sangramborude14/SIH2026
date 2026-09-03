from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, JSON, Index
from backend.app.core.database import Base


class LandslideForecastRecord(Base):
    """
    Persistent audit record of an AI/ML Landslide Probability Forecast.
    Captures forecast horizon, target window, calibrated probability, model provenance,
    data freshness, and compact feature snapshots for regulatory auditability.
    """
    __tablename__ = "landslide_forecasts"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    location_id = Column(String(64), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_timestamp = Column(DateTime(timezone=True), nullable=False, index=True, default=lambda: datetime.now(timezone.utc))
    forecast_horizon = Column(String(16), nullable=False, index=True)  # e.g., "24H", "12H", "6H"
    target_window_start = Column(DateTime(timezone=True), nullable=False)
    target_window_end = Column(DateTime(timezone=True), nullable=False)

    probability = Column(Float, nullable=True)  # None if model was in fallback/untrained state
    model_version = Column(String(32), nullable=False, default="2.0.0")
    feature_schema_version = Column(String(32), nullable=False, default="2.0.0")
    data_timestamp = Column(DateTime(timezone=True), nullable=False)
    data_freshness = Column(String(32), nullable=False, default="FRESH")  # "FRESH", "AGING", "STALE"
    model_status = Column(String(32), nullable=False, default="READY")    # "READY", "NOT_TRAINED", "FALLBACK"
    decision_threshold = Column(Float, nullable=False, default=0.50)
    warning_status = Column(String(32), nullable=False, default="NORMAL") # "NORMAL", "ADVISORY", "WARNING", "CRITICAL"

    # Compact audit snapshot of key contributing factors (avoiding massive arrays)
    primary_features_compact = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_forecast_loc_horizon_time", "location_id", "forecast_horizon", "prediction_timestamp"),
    )
