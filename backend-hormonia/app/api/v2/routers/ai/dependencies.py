"""
AI Services Dependencies - Shared dependencies and utility functions.
"""

import logging
import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
import redis.asyncio as redis

from app.models.user import User, UserRole
from app.dependencies import get_current_user
from app.schemas.v2.ai import TokenUsage, AIModelType
from app.config import settings
from .constants import COST_PER_1K_TOKENS

logger = logging.getLogger(__name__)


async def verify_physician_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verify user is physician or admin."""
    role_value = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role or "").lower()
    )

    if role_value not in {UserRole.DOCTOR.value, UserRole.ADMIN.value}:
        logger.warning(
            f"Unauthorized AI access by user {current_user.id} with role {role_value}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI features require physician or admin privileges",
        )
    return current_user


async def get_redis_cache() -> Optional[redis.Redis]:
    """Get Redis client with error handling."""
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            max_connections=20,
        )
        await client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        return None


def generate_cache_key(prefix: str, **kwargs) -> str:
    """Generate deterministic cache key from parameters."""
    # Sort kwargs to ensure consistent ordering
    sorted_params = sorted(kwargs.items())
    param_str = json.dumps(sorted_params, default=str, sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]
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
