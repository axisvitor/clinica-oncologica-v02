"""
RedisManager - Core Manager Class

Manages Redis client connections, pooling, and lifecycle.
Provides both async and sync interfaces with automatic compatibility detection.
"""

import logging
import threading
import ssl
from typing import Optional, Union
import redis.asyncio as redis_async
import redis as redis_sync
from redis.exceptions import ConnectionError, TimeoutError

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

        # Connection settings from config - Aumentados para evitar timeouts
        self.decode_responses = getattr(settings, 'REDIS_DECODE_RESPONSES', True)
        self.socket_timeout = getattr(settings, 'REDIS_SOCKET_TIMEOUT', 30.0)  # Aumentado de 10 para 30
        self.socket_connect_timeout = getattr(settings, 'REDIS_SOCKET_CONNECT_TIMEOUT', 30.0)  # Aumentado de 5 para 30
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

            # FIXED: redis-py 6.0+ handles rediss:// URLs automatically
            # We only pass ssl_cert_reqs, ssl_check_hostname (NOT ssl_context or ssl=True)
            # Since .env already defines REDIS_URL with rediss://, no URL rewriting needed
            redis_url = self.redis_url

            if settings.REDIS_ENABLE_SSL:
                ssl_cert_reqs = getattr(settings, 'REDIS_SSL_CERT_REQS', 'required').lower()

                # Configure SSL certificate validation level
                if ssl_cert_reqs == 'none':
                    connection_kwargs['ssl_cert_reqs'] = ssl.CERT_NONE
                    connection_kwargs['ssl_check_hostname'] = False
                    logger.info("Redis async SSL: Certificate verification DISABLED (CERT_NONE)")
                elif ssl_cert_reqs == 'optional':
                    connection_kwargs['ssl_cert_reqs'] = ssl.CERT_OPTIONAL
                    logger.info("Redis async SSL: Certificate verification OPTIONAL")
                else:  # 'required'
                    connection_kwargs['ssl_cert_reqs'] = ssl.CERT_REQUIRED
                    connection_kwargs['ssl_check_hostname'] = True  # SEC-002: Explicit hostname verification

                    # Use CA certificate for validation if provided
                    ssl_ca_certs = getattr(settings, 'REDIS_SSL_CA_CERTS', None)
                    if ssl_ca_certs:
                        import os
                        # Support both absolute and relative paths
                        if os.path.isabs(ssl_ca_certs):
                            ca_path = ssl_ca_certs
                        else:
                            ca_path = os.path.join(settings.BASE_DIR, ssl_ca_certs)

                        if os.path.exists(ca_path):
                            connection_kwargs['ssl_ca_certs'] = ca_path
                            logger.info(f"Redis async SSL: Using CA certificate from {ssl_ca_certs}")
                        else:
                            logger.error(f"Redis CA certificate not found at {ca_path}. Falling back to certifi.")
                            ssl_ca_certs = None  # Trigger fallback below

                    # Fallback to certifi if no custom CA specified
                    if not ssl_ca_certs:
                        try:
                            import certifi
                            connection_kwargs['ssl_ca_certs'] = certifi.where()
                            logger.info(f"Redis async SSL: Using certifi CA bundle: {certifi.where()}")
                        except ImportError:
                            logger.warning("Redis async SSL: certifi not available, using system CA store")

                    logger.info("Redis async SSL: Certificate verification REQUIRED")

                # FIX: Add explicit TLS version support for Redis Cloud compatibility
                # Python 3.13 + OpenSSL 3.x defaults to TLS 1.3, but some Redis Cloud
                # instances require TLS 1.2. Allow configuration via environment variable.
                ssl_min_version = getattr(settings, 'REDIS_SSL_MIN_VERSION', None)
                if ssl_min_version:
                    ssl_min_version = ssl_min_version.upper()
                    if ssl_min_version == 'TLSV1_2':
                        connection_kwargs['ssl_min_version'] = ssl.TLSVersion.TLSv1_2
                        logger.info("Redis async SSL: Enforcing minimum TLS version 1.2")
                    elif ssl_min_version == 'TLSV1_3':
                        connection_kwargs['ssl_min_version'] = ssl.TLSVersion.TLSv1_3
                        logger.info("Redis async SSL: Enforcing minimum TLS version 1.3")
                    else:
                        logger.warning(f"Invalid REDIS_SSL_MIN_VERSION: {ssl_min_version}. Ignoring.")
                else:
                    logger.info("Redis async SSL: Using Python default TLS version negotiation")

                # Validate URL scheme matches SSL config
                if not redis_url.startswith('rediss://'):
                    logger.error(f"REDIS_SSL=true but URL uses {redis_url.split('://')[0]}:// scheme. Fix .env to use rediss://")
            else:
                # Warn if SSL URL used without REDIS_SSL=true
                if redis_url.startswith('rediss://'):
                    logger.warning("URL uses rediss:// but REDIS_SSL=false. Connection may fail.")
                logger.info("Redis async: Using non-SSL connection")

            # Create async connection pool - from_url() handles SSL via rediss:// + ssl_cert_reqs
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
            if settings.REDIS_ENABLE_SSL:
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

    def get_compatible_client(self, preferred_type: str = "auto") -> Union[redis_async.Redis, redis_sync.Redis, 'AsyncToSyncWrapper']:
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
