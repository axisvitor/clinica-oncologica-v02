"""
AI Services Dependencies - Shared dependencies and utility functions.
"""

# Standard library imports
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

# Third-party imports
import redis.asyncio as redis
from fastapi import Depends, HTTPException, status

# Local application imports
from app.config import settings
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User, UserRole
from app.schemas.v2.ai import AIModelType, TokenUsage

from .constants import COST_PER_1K_TOKENS

logger = logging.getLogger(__name__)


# Shared Redis connection pool to prevent connection leaks
_redis_pool: Optional[redis.ConnectionPool] = None


async def verify_physician_or_admin(
    current_user: Any = Depends(get_current_user_from_session),
) -> Any:
    """Verify user is physician or admin."""
    # Handle both dictionary (from session) and User object (from DB)
    if isinstance(current_user, dict):
        role_value = current_user.get("role", "")
        user_id = current_user.get("id", "unknown")
    else:
        role_value = (
            current_user.role.value
            if isinstance(current_user.role, UserRole)
            else str(current_user.role or "")
        )
        user_id = str(getattr(current_user, "id", "unknown"))

    # Normalize role value for comparison
    role_value = str(role_value).lower()

    if role_value not in {UserRole.DOCTOR.value, UserRole.ADMIN.value}:
        logger.warning(
            f"Unauthorized AI access by user {user_id} with role {role_value}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI features require physician or admin privileges",
        )
    return current_user


async def _get_redis_pool() -> Optional[redis.ConnectionPool]:
    """Get or create shared Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        try:
            _redis_pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=20,
            )
        except Exception as e:
            logger.warning(f"Failed to create Redis pool: {e}")
            return None
    return _redis_pool


async def get_redis_cache() -> Optional[redis.Redis]:
    """Get Redis client with error handling using shared pool."""
    try:
        pool = await _get_redis_pool()
        if pool is None:
            return None

        client = redis.Redis(
            connection_pool=pool,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        return None


@asynccontextmanager
async def redis_connection():
    """
    Context manager for Redis connections that ensures proper cleanup.

    FIX: Use this instead of get_redis_cache() to prevent connection leaks.

    Usage:
        async with redis_connection() as client:
            if client:
                await client.get("key")
    """
    client = None
    try:
        client = await get_redis_cache()
        yield client
    finally:
        if client:
            try:
                await client.close()
            except Exception as e:
                logger.debug(f"Redis close warning: {e}")


def generate_cache_key(prefix: str, user_id: Optional[str] = None, **kwargs) -> str:
    """
    Generate deterministic cache key from parameters.

    FIX: Added user_id parameter to prevent cache key collisions between users.
    This ensures different users don't see each other's cached AI responses (privacy/HIPAA).

    Args:
        prefix: Cache key prefix (e.g., "ai:insights:v2")
        user_id: User ID to include in cache key for user-specific caching
        **kwargs: Additional parameters for cache key generation
    """
    # Include user_id in cache key to prevent cross-user cache sharing
    if user_id:
        kwargs["_user_id"] = user_id

    # Sort kwargs to ensure consistent ordering
    sorted_params = sorted(kwargs.items())
    param_str = json.dumps(sorted_params, default=str, sort_keys=True)
    # FIX: Use SHA-256 instead of MD5 for better collision resistance
    param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
    return f"{prefix}:{param_hash}"


async def get_cached_response(
    redis_client: Optional[redis.Redis],
    cache_key: str,
) -> Optional[Dict[str, Any]]:
    """Get cached response with error handling."""
    if not redis_client:
        return None

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"Cache read error for {cache_key}: {e}")
        return None


async def set_cached_response(
    redis_client: Optional[redis.Redis],
    cache_key: str,
    data: Dict[str, Any],
    ttl_seconds: int,
) -> bool:
    """Set cached response with TTL."""
    if not redis_client:
        return False

    try:
        serialized = json.dumps(data, default=str, ensure_ascii=False)
        await redis_client.setex(cache_key, ttl_seconds, serialized)
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl_seconds}s)")
        return True
    except Exception as e:
        logger.warning(f"Cache write error for {cache_key}: {e}")
        return False


def calculate_token_cost(
    token_usage: TokenUsage, model: AIModelType = AIModelType.GEMINI_PRO
) -> float:
    """Calculate estimated cost from token usage."""
    cost_per_1k = COST_PER_1K_TOKENS.get(model, 0.0015)
    return (token_usage.total_tokens / 1000) * cost_per_1k


def create_fallback_response(
    message: str, error_type: str = "ai_unavailable"
) -> Dict[str, Any]:
    """Create fallback response when AI service fails."""
    return {
        "fallback_used": True,
        "error_type": error_type,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def track_token_usage(
    redis_client: Optional[redis.Redis],
    endpoint: str,
    token_usage: TokenUsage,
    user_id: UUID,
) -> None:
    """Track token usage for billing and analytics."""
    if not redis_client:
        return

    try:
        # Daily usage key
        today = datetime.now(timezone.utc).date().isoformat()
        usage_key = f"ai:usage:{today}:{endpoint}:{user_id}"

        # Increment counters
        await redis_client.hincrby(usage_key, "requests", 1)
        await redis_client.hincrby(usage_key, "tokens", token_usage.total_tokens)
        await redis_client.hincrbyfloat(
            usage_key, "cost_usd", token_usage.estimated_cost_usd
        )

        # Set expiry to 90 days for historical data
        await redis_client.expire(usage_key, 90 * 24 * 3600)

        logger.debug(
            f"Tracked usage: {endpoint} - {token_usage.total_tokens} tokens, "
            f"${token_usage.estimated_cost_usd:.4f}"
        )
    except Exception as e:
        logger.warning(f"Failed to track token usage: {e}")
