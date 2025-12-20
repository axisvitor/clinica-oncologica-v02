"""
RedisManager - Core Manager Class

Manages Redis client connections, pooling, and lifecycle.
Provides both async and sync interfaces with automatic compatibility detection.
"""

import asyncio
import logging
import threading
import ssl
from pathlib import Path
from typing import Optional, Union, TYPE_CHECKING
import redis.asyncio as redis_async
import redis as redis_sync
from redis.exceptions import ConnectionError, TimeoutError

if TYPE_CHECKING:
    from .sync_client import AsyncToSyncWrapper

from app.config import settings

logger = logging.getLogger(__name__)

# Path to Redis CA certificate for SSL/TLS connections
REDIS_CA_CERT_PATH = Path(__file__).parent.parent.parent.parent / "certs" / "redis_ca.pem"


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
        if db_number is not None and getattr(
            settings, "REDIS_ENABLE_DB_ISOLATION", True
        ):
            # Override DB in URL if isolation is enabled
            base_url = (
                self.redis_url.rsplit("/", 1)[0]
                if "/" in self.redis_url
                else self.redis_url
            )
            self.redis_url = f"{base_url}/{db_number}"
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

    def _create_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context for Redis Cloud connection.

        Respects REDIS_SSL_CERT_REQS setting:
        - "none": No certificate verification (common for Redis Cloud free tier)
        - "required": Full certificate verification with CA cert

        This is required for Python 3.13 compatibility with redis-py 5.x.
        """
        # Check if certificate verification is disabled
        ssl_cert_reqs = getattr(settings, "REDIS_SSL_CERT_REQS", "required").lower()

        if ssl_cert_reqs == "none":
            # Create SSL context without certificate verification
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            logger.info("Redis SSL: Enabled without certificate verification (CERT_NONE)")
            return ssl_context

        # Full certificate verification
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

        # Load CA certificate if it exists
        if REDIS_CA_CERT_PATH.exists():
            ssl_context.load_verify_locations(cafile=str(REDIS_CA_CERT_PATH))
            logger.info(f"Redis SSL: Loaded CA certificate from {REDIS_CA_CERT_PATH}")
        else:
            # Use system CA certificates as fallback
            ssl_context.load_default_certs()
            logger.warning(
                f"Redis CA cert not found at {REDIS_CA_CERT_PATH}, using system certs"
            )

        # Verify server certificate
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

        return ssl_context

    async def _create_async_client(self):
        """
        Create async Redis client with connection pool.

        SSL is configured using SSLContext for Python 3.13 compatibility.
        This is the correct approach for redis-py 5.x with Python 3.13.
        """
        try:
            # Base connection configuration - OPTIMIZED
            connection_kwargs = {
                "decode_responses": self.decode_responses,
                "socket_timeout": self.socket_timeout,  # 5s (optimized for SSL)
                "socket_connect_timeout": self.socket_connect_timeout,  # 2s (optimized)
                "retry_on_timeout": self.retry_on_timeout,
                "retry_on_error": [ConnectionError, TimeoutError],
                "max_connections": self.max_connections,  # 20 (reduced from 50)
                "health_check_interval": self.health_check_interval
                if self.enable_health_check
                else 0,
            }

            redis_url = self.redis_url

            # Configure SSL if enabled
            if settings.REDIS_ENABLE_SSL:
                # Convert redis:// to rediss:// for SSL
                if redis_url.startswith("redis://"):
                    redis_url = "rediss://" + redis_url[8:]

                # For redis-py 6.x: use ssl_context parameter (not ssl=SSLContext)
                ssl_context = self._create_ssl_context()
                connection_kwargs["ssl_context"] = ssl_context

                # Log reflects actual SSL verification mode
                ssl_cert_reqs = getattr(settings, "REDIS_SSL_CERT_REQS", "required").lower()
                verify_mode = "CERT_NONE" if ssl_cert_reqs == "none" else "CERT_REQUIRED"
                logger.info(
                    f"Redis async SSL: Enabled (TLS >= 1.2, verify={verify_mode})"
                )
            else:
                # Ensure using non-SSL scheme
                if redis_url.startswith("rediss://"):
                    redis_url = "redis://" + redis_url[9:]
                logger.info("Redis async: Using non-SSL connection")

            # Create async connection pool
            self._async_pool = redis_async.ConnectionPool.from_url(
                redis_url, **connection_kwargs
            )

            # Create client from pool
            self._async_client = redis_async.Redis(connection_pool=self._async_pool)

            # Test connection
            await self._async_client.ping()
            logger.info(
                f"Async Redis client connected successfully "
                f"(pool_size={self.max_connections}, "
                f"timeout={self.socket_timeout}s, "
                f"connect_timeout={self.socket_connect_timeout}s)"
            )

            # OPTIMIZATION: Warmup connection pool for SSL/TLS
            if settings.REDIS_ENABLE_SSL and self.ssl_warmup_enabled:
                await self._warmup_connection_pool_async()
                logger.info(
                    f"Redis async pool warmed up with {self.ssl_warmup_connections} connections"
                )

        except Exception as e:
            logger.error(f"Failed to create async Redis client: {e}")
            raise

    def _create_sync_client(self):
        """
        Create sync Redis client with connection pool.

        For sync redis-py 5.x, SSL is configured via ssl_cert_reqs parameter,
        NOT via ssl=SSLContext (which only works for async).
        """
        try:
            # Base connection configuration - OPTIMIZED
            connection_kwargs = {
                "decode_responses": self.decode_responses,
                "socket_timeout": self.socket_timeout,  # 5s (optimized for SSL)
                "socket_connect_timeout": self.socket_connect_timeout,  # 2s (optimized)
                "retry_on_timeout": self.retry_on_timeout,
                "retry_on_error": [ConnectionError, TimeoutError],
                "max_connections": self.max_connections,  # 20 (reduced from 50)
                "health_check_interval": self.health_check_interval
                if self.enable_health_check
                else 0,
            }

            redis_url = self.redis_url

            # Configure SSL if enabled
            if settings.REDIS_ENABLE_SSL:
                # Convert redis:// to rediss:// for SSL
                if redis_url.startswith("redis://"):
                    redis_url = "rediss://" + redis_url[8:]

                # For sync redis, use ssl_cert_reqs parameter (NOT ssl=SSLContext)
                ssl_cert_reqs = getattr(settings, "REDIS_SSL_CERT_REQS", "required").lower()
                if ssl_cert_reqs == "none":
                    connection_kwargs["ssl_cert_reqs"] = None  # No verification
                    logger.info("Redis sync SSL: Enabled without certificate verification")
                else:
                    connection_kwargs["ssl_cert_reqs"] = "required"
                    # Optionally add CA cert path if exists
                    if REDIS_CA_CERT_PATH.exists():
                        connection_kwargs["ssl_ca_certs"] = str(REDIS_CA_CERT_PATH)
                        logger.info(f"Redis sync SSL: Using CA cert from {REDIS_CA_CERT_PATH}")
                    else:
                        logger.info("Redis sync SSL: Using system CA certificates")
            else:
                # Ensure using non-SSL scheme
                if redis_url.startswith("rediss://"):
                    redis_url = "redis://" + redis_url[9:]
                logger.info("Redis sync: Using non-SSL connection")

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
            if self._async_client:
                # Use aclose() for proper async cleanup (redis 5.x)
                await self._async_client.aclose()
                self._async_client = None
                logger.debug("Async Redis client closed")

            if self._async_pool:
                # Use aclose() for ConnectionPool in redis 5.x
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

    async def _warmup_connection_pool_async(self):
        """
        Pre-create connections in the pool to amortize SSL/TLS handshake cost.

        This is particularly beneficial for Redis Cloud with SSL/TLS enabled,
        as it moves the handshake overhead from request time to startup time.
        """
        if not self._async_client:
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
                tasks.append(self._async_client.ping())

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
        if not self._async_pool:
            return {"status": "not_initialized"}

        try:
            # Note: redis-py async pool doesn't expose all stats like sync pool
            # We can only get basic info
            return {
                "status": "healthy",
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
