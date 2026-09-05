from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class User(Base):
    """
    Centralized user identity model supporting multi-tier RBAC:
    CITIZEN, FIELD_RESPONDER, EXPERT, ADMIN.
    """
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(128), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=False)
    phone_number = Column(String(32), nullable=True, index=True)
    role = Column(String(32), nullable=False, default="CITIZEN", index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_users_role_active", "role", "is_active"),
    )


class RefreshToken(Base):
    """
    Cryptographic refresh token state storage for session rotation,
    device binding, and instant revocation / logout.
    Stores SHA-256 hash of token, never raw secrets.
    """
    __tablename__ = "refresh_tokens"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    user_agent = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_tokens_user_expires", "user_id", "expires_at"),
        Index("idx_refresh_tokens_hash_revoked", "token_hash", "revoked_at"),
    )
