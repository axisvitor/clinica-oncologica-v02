"""
FastAPI dependencies for upload module.

Contains:
- Redis client dependency
- Cache key generation
- Rate limit checking
- User quota validation
"""

import hashlib
import json
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.redis_manager import get_cache_redis_manager
from app.utils.logging import get_logger

from .config import RATE_LIMIT_SMALL_FILE, RATE_LIMIT_LARGE_FILE

logger = get_logger(__name__)


async def get_redis_client():
    """Get Redis client for caching via centralized RedisManager.

    Uses ``get_cache_redis_manager()`` (DB 1) instead of creating a
    standalone ``redis.from_url()`` connection.  This ensures consistent
    SSL/TLS settings, connection pooling, and DB isolation across the
    entire application.
    """
    try:
        manager = get_cache_redis_manager()
        client = await manager.get_async_client()
        await client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        return None


def generate_cache_key(prefix: str, **kwargs) -> str:
    """Generate cache key from parameters."""
    sorted_params = sorted(kwargs.items())
    param_str = json.dumps(sorted_params, default=str, sort_keys=True)
    # Use SHA-256 instead of MD5 for better collision resistance
    param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
    return f"upload:{prefix}:{param_hash}"


async def check_rate_limit(
    redis_client,
    user_id: UUID,
    file_size: int,
) -> bool:
    """
    Check upload rate limit for user.

    Args:
        redis_client: Redis client
        user_id: User ID
        file_size: File size in bytes

    Returns:
        True if within limits, False if exceeded

    Raises:
        HTTPException: If rate limit exceeded
    """
    if not redis_client:
        return True  # Skip if Redis unavailable

    # Determine rate limit based on file size
    limit = RATE_LIMIT_SMALL_FILE if file_size < 1024 * 1024 else RATE_LIMIT_LARGE_FILE
    key = f"upload:ratelimit:{user_id}"

    try:
        # Get current count
        count = await redis_client.get(key)
        current = int(count) if count else 0

        if current >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Upload rate limit exceeded. Maximum {limit} uploads per hour.",
            )

        # Increment counter
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 3600)  # 1 hour
        await pipe.execute()

        return True
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return True  # Allow on error


async def check_user_quota(
    db,
    user_id: UUID,
    file_size: int,
    redis_client=None,
) -> bool:
    """
    Check if user has quota for upload.

    Args:
        db: Database session
        user_id: User ID
        file_size: File size to upload
        redis_client: Optional Redis client for caching

    Returns:
        True if within quota

    Raises:
        HTTPException: If quota exceeded
    """
    from app.services.upload_quota import get_quota_service, QuotaExceededError
    from app.models.user import User

    try:
        # Get quota service
        quota_service = await get_quota_service(redis_client)

        # Get user tier (from User model)
        user = db.query(User).filter(User.id == user_id).first()
        user_tier = getattr(user, "tier", "free") if user else "free"

        # Check quota
        await quota_service.check_quota(db, user_id, file_size, user_tier)

        return True

    except QuotaExceededError as e:
        logger.warning(
            f"Quota exceeded for user {user_id}",
            extra={
                "user_id": str(user_id),
                "current_usage": e.current_usage,
                "quota_limit": e.quota_limit,
                "file_size": file_size,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Storage quota exceeded. {e}",
        )
    except Exception as e:
        logger.error(f"Quota check failed: {e}", exc_info=True)
        # Fail open on error
        return True
