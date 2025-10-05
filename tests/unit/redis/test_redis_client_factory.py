"""
Tests for Redis Client Factory

Validates:
- Sync client creation and TLS configuration
- Async client creation and TLS configuration
- SSL context creation with certifi
- Connection pooling
- Error handling and graceful degradation
- Health checks
"""

import pytest
import ssl
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from app.core.redis_client_factory import (
    RedisClientFactory,
    get_redis_factory,
    get_redis_client,
    get_redis_client_async,
    redis_health_check,
    cleanup_redis_connections,
)


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('app.core.redis_client_factory.settings') as mock:
        mock.REDIS_URL = "rediss://test-redis.cloud:14149"
        mock.REDIS_PASSWORD = "test-password"
        mock.REDIS_SSL = True
        mock.REDIS_SSL_CERT_REQS = "required"
        mock.REDIS_SOCKET_TIMEOUT = 10.0
        mock.REDIS_SOCKET_CONNECT_TIMEOUT = 5.0
        mock.REDIS_RETRY_ON_TIMEOUT = True
        mock.REDIS_HEALTH_CHECK_INTERVAL = 30
        yield mock


@pytest.fixture
def redis_factory():
    """Create a fresh Redis factory instance for each test."""
    factory = RedisClientFactory()
    yield factory
    # No cleanup needed as we're mocking the actual connections


class TestSSLContextCreation:
    """Test SSL context creation."""

    def test_ssl_disabled(self, redis_factory, mock_settings):
        """Test that no SSL context is created when SSL is disabled."""
        mock_settings.REDIS_SSL = False

        ssl_context = redis_factory._create_ssl_context("localhost")

        assert ssl_context is None

    def test_ssl_cert_none(self, redis_factory, mock_settings):
        """Test SSL context with CERT_NONE (no validation)."""
        mock_settings.REDIS_SSL = True
        mock_settings.REDIS_SSL_CERT_REQS = "none"

        ssl_context = redis_factory._create_ssl_context("localhost")

        assert ssl_context is not None
        assert ssl_context.check_hostname is False
        assert ssl_context.verify_mode == ssl.CERT_NONE

    def test_ssl_cert_optional(self, redis_factory, mock_settings):
        """Test SSL context with CERT_OPTIONAL."""
        mock_settings.REDIS_SSL = True
        mock_settings.REDIS_SSL_CERT_REQS = "optional"

        ssl_context = redis_factory._create_ssl_context("localhost")

        assert ssl_context is not None
        assert ssl_context.check_hostname is False
        assert ssl_context.verify_mode == ssl.CERT_OPTIONAL

    @patch('app.core.redis_client_factory.CERTIFI_AVAILABLE', True)
    @patch('app.core.redis_client_factory.certifi')
    def test_ssl_cert_required_with_certifi(self, mock_certifi, redis_factory, mock_settings):
        """Test SSL context with CERT_REQUIRED and certifi."""
        mock_settings.REDIS_SSL = True
        mock_settings.REDIS_SSL_CERT_REQS = "required"
        mock_certifi.where.return_value = "/path/to/cacert.pem"

        ssl_context = redis_factory._create_ssl_context("test-redis.cloud")

        assert ssl_context is not None
        assert ssl_context.check_hostname is True
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        mock_certifi.where.assert_called_once()

    @patch('app.core.redis_client_factory.CERTIFI_AVAILABLE', False)
    def test_ssl_cert_required_without_certifi(self, redis_factory, mock_settings):
        """Test SSL context with CERT_REQUIRED but no certifi."""
        mock_settings.REDIS_SSL = True
        mock_settings.REDIS_SSL_CERT_REQS = "required"

        ssl_context = redis_factory._create_ssl_context("test-redis.cloud")

        assert ssl_context is not None
        assert ssl_context.check_hostname is True
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED


class TestURLParsing:
    """Test Redis URL parsing."""

    def test_parse_redis_url_basic(self, redis_factory, mock_settings):
        """Test parsing basic redis:// URL."""
        mock_settings.REDIS_URL = "redis://localhost:6379/0"

        params = redis_factory._parse_redis_url(mock_settings.REDIS_URL)

        assert params['scheme'] == 'redis'
        assert params['host'] == 'localhost'
        assert params['port'] == 6379
        assert params['db'] == 0

    def test_parse_redis_url_with_auth(self, redis_factory, mock_settings):
        """Test parsing redis:// URL with authentication."""
        mock_settings.REDIS_URL = "redis://user:pass@localhost:6379/1"

        params = redis_factory._parse_redis_url(mock_settings.REDIS_URL)

        assert params['scheme'] == 'redis'
        assert params['host'] == 'localhost'
        assert params['port'] == 6379
        assert params['username'] == 'user'
        assert params['password'] == 'pass'
        assert params['db'] == 1

    def test_parse_rediss_url_cloud(self, redis_factory, mock_settings):
        """Test parsing rediss:// URL (SSL)."""
        mock_settings.REDIS_URL = "rediss://default:password@redis-cloud.com:14149"

        params = redis_factory._parse_redis_url(mock_settings.REDIS_URL)

        assert params['scheme'] == 'rediss'
        assert params['host'] == 'redis-cloud.com'
        assert params['port'] == 14149
        assert params['username'] == 'default'
        assert params['password'] == 'password'


