"""
User model for healthcare providers (doctors, admins).
"""

from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

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
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=UserRole.DOCTOR,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Canonical live auth/profile/settings storage.
    last_login = Column(DateTime(timezone=True), nullable=True)
    auth_created_at = Column(DateTime(timezone=True), nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False, server_default=text("false"))
    display_name = Column(String(255), nullable=True)
    photo_url = Column(String(500), nullable=True)
    preferences = Column(
        JSONB,
        default=dict,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    specialty = Column(String(255), nullable=True)
    specialties = Column(
        JSONB,
        default=list,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    license_number = Column(String(50), nullable=True)
    phone = Column(String(32), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Compatibility / historical auth linkage that still exists while downstream
    # readers/tests finish the cut-over.
    firebase_uid = Column(String(255), unique=True, nullable=True, index=True)
    auth_provider = Column(
        Enum(
            AuthProvider,
            name="auth_provider",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AuthProvider.LOCAL,
    )

    # Legacy Firebase-era storage preserved for transition compatibility only.
    firebase_last_sign_in = Column(DateTime(timezone=True), nullable=True)
    firebase_created_at = Column(DateTime(timezone=True), nullable=True)
    firebase_email_verified = Column(Boolean, default=False, nullable=False)
    firebase_display_name = Column(String(255), nullable=True)
    firebase_photo_url = Column(String(500), nullable=True)
    firebase_custom_claims = Column(JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb"))
    last_firebase_sync = Column(DateTime(timezone=True), nullable=True)

    # Account security fields
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    force_change_password = Column(Boolean, default=False, nullable=False)
    last_password_change = Column(DateTime(timezone=True), nullable=True)

    # Granular permissions (RBAC enhancement)
    # Stores array of permission strings like ["patients:read", "patients:write", "reports:admin"]
    permissions = Column(JSONB, default=list, nullable=False, server_default="[]")

    # Relationships
    patients = relationship("Patient", back_populates="doctor")
    generated_reports = relationship(
        "MedicalReport", back_populates="generated_by_user"
    )
    acknowledged_alerts = relationship("Alert", back_populates="acknowledged_by_user")

    # New relationships for Sprint 1 eager loading optimization
    treatments_managed = relationship(
        "Treatment",
        back_populates="doctor",
        foreign_keys="[Treatment.doctor_id]",
        lazy="select",
    )
    appointments_managed = relationship(
        "Appointment",
        back_populates="practitioner",
        foreign_keys="[Appointment.practitioner_id]",
        lazy="select",
    )
    medications_prescribed = relationship(
        "Medication",
        back_populates="prescribed_by",
        foreign_keys="[Medication.prescribed_by_id]",
        lazy="select",
    )
    notifications = relationship("Notification", back_populates="user", lazy="select")
    sessions = relationship("Session", back_populates="user", lazy="select")
    consents_managed = relationship(
        "Consent",
        back_populates="consented_by",
        foreign_keys="[Consent.consented_by_id]",
        lazy="select",
    )

    @staticmethod
    def _copy_mapping(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _copy_list(value: Any) -> list[Any]:
        return list(value) if isinstance(value, list) else []

    def _legacy_claims(self) -> dict[str, Any]:
        return self._copy_mapping(self.firebase_custom_claims)

    def _set_legacy_claim(self, key: str, value: Any) -> None:
        claims = self._legacy_claims()
        if value in (None, "", [], {}):
            claims.pop(key, None)
        else:
            claims[key] = value
        self.firebase_custom_claims = claims

    def get_last_login(self):
        return self.last_login or self.firebase_last_sign_in

    def set_last_login(self, value, *, mirror_legacy: bool = True) -> None:
        self.last_login = value
        if mirror_legacy:
            self.firebase_last_sign_in = value

    def get_auth_created_at(self):
        return self.auth_created_at or self.firebase_created_at

    def set_auth_created_at(self, value, *, mirror_legacy: bool = True) -> None:
        self.auth_created_at = value
        if mirror_legacy:
            self.firebase_created_at = value

    def get_email_verified(self) -> bool:
        if self.email_verified is not None:
            return bool(self.email_verified)
        return bool(self.firebase_email_verified)

    def set_email_verified(self, value: bool, *, mirror_legacy: bool = True) -> None:
        verified = bool(value)
        self.email_verified = verified
        if mirror_legacy:
            self.firebase_email_verified = verified

    def get_display_name(self) -> str | None:
        return self.display_name or self.firebase_display_name or self.full_name

    def set_display_name(self, value: str | None, *, mirror_legacy: bool = True) -> None:
        self.display_name = value
        if mirror_legacy:
            self.firebase_display_name = value
        if value and not self.full_name:
            self.full_name = value

    def get_photo_url(self) -> str | None:
        return self.photo_url or self.firebase_photo_url

    def set_photo_url(self, value: str | None, *, mirror_legacy: bool = True) -> None:
        self.photo_url = value
        if mirror_legacy:
            self.firebase_photo_url = value

    def get_preferences_data(self) -> dict[str, Any]:
        canonical = self._copy_mapping(self.preferences)
        if canonical:
            return canonical

        legacy_preferences = self._legacy_claims().get("preferences")
        if isinstance(legacy_preferences, dict):
            return dict(legacy_preferences)

        return canonical

    def set_preferences_data(
        self,
        value: dict[str, Any] | None,
        *,
        mirror_legacy: bool = True,
    ) -> None:
        normalized = self._copy_mapping(value)
        self.preferences = normalized
        if mirror_legacy:
            self._set_legacy_claim("preferences", normalized)

    def get_specialty(self) -> str | None:
        if self.specialty:
            return self.specialty

        legacy_claims = self._legacy_claims()
        legacy_specialty = legacy_claims.get("specialty")
        if isinstance(legacy_specialty, str) and legacy_specialty.strip():
            return legacy_specialty

        specialties = self.get_specialties_data()
        return specialties[0] if specialties else None

    def set_specialty(self, value: str | None, *, mirror_legacy: bool = True) -> None:
        self.specialty = value
        if mirror_legacy:
            self._set_legacy_claim("specialty", value)

    def get_specialties_data(self) -> list[str]:
        canonical = [item for item in self._copy_list(self.specialties) if isinstance(item, str)]
        if canonical:
            return canonical

        legacy_claims = self._legacy_claims()
        legacy_specialties = legacy_claims.get("specialties")
        if isinstance(legacy_specialties, list):
            return [item for item in legacy_specialties if isinstance(item, str)]

        legacy_specialty = legacy_claims.get("specialty")
        if isinstance(legacy_specialty, str) and legacy_specialty.strip():
            return [legacy_specialty]

        return canonical

    def set_specialties_data(
        self,
        value: list[str] | None,
        *,
        mirror_legacy: bool = True,
    ) -> None:
        normalized = [item for item in self._copy_list(value) if isinstance(item, str)]
        self.specialties = normalized
        if mirror_legacy:
            self._set_legacy_claim("specialties", normalized)
            if normalized:
                self._set_legacy_claim("specialty", normalized[0])

    def get_license_number(self) -> str | None:
        return self.license_number or self._legacy_claims().get("license_number")

    def set_license_number(self, value: str | None, *, mirror_legacy: bool = True) -> None:
        self.license_number = value
        if mirror_legacy:
            self._set_legacy_claim("license_number", value)

    def get_phone(self) -> str | None:
        return self.phone or self._legacy_claims().get("phone")

    def set_phone(self, value: str | None, *, mirror_legacy: bool = True) -> None:
        self.phone = value
        if mirror_legacy:
            self._set_legacy_claim("phone", value)

    def get_bio(self) -> str | None:
        return self.bio or self._legacy_claims().get("bio")

    def set_bio(self, value: str | None, *, mirror_legacy: bool = True) -> None:
        self.bio = value
        if mirror_legacy:
            self._set_legacy_claim("bio", value)

    def get_avatar_url(self) -> str | None:
        return self.avatar_url or self._legacy_claims().get("avatar_url")

    def set_avatar_url(self, value: str | None, *, mirror_legacy: bool = True) -> None:
        self.avatar_url = value
        if mirror_legacy:
            self._set_legacy_claim("avatar_url", value)

    @property
    def password_hash(self):
        """
        Backward-compatible alias for legacy payloads/tests.

        Canonical field remains `hashed_password`.
        """
        return self.hashed_password

    @password_hash.setter
    def password_hash(self, value):
        self.hashed_password = value

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role.value}')>"
