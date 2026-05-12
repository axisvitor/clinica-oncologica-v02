"""
Shared patient access and normalization helpers.

This module centralizes sync utilities reused by patients modules and includes
an async session helper to avoid duplicated get_current_user logic.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.patient import FlowState, Patient
from app.models.user import UserRole
from app.api.v2.auth_session_shared import resolve_session_id, get_user_data_from_session
from app.utils.auth_helpers import (
    ensure_uuid as auth_ensure_uuid,
    extract_user_context,
    extract_user_role_and_uuid,
    get_user_uuid,
)

logger = logging.getLogger(__name__)

_PATIENT_ACCESS_DENIED_DETAIL = "Not enough permissions to access this patient"
_PATIENT_NOT_FOUND_DETAIL = "Patient not found"
_INVALID_PATIENT_ID_DETAIL = "Invalid patient ID format"


async def get_current_user_simple_shared(
    session_cookie_id: Optional[str],
    db: Any,
    redis_cache: Any,
) -> Dict[str, Any]:
    """Shared session validation using the canonical session cookie only."""
    final_session_id = resolve_session_id(session_cookie_id=session_cookie_id)
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session cookie required",
        )

    return await get_user_data_from_session(
        session_id=final_session_id,
        db=db,
        redis_cache=redis_cache,
    )


def extract_user_context_sync(
    current_user: Any,
) -> Tuple[Optional[UserRole], Optional[str]]:
    """Return (role, user_id as str) from current_user (model or dict)."""
    return extract_user_context(current_user)


def is_admin_sync(current_user: Any, allow_dict_role_shortcut: bool = False) -> bool:
    """Check admin role with optional dict shortcut compatibility."""
    if allow_dict_role_shortcut and isinstance(current_user, dict):
        role = current_user.get("role", "")
        if isinstance(role, str) and role.lower() == "admin":
            return True
        if hasattr(role, "value") and role.value == "admin":
            return True

    role_enum, _ = extract_user_context_sync(current_user)
    return role_enum == UserRole.ADMIN


def ensure_uuid_sync(value: Optional[str | UUID]) -> Optional[UUID]:
    """Convert string/UUID to UUID safely; return None on invalid values."""
    return auth_ensure_uuid(value)


def _safe_log_patient_access_denied(
    *,
    actor_id: Optional[UUID],
    actor_role: Optional[UserRole],
    patient_id: Optional[Any],
    reason: str,
) -> None:
    """Emit patient ownership denial diagnostics without PHI payloads."""
    try:
        logger.warning(
            "Patient access denied",
            extra={
                "actor_id": str(actor_id) if actor_id else None,
                "actor_role": actor_role.value if actor_role else None,
                "patient_id": str(patient_id) if patient_id is not None else None,
                "resource_id": str(patient_id) if patient_id is not None else None,
                "reason": reason,
            },
        )
    except Exception:
        # Observability must never change the authorization result.
        return


def _raise_patient_access_denied(
    *,
    actor_id: Optional[UUID],
    actor_role: Optional[UserRole],
    patient_id: Optional[Any],
    reason: str,
) -> None:
    _safe_log_patient_access_denied(
        actor_id=actor_id,
        actor_role=actor_role,
        patient_id=patient_id,
        reason=reason,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=_PATIENT_ACCESS_DENIED_DETAIL,
    )


def _extract_patient_access_actor(
    current_user: Any,
) -> Tuple[Optional[UserRole], Optional[UUID]]:
    """Extract a strict role and UUID for patient ownership checks."""
    role_enum, _ = extract_user_context(current_user)
    user_uuid = get_user_uuid(current_user)
    if role_enum is None:
        return None, user_uuid

    resolved_role, resolved_uuid = extract_user_role_and_uuid(
        current_user,
        default_role=role_enum,
    )
    return resolved_role, resolved_uuid


def assert_admin_or_assigned_doctor(
    current_user: Any,
    patient_doctor_id: Optional[str | UUID],
    patient_id: Optional[Any] = None,
) -> None:
    """
    Ensure the actor is an admin or the doctor assigned to the patient.

    Admins may access any patient record. Doctors may access only patients whose
    ``Patient.doctor_id`` matches their authenticated user UUID. Missing,
    malformed, or unsupported user contexts fail closed with a generic 403.
    """
    actor_role, actor_uuid = _extract_patient_access_actor(current_user)

    if actor_role is None:
        _raise_patient_access_denied(
            actor_id=actor_uuid,
            actor_role=None,
            patient_id=patient_id,
            reason="invalid_user_context",
        )

    if actor_uuid is None:
        _raise_patient_access_denied(
            actor_id=None,
            actor_role=actor_role,
            patient_id=patient_id,
            reason="invalid_user_id",
        )

    if actor_role == UserRole.ADMIN:
        return

    if actor_role != UserRole.DOCTOR:
        _raise_patient_access_denied(
            actor_id=actor_uuid,
            actor_role=actor_role,
            patient_id=patient_id,
            reason="unsupported_role",
        )

    assigned_doctor_uuid = auth_ensure_uuid(patient_doctor_id)
    if assigned_doctor_uuid is None:
        _raise_patient_access_denied(
            actor_id=actor_uuid,
            actor_role=actor_role,
            patient_id=patient_id,
            reason="patient_unassigned",
        )

    if assigned_doctor_uuid != actor_uuid:
        _raise_patient_access_denied(
            actor_id=actor_uuid,
            actor_role=actor_role,
            patient_id=patient_id,
            reason="foreign_patient",
        )


async def load_patient_with_access(
    db: Any,
    patient_id: str | UUID,
    current_user: Any,
) -> Patient:
    """Load one patient by ID and enforce the shared ownership boundary."""
    patient_uuid = auth_ensure_uuid(patient_id)
    if patient_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_INVALID_PATIENT_ID_DETAIL,
        )

    result = await db.execute(select(Patient).where(Patient.id == patient_uuid))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PATIENT_NOT_FOUND_DETAIL,
        )

    assert_admin_or_assigned_doctor(
        current_user=current_user,
        patient_doctor_id=getattr(patient, "doctor_id", None),
        patient_id=getattr(patient, "id", patient_uuid),
    )
    return patient


def normalize_cpf_sync(cpf: Optional[str]) -> Optional[str]:
    """Normalize CPF by stripping non-digits and capping at 11 chars."""
    if not cpf:
        return None
    normalized = re.sub(r"[^0-9]", "", cpf)
    return normalized[:11] if normalized else None


def normalize_phone_sync(phone: Optional[str]) -> Optional[str]:
    """Normalize phone to E.164 (BR) while preserving legacy None semantics."""
    if not phone:
        return None

    from app.schemas.validators.phone import PhoneValidationMode, normalize_phone

    try:
        return normalize_phone(phone, mode=PhoneValidationMode.BR_TO_E164, allow_none=True)
    except ValueError:
        return None


def serialize_patient_common_fields_sync(
    patient: Any, extra_fields: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Serialize the common patient field block with optional module-specific fields."""
    flow_state = getattr(patient, "flow_state", None)
    if isinstance(flow_state, FlowState):
        flow_state_value = flow_state.value
    else:
        flow_state_value = flow_state

    patient_data = {
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
    }

    if extra_fields:
        patient_data.update(extra_fields)

    patient_data.update(
        {
            "current_day": getattr(patient, "current_day", None),
            "flow_state": flow_state_value,
            "created_at": getattr(patient, "created_at", None),
            "updated_at": getattr(patient, "updated_at", None),
        }
    )

    return patient_data


def validate_and_format_phone_sync(
    phone: str,
    strict: bool = True,
    invalid_phone_detail: str = "Invalid phone number format",
    include_validation_error: bool = False,
    phone_validation_error_detail: str = "Invalid phone number format",
) -> Optional[str]:
    """Validate and format phone number with configurable strict-mode detail."""
    from app.schemas.validators.phone import (
        PhoneValidationError,
        validate_and_format_phone as validate_phone_util,
    )

    try:
        is_valid, formatted, error = validate_phone_util(
            phone, default_region="BR", strict=False
        )

        if not is_valid:
            if strict:
                detail = (
                    f"{invalid_phone_detail}: {error}"
                    if include_validation_error
                    else invalid_phone_detail
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=detail,
                )
            return None

        return formatted
    except PhoneValidationError:
        if strict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=phone_validation_error_detail,
            )
        return None
