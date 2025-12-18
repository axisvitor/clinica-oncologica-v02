"""
User Profile and Preferences Cache Helpers

Provides specialized caching functions for user profiles and preferences
with automatic invalidation and TTL management.
"""

import json
import logging
from typing import Optional, Dict, Any

from app.core.redis_unified import get_sync_redis, get_async_redis

logger = logging.getLogger(__name__)

# Cache TTL configurations
USER_PROFILE_TTL = 3600  # 1 hour
USER_PREFERENCES_TTL = 1800  # 30 minutes


def _get_profile_cache_key(firebase_uid: str) -> str:
    """Generate cache key for user profile."""
    return f"user_profile:{firebase_uid}"


def _get_preferences_cache_key(user_id: str) -> str:
    """Generate cache key for user preferences."""
    return f"preferences:{user_id}"


def _get_password_attempt_key(firebase_uid: str) -> str:
    """Generate cache key for password change rate limiting."""
    return f"password_change_attempts:{firebase_uid}"


# Synchronous cache functions


def get_cached_profile(firebase_uid: str) -> Optional[Dict[str, Any]]:
    """
    Get cached user profile by Firebase UID.

    Args:
        firebase_uid: Firebase user ID

    Returns:
        Cached profile dict or None if not found
    """
    try:
        redis_client = get_sync_redis()
        if not redis_client:
            return None

        key = _get_profile_cache_key(firebase_uid)
        cached = redis_client.get(key)

        if cached:
            logger.debug(f"Profile cache hit for {firebase_uid}")
            return json.loads(cached)

        logger.debug(f"Profile cache miss for {firebase_uid}")
        return None
    except Exception as e:
        logger.error(f"Error getting cached profile for {firebase_uid}: {e}")
        return None


def set_cached_profile(firebase_uid: str, profile: Dict[str, Any]) -> bool:
    """
    Cache user profile with TTL.

    Args:
        firebase_uid: Firebase user ID
        profile: Profile data to cache

    Returns:
        True if cached successfully, False otherwise
    """
    try:
        redis_client = get_sync_redis()
        if not redis_client:
            return False

        key = _get_profile_cache_key(firebase_uid)
        redis_client.setex(key, USER_PROFILE_TTL, json.dumps(profile, default=str))
        logger.debug(f"Cached profile for {firebase_uid}")
        return True
    except Exception as e:
        logger.error(f"Error caching profile for {firebase_uid}: {e}")
        return False


def invalidate_profile_cache(firebase_uid: str) -> bool:
    """
    Invalidate cached user profile.

    Args:
        firebase_uid: Firebase user ID

    Returns:
        True if invalidated successfully, False otherwise
    """
    try:
        redis_client = get_sync_redis()
        if not redis_client:
            return False

        key = _get_profile_cache_key(firebase_uid)
        redis_client.delete(key)
        logger.debug(f"Invalidated profile cache for {firebase_uid}")
        return True
    except Exception as e:
        logger.error(f"Error invalidating profile cache for {firebase_uid}: {e}")
        return False


