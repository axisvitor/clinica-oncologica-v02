"""
Patients API v2 - Base Module

Shared schemas, dependencies, and utilities for patient endpoints.
This module provides common functionality used across all patient routers.
"""

# Standard library imports
# NOTE: Removed 'from __future__ import annotations' to fix Pydantic/FastAPI
# OpenAPI schema generation issues with Query() and Depends() parameters
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

# Third-party imports
from fastapi import Cookie, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

# Local application imports
from app.database import get_db
from app.dependencies.auth_dependencies import get_redis_cache
from app.models.patient import FlowState, Patient
from app.models.user import User, UserRole
from app.utils.phone_validator import (
    PhoneValidationError,
    validate_and_format_phone as validate_phone_util,
)

logger = logging.getLogger(__name__)


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
    redis_cache=Depends(get_redis_cache),
) -> Dict[str, Any]:
    """
    Simplified session validation without ServiceProvider.

    Returns user data dict from Redis cache or database.
    """
    final_session_id = session_cookie_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session ID not provided"
        )

    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_active": user.is_active,
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    return user_data


async def extract_user_context(current_user: Any) -> Tuple[Optional[UserRole], Optional[str]]:
    """
    Extract role and user_id from current_user (model or dict).

    Returns:
        Tuple of (UserRole enum, user_id as string)
    """
    role = None
    user_id = None

    if isinstance(current_user, dict):
        role = current_user.get("role")
        user_id = current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole):
        role_enum = role
    elif isinstance(role, str):
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            role_enum = None
    else:
        role_enum = None

    if user_id is not None:
        user_id = str(user_id)

    return role_enum, user_id


async def is_admin(current_user: Any) -> bool:
    """Check if current user is an administrator."""
    # Direct string check for dict (most common case in v2 API)
    if isinstance(current_user, dict):
        role = current_user.get("role", "")
        if isinstance(role, str) and role.lower() == "admin":
            return True
        if hasattr(role, "value") and role.value == "admin":
            return True
    
    # Fallback to enum-based check
    role_enum, _ = await extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


# ============================================================================
# UUID and Access Control Utilities
# ============================================================================


async def ensure_uuid(value: Optional[str]) -> Optional[UUID]:
    """
    Convert string to UUID safely.

    Returns None if conversion fails.
    """
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


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
    if not cpf:
        return None
    normalized = re.sub(r"[^0-9]", "", cpf)
    return normalized[:11] if normalized else None


async def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone by removing non-digit characters (except +).

    DEPRECATED: Use app.utils.phone_validator.normalize_phone() instead.
    This function is kept for backward compatibility.

    Args:
        phone: Phone string with optional formatting

    Returns:
        Phone with only digits and + or None
    """
    if not phone:
        return None
    normalized = re.sub(r"[^0-9+]", "", phone)
    return normalized if normalized else None


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
    try:
        is_valid, formatted, error = validate_phone_util(
            phone, default_region="BR", strict=False
        )

        if not is_valid:
            if strict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid phone number format",
                )
            return None

        return formatted

    except PhoneValidationError:
        if strict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number format")
        return None


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
                "name": patient.doctor.name,
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
    # NOTE: normalize_phone removed - use app.utils.phone_validator.normalize_phone()
    "validate_and_format_phone",
    # Serialization
    "serialize_patient",
    "serialize_patient_with_includes",
    # Flow state
    "parse_flow_state_filter",
]
