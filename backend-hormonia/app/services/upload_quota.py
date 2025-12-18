"""
Upload Quota Tracking Service.

Manages user upload quotas with Redis caching for performance.
Tracks per-user storage usage and enforces quota limits.

Features:
- Per-user quota tracking
- Redis-cached quota counters
- Database persistence
- Quota enforcement
- Usage analytics
- Quota increase/decrease operations
"""

from typing import Optional, Dict, Any
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import func

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class QuotaExceededError(Exception):
    """Exception raised when user quota is exceeded."""

    def __init__(self, message: str, current_usage: int, quota_limit: int):
        """
        Initialize quota exceeded error.

        Args:
            message: Error message
            current_usage: Current storage usage in bytes
            quota_limit: Quota limit in bytes
        """
        super().__init__(message)
        self.current_usage = current_usage
        self.quota_limit = quota_limit
        self.available = quota_limit - current_usage


class UploadQuotaService:
    """
    Service for tracking and enforcing user upload quotas.

    Manages storage quotas per user with Redis caching for fast lookups.
    Persists quota data to database for durability.

    Configuration (via environment variables):
        DEFAULT_USER_QUOTA_GB: Default quota per user in GB (default: 1)
        PREMIUM_USER_QUOTA_GB: Premium user quota in GB (default: 10)
        QUOTA_CACHE_TTL: Cache TTL in seconds (default: 300)
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize upload quota service.

        Args:
            redis_client: Optional Redis client for caching
        """
        self.redis = redis_client

        # Load quota configuration
        self.default_quota = (
            getattr(settings, "DEFAULT_USER_QUOTA_GB", 1) * 1024 * 1024 * 1024
        )  # Convert GB to bytes

        self.premium_quota = (
            getattr(settings, "PREMIUM_USER_QUOTA_GB", 10) * 1024 * 1024 * 1024
        )

        self.cache_ttl = getattr(settings, "QUOTA_CACHE_TTL", 300)  # 5 minutes

        logger.info(
            f"Upload quota service initialized: "
            f"default={self.default_quota / (1024**3):.1f}GB, "
            f"premium={self.premium_quota / (1024**3):.1f}GB"
        )

    async def check_quota(
        self, db: Any, user_id: UUID, file_size: int, user_tier: str = "free"
    ) -> bool:
        """
        Check if user has quota for upload.

        Args:
            db: Database session
            user_id: User ID
            file_size: Size of file to upload in bytes
            user_tier: User tier (free, premium, enterprise)

        Returns:
            True if user has quota, False otherwise

        Raises:
            QuotaExceededError: If quota would be exceeded
        """
        # Get current usage
        current_usage = await self.get_usage(db, user_id)

        # Get quota limit
        quota_limit = self._get_quota_limit(user_tier)

        # Calculate new usage
        new_usage = current_usage + file_size

        if new_usage > quota_limit:
            logger.warning(
                f"Quota exceeded for user {user_id}: "
                f"{new_usage / (1024**2):.2f}MB > {quota_limit / (1024**2):.2f}MB",
                extra={
                    "user_id": str(user_id),
                    "current_usage": current_usage,
                    "file_size": file_size,
                    "quota_limit": quota_limit,
                    "user_tier": user_tier,
                },
            )

            raise QuotaExceededError(
                f"Upload would exceed quota limit. "
                f"Current: {current_usage / (1024**2):.1f}MB, "
                f"Quota: {quota_limit / (1024**2):.1f}MB, "
                f"Available: {(quota_limit - current_usage) / (1024**2):.1f}MB",
                current_usage=current_usage,
                quota_limit=quota_limit,
            )

        return True

    async def get_usage(self, db: Any, user_id: UUID) -> int:
        """
        Get current storage usage for user.

        Checks Redis cache first, falls back to database.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Current usage in bytes
        """
        # Try cache first
        if self.redis:
            try:
                cache_key = f"quota:usage:{user_id}"
                cached = await self.redis.get(cache_key)

                if cached:
                    logger.debug(f"Cache hit for quota usage: {user_id}")
                    return int(cached)
            except Exception as e:
                logger.warning(f"Failed to get cached quota: {e}")

        # Query database
        usage = await self._query_database_usage(db, user_id)

        # Cache the result
        if self.redis:
            try:
                cache_key = f"quota:usage:{user_id}"
                await self.redis.setex(cache_key, self.cache_ttl, usage)
            except Exception as e:
                logger.warning(f"Failed to cache quota usage: {e}")

        return usage

    async def _query_database_usage(self, db: Any, user_id: UUID) -> int:
        """
        Query database for user's storage usage.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Total storage usage in bytes
        """
        try:
            # Import here to avoid circular dependencies
            from app.models.upload import Upload

            # Sum all upload sizes for user
            result = (
                db.query(func.sum(Upload.file_size).label("total_size"))
                .filter(Upload.user_id == user_id, Upload.deleted_at.is_(None))
                .first()
            )

            total_size = result.total_size if result and result.total_size else 0

            logger.debug(
                f"Database query for user {user_id} usage: {total_size / (1024**2):.2f}MB"
            )

            return int(total_size)

        except Exception as e:
            logger.error(f"Failed to query database usage: {e}", exc_info=True)
            # Return 0 on error to fail open (allow uploads)
            return 0

    async def increment_usage(self, db: Any, user_id: UUID, file_size: int) -> int:
        """
        Increment user's storage usage.

        Args:
            db: Database session
            user_id: User ID
            file_size: Size of uploaded file in bytes

        Returns:
            New total usage in bytes
        """
        # Update cache
        if self.redis:
            try:
                cache_key = f"quota:usage:{user_id}"
                new_usage = await self.redis.incrby(cache_key, file_size)
                await self.redis.expire(cache_key, self.cache_ttl)

                logger.info(
                    f"Incremented quota for user {user_id}: +{file_size / (1024**2):.2f}MB "
                    f"(total: {new_usage / (1024**2):.2f}MB)"
                )

                return int(new_usage)
            except Exception as e:
                logger.warning(f"Failed to increment cached quota: {e}")

        # Fallback: return current usage
        return await self.get_usage(db, user_id)

    async def decrement_usage(self, db: Any, user_id: UUID, file_size: int) -> int:
        """
        Decrement user's storage usage (after file deletion).

        Args:
            db: Database session
            user_id: User ID
            file_size: Size of deleted file in bytes

        Returns:
            New total usage in bytes
        """
        # Update cache
        if self.redis:
            try:
                cache_key = f"quota:usage:{user_id}"
                new_usage = await self.redis.decrby(cache_key, file_size)

                # Ensure usage doesn't go negative
                if new_usage < 0:
                    await self.redis.set(cache_key, 0)
                    new_usage = 0

                await self.redis.expire(cache_key, self.cache_ttl)

                logger.info(
                    f"Decremented quota for user {user_id}: -{file_size / (1024**2):.2f}MB "
                    f"(total: {new_usage / (1024**2):.2f}MB)"
                )

                return int(new_usage)
            except Exception as e:
                logger.warning(f"Failed to decrement cached quota: {e}")

        # Fallback: return current usage
        return await self.get_usage(db, user_id)

    async def get_quota_info(
        self, db: Any, user_id: UUID, user_tier: str = "free"
    ) -> Dict[str, Any]:
        """
        Get quota information for user.

        Args:
            db: Database session
            user_id: User ID
            user_tier: User tier

        Returns:
            Dictionary with quota information
        """
        current_usage = await self.get_usage(db, user_id)
        quota_limit = self._get_quota_limit(user_tier)

        return {
            "user_id": str(user_id),
            "current_usage_bytes": current_usage,
            "current_usage_mb": round(current_usage / (1024**2), 2),
            "quota_limit_bytes": quota_limit,
            "quota_limit_mb": round(quota_limit / (1024**2), 2),
            "available_bytes": quota_limit - current_usage,
            "available_mb": round((quota_limit - current_usage) / (1024**2), 2),
            "usage_percent": round((current_usage / quota_limit * 100), 2),
            "tier": user_tier,
        }

    async def invalidate_cache(self, user_id: UUID):
        """
        Invalidate cached quota for user.

        Forces next quota check to query database.

        Args:
            user_id: User ID
        """
        if self.redis:
            try:
                cache_key = f"quota:usage:{user_id}"
                await self.redis.delete(cache_key)
                logger.debug(f"Invalidated quota cache for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to invalidate quota cache: {e}")

    def _get_quota_limit(self, user_tier: str) -> int:
        """
        Get quota limit for user tier.

        Args:
            user_tier: User tier (free, premium, enterprise)

        Returns:
            Quota limit in bytes
        """
        tier_quotas = {
            "free": self.default_quota,
            "premium": self.premium_quota,
            "enterprise": self.premium_quota * 10,  # 100GB for enterprise
        }

        return tier_quotas.get(user_tier.lower(), self.default_quota)


# Singleton instance
_quota_service: Optional[UploadQuotaService] = None


async def get_quota_service(
    redis_client: Optional[redis.Redis] = None,
) -> UploadQuotaService:
    """
    Get or create upload quota service singleton.

    Args:
        redis_client: Optional Redis client

    Returns:
        UploadQuotaService instance
    """
    global _quota_service

    if _quota_service is None:
        _quota_service = UploadQuotaService(redis_client=redis_client)

    return _quota_service
