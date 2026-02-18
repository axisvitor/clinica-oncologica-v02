"""
Patients API v2 - Base Module

Shared schemas, dependencies, and utilities for patient endpoints.
This module provides common functionality used across all patient routers.
"""

# Standard library imports
# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from uuid import UUID

# Third-party imports
from fastapi import Cookie, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

# Local application imports
from app.database import get_db
from app.dependencies.auth_dependencies import get_redis_cache
from app.models.patient import FlowState, Patient
from app.models.user import User, UserRole
from app.api.v2.patients_shared_helpers import (
    ensure_uuid_sync,
    extract_user_context_sync,
    get_current_user_simple_shared,
    is_admin_sync,
    normalize_cpf_sync,
    normalize_phone_sync,
    validate_and_format_phone_sync,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.core.redis_manager import FirebaseRedisCache


# Helper for running sync DB access off the event loop.
def _get_user_by_firebase_uid(db: Session, firebase_uid: str) -> Optional[User]:
    return db.query(User).filter(User.firebase_uid == firebase_uid).first()

# ============================================================================
# Pydantic Models - Shared Schemas
# ============================================================================


class CPFValidationRequest(BaseModel):
    """Request model for CPF validation."""

    cpf: str


class EmailCheckResponse(BaseModel):
    """Response model for email existence check."""

    email: EmailStr
    exists: bool


class ImportError(BaseModel):
    """Error details for CSV import failures."""

    row: int
    message: str


class ImportResponse(BaseModel):
    """Response model for CSV import operations."""

    success: int
    failed: int
    errors: List[ImportError]


class PatientStatsResponse(BaseModel):
    """Response model for patient statistics."""

    total_patients: int
    active_patients: int
    inactive_patients: int
    new_this_month: int
    by_status: Dict[str, int]


# ============================================================================
# User Context Utilities
# ============================================================================


async def get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache: "FirebaseRedisCache" = Depends(get_redis_cache),
) -> Dict[str, Any]:
    """
    Simplified session validation without ServiceProvider.

    Returns user data dict from Redis cache or database.
    """
    async def _fetch_user(firebase_uid: str) -> Optional[User]:
        return await run_in_threadpool(_get_user_by_firebase_uid, db, firebase_uid)

    return await get_current_user_simple_shared(
        session_cookie_id=session_cookie_id,
        x_session_id=x_session_id,
        redis_cache=redis_cache,
        fetch_user_by_uid=_fetch_user,
    )


async def extract_user_context(current_user: Any) -> Tuple[Optional[UserRole], Optional[str]]:
    """
    Extract role and user_id from current_user (model or dict).

    Returns:
        Tuple of (UserRole enum, user_id as string)
    """
    return extract_user_context_sync(current_user)


async def is_admin(current_user: Any) -> bool:
    """Check if current user is an administrator."""
    return is_admin_sync(current_user, allow_dict_role_shortcut=True)


# ============================================================================
# UUID and Access Control Utilities
# ============================================================================


async def ensure_uuid(value: Optional[str]) -> Optional[UUID]:
    """
    Convert string to UUID safely.

    Returns None if conversion fails.
    """
    return ensure_uuid_sync(value)


async def ensure_patient_access(current_user: Any, patient_doctor_id: UUID) -> None:
    """
    Verify that current user has access to patient.

    Admins have access to all patients.
    Doctors can only access their own patients.

    Raises:
        HTTPException: If user lacks permissions
    """
    if await is_admin(current_user):
        return

    _, user_id = await extract_user_context(current_user)
    user_uuid = await ensure_uuid(user_id)

    if user_uuid is None or patient_doctor_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this patient",
        )


# ============================================================================
# Data Normalization Utilities
# ============================================================================


async def normalize_cpf(cpf: Optional[str]) -> Optional[str]:
    """
    Normalize CPF by removing non-digit characters.

    Args:
        cpf: CPF string with optional formatting (dots, dashes)

    Returns:
        CPF with only digits (max 11 chars) or None
    """
    return normalize_cpf_sync(cpf)


