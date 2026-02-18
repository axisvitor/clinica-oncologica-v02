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
from app.core.redis_manager import get_cache_redis_manager
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User, UserRole
from app.schemas.v2.ai import AIModelType, TokenUsage
from app.services.ai.execution_policy import decide_ai_failure, is_real_ai_ready

from .constants import COST_PER_1K_TOKENS
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


async def verify_physician_or_admin(
    current_user: Any = Depends(get_current_user_from_session),
) -> Any:
    """Verify user is physician or admin."""
    # Handle both dictionary (from session) and User object (from DB)
    if isinstance(current_user, dict):
        role_value = current_user.get("role", "")
        user_id = str(current_user.get("id", "unknown"))
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


async def get_redis_cache() -> Optional[redis.Redis]:
    """Get shared Redis cache client via centralized RedisManager."""
    try:
        manager = get_cache_redis_manager()
        client = await manager.get_async_client()
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
    client = await get_redis_cache()
    # Shared pooled clients are managed by RedisManager lifecycle.
    yield client


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
        "timestamp": now_sao_paulo().isoformat(),
    }


def ensure_real_ai_ready(api_key: Optional[str] = None) -> None:
    """Raise RuntimeError when real AI execution is not ready."""
    if not is_real_ai_ready(api_key):
        raise RuntimeError("AI_GEMINI_API_KEY is not configured")


def handle_ai_failure(
    *,
    logger: logging.Logger,
    operation: str,
    error: Exception,
    allow_simulation: bool,
    context: Optional[Dict[str, Any]] = None,
    disabled_detail: Optional[str] = None,
) -> bool:
    """
    Centralized fallback resolution for AI endpoints.

    Returns True when caller should execute simulation fallback.
    Raises HTTPException(502) when simulation is disabled.
    """
    decision = decide_ai_failure(
        operation,
        allow_simulation=allow_simulation,
        detail=disabled_detail,
    )

    extra = {
        "endpoint": operation,
        "error": str(error),
    }
    if context:
        extra.update(context)

    if decision.use_simulation:
        logger.warning(
            "%s failed; using simulation fallback",
            operation,
            extra=extra,
        )
        return True

    logger.error(
        "%s failed with simulation disabled",
        operation,
        extra=extra,
        exc_info=True,
    )
    raise HTTPException(
        status_code=decision.status_code,
        detail=decision.detail,
    ) from error


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
        today = now_sao_paulo().date().isoformat()
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
