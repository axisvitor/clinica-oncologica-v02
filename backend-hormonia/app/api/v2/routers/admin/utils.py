"""
Admin utility functions module.

Contains helper functions for user serialization, validation, logging, and statistics.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func

from app.models.user import User
from app.models.appointment import Appointment
from app.utils.request_context import RequestContext
from app.api.v2.dependencies import apply_field_selection


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
        "last_login": getattr(user, "last_login", None),
        "firebase_uid": getattr(user, "firebase_uid", None),
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
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )
    if not any(c.isupper() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter",
        )
    if not any(c.islower() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter",
        )
    if not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one digit",
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


def _status_count(db, status_value: str) -> int:
    """
    Count appointments by status.

    Args:
        db: Database session
        status_value: Appointment status value

    Returns:
        int: Count of appointments with the given status
    """
    return (
        db.query(func.count(Appointment.id))
        .filter(Appointment.status == status_value)
        .scalar()
        or 0
    )
