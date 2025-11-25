"""
Authentication and Authorization Helpers.

Provides helper functions for:
- User role validation (admin checks)
- Redis client access for caching
"""

from typing import Optional
import logging

from app.models.user import UserRole
from app.core.redis_client import get_async_redis_client
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _is_admin(current_user) -> bool:
    """
    Check if user has admin role.

    Args:
        current_user: User object or dict containing user information

    Returns:
        bool: True if user has admin role, False otherwise

    Note:
        Handles both User model instances and dict representations.
        Compares against UserRole enum for type safety.
    """
    if isinstance(current_user, dict):
        role = current_user.get("role")
    else:
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole):
        return role == UserRole.ADMIN
    return str(role).upper() == "ADMIN"


async def _get_redis_client() -> Optional[any]:
    """
    Get async Redis client for caching.

    Returns:
        Optional[Redis]: Redis client instance or None if unavailable

    Note:
        Returns None on connection failure without raising exception.
        Logs warning if Redis client initialization fails.
    """
    try:
        return await get_async_redis_client()
    except Exception as e:
        logger.warning(f"Failed to get Redis client: {e}")
        return None


# Public API aliases (without underscore for backward compatibility)
is_admin = _is_admin
get_redis_client = _get_redis_client
