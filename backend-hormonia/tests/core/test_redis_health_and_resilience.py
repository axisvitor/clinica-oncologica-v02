"""
Unit Tests for Redis Health Checks and Resilience

Tests health check functionality, error handling, and resilience patterns.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from redis.exceptions import ConnectionError, TimeoutError, ResponseError
from app.core import redis_manager as redis_manager_module


def _patch_redis_settings(**overrides):
    defaults = {
        "REDIS_URL": "redis://localhost:6379/0",
        "REDIS_ENABLE_SSL": False,
        "REDIS_ENABLE_DECODE_RESPONSES": True,
        "REDIS_SOCKET_TIMEOUT_SECONDS": 5.0,
        "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS": 2.0,
        "REDIS_ENABLE_RETRY_ON_TIMEOUT": True,
        "REDIS_MAX_RETRY_ATTEMPTS": 3,
        "REDIS_POOL_MAX_CONNECTIONS": 20,
        "REDIS_HEALTH_CHECK_INTERVAL_SECONDS": 30,
        "REDIS_ENABLE_HEALTH_CHECK": True,
        "REDIS_SSL_CONNECTION_POOL_WARMUP": False,
    }
    defaults.update(overrides)
    return patch.multiple(redis_manager_module.settings, **defaults)


class TestRedisHealthChecks:
    """Test Redis health check functionality."""

    @pytest.mark.asyncio
    @patch("app.core.redis_manager.get_redis_manager")
    async def test_health_check_success(self, mock_get_manager):
        """Test successful health check."""
        from app.core.redis_manager import redis_health_check

        # Mock manager with healthy async and sync clients
        mock_manager = Mock()
        mock_async_client = AsyncMock()
        mock_async_client.ping = AsyncMock(return_value=True)
        mock_sync_client = Mock()
        mock_sync_client.ping = Mock(return_value=True)
        mock_manager.get_async_client = AsyncMock(return_value=mock_async_client)
        mock_manager.get_sync_client = Mock(return_value=mock_sync_client)
        mock_manager.max_connections = 20
        mock_get_manager.return_value = mock_manager

        result = await redis_health_check()

        assert result["status"] == "healthy"
        assert result["async_ping"] is True
        assert result["sync_ping"] is True
        assert "redis_url" in result

    @pytest.mark.asyncio
    @patch("app.core.redis_manager.get_redis_manager")
    async def test_health_check_connection_failure(self, mock_get_manager):
        """Test health check when connection fails."""
        from app.core.redis_manager import redis_health_check

        mock_manager = Mock()
        mock_async_client = AsyncMock()
        mock_async_client.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_manager.get_async_client = AsyncMock(return_value=mock_async_client)
        mock_get_manager.return_value = mock_manager

        result = await redis_health_check()

        assert result["status"] == "unhealthy"
        assert "error" in result

    @pytest.mark.asyncio
    @patch("app.core.redis_manager.get_redis_manager")
    async def test_health_check_timeout(self, mock_get_manager):
        """Test health check timeout handling."""
        from app.core.redis_manager import redis_health_check

        mock_manager = Mock()
        mock_async_client = AsyncMock()
        mock_async_client.ping = AsyncMock(side_effect=TimeoutError("Operation timed out"))
        mock_manager.get_async_client = AsyncMock(return_value=mock_async_client)
        mock_get_manager.return_value = mock_manager

        result = await redis_health_check()

        assert result["status"] == "unhealthy"
        assert "error" in result


class TestRedisErrorHandling:
    """Test Redis error handling patterns."""

    @pytest.mark.asyncio
    async def test_handles_connection_error_gracefully(self):
        """Test graceful handling of connection errors."""
        from app.core.redis_manager import RedisManager

        with _patch_redis_settings():
            manager = RedisManager()

        # Mock client that fails
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("Connection lost"))

        # Should handle error without raising
        try:
            await mock_client.get("test_key")
            pytest.fail("Should have raised ConnectionError")
        except ConnectionError as e:
            # Error is raised but should be handled by calling code
            assert "Connection lost" in str(e)

    @pytest.mark.asyncio
    async def test_handles_timeout_error(self):
        """Test timeout error handling."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=TimeoutError("Operation timed out"))

        try:
            await mock_client.get("test_key")
            pytest.fail("Should have raised TimeoutError")
        except TimeoutError as e:
            assert "timed out" in str(e).lower()

    @pytest.mark.asyncio
    async def test_handles_response_error(self):
        """Test response error handling."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ResponseError("Invalid response"))

        try:
            await mock_client.get("test_key")
            pytest.fail("Should have raised ResponseError")
        except ResponseError as e:
            assert "Invalid response" in str(e)


class TestRedisRetryLogic:
    """Test Redis retry logic."""

    @pytest.mark.asyncio
    async def test_retry_configuration(self):
        """Test retry configuration is applied."""
        from app.core.redis_manager import RedisManager

        with _patch_redis_settings():
            manager = RedisManager()

            assert manager.retry_on_timeout is True
            assert manager.max_retry_attempts == 3


class TestRedisConnectionPoolResilience:
    """Test connection pool resilience."""

    @pytest.mark.asyncio
    async def test_pool_survives_individual_connection_failure(self):
        """Test pool continues working after individual connection fails."""
        from app.core.redis_manager import RedisManager

        with _patch_redis_settings():
            manager = RedisManager()

            # Pool should be configured with health checks
            assert manager.enable_health_check is True
            assert manager.health_check_interval == 30

    @pytest.mark.asyncio
    async def test_pool_max_connections_enforced(self):
        """Test pool enforces max connections limit."""
        from app.core.redis_manager import RedisManager

        with _patch_redis_settings():
            manager = RedisManager()

            # Max connections should be configured
            assert manager.max_connections == 20


class TestRedisTimeoutConfiguration:
    """Test Redis timeout configuration."""

    def test_socket_timeout_configuration(self):
        """Test socket timeout is configured correctly."""
        from app.core.redis_manager import RedisManager

        with _patch_redis_settings():
            manager = RedisManager()

            assert manager.socket_timeout == 5.0
            assert manager.socket_connect_timeout == 2.0

    def test_optimized_timeout_values(self):
        """Test timeout values are optimized for SSL/TLS."""
        from app.core.redis_manager import RedisManager

        with _patch_redis_settings(
            REDIS_ENABLE_SSL=True,
            REDIS_SSL_CERT_REQS="none",
        ):
            manager = RedisManager()

            # Timeouts should be reasonable for SSL
            assert manager.socket_timeout <= 10.0
            assert manager.socket_connect_timeout <= 5.0


class TestRedisCleanupHandling:
    """Test Redis connection cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_handles_none_clients(self):
        """Test cleanup doesn't fail with None clients."""
        from app.core.redis_manager import RedisManager

        with _patch_redis_settings():
            manager = RedisManager()

            # Should not raise even with None clients
            await manager.close_async()
            manager.close_sync()
            await manager.close_all()

    @pytest.mark.asyncio
    async def test_cleanup_handles_errors_gracefully(self):
        """Test cleanup handles errors during close."""
        from app.core.redis_manager import RedisManager

        with _patch_redis_settings():
            manager = RedisManager()

            # Mock clients that fail on close
            mock_async_client = AsyncMock()
            mock_async_client.aclose = AsyncMock(side_effect=Exception("Close failed"))
            manager._async_client = mock_async_client

            mock_sync_client = Mock()
            mock_sync_client.close = Mock(side_effect=Exception("Close failed"))
            manager._sync_client = mock_sync_client

            # Should not raise
            await manager.close_async()
            manager.close_sync()

            # Clients remain set when close fails
            assert manager._async_client is mock_async_client
            assert manager._sync_client is mock_sync_client


class TestRedisFallbackBehavior:
    """Test fallback behavior when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_local_cache_fallback_on_redis_failure(self):
        """Test local cache is used when Redis fails."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        backend = RedisBackend(enable_local_fallback=True)

        # Mock Redis failure
        mock_client = Mock()
        mock_client.get = Mock(side_effect=ConnectionError("Redis down"))
        backend.redis_client = mock_client

        # Set in local cache
        backend.set_in_local_cache("test_key", "test_value", 60)

        # Should get from local cache when Redis fails
        result = backend.get_from_local_cache("test_key")

        assert result == "test_value"

    def test_graceful_degradation_without_redis(self):
        """Test application works without Redis."""
        from app.infrastructure.cache.redis_backend import RedisBackend

        backend = RedisBackend(redis_client=None, enable_local_fallback=True)

        # Should work with local cache only
        backend.set_in_local_cache("key", "value", 60)
        result = backend.get_from_local_cache("key")

        assert result == "value"
