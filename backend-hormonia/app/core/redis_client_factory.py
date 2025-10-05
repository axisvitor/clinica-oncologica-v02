"""
Redis Client Factory - Centralized Redis Connection Management

Provides a unified factory for creating both sync and async Redis clients with:
- Consistent TLS/SSL configuration across sync and async modes
- Proper certificate validation using certifi
- SNI (Server Name Indication) support for cloud Redis instances
- Comprehensive error handling and logging
- Health check on client creation
- Graceful degradation on connection failures

Based on analysis:
- Sync Redis TLS works correctly
- Async Redis TLS fails with certificate validation errors
- Solution: Unified SSL configuration with proper CA chain and SNI

Usage:
    # Get sync client
    client = get_redis_client(async_mode=False)
    client.set('key', 'value')

    # Get async client
    async_client = await get_redis_client_async()
    await async_client.set('key', 'value')
"""

import ssl
import logging
from typing import Optional, Union, Dict, Any
from urllib.parse import urlparse

try:
    import certifi
    CERTIFI_AVAILABLE = True
except ImportError:
    CERTIFI_AVAILABLE = False
    certifi = None

import redis
import redis.asyncio as redis_async
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from app.config import settings

logger = logging.getLogger(__name__)


class RedisClientFactory:
    """
    Centralized factory for creating Redis clients with consistent TLS configuration.

    This factory ensures both sync and async clients use the same SSL/TLS parameters,
    resolving issues where async Redis fails with certificate validation errors.
    """

    def __init__(self):
        """Initialize the Redis client factory."""
        self._sync_client: Optional[redis.Redis] = None
        self._async_client: Optional[redis_async.Redis] = None
        self._ssl_context: Optional[ssl.SSLContext] = None

    def _parse_redis_url(self, url: str) -> Dict[str, Any]:
        """
        Parse Redis URL and extract connection parameters.

        Args:
            url: Redis connection URL (redis:// or rediss://)

        Returns:
            Dictionary with parsed connection parameters
        """
        parsed = urlparse(url)

        return {
            'scheme': parsed.scheme,
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 6379,
            'password': parsed.password or settings.REDIS_PASSWORD,
            'db': int(parsed.path.lstrip('/')) if parsed.path and parsed.path != '/' else 0,
            'username': parsed.username,
        }

    def _create_ssl_context(self, redis_host: str) -> Optional[ssl.SSLContext]:
        """
        Create SSL context with proper certificate validation.

        This is the key fix: Both sync and async clients need the same SSL configuration.

        Args:
            redis_host: Redis server hostname (for SNI)

        Returns:
            Configured SSLContext or None if SSL is disabled
        """
        if not settings.REDIS_SSL:
            logger.info("Redis SSL disabled")
            return None

        try:
            # Create default SSL context for server authentication
            ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

            # Configure certificate requirements
            cert_reqs = settings.REDIS_SSL_CERT_REQS.lower()

            if cert_reqs == "none":
                # Disable all certificate verification (NOT recommended for production)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                logger.warning(
                    "Redis SSL certificate verification DISABLED (CERT_NONE). "
                    "This is insecure and should only be used for testing!"
                )

            elif cert_reqs == "optional":
                # Optional certificate verification
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_OPTIONAL
                logger.info("Redis SSL using CERT_OPTIONAL mode")

            else:  # "required" (default and recommended)
                # Full certificate verification with CA chain
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED

                # Load CA certificates from certifi if available
                if CERTIFI_AVAILABLE:
                    ssl_context.load_verify_locations(cafile=certifi.where())
                    logger.info(f"Redis SSL using certifi CA bundle: {certifi.where()}")
                else:
                    logger.warning(
                        "certifi not available, using system CA bundle. "
                        "Install certifi for better SSL compatibility: pip install certifi"
                    )

                logger.info(f"Redis SSL enabled with CERT_REQUIRED for host: {redis_host}")

            # Log SSL configuration for debugging
            logger.debug(
                f"SSL Context configured: "
                f"verify_mode={ssl_context.verify_mode}, "
                f"check_hostname={ssl_context.check_hostname}, "
                f"ca_certs_loaded={CERTIFI_AVAILABLE}"
            )

            return ssl_context

        except Exception as e:
            logger.error(f"Failed to create SSL context: {e}", exc_info=True)
            raise

    def _get_connection_kwargs(
        self,
        async_mode: bool = False,
        db: int = 0,
        decode_responses: bool = True
    ) -> Dict[str, Any]:
        """
        Get connection parameters for Redis client.

        Args:
            async_mode: Whether to create async client
            db: Redis database number (0-15)
            decode_responses: Whether to decode responses to strings

        Returns:
            Dictionary of connection parameters
        """
        # Parse Redis URL
        url_params = self._parse_redis_url(settings.REDIS_URL)

        # Override DB if specified
        if db is not None:
            url_params['db'] = db

        # Base connection parameters
        connection_kwargs = {
            'host': url_params['host'],
            'port': url_params['port'],
            'db': url_params['db'],
            'password': url_params['password'],
            'decode_responses': decode_responses,
            'socket_timeout': settings.REDIS_SOCKET_TIMEOUT,
            'socket_connect_timeout': settings.REDIS_SOCKET_CONNECT_TIMEOUT,
            'retry_on_timeout': settings.REDIS_RETRY_ON_TIMEOUT,
            'health_check_interval': settings.REDIS_HEALTH_CHECK_INTERVAL,
        }

        # Add username if present
        if url_params.get('username'):
            connection_kwargs['username'] = url_params['username']

        # FIXED: redis-py 6.0+ handles SSL via rediss:// URL scheme automatically
        # Do NOT pass 'ssl' or 'ssl_context' kwargs - use ssl_cert_reqs instead
        if settings.REDIS_SSL:
            import ssl
            ssl_cert_reqs = getattr(settings, 'REDIS_SSL_CERT_REQS', 'required').lower()

            # Set certificate validation level (redis-py 6.0+ supported params)
            if ssl_cert_reqs == 'none':
                connection_kwargs['ssl_cert_reqs'] = ssl.CERT_NONE
                connection_kwargs['ssl_check_hostname'] = False
                logger.info(f"SSL enabled for {url_params['host']} with CERT_NONE")
            elif ssl_cert_reqs == 'optional':
                connection_kwargs['ssl_cert_reqs'] = ssl.CERT_OPTIONAL
                logger.info(f"SSL enabled for {url_params['host']} with CERT_OPTIONAL")
            else:  # 'required'
                connection_kwargs['ssl_cert_reqs'] = ssl.CERT_REQUIRED
                logger.info(f"SSL enabled for {url_params['host']} with CERT_REQUIRED")

            # Log scheme usage
            if url_params['scheme'] == 'rediss':
                logger.info(f"Using rediss:// scheme for {url_params['host']}")
            else:
                logger.warning(f"REDIS_SSL=true but scheme is {url_params['scheme']} (should be rediss://)")

        # Add retry configuration for error handling
        connection_kwargs['retry_on_error'] = [ConnectionError, TimeoutError]

        logger.debug(
            f"Connection kwargs prepared for {'async' if async_mode else 'sync'} client: "
            f"host={connection_kwargs['host']}, "
            f"port={connection_kwargs['port']}, "
            f"db={connection_kwargs['db']}, "
            f"ssl={'enabled' if connection_kwargs.get('ssl') else 'disabled'}"
        )

        return connection_kwargs

    def get_sync_client(
        self,
        db: int = 0,
        decode_responses: bool = True,
        force_new: bool = False
    ) -> redis.Redis:
        """
        Get or create synchronous Redis client with TLS support.

        Args:
            db: Redis database number (0-15)
            decode_responses: Whether to decode responses to strings
            force_new: Force creation of new client

        Returns:
            Synchronous Redis client

        Raises:
            ConnectionError: If unable to connect to Redis
        """
        if self._sync_client is not None and not force_new:
            logger.debug("Reusing existing sync Redis client")
            return self._sync_client

        try:
            # Get connection parameters
            conn_kwargs = self._get_connection_kwargs(
                async_mode=False,
                db=db,
                decode_responses=decode_responses
            )

            # Create connection pool
            pool = redis.ConnectionPool(**conn_kwargs)

            # Create client from pool
            client = redis.Redis(connection_pool=pool)

            # Health check
            logger.info("Testing sync Redis connection...")
            client.ping()
            logger.info(
                f"✅ Sync Redis client connected successfully to "
                f"{conn_kwargs['host']}:{conn_kwargs['port']} "
                f"(DB: {conn_kwargs['db']}, SSL: {conn_kwargs.get('ssl', False)})"
            )

            # Cache client if db=0 (default)
            if db == 0 and not force_new:
                self._sync_client = client

            return client

        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"❌ Failed to connect to Redis (sync): {e}. "
                f"Check REDIS_URL, REDIS_SSL, and network connectivity."
            )
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error creating sync Redis client: {e}", exc_info=True)
            raise

    async def get_async_client(
        self,
        db: int = 0,
        decode_responses: bool = True,
        force_new: bool = False
    ) -> redis_async.Redis:
        """
        Get or create asynchronous Redis client with TLS support.

        This method uses the SAME SSL configuration as sync client to ensure consistency.

        Args:
            db: Redis database number (0-15)
            decode_responses: Whether to decode responses to strings
            force_new: Force creation of new client

        Returns:
            Asynchronous Redis client

        Raises:
            ConnectionError: If unable to connect to Redis
        """
        if self._async_client is not None and not force_new:
            logger.debug("Reusing existing async Redis client")
            return self._async_client

        try:
            # Get connection parameters (same as sync!)
            conn_kwargs = self._get_connection_kwargs(
                async_mode=True,
                db=db,
                decode_responses=decode_responses
            )

            # Create async connection pool
            pool = redis_async.ConnectionPool(**conn_kwargs)

            # Create async client from pool
            client = redis_async.Redis(connection_pool=pool)

            # Health check
            logger.info("Testing async Redis connection...")
            await client.ping()
            logger.info(
                f"✅ Async Redis client connected successfully to "
                f"{conn_kwargs['host']}:{conn_kwargs['port']} "
                f"(DB: {conn_kwargs['db']}, SSL: {conn_kwargs.get('ssl', False)})"
            )

            # Cache client if db=0 (default)
            if db == 0 and not force_new:
                self._async_client = client

            return client

        except (ConnectionError, TimeoutError) as e:
            logger.error(
                f"❌ Failed to connect to Redis (async): {e}. "
                f"Check REDIS_URL, REDIS_SSL, SSL certificate validation, and network connectivity."
            )
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error creating async Redis client: {e}", exc_info=True)
            raise

    async def close_all(self):
        """Close all Redis connections."""
        try:
            if self._async_client:
                await self._async_client.aclose()
                self._async_client = None
                logger.info("Async Redis client closed")

            if self._sync_client:
                self._sync_client.close()
                self._sync_client = None
                logger.info("Sync Redis client closed")

        except Exception as e:
            logger.error(f"Error closing Redis clients: {e}", exc_info=True)


