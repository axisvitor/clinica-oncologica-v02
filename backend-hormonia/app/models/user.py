"""
User model for healthcare providers (doctors, admins).
"""

from __future__ import annotations

import enum
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
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

    # Surviving live boundary for local-auth/password-reset/admin flows.
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

    _LEGACY_FIREBASE_FIELD_DEFAULTS = {
        "firebase_uid": None,
        "firebase_last_sign_in": None,
        "firebase_created_at": None,
        "firebase_email_verified": False,
        "firebase_display_name": None,
        "firebase_photo_url": None,
        "firebase_custom_claims": {},
        "last_firebase_sync": None,
    }

    def __init__(self, *args, **kwargs):
        legacy_values = {
            key: kwargs.pop(key)
            for key in tuple(self._LEGACY_FIREBASE_FIELD_DEFAULTS.keys())
            if key in kwargs
        }
        super().__init__(*args, **kwargs)
        for field_name, value in legacy_values.items():
            setattr(self, field_name, value)

    @staticmethod
    def _legacy_null_expression(type_):
        return sa.cast(sa.null(), type_)

    def _get_legacy_firebase_field(self, field_name: str):
        if field_name == "firebase_custom_claims":
            value = getattr(self, f"_{field_name}", None)
            return value if isinstance(value, dict) else {}
        if field_name == "firebase_email_verified":
            return bool(getattr(self, f"_{field_name}", False))
        return getattr(
            self,
            f"_{field_name}",
            self._LEGACY_FIREBASE_FIELD_DEFAULTS[field_name],
        )

    def _set_legacy_firebase_field(self, field_name: str, value: Any) -> None:
        if field_name == "firebase_custom_claims":
            setattr(self, f"_{field_name}", self._copy_mapping(value))
            return
        if field_name == "firebase_email_verified":
            setattr(self, f"_{field_name}", bool(value))
            return
        setattr(self, f"_{field_name}", value)

    @hybrid_property
    def firebase_uid(self):
        return self._get_legacy_firebase_field("firebase_uid")

    @firebase_uid.setter
    def firebase_uid(self, value):
        self._set_legacy_firebase_field("firebase_uid", value)

    @firebase_uid.expression
    def firebase_uid(cls):
        return cls._legacy_null_expression(sa.String(length=255))

    @property
    def firebase_last_sign_in(self):
        return self._get_legacy_firebase_field("firebase_last_sign_in")

    @firebase_last_sign_in.setter
    def firebase_last_sign_in(self, value):
        self._set_legacy_firebase_field("firebase_last_sign_in", value)

    @property
    def firebase_created_at(self):
        return self._get_legacy_firebase_field("firebase_created_at")

    @firebase_created_at.setter
    def firebase_created_at(self, value):
        self._set_legacy_firebase_field("firebase_created_at", value)

    @property
    def firebase_email_verified(self):
        return self._get_legacy_firebase_field("firebase_email_verified")

    @firebase_email_verified.setter
    def firebase_email_verified(self, value):
        self._set_legacy_firebase_field("firebase_email_verified", value)

    @property
    def firebase_display_name(self):
        return self._get_legacy_firebase_field("firebase_display_name")

    @firebase_display_name.setter
    def firebase_display_name(self, value):
        self._set_legacy_firebase_field("firebase_display_name", value)

    @property
    def firebase_photo_url(self):
        return self._get_legacy_firebase_field("firebase_photo_url")

    @firebase_photo_url.setter
    def firebase_photo_url(self, value):
        self._set_legacy_firebase_field("firebase_photo_url", value)

    @property
    def firebase_custom_claims(self):
        return self._get_legacy_firebase_field("firebase_custom_claims")

    @firebase_custom_claims.setter
    def firebase_custom_claims(self, value):
        self._set_legacy_firebase_field("firebase_custom_claims", value)

    @property
    def last_firebase_sync(self):
        return self._get_legacy_firebase_field("last_firebase_sync")

    @last_firebase_sync.setter
    def last_firebase_sync(self, value):
        self._set_legacy_firebase_field("last_firebase_sync", value)

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
        return self.last_login

    def set_last_login(self, value, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.last_login = value

    def get_auth_created_at(self):
        return self.auth_created_at

    def set_auth_created_at(self, value, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.auth_created_at = value

    def get_email_verified(self) -> bool:
        return bool(self.email_verified)

    def set_email_verified(self, value: bool, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.email_verified = bool(value)

    def get_display_name(self) -> str | None:
        return self.display_name or self.full_name

    def set_display_name(self, value: str | None, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.display_name = value
        if value and not self.full_name:
            self.full_name = value

    def get_photo_url(self) -> str | None:
        return self.photo_url

    def set_photo_url(self, value: str | None, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.photo_url = value

    def get_preferences_data(self) -> dict[str, Any]:
        return self._copy_mapping(self.preferences)

    def set_preferences_data(
        self,
        value: dict[str, Any] | None,
        *,
        mirror_legacy: bool = False,
    ) -> None:
        del mirror_legacy
        self.preferences = self._copy_mapping(value)

    def get_specialty(self) -> str | None:
        if self.specialty:
            return self.specialty

        specialties = self.get_specialties_data()
        return specialties[0] if specialties else None

    def set_specialty(self, value: str | None, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.specialty = value

    def get_specialties_data(self) -> list[str]:
        return [item for item in self._copy_list(self.specialties) if isinstance(item, str)]

    def set_specialties_data(
        self,
        value: list[str] | None,
        *,
        mirror_legacy: bool = False,
    ) -> None:
        del mirror_legacy
        normalized = [item for item in self._copy_list(value) if isinstance(item, str)]
        self.specialties = normalized
        self.specialty = normalized[0] if normalized else None

    def get_license_number(self) -> str | None:
        return self.license_number

    def set_license_number(self, value: str | None, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.license_number = value

    def get_phone(self) -> str | None:
        return self.phone

    def set_phone(self, value: str | None, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.phone = value

    def get_bio(self) -> str | None:
        return self.bio

    def set_bio(self, value: str | None, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.bio = value

    def get_avatar_url(self) -> str | None:
        return self.avatar_url

    def set_avatar_url(self, value: str | None, *, mirror_legacy: bool = False) -> None:
        del mirror_legacy
        self.avatar_url = value

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
