"""
Redis Manager - Unified Redis Client Management

Provides both async and sync Redis interfaces with automatic compatibility detection.
Manages connection pooling, error handling, and proper resource cleanup.
"""

import logging
import asyncio
import os
from typing import Optional, Union, Any
import redis.asyncio as redis_async
import redis as redis_sync
from redis.exceptions import ConnectionError, TimeoutError
from contextlib import asynccontextmanager
import threading
import concurrent.futures

from app.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Unified Redis manager providing both async and sync interfaces.

    Features:
    - Automatic client type detection
    - Connection pooling for both sync and async
    - Error handling and retry logic
    - Resource cleanup
    - Interface compatibility layer
    """

    def __init__(self, db_number: Optional[int] = None):
        self._async_client: Optional[redis_async.Redis] = None
        self._sync_client: Optional[redis_sync.Redis] = None
        self._async_pool: Optional[redis_async.ConnectionPool] = None
        self._sync_pool: Optional[redis_sync.ConnectionPool] = None
        self._lock = threading.Lock()

        # Connection settings (use Redis Cloud URL from settings)
        self.redis_url = settings.REDIS_URL

        # SSL is now configured manually via connection_kwargs (see _create_*_client methods)
        # This approach works better with Python 3.13's strict SSL validation
        # No need to convert redis:// to rediss:// - we configure SSL parameters directly

        # DB isolation support
        self.db_number = db_number
        if db_number is not None and getattr(settings, 'REDIS_ENABLE_DB_ISOLATION', True):
            # Override DB in URL if isolation is enabled
            base_url = self.redis_url.rsplit('/', 1)[0] if '/' in self.redis_url else self.redis_url
            self.redis_url = f"{base_url}/{db_number}"
            logger.info(f"Redis DB isolation enabled: using DB {db_number}")

        # Connection settings from config
        self.decode_responses = getattr(settings, 'REDIS_DECODE_RESPONSES', True)
        self.socket_timeout = getattr(settings, 'REDIS_SOCKET_TIMEOUT', 10.0)
        self.socket_connect_timeout = getattr(settings, 'REDIS_SOCKET_CONNECT_TIMEOUT', 5.0)
        self.retry_on_timeout = getattr(settings, 'REDIS_RETRY_ON_TIMEOUT', True)
        self.health_check_interval = getattr(settings, 'REDIS_HEALTH_CHECK_INTERVAL', 30)
        self.max_connections = getattr(settings, 'REDIS_MAX_CONNECTIONS', 50)

    async def get_async_client(self) -> redis_async.Redis:
        """
        Get or create async Redis client.

        Returns:
            Async Redis client instance
        """
        if self._async_client is None:
            await self._create_async_client()
        return self._async_client

    def get_sync_client(self) -> redis_sync.Redis:
        """
        Get or create sync Redis client.

        Returns:
            Sync Redis client instance
        """
        if self._sync_client is None:
            with self._lock:
                if self._sync_client is None:
                    self._create_sync_client()
        return self._sync_client

    async def _create_async_client(self):
        """
        Create async Redis client with connection pool.

        SSL is configured using SSLContext for Python 3.13 compatibility.
        This is the correct approach for redis-py 5.x with Python 3.13.
        """
        try:
            import ssl

            # Base connection configuration
            connection_kwargs = {
                'decode_responses': self.decode_responses,
                'socket_timeout': self.socket_timeout,
                'socket_connect_timeout': self.socket_connect_timeout,
                'retry_on_timeout': self.retry_on_timeout,
                'retry_on_error': [ConnectionError, TimeoutError],
                'max_connections': self.max_connections,
                'health_check_interval': self.health_check_interval
            }

            # Configure SSL if enabled
            redis_url = self.redis_url
            if settings.REDIS_SSL:
                # Change redis:// to rediss:// for SSL
                if redis_url.startswith('redis://'):
                    redis_url = 'rediss://' + redis_url[8:]
                logger.info("Redis async SSL: Enabled with rediss:// scheme")

                # Create SSL context based on REDIS_SSL_CERT_REQS setting
                # CRITICAL FIX: redis-py 6.0+ async clients require explicit SSL context
                # when REDIS_SSL_CERT_REQS='none' (disables certificate validation)
                import ssl
                ssl_cert_reqs = getattr(settings, 'REDIS_SSL_CERT_REQS', 'required').lower()

                if ssl_cert_reqs == 'none':
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    logger.info("Redis async SSL: Certificate verification DISABLED (CERT_NONE)")
                elif ssl_cert_reqs == 'optional':
                    ssl_context = ssl.create_default_context()
                    ssl_context.verify_mode = ssl.CERT_OPTIONAL
                    logger.info("Redis async SSL: Certificate verification OPTIONAL")
                else:  # 'required'
                    ssl_context = ssl.create_default_context()
                    ssl_context.verify_mode = ssl.CERT_REQUIRED
                    logger.info("Redis async SSL: Certificate verification REQUIRED")

                # Add SSL context to connection kwargs
                connection_kwargs['ssl'] = ssl_context
            else:
                # Ensure using non-SSL scheme
                if redis_url.startswith('rediss://'):
                    redis_url = 'redis://' + redis_url[9:]
                logger.info("Redis async: Using non-SSL connection")

            # Create async connection pool with SSL context (if SSL enabled)
            self._async_pool = redis_async.ConnectionPool.from_url(
                redis_url,
                **connection_kwargs
            )

            # Create client from pool
            self._async_client = redis_async.Redis(connection_pool=self._async_pool)

            # Test connection
            await self._async_client.ping()
            logger.info("Async Redis client connected successfully")

        except Exception as e:
            logger.error(f"Failed to create async Redis client: {e}")
            raise

    def _create_sync_client(self):
        """
        Create sync Redis client with connection pool.

        SSL is configured using SSLContext for Python 3.13 compatibility.
        This is the correct approach for redis-py 5.x with Python 3.13.
        """
        try:
            import ssl

            # Base connection configuration
            connection_kwargs = {
                'decode_responses': self.decode_responses,
                'socket_timeout': self.socket_timeout,
                'socket_connect_timeout': self.socket_connect_timeout,
                'retry_on_timeout': self.retry_on_timeout,
                'retry_on_error': [ConnectionError, TimeoutError],
                'max_connections': self.max_connections,
                'health_check_interval': self.health_check_interval
            }

            # Configure SSL if enabled
            redis_url = self.redis_url
            if settings.REDIS_SSL:
                # Change redis:// to rediss:// for SSL
                if redis_url.startswith('redis://'):
                    redis_url = 'rediss://' + redis_url[8:]
                logger.info("Redis sync SSL: Enabled with rediss:// scheme")
            else:
                # Ensure using non-SSL scheme
                if redis_url.startswith('rediss://'):
                    redis_url = 'redis://' + redis_url[9:]
                logger.info("Redis sync: Using non-SSL connection")

            # Create sync connection pool
            # NOTE: Do NOT pass ssl_cert_reqs/ssl_check_hostname as kwargs
            # redis-py 6.0+ handles SSL via URL scheme (rediss://) automatically
            self._sync_pool = redis_sync.ConnectionPool.from_url(
                redis_url,
                **connection_kwargs
            )

            # Create client from pool
            self._sync_client = redis_sync.Redis(connection_pool=self._sync_pool)

            # Test connection
            self._sync_client.ping()
            logger.info("Sync Redis client connected successfully")

        except Exception as e:
            logger.error(f"Failed to create sync Redis client: {e}")
            raise

    async def close_async(self):
        """Close async Redis connections."""
        try:
            if self._async_client:
                await self._async_client.aclose()
                self._async_client = None
                logger.debug("Async Redis client closed")

            if self._async_pool:
                await self._async_pool.aclose()
                self._async_pool = None
                logger.debug("Async Redis pool closed")

        except Exception as e:
            logger.error(f"Error closing async Redis connections: {e}")

    def close_sync(self):
        """Close sync Redis connections."""
        try:
            with self._lock:
                if self._sync_client:
                    self._sync_client.close()
                    self._sync_client = None
                    logger.debug("Sync Redis client closed")

                if self._sync_pool:
                    self._sync_pool.disconnect()
                    self._sync_pool = None
                    logger.debug("Sync Redis pool closed")

        except Exception as e:
            logger.error(f"Error closing sync Redis connections: {e}")

    async def close_all(self):
        """Close all Redis connections."""
        await self.close_async()
        self.close_sync()

    def get_compatible_client(self, preferred_type: str = "auto") -> Union[redis_async.Redis, redis_sync.Redis, 'CompatibilityWrapper']:
        """
        Get Redis client with automatic compatibility detection.

        Args:
            preferred_type: "async", "sync", or "auto" (default)

        Returns:
            Redis client or compatibility wrapper
        """
        if preferred_type == "async":
            # Return async client wrapped for sync compatibility if needed
            return AsyncToSyncWrapper(self)
        elif preferred_type == "sync":
            return self.get_sync_client()
        else:
            # Auto-detect based on current context
            try:
                # Check if we're in an async context
                asyncio.get_running_loop()
                return AsyncToSyncWrapper(self)  # Use wrapper for mixed usage
            except RuntimeError:
                # No event loop, use sync client
                return self.get_sync_client()


class AsyncToSyncWrapper:
    """
    Wrapper that provides sync interface for async Redis operations.

    This allows services expecting sync Redis to work with async Redis clients
    without major refactoring.
    """

    def __init__(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def _run_async(self, coro):
        """Run async coroutine in sync context."""
        try:
            # Try to get current loop
            loop = asyncio.get_running_loop()

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

    def close(self):
        """Close wrapper resources."""
        self._executor.shutdown(wait=False)


# Global Redis manager instances
_redis_manager: Optional[RedisManager] = None
_redis_cache_manager: Optional[RedisManager] = None
_redis_broker_manager: Optional[RedisManager] = None


def get_redis_manager(db_number: Optional[int] = None) -> RedisManager:
    """
    Get or create global Redis manager instance.

    Args:
        db_number: Optional Redis DB number for isolation (0-15)

    Returns:
        RedisManager instance
    """
    global _redis_manager
    if db_number is None:
        if _redis_manager is None:
            _redis_manager = RedisManager()
        return _redis_manager
    else:
        # Create isolated manager for specific DB
        return RedisManager(db_number=db_number)


def get_cache_redis_manager() -> RedisManager:
    """
    Get Redis manager for cache operations (DB 1 by default).

    Returns:
        RedisManager instance configured for cache
    """
    global _redis_cache_manager
    if _redis_cache_manager is None:
        cache_db = getattr(settings, 'REDIS_CACHE_DB', 1)
        _redis_cache_manager = RedisManager(db_number=cache_db)
    return _redis_cache_manager


def get_broker_redis_manager() -> RedisManager:
    """
    Get Redis manager for Celery broker operations (DB 0 by default).

    Note: Celery manages its own connections via CELERY_BROKER_URL.
    This is for direct broker inspection/management only.

    Returns:
        RedisManager instance configured for broker
    """
    global _redis_broker_manager
    if _redis_broker_manager is None:
        broker_db = getattr(settings, 'REDIS_BROKER_DB', 0)
        _redis_broker_manager = RedisManager(db_number=broker_db)
    return _redis_broker_manager


async def get_async_redis_client() -> redis_async.Redis:
    """
    Get async Redis client from manager.

    Returns:
        Async Redis client
    """
    manager = get_redis_manager()
    return await manager.get_async_client()


def get_sync_redis_client() -> redis_sync.Redis:
    """
    Get sync Redis client from manager.

    Returns:
        Sync Redis client
    """
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
    manager = get_redis_manager()
    return manager.get_compatible_client(preferred_type)


@asynccontextmanager
async def redis_transaction():
    """
    Async context manager for Redis transactions.

    Usage:
        async with redis_transaction() as pipe:
            pipe.set('key', 'value')
            pipe.incr('counter')
            results = await pipe.execute()
    """
    client = await get_async_redis_client()
    pipe = client.pipeline()
    try:
        yield pipe
    finally:
        # Pipeline cleanup is automatic
        pass


async def cleanup_redis_connections():
    """Cleanup all Redis connections (for application shutdown)."""
    global _redis_manager
    if _redis_manager:
        await _redis_manager.close_all()
        _redis_manager = None
        logger.info("All Redis connections cleaned up")


# Health check function
async def redis_health_check() -> dict:
    """
    Perform Redis health check.

    Returns:
        Health check results
    """
    try:
        manager = get_redis_manager()

        # Test async client
        async_client = await manager.get_async_client()
        async_ping = await async_client.ping()

        # Test sync client
        sync_client = manager.get_sync_client()
        sync_ping = sync_client.ping()

        return {
            "status": "healthy",
            "async_ping": bool(async_ping),
            "sync_ping": bool(sync_ping),
            "redis_url": settings.REDIS_URL,
            "max_connections": manager.max_connections
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "redis_url": getattr(settings, 'REDIS_URL', 'not_configured')
        }
