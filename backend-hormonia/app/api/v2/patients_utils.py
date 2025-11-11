"""
Patients API v2 - Shared Utilities Module

This module contains shared helper functions extracted from the patients API endpoints.
Functions are used for common operations like user context extraction, data normalization,
access control, and serialization.
"""

from typing import Optional, Tuple
import re
from uuid import UUID
from fastapi import Cookie, Header, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.patient import FlowState
from app.database import get_db
from app.dependencies.auth_dependencies import get_redis_cache


async def _get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """Simplified session validation without ServiceProvider."""
    final_session_id = session_cookie_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided"
        )

    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        # Query DB directly
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user_data


def _extract_user_context(current_user) -> Tuple[Optional[UserRole], Optional[str]]:
    """Return (role, user_id as str) from current_user (model or dict)."""
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


def _is_admin(current_user) -> bool:
    role_enum, _ = _extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def _ensure_uuid(value: Optional[str]):
    from uuid import UUID

    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


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
    if not cpf:
        return None
    # Remove all non-digit characters
    normalized = re.sub(r'[^0-9]', '', cpf)
    # Limit to 11 digits (CPF max length)
    return normalized[:11] if normalized else None


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone by removing non-digit characters.
    
    DEPRECATED: Use app.utils.phone_validator.normalize_phone() instead.
    This function is kept for backward compatibility.

    Args:
        phone: Phone string with optional formatting

    Returns:
        Phone with only digits or None
    """
    if not phone:
        return None
    # Remove all non-digit characters (spaces, parentheses, dashes)
    normalized = re.sub(r'[^0-9+]', '', phone)
    return normalized if normalized else None


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
    from app.utils.phone_validator import validate_and_format_phone, PhoneValidationError
    
    try:
        is_valid, formatted, error = validate_and_format_phone(
            phone, 
            default_region="BR",
            strict=False
        )
        
        if not is_valid:
            if strict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid phone number: {error}"
                )
            return None
            
        return formatted
        
    except PhoneValidationError as e:
        if strict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        return None


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
        "doctor_id": str(getattr(patient, "doctor_id")) if getattr(patient, "doctor_id", None) else None,
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
