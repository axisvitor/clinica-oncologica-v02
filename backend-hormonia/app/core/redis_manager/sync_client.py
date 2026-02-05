"""
Sync Redis Client Operations

Provides sync Redis client functions and compatibility wrappers.
"""

import logging
import asyncio
from typing import Optional, Any
import redis as redis_sync

# Use centralized executor manager
from app.core.executors import get_cache_executor

logger = logging.getLogger(__name__)


def get_sync_redis_client() -> redis_sync.Redis:
    """
    Get sync Redis client from manager.

    Returns:
        Sync Redis client
    """
    from .utils import get_redis_manager

    manager = get_redis_manager()
    return manager.get_sync_client()


def get_compatible_redis_client(preferred_type: str = "auto"):
    """
    Get Redis client with automatic compatibility.

    Args:
        preferred_type: "async", "sync", or "auto" (default)

    Returns:
        Compatible Redis client
    """
    from .utils import get_redis_manager

    manager = get_redis_manager()
    return manager.get_compatible_client(preferred_type)


import threading

class AsyncToSyncWrapper:
    """
    Wrapper that provides sync interface for async Redis operations.

    This allows services expecting sync Redis to work with async Redis clients
    without major refactoring.
    """

    # Class-level executor to ensure consistency across instances
    _shared_executor = None

    def __init__(self, redis_manager):
        # We store the manager but we might need a fresh one for background threads
        self.redis_manager = redis_manager
        # Use centralized executor from app.core.executors
        if AsyncToSyncWrapper._shared_executor is None:
            AsyncToSyncWrapper._shared_executor = get_cache_executor()
        self._executor = AsyncToSyncWrapper._shared_executor
        self._local = threading.local()

    def _get_local_manager(self):
        """Get or create thread-local RedisManager."""
        if not hasattr(self._local, "manager"):
            # Create a fresh manager for this thread/loop
            from .manager import RedisManager
            self._local.manager = RedisManager()
        return self._local.manager

    def _run_async(self, coro_func):
        """Run async coroutine in sync context using thread-local manager."""
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop and loop.is_running():
            # In async context, run in thread with its own loop
            future = self._executor.submit(self._run_in_new_loop, coro_func)
            return future.result(timeout=30)

        # No running loop, safe to use asyncio.run
        return asyncio.run(coro_func(self.redis_manager))

    def _run_in_new_loop(self, coro_func):
        """Run coroutine in new event loop with thread-local manager."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            manager = self._get_local_manager()
            return loop.run_until_complete(coro_func(manager))
        finally:
            # We don't close manager here to keep connection pool alive in this thread
            loop.close()

    def get(self, key: str) -> Optional[str]:
        """Sync wrapper for get operation."""

        async def _get(manager):
            client = await manager.get_async_client()
            return await client.get(key)

        try:
            return self._run_async(_get)
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> bool:
        """Sync wrapper for set operation."""

        async def _set(manager):
            client = await manager.get_async_client()
            return await client.set(key, value, ex=ex, **kwargs)

        try:
            return self._run_async(_set)
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False

    def setex(self, key: str, seconds: int, value: Any) -> bool:
        """Sync wrapper for setex operation."""

        async def _setex(manager):
            client = await manager.get_async_client()
            return await client.setex(key, seconds, value)

        try:
            return self._run_async(_setex)
        except Exception as e:
            logger.error(f"Redis SETEX error: {e}")
            return False

    def delete(self, *keys: str) -> int:
        """Sync wrapper for delete operation."""

        async def _delete(manager):
            client = await manager.get_async_client()
            return await client.delete(*keys)

        try:
            return self._run_async(_delete)
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return 0

    def exists(self, *keys: str) -> int:
        """Sync wrapper for exists operation."""

        async def _exists(manager):
            client = await manager.get_async_client()
            return await client.exists(*keys)

        try:
            return self._run_async(_exists)
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return 0

    def expire(self, key: str, seconds: int) -> bool:
        """Sync wrapper for expire operation."""

        async def _expire(manager):
            client = await manager.get_async_client()
            return await client.expire(key, seconds)

        try:
            return self._run_async(_expire)
        except Exception as e:
            logger.error(f"Redis EXPIRE error: {e}")
            return False

    def rpush(self, key: str, *values) -> int:
        """Sync wrapper for rpush operation."""

        async def _rpush(manager):
            client = await manager.get_async_client()
            return await client.rpush(key, *values)

        try:
            return self._run_async(_rpush)
        except Exception as e:
            logger.error(f"Redis RPUSH error: {e}")
            return 0

    def lpop(self, key: str) -> Optional[str]:
        """Sync wrapper for lpop operation."""

        async def _lpop(manager):
            client = await manager.get_async_client()
            return await client.lpop(key)

        try:
            return self._run_async(_lpop)
        except Exception as e:
            logger.error(f"Redis LPOP error: {e}")
            return None

    def ping(self) -> bool:
        """Sync wrapper for ping operation."""

        async def _ping(manager):
            client = await manager.get_async_client()
            return await client.ping()

        try:
            result = self._run_async(_ping)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis PING error: {e}")
            return False

    def scan_iter(self, match: Optional[str] = None, count: Optional[int] = None):
        """Sync wrapper for scan_iter operation."""

        async def _scan_iter(manager):
            client = await manager.get_async_client()
            results = []
            async for key in client.scan_iter(match=match, count=count):
                results.append(key)
            return results

        try:
            return self._run_async(_scan_iter)
        except Exception as e:
            logger.error(f"Redis SCAN_ITER error: {e}")
            return []

    def ttl(self, key: str) -> int:
        """Sync wrapper for ttl operation."""

        async def _ttl(manager):
            client = await manager.get_async_client()
            return await client.ttl(key)

        try:
            return self._run_async(_ttl)
        except Exception as e:
            logger.error(f"Redis TTL error: {e}")
            return -1

    def close(self):
        """Close wrapper resources."""
        # Note: Class-level executor remains shared
        pass
