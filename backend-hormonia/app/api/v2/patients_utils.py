"""
Patients API v2 - Shared Utilities Module

This module contains shared helper functions extracted from the patients API endpoints.
Functions are used for common operations like user context extraction, data normalization,
access control, and serialization.
"""

from typing import Optional, Tuple
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.models.patient import FlowState
from app.database import get_db
from app.dependencies.auth_dependencies import get_redis_cache
from app.api.v2.patients_shared_helpers import (
    ensure_uuid_sync,
    extract_user_context_sync,
    get_current_user_simple_shared,
    is_admin_sync,
    normalize_cpf_sync,
    normalize_phone_sync,
    validate_and_format_phone_sync,
)


async def _get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    db: Session = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Simplified session validation without ServiceProvider."""
    return await get_current_user_simple_shared(
        session_cookie_id=session_cookie_id,
        db=db,
        redis_cache=redis_cache,
    )


def _extract_user_context(current_user) -> Tuple[Optional[UserRole], Optional[str]]:
    """Return (role, user_id as str) from current_user (model or dict)."""
    return extract_user_context_sync(current_user)


def _is_admin(current_user) -> bool:
    return is_admin_sync(current_user)


def _ensure_uuid(value: Optional[str]):
    return ensure_uuid_sync(value)


def _ensure_patient_access(current_user, patient_doctor_id):
    if _is_admin(current_user):
        return

    _, user_id = _extract_user_context(current_user)
    user_uuid = _ensure_uuid(user_id)

    if user_uuid is None or patient_doctor_id != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this patient",
        )


def _normalize_cpf(cpf: Optional[str]) -> Optional[str]:
    """
    Normalize CPF by removing non-digit characters.

    Args:
        cpf: CPF string with optional formatting (dots, dashes)

    Returns:
        CPF with only digits (max 11 chars) or None
    """
    return normalize_cpf_sync(cpf)


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
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


def _validate_and_format_phone(phone: str, strict: bool = True) -> str:
    """
    Validate and format phone to E.164 format using robust validation.

    Args:
        phone: Phone number to validate
        strict: If True, raise HTTPException on invalid phone

    Returns:
        Phone in E.164 format (+5511987654321)

    Raises:
        HTTPException: If phone is invalid and strict=True
    """
    return validate_and_format_phone_sync(
        phone=phone,
        strict=strict,
        invalid_phone_detail="Invalid phone number",
        include_validation_error=True,
        phone_validation_error_detail="Invalid phone number format",
    )


def _serialize_patient(patient) -> Optional[dict]:
    """Serialize Patient SQLAlchemy model to API-friendly dict."""
    if patient is None:
        return None

    flow_state = getattr(patient, "flow_state", None)
    if isinstance(flow_state, FlowState):
        flow_state_value = flow_state.value
    else:
        flow_state_value = flow_state

    created_at = getattr(patient, "created_at", None)
    updated_at = getattr(patient, "updated_at", None)

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
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _serialize_patient_with_includes(
    patient, include: Optional[list] = None
) -> Optional[dict]:
    """
    Serialize patient with optional eager loaded relations.
    Encapsulates manual serialization logic for nested objects.
    """
    if not patient:
        return None

    patient_dict = _serialize_patient(patient)

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
            # Use getattr to be safe with None/Missing
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
