"""
Authentication and Authorization Helper Utilities.

Centralized utility functions for user context extraction, admin checks,
and UUID handling across all API v2 routers.

This module consolidates previously duplicated functions from:
- enhanced_analytics.py, enhanced_quiz.py, enhanced_reports.py
- physicians.py, quiz_sessions.py, appointments.py
- medications.py, treatments.py, physicians/base.py
- system/components.py, system/initialization.py
- system/metrics.py, system/validation.py, system/helpers/auth.py
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

    Example:
        >>> role, user_id = extract_user_context(current_user)
        >>> if role == UserRole.ADMIN:
        ...     # Handle admin access
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

    Args:
        current_user: User model instance or dict with user data

    Returns:
        True if user has admin role, False otherwise

    Example:
        >>> if is_admin(current_user):
        ...     # Perform admin-only operation
    """
    role_enum, _ = extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def ensure_uuid(value: Optional[Union[str, UUID]]) -> Optional[UUID]:
    """
    Convert string to UUID safely.

    Handles both string and UUID inputs gracefully.
    Returns None if conversion fails.

    Args:
        value: String UUID or UUID instance

    Returns:
        UUID instance or None if conversion fails

    Example:
        >>> uuid_val = ensure_uuid("550e8400-e29b-41d4-a716-446655440000")
        >>> if uuid_val:
        ...     # Use the UUID
    """
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def get_user_uuid(current_user: Any) -> Optional[UUID]:
    """
    Get user's UUID from current_user context.

    Convenience function that combines extract_user_context and ensure_uuid.

    Args:
        current_user: User model instance or dict with user data

    Returns:
        User's UUID or None if not available
    """
    _, user_id = extract_user_context(current_user)
    return ensure_uuid(user_id)


def has_role(current_user: Any, required_role: UserRole) -> bool:
    """
    Check if current user has a specific role.

    Args:
        current_user: User model instance or dict with user data
        required_role: The role to check for

    Returns:
        True if user has the required role, False otherwise
    """
    role_enum, _ = extract_user_context(current_user)
    return role_enum == required_role


def is_doctor_or_admin(current_user: Any) -> bool:
    """
    Check if current user is a doctor or administrator.

    Args:
        current_user: User model instance or dict with user data

    Returns:
        True if user has doctor or admin role, False otherwise
    """
    role_enum, _ = extract_user_context(current_user)
    return role_enum in (UserRole.ADMIN, UserRole.DOCTOR)
