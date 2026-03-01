"""
Authentication and Authorization Helpers.

Provides helper functions for:
- User role validation (admin checks)
- Redis client access for caching

Note: Uses centralized auth_helpers for core logic.
"""

from typing import Optional

from app.utils.auth_helpers import is_admin as _is_admin_impl
from app.core.redis_manager import get_async_redis_client
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _is_admin(current_user) -> bool:
    """
    Check if user has admin role.

    Args:
        current_user: User object or dict containing user information

    Returns:
        bool: True if user has admin role, False otherwise
    """
    return _is_admin_impl(current_user)


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
