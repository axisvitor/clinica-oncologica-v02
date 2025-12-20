"""
Unified Redis Client - Single Entry Point
Deprecates multiple client implementations in favor of redis_manager.py

UPDATED: Now fully delegates to redis_manager (2025-12-19)
- All operations use RedisManager for connection pooling
- SSL/TLS support via RedisManager
- Circuit breaker pattern included
- Health checks and metrics available

This module is maintained for backward compatibility.
New code should import directly from app.core.redis_manager.
"""

import logging

from app.core.redis_manager import (
    get_async_redis_client,
    get_sync_redis_client,
    get_compatible_redis_client,
    cleanup_redis_connections,
    redis_health_check,
)

logger = logging.getLogger(__name__)

# Log import for deprecation tracking
logger.debug("redis_unified loaded - redirecting to redis_manager")

# Re-export recommended functions
__all__ = [
    "get_redis_client",  # Unified entry point
    "get_async_redis",  # Async client
    "get_sync_redis",  # Sync client
    "get_cache_redis",  # Cache-specific client
    "get_broker_redis",  # Celery broker client
    "cleanup_redis",  # Cleanup function
    "redis_health",  # Health check
]


def get_redis_client(client_type: str = "auto"):
    """
    Unified Redis client getter - RECOMMENDED ENTRY POINT

    Args:
        client_type: "auto" (default), "sync", or "async"

    Returns:
        Redis client with appropriate interface

    Examples:
        # Auto-detect (recommended)
        redis = get_redis_client()
        redis.set('key', 'value', ex=3600)

        # Force sync
        redis = get_redis_client('sync')
        redis.set('key', 'value')

        # Force async (returns wrapper for sync usage)
        redis = get_redis_client('async')
        redis.set('key', 'value')  # Works in sync context
    """
    return get_compatible_redis_client(client_type)


async def get_async_redis():
    """
    Get async Redis client - for pure async contexts

    Returns:
        Async Redis client

    Example:
        redis = await get_async_redis()
        await redis.set('key', 'value', ex=3600)
    """
    return await get_async_redis_client()


def get_sync_redis():
    """
    Get sync Redis client - for pure sync contexts

    Returns:
        Sync Redis client

    Example:
        redis = get_sync_redis()
        redis.set('key', 'value', ex=3600)
    """
    return get_sync_redis_client()


def get_cache_redis():
    """
    Get Redis client for cache operations (DB 1)

    Returns:
        Redis client configured for cache
    """
    # Use same client for now - isolation happens at config level
    return get_sync_redis_client()


def get_broker_redis():
    """
    Get Redis client for Celery broker operations (DB 0)

    Note: Celery manages its own connections via CELERY_BROKER_URL
    This is provided for direct broker inspection/management only.

    Returns:
        Redis client configured for broker
    """
    # Use same client for now - isolation happens at config level
    return get_sync_redis_client()


async def cleanup_redis():
    """
    Cleanup all Redis connections

    Call this during application shutdown.
    """
    await cleanup_redis_connections()
    logger.info("Redis connections cleaned up via unified client")


async def redis_health():
    """
    Perform Redis health check

    Returns:
        Health check results dict
    """
    return await redis_health_check()


# ============================================================================
# MIGRATION REFERENCE (Legacy code removed 2025-11-26)
# ============================================================================


def print_migration_guide():
    """Print migration guide for updating code"""
    import logging

    logger = logging.getLogger(__name__)

    guide = """
    ╔══════════════════════════════════════════════════════════════╗
    ║        Redis Client Migration Guide                          ║
    ╚══════════════════════════════════════════════════════════════╝

    Old Code → New Code
    ────────────────────────────────────────────────────────────────

    1. Factory Pattern (redis_client_factory.py):

       OLD:
         from app.core.redis_client_factory import get_redis_factory
         factory = get_redis_factory()
         redis = factory.get_sync_client()

       NEW:
         from app.core.redis_unified import get_redis_client
         redis = get_redis_client('sync')

    ────────────────────────────────────────────────────────────────

    2. Simple Client (redis_simple.py):

       OLD:
         from app.core.redis_simple import get_simple_redis
         redis = get_simple_redis()

       NEW:
         from app.core.redis_unified import get_redis_client
         redis = get_redis_client()

    ────────────────────────────────────────────────────────────────

    3. Utils Client (redis_client.py):

       OLD:
         from app.utils.redis_client import get_sync_redis_client
         redis = get_sync_redis_client()

       NEW:
         from app.core.redis_unified import get_sync_redis
         redis = get_sync_redis()

    ────────────────────────────────────────────────────────────────

    4. Auto-detect (recommended):

       NEW:
         from app.core.redis_unified import get_redis_client

         # Works in both sync and async contexts
         redis = get_redis_client()
         redis.set('key', 'value', ex=3600)

    ────────────────────────────────────────────────────────────────

    5. Pure Async:

       NEW:
         from app.core.redis_unified import get_async_redis

         redis = await get_async_redis()
         await redis.set('key', 'value', ex=3600)

    ════════════════════════════════════════════════════════════════

    Benefits:
    ✓ Single import location
    ✓ Consistent API across codebase
    ✓ Automatic async/sync detection
    ✓ Connection pooling handled automatically
    ✓ Deprecation warnings guide migration

    ════════════════════════════════════════════════════════════════
    """
    logger.info(guide)


if __name__ == "__main__":
    print_migration_guide()
