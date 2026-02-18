"""
RedisManager - Core Manager Class

Manages Redis client connections, pooling, and lifecycle.
Provides both async and sync interfaces with automatic compatibility detection.
"""

import asyncio
import logging
import threading
from weakref import WeakKeyDictionary
from typing import Optional, Union, TYPE_CHECKING, Any, Dict
import redis.asyncio as redis_async
import redis as redis_sync
from redis.exceptions import ConnectionError, TimeoutError

if TYPE_CHECKING:
    from .sync_client import AsyncToSyncWrapper

from app.config import settings
from .utils import build_redis_url_for_db

logger = logging.getLogger(__name__)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    """Coerce config flags safely, ignoring truthy MagicMock objects."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return default


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
        self._sync_client: Optional[redis_sync.Redis] = None
        self._sync_pool: Optional[redis_sync.ConnectionPool] = None
        self._lock = threading.Lock()
        self._async_lock = threading.Lock()
        self._async_clients: WeakKeyDictionary[
            asyncio.AbstractEventLoop, redis_async.Redis
        ] = WeakKeyDictionary()
        self._async_pools: WeakKeyDictionary[
            asyncio.AbstractEventLoop, redis_async.ConnectionPool
        ] = WeakKeyDictionary()

        # Connection settings (use Redis Cloud URL from settings)
        redis_url_setting = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        self.redis_url = (
            redis_url_setting
            if isinstance(redis_url_setting, str) and redis_url_setting
            else "redis://localhost:6379/0"
        )

        # SSL is now configured manually via connection_kwargs (see _create_*_client methods)
        # This approach works better with Python 3.13's strict SSL validation
        # No need to convert redis:// to rediss:// - we configure SSL parameters directly

        # DB isolation support
        self.db_number = db_number
        cluster_mode = _coerce_bool(
            getattr(settings, "REDIS_ENABLE_CLUSTER_MODE", False), default=False
        )
        if cluster_mode:
            if db_number is not None and int(db_number) != 0:
                logger.warning(
                    "Redis cluster mode enabled: ignoring DB isolation for DB=%s; using DB 0",
                    db_number,
                )
            self.db_number = 0
            self.redis_url = build_redis_url_for_db(self.redis_url, 0)
        elif db_number is not None and _coerce_bool(
            getattr(settings, "REDIS_ENABLE_DB_ISOLATION", True), default=True
        ):
            # Override DB in URL if isolation is enabled.
            self.redis_url = build_redis_url_for_db(self.redis_url, db_number)
            logger.info(f"Redis DB isolation enabled: using DB {db_number}")

        # Connection settings from config - OPTIMIZED for SSL/TLS performance
        self.decode_responses = getattr(settings, "REDIS_ENABLE_DECODE_RESPONSES", True)

        # OPTIMIZED: Reduced timeouts (SSL handshake should be fast)
        self.socket_timeout = getattr(
            settings, "REDIS_SOCKET_TIMEOUT_SECONDS", 5.0
        )  # Reduced from 30s
        self.socket_connect_timeout = getattr(
            settings, "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", 2.0
        )  # Reduced from 30s

        self.retry_on_timeout = getattr(settings, "REDIS_ENABLE_RETRY_ON_TIMEOUT", True)
        self.max_retry_attempts = getattr(settings, "REDIS_MAX_RETRY_ATTEMPTS", 3)

        # OPTIMIZED: Reduced pool size (Redis needs fewer connections than DB)
        self.max_connections = getattr(
            settings, "REDIS_POOL_MAX_CONNECTIONS", 20
        )  # Reduced from 50

        # Health check configuration
        self.health_check_interval = getattr(
            settings, "REDIS_HEALTH_CHECK_INTERVAL_SECONDS", 30
        )
        self.enable_health_check = getattr(settings, "REDIS_ENABLE_HEALTH_CHECK", True)

        # SSL/TLS optimization settings
        self.ssl_session_reuse = getattr(settings, "REDIS_SSL_SESSION_REUSE", True)
        self.ssl_warmup_enabled = getattr(
            settings, "REDIS_SSL_CONNECTION_POOL_WARMUP", True
        )
        self.ssl_warmup_connections = getattr(
            settings, "REDIS_SSL_WARMUP_CONNECTIONS", 5
        )

    async def get_async_client(self) -> redis_async.Redis:
        """
        Get or create async Redis client.

        Returns:
            Async Redis client instance
        """
        current_loop = asyncio.get_running_loop()
        existing_client = self._async_clients.get(current_loop)
        if existing_client is not None:
            return existing_client

        client, pool = await self._create_async_client()
        cleanup_client = None
        cleanup_pool = None

        with self._async_lock:
            existing_client = self._async_clients.get(current_loop)
            if existing_client is not None:
                cleanup_client = client
                cleanup_pool = pool
            else:
                self._async_clients[current_loop] = client
                self._async_pools[current_loop] = pool

        if cleanup_client is not None:
            try:
                await cleanup_client.aclose()
            except Exception:
                pass
            try:
                await cleanup_pool.aclose()
            except Exception:
                pass
            return existing_client

        return client

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

    def _build_connection_kwargs(self) -> Dict[str, Any]:
        """Build shared Redis connection kwargs for sync/async clients."""
        return {
            "decode_responses": self.decode_responses,
            "socket_timeout": self.socket_timeout,
            "socket_connect_timeout": self.socket_connect_timeout,
            "retry_on_timeout": self.retry_on_timeout,
            "retry_on_error": [ConnectionError, TimeoutError],
            "max_connections": self.max_connections,
            "health_check_interval": self.health_check_interval
            if self.enable_health_check
            else 0,
        }

    def _prepare_connection_config(self, client_kind: str) -> tuple[str, Dict[str, Any]]:
        """Prepare URL + kwargs with SSL normalization for sync/async clients."""
        connection_kwargs = self._build_connection_kwargs()
        redis_url = self.redis_url

        if settings.REDIS_ENABLE_SSL:
            if redis_url.startswith("redis://"):
                redis_url = "rediss://" + redis_url[8:]

            ssl_cert_reqs = getattr(settings, "REDIS_SSL_CERT_REQS", "required").lower()
            verify_mode = "CERT_NONE" if ssl_cert_reqs == "none" else "CERT_REQUIRED"
            connection_kwargs["ssl_cert_reqs"] = ssl_cert_reqs

            logger.info(
                f"Redis {client_kind} SSL: Enabled (TLS >= 1.2, verify={verify_mode}, "
                f"redis-py={redis_sync.__version__})"
            )
        else:
            if redis_url.startswith("rediss://"):
                redis_url = "redis://" + redis_url[9:]
            logger.info(f"Redis {client_kind}: Using non-SSL connection")

        return redis_url, connection_kwargs

    async def _create_async_client(self) -> tuple[redis_async.Redis, redis_async.ConnectionPool]:
        """
        Create async Redis client with connection pool.

        SSL is configured using SSLContext for Python 3.13 compatibility.
        This is the correct approach for redis-py 5.x with Python 3.13.
        """
        try:
            redis_url, connection_kwargs = self._prepare_connection_config("async")

            # Create async connection pool
            async_pool = redis_async.ConnectionPool.from_url(
                redis_url, **connection_kwargs
            )

            # Create client from pool
            async_client = redis_async.Redis(connection_pool=async_pool)

            # Test connection
            await async_client.ping()
            logger.info(
                f"Async Redis client connected successfully "
                f"(pool_size={self.max_connections}, "
                f"timeout={self.socket_timeout}s, "
                f"connect_timeout={self.socket_connect_timeout}s)"
            )

            # OPTIMIZATION: Warmup connection pool for SSL/TLS
            if settings.REDIS_ENABLE_SSL and self.ssl_warmup_enabled:
                await self._warmup_connection_pool_async(async_client)
                logger.info(
                    f"Redis async pool warmed up with {self.ssl_warmup_connections} connections"
                )

            return async_client, async_pool

        except Exception as e:
            logger.error(f"Failed to create async Redis client: {e}")
            raise

    def _create_sync_client(self):
        """
        Create sync Redis client with connection pool.

        For redis-py 6.x, both sync and async use ssl_context parameter.
        """
        try:
            redis_url, connection_kwargs = self._prepare_connection_config("sync")

            # Create sync connection pool
            self._sync_pool = redis_sync.ConnectionPool.from_url(
                redis_url, **connection_kwargs
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
            with self._async_lock:
                async_clients = list(self._async_clients.values())
                async_pools = list(self._async_pools.values())
                self._async_clients.clear()
                self._async_pools.clear()

            for client in async_clients:
                try:
                    # Use aclose() for proper async cleanup (redis 5.x)
                    await client.aclose()
                    logger.debug("Async Redis client closed")
                except Exception as e:
                    logger.error(f"Error closing async Redis client: {e}")

            for pool in async_pools:
                try:
                    # Use aclose() for ConnectionPool in redis 5.x
                    await pool.aclose()
                    logger.debug("Async Redis pool closed")
                except Exception as e:
                    logger.error(f"Error closing async Redis pool: {e}")

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

    async def _warmup_connection_pool_async(
        self, client: Optional[redis_async.Redis] = None
    ):
        """
        Pre-create connections in the pool to amortize SSL/TLS handshake cost.

        This is particularly beneficial for Redis Cloud with SSL/TLS enabled,
        as it moves the handshake overhead from request time to startup time.
        """
        target_client = client
        if target_client is None:
            target_client = self._async_clients.get(asyncio.get_running_loop())
        if not target_client:
            logger.warning("Cannot warmup pool: async client not initialized")
            return

        try:
            warmup_count = min(self.ssl_warmup_connections, self.max_connections)
            logger.info(
                f"Warming up Redis async pool with {warmup_count} connections..."
            )

            # Perform multiple PING operations to force connection creation
            tasks = []
            for i in range(warmup_count):
                tasks.append(target_client.ping())

            # Execute all PINGs concurrently
            await asyncio.gather(*tasks, return_exceptions=True)

            logger.info(
                f"Redis async pool warmup completed: {warmup_count} connections created"
            )

        except Exception as e:
            logger.warning(f"Redis pool warmup failed (non-fatal): {e}")

    def _warmup_connection_pool_sync(self):
        """
        Pre-create connections in the sync pool.

        Sync version of pool warmup for non-async contexts.
        """
        if not self._sync_client:
            logger.warning("Cannot warmup pool: sync client not initialized")
            return

        try:
            warmup_count = min(self.ssl_warmup_connections, self.max_connections)
            logger.info(
                f"Warming up Redis sync pool with {warmup_count} connections..."
            )

            # Create a connection and return it to pool multiple times
            for i in range(warmup_count):
                self._sync_client.ping()

            logger.info(
                f"Redis sync pool warmup completed: {warmup_count} connections created"
            )

        except Exception as e:
            logger.warning(f"Redis sync pool warmup failed (non-fatal): {e}")

    async def get_pool_stats_async(self):
        """
        Get async connection pool statistics.

        Returns:
            Dict with pool metrics
        """
        async_pools = list(self._async_pools.values())
        if not async_pools:
            return {"status": "not_initialized"}

        try:
            # Note: redis-py async pool doesn't expose all stats like sync pool
            # We can only get basic info
            return {
                "status": "healthy",
                "pool_count": len(async_pools),
                "max_connections": self.max_connections,
                "socket_timeout": self.socket_timeout,
                "connect_timeout": self.socket_connect_timeout,
                "health_check_interval": self.health_check_interval,
                "pool_type": "async",
            }
        except Exception as e:
            logger.error(f"Failed to get async pool stats: {e}")
            return {"status": "error", "error": str(e)}

    def get_pool_stats_sync(self):
        """
        Get sync connection pool statistics.

        Returns:
            Dict with detailed pool metrics
        """
        if not self._sync_pool:
            return {"status": "not_initialized"}

        try:
            # Get detailed pool statistics
            pool = self._sync_pool
            return {
                "status": "healthy",
                "max_connections": self.max_connections,
                "socket_timeout": self.socket_timeout,
                "connect_timeout": self.socket_connect_timeout,
                "health_check_interval": self.health_check_interval,
                "pool_type": "sync",
                # Note: Some pool stats may not be available depending on redis-py version
                "created_connections": getattr(pool, "_created_connections", "N/A"),
                "available_connections": getattr(pool, "_available_connections", "N/A"),
            }
        except Exception as e:
            logger.error(f"Failed to get sync pool stats: {e}")
            return {"status": "error", "error": str(e)}

    def get_compatible_client(
        self, preferred_type: str = "auto"
    ) -> Union[redis_async.Redis, redis_sync.Redis, "AsyncToSyncWrapper"]:
        """
        Get Redis client with automatic compatibility detection.

        Args:
            preferred_type: "async", "sync", or "auto" (default)

        Returns:
            Redis client or compatibility wrapper
        """
        from .sync_client import AsyncToSyncWrapper

        if preferred_type == "async":
            # Return async client wrapped for sync compatibility if needed
            return AsyncToSyncWrapper(self)
        elif preferred_type == "sync":
            return self.get_sync_client()
        else:
            # Auto-detect based on current context
            import asyncio

            try:
                # Check if we're in an async context
                asyncio.get_running_loop()
                return AsyncToSyncWrapper(self)  # Use wrapper for mixed usage
            except RuntimeError:
                # No event loop, use sync client
                return self.get_sync_client()

    # ------------------------------------------------------------------
    # Legacy compatibility helpers
    # ------------------------------------------------------------------
    async def get_user_by_uid(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """
        Backward-compatible user cache lookup.

        Some legacy code paths and tests patch methods on RedisManager directly.
        """
        from .firebase_cache import FirebaseRedisCache

        cache = FirebaseRedisCache(self.get_sync_client())
        return await cache.get_user_by_uid(firebase_uid)

    async def get(self, key: str) -> Optional[Any]:
        """Backward-compatible async get helper."""
        client = await self.get_async_client()
        return await client.get(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Backward-compatible async delete by key pattern."""
        client = await self.get_async_client()
        deleted_count = 0
        batch: list[Any] = []

        async for key in client.scan_iter(match=pattern):
            batch.append(key)
            if len(batch) >= 500:
                for batch_key in batch:
                    try:
                        if hasattr(client, "unlink"):
                            deleted_count += int((await client.unlink(batch_key)) or 0)
                        else:
                            deleted_count += int((await client.delete(batch_key)) or 0)
                    except Exception:
                        deleted_count += int((await client.delete(batch_key)) or 0)
                batch.clear()

        if batch:
            for batch_key in batch:
                try:
                    if hasattr(client, "unlink"):
                        deleted_count += int((await client.unlink(batch_key)) or 0)
                    else:
                        deleted_count += int((await client.delete(batch_key)) or 0)
                except Exception:
                    deleted_count += int((await client.delete(batch_key)) or 0)

        return deleted_count

    async def cache_user_data(
        self, firebase_uid: str, user_data: Dict[str, Any], ttl: int = 900
    ) -> None:
        """Backward-compatible user cache write helper."""
        from .firebase_cache import FirebaseRedisCache

        cache = FirebaseRedisCache(self.get_sync_client())
        await cache.cache_user_data(firebase_uid, user_data, ttl=ttl)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Backward-compatible session lookup helper."""
        from .session_cache import SessionCache

        session_cache = SessionCache(
            self.get_sync_client(),
            session_ttl=getattr(settings, "FIREBASE_SESSION_TTL", 86400),
            max_session_age=getattr(settings, "SESSION_MAX_AGE_SECONDS", 604800),
        )
        return await session_cache.get_session(session_id)

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        firebase_uid: str,
        ttl: int = 86400,
    ) -> bool:
        """Backward-compatible session creation helper."""
        from .session_cache import SessionCache

        session_cache = SessionCache(
            self.get_sync_client(),
            session_ttl=getattr(settings, "FIREBASE_SESSION_TTL", 86400),
            max_session_age=getattr(settings, "SESSION_MAX_AGE_SECONDS", 604800),
        )
        return await session_cache.create_session(
            session_id=session_id,
            user_id=user_id,
            firebase_uid=firebase_uid,
            ttl=ttl,
        )

    async def update_session_activity(
        self, session_id: str, extend_ttl: bool = True, custom_ttl: Optional[int] = None
    ) -> bool:
        """Backward-compatible session activity update helper."""
        from .session_cache import SessionCache

        session_cache = SessionCache(
            self.get_sync_client(),
            session_ttl=getattr(settings, "FIREBASE_SESSION_TTL", 86400),
            max_session_age=getattr(settings, "SESSION_MAX_AGE_SECONDS", 604800),
        )
        return await session_cache.update_session_activity(
            session_id=session_id, extend_ttl=extend_ttl, custom_ttl=custom_ttl
        )
