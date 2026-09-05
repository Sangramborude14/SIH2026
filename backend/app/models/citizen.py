from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, Index, Text, ForeignKey
from backend.app.core.database import Base


class CitizenSOS(Base):
    """
    Emergency distress beacon dispatched by a citizen before, during, or after a landslide.
    Supports tracking from initial dispatch to rescue resolution.
    """
    __tablename__ = "citizen_sos"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Category: TRAPPED_BY_LANDSLIDE, ROAD_BLOCKED_STRANDED, MEDICAL_EMERGENCY, EVACUATION_NEEDED, SHELTER_NEEDED, OTHER
    emergency_type = Column(String(64), nullable=False, default="EVACUATION_NEEDED", index=True)
    
    # Progression status: SENT, RECEIVED, ASSIGNED, RESCUE_EN_ROUTE, RESOLVED
    status = Column(String(32), nullable=False, default="RECEIVED", index=True)
    
    # Location coordinates & accuracy
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_accuracy = Column(Float, nullable=True)  # in meters
    location_name = Column(String(255), nullable=True)
    
    # Contact & situation details
    contact_name = Column(String(128), nullable=True)
    contact_phone = Column(String(32), nullable=True, index=True)
    num_people = Column(Integer, nullable=False, default=1)
    message = Column(Text, nullable=True)
    
    # Client identifier for duplicate suppression
    device_fingerprint = Column(String(128), nullable=True, index=True)
    
    # Ownership & Anonymous Tracking
    user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tracking_token = Column(String(64), nullable=False, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Command Center & Rescue Unit Assignment
    assigned_unit = Column(String(128), nullable=True)
    responder_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_citizen_sos_status_created", "status", "created_at"),
        Index("idx_citizen_sos_phone_created", "contact_phone", "created_at"),
        Index("idx_citizen_sos_user_created", "user_id", "created_at"),
    )


class CitizenReport(Base):
    """
    Abnormality or pre-landslide hazard report submitted by a citizen with photo evidence.
    Processed through human verification before altering hazard intelligence.
    """
    __tablename__ = "citizen_reports"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_number = Column(String(32), nullable=False, unique=True, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Abnormality category: GROUND_CRACK, ROCKFALL, MUD_FLOW, LEANING_TREE_POLE, BLOCKED_ROAD_DRAIN, RUMBLING_SOUND, OTHER
    category = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    # Location information
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_accuracy = Column(Float, nullable=True)
    location_name = Column(String(255), nullable=True)
    
    # Optional citizen contact
    contact_phone = Column(String(32), nullable=True)
    
    # Media attachment stored via StorageProvider
    photo_storage_key = Column(String(255), nullable=True)
    thumbnail_storage_key = Column(String(255), nullable=True)
    photo_content_hash = Column(String(64), nullable=True, index=True)
    photo_url = Column(String(512), nullable=True)
    photo_size_bytes = Column(Float, nullable=True)
    mime_type = Column(String(64), nullable=True)
    
    # Verification workflow: RECEIVED, UNDER_REVIEW, VERIFIED, REJECTED, DUPLICATE
    status = Column(String(32), nullable=False, default="RECEIVED", index=True)
    verified_by = Column(String(128), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_citizen_rep_cat_status", "category", "status"),
        Index("idx_citizen_rep_created", "created_at"),
        Index("idx_citizen_rep_user_created", "user_id", "created_at"),
    )
