"""
Redis Manager Package - Unified Redis Client Management

Provides both async and sync Redis interfaces with automatic compatibility detection.
Manages connection pooling, error handling, and proper resource cleanup.

Main exports:
- RedisManager: Core manager class
- FirebaseRedisCache: 3-layer caching system for Firebase authentication
- get_redis_manager: Get or create global Redis manager instance
- get_cache_redis_manager: Get Redis manager for cache operations
- get_broker_redis_manager: Get Redis manager for Celery broker operations
- get_async_redis_client: Get async Redis client
- get_sync_redis_client: Get sync Redis client
- get_compatible_redis_client: Get Redis client with automatic compatibility
- redis_transaction: Async context manager for Redis transactions
- cleanup_redis_connections: Cleanup all Redis connections
- redis_health_check: Perform Redis health check
"""

from .manager import RedisManager
from .firebase_cache import FirebaseRedisCache
from .async_client import (
    get_async_redis_client,
    redis_transaction,
    cleanup_redis_connections,
    redis_health_check,
)
from .sync_client import get_sync_redis_client, get_compatible_redis_client
from .utils import get_redis_manager, get_cache_redis_manager, get_broker_redis_manager

__all__ = [
    # Classes
    "RedisManager",
    "FirebaseRedisCache",
    # Manager functions
    "get_redis_manager",
    "get_cache_redis_manager",
    "get_broker_redis_manager",
    # Client functions
    "get_async_redis_client",
    "get_sync_redis_client",
    "get_compatible_redis_client",
    # Utilities
    "redis_transaction",
    "cleanup_redis_connections",
    "redis_health_check",
]