class TestSyncClient:
    """Test synchronous Redis client creation."""

    @patch('app.core.redis_client_factory.redis.ConnectionPool')
    @patch('app.core.redis_client_factory.redis.Redis')
    def test_get_sync_client_success(
        self, mock_redis_class, mock_pool_class, redis_factory, mock_settings
    ):
        """Test successful sync client creation."""
        # Mock pool and client
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis_class.return_value = mock_client

        # Create client
        client = redis_factory.get_sync_client()

        # Assertions
        assert client is not None
        mock_pool_class.assert_called_once()
        mock_redis_class.assert_called_once_with(connection_pool=mock_pool)
        mock_client.ping.assert_called_once()

    @patch('app.core.redis_client_factory.redis.ConnectionPool')
    @patch('app.core.redis_client_factory.redis.Redis')
    def test_get_sync_client_reuse_cached(
        self, mock_redis_class, mock_pool_class, redis_factory, mock_settings
    ):
        """Test that sync client is reused when cached."""
        # Mock pool and client
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis_class.return_value = mock_client

        # Create client twice
        client1 = redis_factory.get_sync_client()
        client2 = redis_factory.get_sync_client()

        # Should reuse cached client
        assert client1 is client2
        mock_pool_class.assert_called_once()
        mock_redis_class.assert_called_once()

    @patch('app.core.redis_client_factory.redis.ConnectionPool')
    @patch('app.core.redis_client_factory.redis.Redis')
    def test_get_sync_client_force_new(
        self, mock_redis_class, mock_pool_class, redis_factory, mock_settings
    ):
        """Test forcing creation of new sync client."""
        # Mock pool and client
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis_class.return_value = mock_client

        # Create clients with force_new
        client1 = redis_factory.get_sync_client()
        client2 = redis_factory.get_sync_client(force_new=True)

        # Should create new client
        assert mock_pool_class.call_count == 2
        assert mock_redis_class.call_count == 2

    @patch('app.core.redis_client_factory.redis.ConnectionPool')
    @patch('app.core.redis_client_factory.redis.Redis')
    def test_get_sync_client_connection_error(
        self, mock_redis_class, mock_pool_class, redis_factory, mock_settings
    ):
        """Test handling of connection errors."""
        from redis.exceptions import ConnectionError

        # Mock pool and client that fails to ping
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_client = Mock()
        mock_client.ping.side_effect = ConnectionError("Connection refused")
        mock_redis_class.return_value = mock_client

        # Should raise ConnectionError
        with pytest.raises(ConnectionError):
            redis_factory.get_sync_client()