# Global factory instance
_redis_factory: Optional[RedisClientFactory] = None


def get_redis_factory() -> RedisClientFactory:
    """
    Get the global Redis client factory instance.

    Returns:
        RedisClientFactory singleton
    """
    global _redis_factory
    if _redis_factory is None:
        _redis_factory = RedisClientFactory()
    return _redis_factory


def get_redis_client(
    async_mode: bool = False,
    db: int = 0,
    decode_responses: bool = True
) -> Union[redis.Redis, redis_async.Redis]:
    """
    Get Redis client (sync or async) with unified TLS configuration.

    This is the recommended entry point for all Redis operations.

    Args:
        async_mode: If True, return async client (must be called with await)
        db: Redis database number (0-15)
        decode_responses: Whether to decode responses to strings

    Returns:
        Redis client (sync or async based on async_mode)

    Examples:
        # Sync client
        redis = get_redis_client(async_mode=False)
        redis.set('key', 'value', ex=3600)

        # Async client (call with await)
        redis = await get_redis_client_async()
        await redis.set('key', 'value', ex=3600)
    """
    factory = get_redis_factory()

    if async_mode:
        # Note: This function itself is not async, so we can't await here
        # Callers should use get_redis_client_async() instead
        raise ValueError(
            "For async client, use 'await get_redis_client_async()' instead of "
            "'get_redis_client(async_mode=True)'"
        )

    return factory.get_sync_client(db=db, decode_responses=decode_responses)


