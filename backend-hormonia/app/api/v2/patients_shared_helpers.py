"""
Shared patient access and normalization helpers.

This module centralizes sync utilities reused by patients modules and includes
an async session helper to avoid duplicated get_current_user logic.
"""

from __future__ import annotations

import re
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, TypeVar
from uuid import UUID

from fastapi import HTTPException, status

from app.models.patient import FlowState
from app.models.user import UserRole
from app.api.v2.user_cache_shared import get_or_cache_user_data, ensure_user_is_active
from app.utils.auth_helpers import extract_user_context

TUser = TypeVar("TUser")


async def get_current_user_simple_shared(
    session_cookie_id: Optional[str],
    x_session_id: Optional[str],
    redis_cache: Any,
    fetch_user_by_uid: Callable[[str], Awaitable[Optional[TUser]]],
) -> Dict[str, Any]:
    """Shared session validation and user fetch logic."""
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

    user_data = await get_or_cache_user_data(
        firebase_uid=firebase_uid,
        redis_cache=redis_cache,
        fetch_user_by_uid=fetch_user_by_uid,
    )
    return ensure_user_is_active(user_data)


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


def ensure_uuid_sync(value: Optional[str]) -> Optional[UUID]:
    """Convert string to UUID safely; return None on invalid values."""
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


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