def get_cached_preferences(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached user preferences.

    Args:
        user_id: User ID

    Returns:
        Cached preferences dict or None if not found
    """
    try:
        redis_client = get_sync_redis()
        if not redis_client:
            return None

        key = _get_preferences_cache_key(user_id)
        cached = redis_client.get(key)

        if cached:
            logger.debug(f"Preferences cache hit for {user_id}")
            return json.loads(cached)

        logger.debug(f"Preferences cache miss for {user_id}")
        return None
    except Exception as e:
        logger.error(f"Error getting cached preferences for {user_id}: {e}")
        return None


def set_cached_preferences(user_id: str, preferences: Dict[str, Any]) -> bool:
    """
    Cache user preferences with TTL.

    Args:
        user_id: User ID
        preferences: Preferences data to cache

    Returns:
        True if cached successfully, False otherwise
    """
    try:
        redis_client = get_sync_redis()
        if not redis_client:
            return False

        key = _get_preferences_cache_key(user_id)
        redis_client.setex(
            key, USER_PREFERENCES_TTL, json.dumps(preferences, default=str)
        )
        logger.debug(f"Cached preferences for {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error caching preferences for {user_id}: {e}")
        return False


def invalidate_preferences_cache(user_id: str) -> bool:
    """
    Invalidate cached user preferences.

    Args:
        user_id: User ID

    Returns:
        True if invalidated successfully, False otherwise
    """
    try:
        redis_client = get_sync_redis()
        if not redis_client:
            return False

        key = _get_preferences_cache_key(user_id)
        redis_client.delete(key)
        logger.debug(f"Invalidated preferences cache for {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error invalidating preferences cache for {user_id}: {e}")
        return False


def invalidate_user_cache(firebase_uid: str, user_id: str) -> bool:
    """
    Invalidate all cached data for a user (profile and preferences).

    Args:
        firebase_uid: Firebase user ID
        user_id: User ID

    Returns:
        True if all caches invalidated successfully
    """
    profile_ok = invalidate_profile_cache(firebase_uid)
    prefs_ok = invalidate_preferences_cache(user_id)
    return profile_ok and prefs_ok


# Rate limiting for password changes


def check_password_change_rate_limit(
    firebase_uid: str, max_attempts: int = 3, window_seconds: int = 3600
) -> bool:
    """
    Check if user has exceeded password change rate limit.

    Args:
        firebase_uid: Firebase user ID
        max_attempts: Maximum allowed attempts in window
        window_seconds: Time window in seconds

    Returns:
        True if allowed, False if rate limit exceeded
    """
    try:
        redis_client = get_sync_redis()
        if not redis_client:
            # If Redis unavailable, allow operation (fail open)
            return True

        key = _get_password_attempt_key(firebase_uid)

        # Get current count
        current = redis_client.get(key)
        count = int(current) if current else 0

        if count >= max_attempts:
            logger.warning(f"Password change rate limit exceeded for {firebase_uid}")
            return False

        # Increment counter with TTL
        if count == 0:
            redis_client.setex(key, window_seconds, 1)
        else:
            redis_client.incr(key)

        return True
    except Exception as e:
        logger.error(f"Error checking password rate limit for {firebase_uid}: {e}")
        # Fail open on error
        return True


def reset_password_change_rate_limit(firebase_uid: str) -> bool:
    """
    Reset password change rate limit counter.

    Args:
        firebase_uid: Firebase user ID

    Returns:
        True if reset successfully
    """
    try:
        redis_client = get_sync_redis()
        if not redis_client:
            return False

        key = _get_password_attempt_key(firebase_uid)
        redis_client.delete(key)
        logger.debug(f"Reset password rate limit for {firebase_uid}")
        return True
    except Exception as e:
        logger.error(f"Error resetting password rate limit for {firebase_uid}: {e}")
        return False


# Async versions


async def get_cached_profile_async(firebase_uid: str) -> Optional[Dict[str, Any]]:
    """Async version of get_cached_profile."""
    try:
        redis_client = await get_async_redis()
        if not redis_client:
            return None

        key = _get_profile_cache_key(firebase_uid)
        cached = await redis_client.get(key)

        if cached:
            logger.debug(f"Profile cache hit for {firebase_uid}")
            return json.loads(cached)

        logger.debug(f"Profile cache miss for {firebase_uid}")
        return None
    except Exception as e:
        logger.error(f"Error getting cached profile for {firebase_uid}: {e}")
        return None


async def set_cached_profile_async(firebase_uid: str, profile: Dict[str, Any]) -> bool:
    """Async version of set_cached_profile."""
    try:
        redis_client = await get_async_redis()
        if not redis_client:
            return False

        key = _get_profile_cache_key(firebase_uid)
        await redis_client.setex(
            key, USER_PROFILE_TTL, json.dumps(profile, default=str)
        )
        logger.debug(f"Cached profile for {firebase_uid}")
        return True
    except Exception as e:
        logger.error(f"Error caching profile for {firebase_uid}: {e}")
        return False


async def invalidate_user_cache_async(firebase_uid: str, user_id: str) -> bool:
    """Async version of invalidate_user_cache."""
    try:
        redis_client = await get_async_redis()
        if not redis_client:
            return False

        profile_key = _get_profile_cache_key(firebase_uid)
        prefs_key = _get_preferences_cache_key(user_id)

        await redis_client.delete(profile_key)
        await redis_client.delete(prefs_key)

        logger.debug(f"Invalidated all cache for user {firebase_uid}/{user_id}")
        return True
    except Exception as e:
        logger.error(f"Error invalidating user cache: {e}")
        return False