async def get_redis_client_async(
    db: int = 0,
    decode_responses: bool = True
) -> redis_async.Redis:
    """
    Get async Redis client with unified TLS configuration.

    Args:
        db: Redis database number (0-15)
        decode_responses: Whether to decode responses to strings

    Returns:
        Async Redis client

    Example:
        redis = await get_redis_client_async()
        await redis.set('key', 'value', ex=3600)
    """
    factory = get_redis_factory()
    return await factory.get_async_client(db=db, decode_responses=decode_responses)


async def cleanup_redis_connections():
    """
    Cleanup all Redis connections.

    Should be called during application shutdown.
    """
    global _redis_factory
    if _redis_factory:
        await _redis_factory.close_all()
        _redis_factory = None
        logger.info("All Redis factory connections cleaned up")


# Health check function
async def redis_health_check() -> Dict[str, Any]:
    """
    Perform Redis health check for both sync and async clients.

    Returns:
        Health check results with connection status
    """
    results = {
        "status": "unknown",
        "sync": {"connected": False, "error": None},
        "async": {"connected": False, "error": None},
        "ssl_enabled": settings.REDIS_SSL,
        "redis_url": settings.REDIS_URL,
    }

    factory = get_redis_factory()

    # Test sync client
    try:
        sync_client = factory.get_sync_client(force_new=True)
        sync_client.ping()
        results["sync"]["connected"] = True
        logger.info("✅ Sync Redis health check passed")
    except Exception as e:
        results["sync"]["error"] = str(e)
        logger.error(f"❌ Sync Redis health check failed: {e}")

    # Test async client
    try:
        async_client = await factory.get_async_client(force_new=True)
        await async_client.ping()
        results["async"]["connected"] = True
        logger.info("✅ Async Redis health check passed")
    except Exception as e:
        results["async"]["error"] = str(e)
        logger.error(f"❌ Async Redis health check failed: {e}")

    # Determine overall status
    if results["sync"]["connected"] and results["async"]["connected"]:
        results["status"] = "healthy"
    elif results["sync"]["connected"] or results["async"]["connected"]:
        results["status"] = "degraded"
    else:
        results["status"] = "unhealthy"

    return results