async def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone number to E.164 format.

    DEPRECATED: Use app.schemas.validators.phone.normalize_phone() instead.
    This function is kept for backward compatibility.

    Args:
        phone: Phone string with optional formatting

    Returns:
        Phone in E.164 format or None
    """
    return normalize_phone_sync(phone)


async def validate_and_format_phone(phone: str, strict: bool = True) -> Optional[str]:
    """
    Validate and format phone to E.164 format using robust validation.

    Args:
        phone: Phone number to validate
        strict: If True, raise HTTPException on invalid phone

    Returns:
        Phone in E.164 format (+5511987654321) or None

    Raises:
        HTTPException: If phone is invalid and strict=True
    """
    return validate_and_format_phone_sync(
        phone=phone,
        strict=strict,
        invalid_phone_detail="Invalid phone number format",
        include_validation_error=False,
        phone_validation_error_detail="Invalid phone number format",
    )


# ============================================================================
# Serialization Utilities
# ============================================================================


async def serialize_patient(patient: Optional[Patient]) -> Optional[Dict[str, Any]]:
    """
    Serialize Patient SQLAlchemy model to API-friendly dict.

    Args:
        patient: Patient model instance

    Returns:
        Dictionary with patient data or None
    """
    if patient is None:
        return None

    flow_state = getattr(patient, "flow_state", None)
    if isinstance(flow_state, FlowState):
        flow_state_value = flow_state.value
    else:
        flow_state_value = flow_state

    payload = getattr(patient, "patient_data", None)
    if not isinstance(payload, dict):
        payload = {}

    medical_history = payload.get("medical_history")
    if not isinstance(medical_history, dict):
        medical_history = {}

    emergency_contact = payload.get("emergency_contact")
    if not isinstance(emergency_contact, dict):
        emergency_contact = {}

    custom_fields = payload.get("custom_fields")
    if not isinstance(custom_fields, dict):
        custom_fields = {}

    emergency_contact_name = emergency_contact.get("name") or custom_fields.get(
        "emergency_contact_name"
    )
    emergency_contact_phone = emergency_contact.get("phone") or custom_fields.get(
        "emergency_contact_phone"
    )

    emergency_contact_text = None
    if emergency_contact_name and emergency_contact_phone:
        emergency_contact_text = f"{emergency_contact_name} - {emergency_contact_phone}"
    elif emergency_contact_name:
        emergency_contact_text = emergency_contact_name
    elif emergency_contact_phone:
        emergency_contact_text = emergency_contact_phone

    return {
        "id": str(getattr(patient, "id")),
        "name": getattr(patient, "name"),
        "email": getattr(patient, "email"),
        "phone": getattr(patient, "phone"),
        "birth_date": getattr(patient, "birth_date"),
        "cpf": getattr(patient, "cpf"),
        "doctor_id": str(getattr(patient, "doctor_id"))
        if getattr(patient, "doctor_id", None)
        else None,
        "treatment_type": getattr(patient, "treatment_type", None),
        "treatment_start_date": getattr(patient, "treatment_start_date", None),
        "doctor_notes": getattr(patient, "doctor_notes", None),
        "diagnosis": getattr(patient, "diagnosis", None),
        "treatment_phase": getattr(patient, "treatment_phase", None),
        "allergies": medical_history.get("allergies"),
        "current_medications": medical_history.get("medications"),
        "comorbidities": medical_history.get("conditions"),
        # Legacy aliases kept for backward compatibility
        "medications": medical_history.get("medications"),
        "blood_type": payload.get("blood_type"),
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_phone": emergency_contact_phone,
        "emergency_contact": emergency_contact_text,
        "current_day": getattr(patient, "current_day", None),
        "flow_state": flow_state_value,
        "created_at": getattr(patient, "created_at", None),
        "updated_at": getattr(patient, "updated_at", None),
    }


async def serialize_patient_with_includes(
    patient: Optional[Patient], include: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Serialize patient with optional eager loaded relations.

    Args:
        patient: Patient model instance
        include: List of relations to include (e.g., ['doctor', 'quiz_sessions'])

    Returns:
        Dictionary with patient data and requested relations
    """
    if not patient:
        return None

    patient_dict = await serialize_patient(patient)

    if include:
        if "doctor" in include and getattr(patient, "doctor", None):
            patient_dict["doctor"] = {
                "id": str(patient.doctor.id),
                "name": patient.doctor.full_name,
                "email": patient.doctor.email,
            }

        if ("quiz_sessions" in include or "quizzes" in include) and hasattr(
            patient, "quiz_sessions"
        ):
            sessions = getattr(patient, "quiz_sessions", [])
            patient_dict["quiz_sessions"] = [
                {
                    "id": str(q.id),
                    "status": q.status,
                    "started_at": q.started_at,
                    "completed_at": q.completed_at,
                    "score": float(q.score) if q.score is not None else None,
                    "passed": q.passed,
                }
                for q in sessions
            ]

    return patient_dict


# ============================================================================
# Flow State Utilities
# ============================================================================


async def parse_flow_state_filter(status_filter: str) -> FlowState:
    """
    Parse and normalize flow state filter string.

    Args:
        status_filter: Status string (e.g., 'active', 'inactive', 'cancelled')

    Returns:
        FlowState enum value

    Raises:
        HTTPException: If status is invalid
    """
    status_value = status_filter.strip().lower()

    # Handle common aliases
    status_aliases = {
        "inactive": FlowState.CANCELLED,
        "canceled": FlowState.CANCELLED,
        "cancelled": FlowState.CANCELLED,
    }

    target_state = status_aliases.get(status_value)
    if target_state is None:
        try:
            target_state = FlowState(status_value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter. Use active, paused, completed, cancelled or inactive.",
            )

    return target_state


__all__ = [
    # Schemas
    "CPFValidationRequest",
    "EmailCheckResponse",
    "ImportError",
    "ImportResponse",
    "PatientStatsResponse",
    # User utilities
    "get_current_user_simple",
    "extract_user_context",
    "is_admin",
    # UUID utilities
    "ensure_uuid",
    "ensure_patient_access",
    # Normalization
    "normalize_cpf",
    # NOTE: normalize_phone deprecated - use app.schemas.validators.phone.normalize_phone()
    "validate_and_format_phone",
    # Serialization
    "serialize_patient",
    "serialize_patient_with_includes",
    # Flow state
    "parse_flow_state_filter",
]