class TestAsyncClient:
    """Test asynchronous Redis client creation."""

    @pytest.mark.asyncio
    @patch('app.core.redis_client_factory.redis_async.ConnectionPool')
    @patch('app.core.redis_client_factory.redis_async.Redis')
    async def test_get_async_client_success(
        self, mock_redis_class, mock_pool_class, redis_factory, mock_settings
    ):
        """Test successful async client creation."""
        # Mock pool and client
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_redis_class.return_value = mock_client

        # Create client
        client = await redis_factory.get_async_client()

        # Assertions
        assert client is not None
        mock_pool_class.assert_called_once()
        mock_redis_class.assert_called_once_with(connection_pool=mock_pool)
        mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.core.redis_client_factory.redis_async.ConnectionPool')
    @patch('app.core.redis_client_factory.redis_async.Redis')
    async def test_get_async_client_reuse_cached(
        self, mock_redis_class, mock_pool_class, redis_factory, mock_settings
    ):
        """Test that async client is reused when cached."""
        # Mock pool and client
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_redis_class.return_value = mock_client

        # Create client twice
        client1 = await redis_factory.get_async_client()
        client2 = await redis_factory.get_async_client()

        # Should reuse cached client
        assert client1 is client2
        mock_pool_class.assert_called_once()
        mock_redis_class.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.core.redis_client_factory.redis_async.ConnectionPool')
    @patch('app.core.redis_client_factory.redis_async.Redis')
    async def test_get_async_client_connection_error(
        self, mock_redis_class, mock_pool_class, redis_factory, mock_settings
    ):
        """Test handling of connection errors in async client."""
        from redis.exceptions import ConnectionError

        # Mock pool and client that fails to ping
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_redis_class.return_value = mock_client

        # Should raise ConnectionError
        with pytest.raises(ConnectionError):
            await redis_factory.get_async_client()


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    @patch('app.core.redis_client_factory.get_redis_factory')
    async def test_health_check_all_healthy(self, mock_get_factory, mock_settings):
        """Test health check when both clients are healthy."""
        # Mock factory with healthy clients
        mock_factory = Mock()

        mock_sync_client = Mock()
        mock_sync_client.ping.return_value = True
        mock_factory.get_sync_client.return_value = mock_sync_client

        mock_async_client = AsyncMock()
        mock_async_client.ping = AsyncMock(return_value=True)
        mock_factory.get_async_client = AsyncMock(return_value=mock_async_client)

        mock_get_factory.return_value = mock_factory

        # Run health check
        results = await redis_health_check()

        # Assertions
        assert results["status"] == "healthy"
        assert results["sync"]["connected"] is True
        assert results["async"]["connected"] is True
        assert results["sync"]["error"] is None
        assert results["async"]["error"] is None

    @pytest.mark.asyncio
    @patch('app.core.redis_client_factory.get_redis_factory')
    async def test_health_check_sync_only(self, mock_get_factory, mock_settings):
        """Test health check when only sync client works."""
        from redis.exceptions import ConnectionError

        # Mock factory with working sync, failing async
        mock_factory = Mock()

        mock_sync_client = Mock()
        mock_sync_client.ping.return_value = True
        mock_factory.get_sync_client.return_value = mock_sync_client

        mock_factory.get_async_client = AsyncMock(
            side_effect=ConnectionError("Async connection failed")
        )

        mock_get_factory.return_value = mock_factory

        # Run health check
        results = await redis_health_check()

        # Assertions
        assert results["status"] == "degraded"
        assert results["sync"]["connected"] is True
        assert results["async"]["connected"] is False
        assert results["async"]["error"] is not None

    @pytest.mark.asyncio
    @patch('app.core.redis_client_factory.get_redis_factory')
    async def test_health_check_all_failed(self, mock_get_factory, mock_settings):
        """Test health check when both clients fail."""
        from redis.exceptions import ConnectionError

        # Mock factory with both clients failing
        mock_factory = Mock()

        mock_factory.get_sync_client.side_effect = ConnectionError("Sync connection failed")
        mock_factory.get_async_client = AsyncMock(
            side_effect=ConnectionError("Async connection failed")
        )

        mock_get_factory.return_value = mock_factory

        # Run health check
        results = await redis_health_check()

        # Assertions
        assert results["status"] == "unhealthy"
        assert results["sync"]["connected"] is False
        assert results["async"]["connected"] is False


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_redis_client_raises_on_async_mode(self, mock_settings):
        """Test that get_redis_client raises error when async_mode=True."""
        with pytest.raises(ValueError, match="use 'await get_redis_client_async'"):
            get_redis_client(async_mode=True)

    @patch('app.core.redis_client_factory.get_redis_factory')
    def test_get_redis_client_sync(self, mock_get_factory, mock_settings):
        """Test get_redis_client returns sync client."""
        mock_factory = Mock()
        mock_client = Mock()
        mock_factory.get_sync_client.return_value = mock_client
        mock_get_factory.return_value = mock_factory

        client = get_redis_client()

        assert client is mock_client
        mock_factory.get_sync_client.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.core.redis_client_factory.get_redis_factory')
    async def test_get_redis_client_async(self, mock_get_factory, mock_settings):
        """Test get_redis_client_async returns async client."""
        mock_factory = Mock()
        mock_client = AsyncMock()
        mock_factory.get_async_client = AsyncMock(return_value=mock_client)
        mock_get_factory.return_value = mock_factory

        client = await get_redis_client_async()

        assert client is mock_client
        mock_factory.get_async_client.assert_called_once()


class TestCleanup:
    """Test cleanup functionality."""

    @pytest.mark.asyncio
    @patch('app.core.redis_client_factory._redis_factory')
    async def test_cleanup_redis_connections(self, mock_factory):
        """Test cleanup of all Redis connections."""
        mock_factory.close_all = AsyncMock()

        await cleanup_redis_connections()

        mock_factory.close_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_factory_close_all(self):
        """Test factory close_all method."""
        factory = RedisClientFactory()

        # Mock clients
        mock_sync = Mock()
        mock_async = AsyncMock()
        mock_async.aclose = AsyncMock()

        factory._sync_client = mock_sync
        factory._async_client = mock_async

        # Close all
        await factory.close_all()

        # Assertions
        mock_sync.close.assert_called_once()
        mock_async.aclose.assert_called_once()
        assert factory._sync_client is None
        assert factory._async_client is None
