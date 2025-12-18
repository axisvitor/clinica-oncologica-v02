"""
Session model for user authentication sessions.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    pass


class Session(BaseModel):
    """
    Session model representing user authentication sessions.

    Relationships (configured for eager loading):
    - user: Many-to-one with User (joinedload)
    """

    __tablename__ = "sessions"

    # Foreign Keys
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Session Details
    session_token = Column(String(500), nullable=False, unique=True, index=True)
    refresh_token = Column(String(500), nullable=True, unique=True, index=True)

    # Device Information
    device_id = Column(String(200), nullable=True, index=True)
    device_name = Column(String(200), nullable=True)
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet

    # Network Information
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)

    # Geolocation
    location = Column(JSONB, nullable=True)  # {city, region, country, lat, lon}

    # Session Timing
    last_activity = Column(DateTime(timezone=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Session Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(Text, nullable=True)

    # Security
    is_suspicious = Column(Boolean, default=False, nullable=False, index=True)
    risk_score = Column(String(50), nullable=True)  # low, medium, high

    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    session_metadata = Column(JSONB, nullable=True)

    # Relationships (optimized for eager loading)
    user = relationship("User", back_populates="sessions", lazy="select")

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, is_active={self.is_active}, last_activity={self.last_activity})>"
