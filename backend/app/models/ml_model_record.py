from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Index, JSON
from backend.app.core.database import Base


class MLModelVersionRecord(Base):
    """
    Registry database record for versioned ML model artifacts.
    Tracks artifact paths, cryptographic checksums, metrics, and active deployment status.
    Model binaries themselves are preserved on disk / artifact storage.
    """
    __tablename__ = "ml_model_versions"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_name = Column(String(128), nullable=False, index=True)
    version = Column(String(32), nullable=False, index=True)
    forecast_horizon_hours = Column(Integer, nullable=False, default=24)

    training_source = Column(String(32), nullable=False, default="SYNTHETIC")  # SYNTHETIC, REAL, MIXED
    dataset_name = Column(String(128), nullable=False, default="synthetic_landslide_v1")
    dataset_version = Column(String(32), nullable=False, default="v1.0")

    artifact_path = Column(String(512), nullable=False)
    artifact_sha256 = Column(String(64), nullable=True)

    feature_schema_version = Column(String(32), nullable=False, default="2.0.0")
    status = Column(String(32), nullable=False, default="READY")  # READY, NOT_TRAINED, INCOMPATIBLE, FAILED, STALE

    metrics_json = Column(JSON, nullable=True)

    trained_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_ml_model_ver_name_status", "model_name", "status"),
        Index("idx_ml_model_ver_horizon", "forecast_horizon_hours", "status"),
    )
