"""
User model for healthcare providers (doctors, admins).
"""
from sqlalchemy import Column, String, Boolean, Enum, DateTime, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum

from app.models.base import BaseModel


class UserRole(enum.Enum):
    """User role enumeration."""
    ADMIN = "admin"
    DOCTOR = "doctor"


class AuthProvider(enum.Enum):
    """Authentication provider enumeration."""
    LOCAL = "local"
    FIREBASE = "firebase"


class User(BaseModel):
    """User model for healthcare providers."""
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for Firebase users
    full_name = Column(String(255), nullable=True)
    # Use native PostgreSQL enum with explicit name and values_callable to ensure lowercase values
    role = Column(
        Enum(UserRole, name='user_role', native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.DOCTOR
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Firebase authentication fields
    firebase_uid = Column(String(255), unique=True, nullable=True, index=True)
    auth_provider = Column(
        Enum(AuthProvider, name='auth_provider', native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AuthProvider.LOCAL
    )
    firebase_last_sign_in = Column(DateTime(timezone=True), nullable=True)
    firebase_created_at = Column(DateTime(timezone=True), nullable=True)
    firebase_email_verified = Column(Boolean, default=False, nullable=False)
    firebase_display_name = Column(String(255), nullable=True)
    firebase_photo_url = Column(String(500), nullable=True)
    firebase_custom_claims = Column(JSONB, default={}, nullable=False)
    last_firebase_sync = Column(DateTime(timezone=True), nullable=True)

    # Account security fields
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    force_change_password = Column(Boolean, default=False, nullable=False)
    last_password_change = Column(DateTime(timezone=True), nullable=True)

    # Granular permissions (RBAC enhancement)
    # Stores array of permission strings like ["patients:read", "patients:write", "reports:admin"]
    permissions = Column(JSONB, default=[], nullable=False, server_default='[]')

    # Relationships
    patients = relationship("Patient", back_populates="doctor")
    generated_reports = relationship("MedicalReport", back_populates="generated_by_user")
    acknowledged_alerts = relationship("Alert", back_populates="acknowledged_by_user")

    # New relationships for Sprint 1 eager loading optimization
    treatments_managed = relationship("Treatment", back_populates="doctor", foreign_keys="[Treatment.doctor_id]", lazy="select")
    appointments_managed = relationship("Appointment", back_populates="practitioner", foreign_keys="[Appointment.practitioner_id]", lazy="select")
    medications_prescribed = relationship("Medication", back_populates="prescribed_by", foreign_keys="[Medication.prescribed_by_id]", lazy="select")
    notifications = relationship("Notification", back_populates="user", lazy="select")
    sessions = relationship("Session", back_populates="user", lazy="select")
    consents_managed = relationship("Consent", back_populates="consented_by", foreign_keys="[Consent.consented_by_id]", lazy="select")
    
    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role.value}')>"