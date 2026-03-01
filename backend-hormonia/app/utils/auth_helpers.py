"""
Authentication and Authorization Helper Utilities.

Shared helper functions for user context extraction, admin checks,
and UUID handling across the backend.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple, Union
from uuid import UUID

from app.models.user import UserRole

logger = logging.getLogger(__name__)


def extract_user_context(current_user: Any) -> Tuple[Optional[UserRole], Optional[str]]:
    """
    Extract role and user_id from current_user (model or dict).

    Handles both SQLAlchemy model instances and dictionary representations
    of user data from session/cache.

    Args:
        current_user: User model instance or dict with user data

    Returns:
        Tuple of (UserRole enum or None, user_id as string or None)
    """
    role = None
    user_id = None

    if isinstance(current_user, dict):
        role = current_user.get("role")
        user_id = current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
        role = getattr(current_user, "role", None)

    # Convert role to UserRole enum
    if isinstance(role, UserRole):
        role_enum = role
    elif isinstance(role, str):
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            role_enum = None
    else:
        role_enum = None

    # Ensure user_id is string
    if user_id is not None:
        user_id = str(user_id)

    return role_enum, user_id


def is_admin(current_user: Any) -> bool:
    """
    Check if current user is an administrator.
    """
    role_enum, _ = extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def ensure_uuid(value: Optional[Union[str, UUID]]) -> Optional[UUID]:
    """
    Convert string to UUID safely.

    Handles both string and UUID inputs gracefully.
    Returns None if conversion fails.
    """
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def extract_user_role_and_uuid(
    current_user: Any,
    *,
    default_role: UserRole = UserRole.DOCTOR,
) -> tuple[UserRole, Optional[UUID]]:
    """
    Extract user role and UUID with safe fallbacks.

    Returns:
        (role_enum, user_uuid)
    """
    role_enum, user_id = extract_user_context(current_user)
    resolved_role = role_enum or default_role
    return resolved_role, ensure_uuid(user_id)


def get_user_uuid(current_user: Any) -> Optional[UUID]:
    """
    Get user's UUID from current_user context.
    """
    _, user_id = extract_user_context(current_user)
    return ensure_uuid(user_id)


def has_role(current_user: Any, required_role: UserRole) -> bool:
    """
    Check if current user has a specific role.
    """
    role_enum, _ = extract_user_context(current_user)
    return role_enum == required_role


def is_doctor_or_admin(current_user: Any) -> bool:
    """
    Check if current user is a doctor or administrator.
    """
    role_enum, _ = extract_user_context(current_user)
    return role_enum in (UserRole.ADMIN, UserRole.DOCTOR)


def extract_user_role(
    current_user: Any,
    *,
    default_role: UserRole = UserRole.DOCTOR,
) -> UserRole:
    """
    Extract user role with fallback for invalid/missing role values.
    """
    role_enum, _ = extract_user_context(current_user)
    return role_enum or default_role


def extract_user_id(current_user: Any) -> Optional[str]:
    """
    Extract user ID preserving legacy fallback semantics.
    """
    _, user_id = extract_user_context(current_user)
    if user_id is not None:
        return user_id
    if isinstance(current_user, dict):
        return current_user.get("id")
    return str(getattr(current_user, "id", None))
