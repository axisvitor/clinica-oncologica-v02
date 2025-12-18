"""
Utility functions for analytics endpoints.
Extracted from enhanced_analytics.py to reduce god class complexity.
"""

from typing import Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
import hashlib
import json
import logging

from app.models.user import UserRole
from app.schemas.v2.enhanced_analytics import TimeRange

logger = logging.getLogger(__name__)

# Cache TTL configurations (aggressive caching for expensive queries)
REALTIME_CACHE_TTL = 300  # 5 minutes
AGGREGATED_CACHE_TTL = 1800  # 30 minutes
HISTORICAL_CACHE_TTL = 7200  # 2 hours

# Rate limiting (handled by middleware)
RATE_LIMIT_PER_MIN = 20


def get_role_and_user(current_user) -> Tuple[UserRole, Optional[UUID]]:
    """
    Extract role and user UUID from current_user which can be model or dict.

    Args:
        current_user: User object or dictionary with user data

    Returns:
        Tuple of (UserRole, Optional[UUID])
    """
    if isinstance(current_user, dict):
        role_value = current_user.get("role", "doctor")
        user_id = current_user.get("id")
    else:
        role_value = getattr(current_user, "role", "doctor")
        user_id = getattr(current_user, "id", None)

    # Optimize role conversion
    if isinstance(role_value, UserRole):
        role = role_value
    elif isinstance(role_value, str):
        role_lower = role_value.lower()
        if role_lower == "admin":
            role = UserRole.ADMIN
        else:
            role = UserRole.DOCTOR
    else:
        role = UserRole.DOCTOR

    # Optimize UUID conversion
    if user_id:
        try:
            user_uuid = UUID(str(user_id))
        except (TypeError, ValueError):
            user_uuid = None
    else:
        user_uuid = None

    return role, user_uuid


def get_cache_key(endpoint: str, **params) -> str:
    """
    Generate consistent cache key for analytics endpoints.

    Args:
        endpoint: Endpoint name
        **params: Additional parameters to include in cache key

    Returns:
        MD5 hash of cache key components
    """
    sorted_params = sorted(params.items())
    key_components = [endpoint] + [f"{k}={v}" for k, v in sorted_params]
    cache_string = ":".join(map(str, key_components))
    return hashlib.md5(cache_string.encode()).hexdigest()


async def get_cached_result(cache_key: str):
    """
    Get cached analytics result if available.

    Args:
        cache_key: Cache key to lookup

    Returns:
        Cached data or None if not found/expired
    """
    try:
        from app.database import redis_client

        cached_data = redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        # Cache failure should not break functionality
        logger.warning(
            f"Cache retrieval failed for key '{cache_key}': {e}", exc_info=True
        )

    return None


async def set_cached_result(cache_key: str, data: dict, ttl: int):
    """
    Cache analytics result with TTL.

    Args:
        cache_key: Cache key to store under
        data: Data to cache
        ttl: Time to live in seconds
    """
    try:
        from app.database import redis_client

        redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
    except Exception as e:
        # Cache failure should not break functionality
        logger.warning(
            f"Cache storage failed for key '{cache_key}': {e}", exc_info=True
        )


def parse_date_range(
    time_range: TimeRange, start_date: Optional[datetime], end_date: Optional[datetime]
) -> Tuple[datetime, datetime]:
    """
    Parse time range into start and end datetimes.

    Args:
        time_range: Predefined time range enum
        start_date: Optional custom start date
        end_date: Optional custom end date

    Returns:
        Tuple of (start_date, end_date)
    """
    now = datetime.utcnow()

    if start_date and end_date:
        return start_date, end_date

    if time_range == TimeRange.LAST_7_DAYS:
        return now - timedelta(days=7), now
    elif time_range == TimeRange.LAST_30_DAYS:
        return now - timedelta(days=30), now
    elif time_range == TimeRange.LAST_90_DAYS:
        return now - timedelta(days=90), now
    elif time_range == TimeRange.LAST_YEAR:
        return now - timedelta(days=365), now
    else:
        # Default to last 30 days
        return now - timedelta(days=30), now
