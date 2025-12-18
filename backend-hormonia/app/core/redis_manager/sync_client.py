"""
Sync Redis Client Operations

Provides sync Redis client functions and compatibility wrappers.
"""

import logging
import asyncio
import concurrent.futures
from typing import Optional, Any
import redis as redis_sync
from redis.exceptions import TimeoutError

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


class AsyncToSyncWrapper:
    """
    Wrapper that provides sync interface for async Redis operations.

    This allows services expecting sync Redis to work with async Redis clients
    without major refactoring.
    """

    def __init__(self, redis_manager):
        self.redis_manager = redis_manager
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def _run_async(self, coro):
        """Run async coroutine in sync context."""
        try:
            # Try to get current loop
            asyncio.get_running_loop()

            # We're in async context, run in thread to avoid blocking
            future = self._executor.submit(self._run_in_new_loop, coro)
            return future.result(timeout=30)  # 30 second timeout

        except RuntimeError:
            # No running loop, safe to create new one
            try:
                return asyncio.run(coro)
            except Exception as e:
                logger.error(f"Failed to run coroutine with asyncio.run: {e}")
                # Fallback to manual loop management
                return self._run_in_new_loop(coro)
        except concurrent.futures.TimeoutError:
            logger.error("Redis operation timed out after 30 seconds")
            raise TimeoutError("Redis operation timed out")

    def _run_in_new_loop(self, coro):
        """Run coroutine in new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def get(self, key: str) -> Optional[str]:
        """Sync wrapper for get operation."""

        async def _get():
            client = await self.redis_manager.get_async_client()
            return await client.get(key)

        try:
            return self._run_async(_get())
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> bool:
        """Sync wrapper for set operation."""

        async def _set():
            client = await self.redis_manager.get_async_client()
            return await client.set(key, value, ex=ex, **kwargs)

        try:
            return self._run_async(_set())
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False

    def setex(self, key: str, seconds: int, value: Any) -> bool:
        """Sync wrapper for setex operation."""

        async def _setex():
            client = await self.redis_manager.get_async_client()
            return await client.setex(key, seconds, value)

        try:
            return self._run_async(_setex())
        except Exception as e:
            logger.error(f"Redis SETEX error: {e}")
            return False

    def delete(self, *keys: str) -> int:
        """Sync wrapper for delete operation."""

        async def _delete():
            client = await self.redis_manager.get_async_client()
            return await client.delete(*keys)

        try:
            return self._run_async(_delete())
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return 0

    def exists(self, *keys: str) -> int:
        """Sync wrapper for exists operation."""

        async def _exists():
            client = await self.redis_manager.get_async_client()
            return await client.exists(*keys)

        try:
            return self._run_async(_exists())
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return 0

    def expire(self, key: str, seconds: int) -> bool:
        """Sync wrapper for expire operation."""

        async def _expire():
            client = await self.redis_manager.get_async_client()
            return await client.expire(key, seconds)

        try:
            return self._run_async(_expire())
        except Exception as e:
            logger.error(f"Redis EXPIRE error: {e}")
            return False

    def rpush(self, key: str, *values) -> int:
        """Sync wrapper for rpush operation."""

        async def _rpush():
            client = await self.redis_manager.get_async_client()
            return await client.rpush(key, *values)

        try:
            return self._run_async(_rpush())
        except Exception as e:
            logger.error(f"Redis RPUSH error: {e}")
            return 0

    def lpop(self, key: str) -> Optional[str]:
        """Sync wrapper for lpop operation."""

        async def _lpop():
            client = await self.redis_manager.get_async_client()
            return await client.lpop(key)

        try:
            return self._run_async(_lpop())
        except Exception as e:
            logger.error(f"Redis LPOP error: {e}")
            return None

    def ping(self) -> bool:
        """Sync wrapper for ping operation."""

        async def _ping():
            client = await self.redis_manager.get_async_client()
            return await client.ping()

        try:
            result = self._run_async(_ping())
            return bool(result)
        except Exception as e:
            logger.error(f"Redis PING error: {e}")
            return False

    def scan_iter(self, match: Optional[str] = None, count: Optional[int] = None):
        """Sync wrapper for scan_iter operation."""

        async def _scan_iter():
            client = await self.redis_manager.get_async_client()
            results = []
            async for key in client.scan_iter(match=match, count=count):
                results.append(key)
            return results

        try:
            return self._run_async(_scan_iter())
        except Exception as e:
            logger.error(f"Redis SCAN_ITER error: {e}")
            return []

    def ttl(self, key: str) -> int:
        """Sync wrapper for ttl operation."""

        async def _ttl():
            client = await self.redis_manager.get_async_client()
            return await client.ttl(key)

        try:
            return self._run_async(_ttl())
        except Exception as e:
            logger.error(f"Redis TTL error: {e}")
            return -1

    def close(self):
        """Close wrapper resources."""
        self._executor.shutdown(wait=False)
