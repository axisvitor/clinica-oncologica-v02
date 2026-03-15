"""
Admin utility functions module.

Contains helper functions for user serialization, validation, logging, and statistics.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.appointment import Appointment
from app.schemas.admin_validation import validate_password_strength as _shared_validate_password_strength
from app.utils.request_context import RequestContext
from app.api.v2.dependencies import apply_field_selection
from app.services.password_reset_service import PasswordResetFailure
from app.utils.timezone import now_sao_paulo


logger = logging.getLogger(__name__)


def _serialize_user(user: User, fields: Optional[List[str]] = None) -> dict:
    """
    Serialize user to dict with optional field selection.

    Args:
        user: User model instance
        fields: Optional list of fields to include

    Returns:
        dict: Serialized user data
    """
    data = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": getattr(
            user,
            "last_login",
            getattr(user, "firebase_last_sign_in", None),
        ),
    }

    if fields:
        required_fields = {
            "id",
            "email",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        }
        normalized_fields = list(set(fields) | required_fields)
        data = apply_field_selection(data, normalized_fields)

    return data


def _validate_password_strength(password: str) -> None:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Raises:
        HTTPException: If password doesn't meet requirements
    """
    try:
        _shared_validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _get_request_id(request: Request) -> Optional[str]:
    """Best-effort request correlation ID used in admin auth diagnostics."""
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id

    monitoring_state = getattr(request.state, "monitoring", None)
    if isinstance(monitoring_state, dict):
        monitoring_request_id = monitoring_state.get("request_id")
        if monitoring_request_id:
            return monitoring_request_id

    return request.headers.get("X-Request-ID")



def _admin_auth_error_content(request: Request, *, error: str, message: str) -> dict[str, Any]:
    """Standardized admin auth failure payload with stable diagnostics."""
    return {
        "error": error,
        "message": message,
        "request_id": _get_request_id(request),
        "timestamp": now_sao_paulo().isoformat(),
    }



def _password_reset_failure_response(
    request: Request,
    failure: PasswordResetFailure,
) -> JSONResponse:
    """Render password-reset failures using the shared diagnostic contract."""
    return JSONResponse(
        status_code=failure.status_code,
        content=_admin_auth_error_content(
            request,
            error=failure.error_code,
            message=failure.message,
        ),
    )


async def _log_admin_action(
    db,
    action: str,
    admin_user: User,
    context: RequestContext,
    target_user_id: Optional[UUID] = None,
    additional_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log admin actions for audit trail.

    Args:
        db: Database session (unused in simplified version)
        action: Action performed (e.g., 'create_user', 'update_role')
        admin_user: Admin user who performed the action
        context: Request context with IP, user agent, etc.
        target_user_id: Optional ID of the target user
        additional_data: Optional additional event data
    """
    try:
        # Simplified logging - just use application logger
        # AuditService was causing db session issues
        event_data = {
            "action": action,
            "admin_user_id": str(admin_user.id),
            "admin_user_email": admin_user.email,
            "ip_address": context.ip_address,
            "user_agent": context.user_agent,
            **(additional_data or {}),
        }

        if target_user_id:
            event_data["target_user_id"] = str(target_user_id)

        logger.info(
            f"Admin action: {action} by {admin_user.email}",
            extra={
                "event_type": f"admin_{action}",
                "category": "admin",
                "user_id": str(admin_user.id),
                "ip": context.ip_address,
                "data": event_data,
            },
        )
    except Exception as e:
        logger.error(f"Failed to log admin action {action}: {e}")


async def _status_count(db: AsyncSession, status_value: str) -> int:
    """
    Count appointments by status.

    Args:
        db: AsyncSession instance
        status_value: Appointment status value

    Returns:
        int: Count of appointments with the given status
    """
    result = await db.execute(
        select(func.count(Appointment.id)).where(Appointment.status == status_value)
    )
    return result.scalar() or 0


async def _status_count_async(db: AsyncSession, status_value: str) -> int:
    """
    Count appointments by status (async version for AsyncSession handlers).

    Args:
        db: AsyncSession instance
        status_value: Appointment status value

    Returns:
        int: Count of appointments with the given status
    """
    result = await db.execute(
        select(func.count(Appointment.id)).where(Appointment.status == status_value)
    )
    return result.scalar() or 0
