"""
Comprehensive Unit Tests for RedisManager

Tests Redis connection management, pooling, SSL/TLS configuration, and lifecycle.
"""
import pytest
import ssl
from unittest.mock import Mock, AsyncMock, patch
from redis.exceptions import ConnectionError


class TestRedisManagerInitialization:
    """Test RedisManager initialization and configuration."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.REDIS_URL = "redis://localhost:6379/0"
        settings.REDIS_ENABLE_SSL = False
        settings.REDIS_SSL_CERT_REQS = "required"
        settings.REDIS_ENABLE_DB_ISOLATION = True
        settings.REDIS_ENABLE_DECODE_RESPONSES = True
        settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        settings.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        settings.REDIS_MAX_RETRY_ATTEMPTS = 3
        settings.REDIS_POOL_MAX_CONNECTIONS = 20
        settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        settings.REDIS_ENABLE_HEALTH_CHECK = True
        settings.REDIS_SSL_SESSION_REUSE = True
        settings.REDIS_SSL_CONNECTION_POOL_WARMUP = True
        settings.REDIS_SSL_WARMUP_CONNECTIONS = 5
        return settings

    @patch('app.core.redis_manager.manager.settings')
    def test_initialization_default(self, mock_settings_module, mock_settings):
        """Test default initialization."""
        mock_settings_module.REDIS_URL = "redis://localhost:6379/0"
        mock_settings_module.REDIS_ENABLE_SSL = False
        mock_settings_module.REDIS_ENABLE_DB_ISOLATION = True
        mock_settings_module.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings_module.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings_module.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings_module.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings_module.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings_module.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings_module.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings_module.REDIS_ENABLE_HEALTH_CHECK = True
        mock_settings_module.REDIS_SSL_SESSION_REUSE = True
        mock_settings_module.REDIS_SSL_CONNECTION_POOL_WARMUP = True
        mock_settings_module.REDIS_SSL_WARMUP_CONNECTIONS = 5

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()

        assert manager.redis_url == "redis://localhost:6379/0"
        assert manager.decode_responses is True
        assert manager.socket_timeout == 5.0
        assert manager.socket_connect_timeout == 2.0
        assert manager.max_connections == 20
        assert manager._async_client is None
        assert manager._sync_client is None

    @patch('app.core.redis_manager.manager.settings')
    def test_initialization_with_db_isolation(self, mock_settings_module, mock_settings):
        """Test initialization with DB isolation."""
        mock_settings_module.REDIS_URL = "redis://localhost:6379/0"
        mock_settings_module.REDIS_ENABLE_SSL = False
        mock_settings_module.REDIS_ENABLE_DB_ISOLATION = True
        mock_settings_module.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings_module.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings_module.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings_module.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings_module.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings_module.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings_module.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings_module.REDIS_ENABLE_HEALTH_CHECK = True
        mock_settings_module.REDIS_SSL_SESSION_REUSE = True
        mock_settings_module.REDIS_SSL_CONNECTION_POOL_WARMUP = True
        mock_settings_module.REDIS_SSL_WARMUP_CONNECTIONS = 5

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager(db_number=2)

        assert "/2" in manager.redis_url
        assert manager.db_number == 2

    @patch('app.core.redis_manager.manager.settings')
    def test_initialization_without_db_isolation(self, mock_settings_module, mock_settings):
        """Test initialization without DB isolation."""
        mock_settings_module.REDIS_URL = "redis://localhost:6379/0"
        mock_settings_module.REDIS_ENABLE_SSL = False
        mock_settings_module.REDIS_ENABLE_DB_ISOLATION = False
        mock_settings_module.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings_module.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings_module.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings_module.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings_module.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings_module.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings_module.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings_module.REDIS_ENABLE_HEALTH_CHECK = True
        mock_settings_module.REDIS_SSL_SESSION_REUSE = True
        mock_settings_module.REDIS_SSL_CONNECTION_POOL_WARMUP = True
        mock_settings_module.REDIS_SSL_WARMUP_CONNECTIONS = 5

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager(db_number=2)

        # DB isolation disabled, so DB number should not be in URL
        assert manager.db_number == 2
        assert manager.redis_url == "redis://localhost:6379/0"


class TestSSLConfiguration:
    """Test SSL/TLS configuration."""

    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.REDIS_CA_CERT_PATH')
    def test_create_ssl_context_with_verification(self, mock_cert_path, mock_settings):
        """Test SSL context creation with certificate verification."""
        mock_settings.REDIS_SSL_CERT_REQS = "required"
        mock_cert_path.exists.return_value = True

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        ssl_context = manager._create_ssl_context()

        assert ssl_context is not None
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname is True
        assert ssl_context.minimum_version == ssl.TLSVersion.TLSv1_2

    @patch('app.core.redis_manager.manager.settings')
    def test_create_ssl_context_without_verification(self, mock_settings):
        """Test SSL context creation without certificate verification."""
        mock_settings.REDIS_SSL_CERT_REQS = "none"

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        ssl_context = manager._create_ssl_context()

        assert ssl_context is not None
        assert ssl_context.verify_mode == ssl.CERT_NONE
        assert ssl_context.check_hostname is False
        assert ssl_context.minimum_version == ssl.TLSVersion.TLSv1_2

    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.REDIS_CA_CERT_PATH')
    def test_create_ssl_context_fallback_to_system_certs(self, mock_cert_path, mock_settings):
        """Test SSL context creation falls back to system certs when CA cert not found."""
        mock_settings.REDIS_SSL_CERT_REQS = "required"
        mock_cert_path.exists.return_value = False

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        ssl_context = manager._create_ssl_context()

        assert ssl_context is not None
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED


class TestAsyncClientManagement:
    """Test async Redis client management."""

    @pytest.mark.asyncio
    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.redis_async.ConnectionPool')
    @patch('app.core.redis_manager.manager.redis_async.Redis')
    async def test_get_async_client_creates_client(self, mock_redis_class, mock_pool_class, mock_settings):
        """Test getting async client creates it if not exists."""
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_ENABLE_SSL = False
        mock_settings.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings.REDIS_ENABLE_HEALTH_CHECK = True
        mock_settings.REDIS_SSL_SESSION_REUSE = True
        mock_settings.REDIS_SSL_CONNECTION_POOL_WARMUP = False

        # Mock pool and client
        mock_pool = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_redis_class.return_value = mock_client

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        client = await manager.get_async_client()

        assert client is not None
        mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.redis_async.ConnectionPool')
    @patch('app.core.redis_manager.manager.redis_async.Redis')
    async def test_get_async_client_reuses_existing(self, mock_redis_class, mock_pool_class, mock_settings):
        """Test getting async client reuses existing instance."""
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_ENABLE_SSL = False
        mock_settings.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings.REDIS_ENABLE_HEALTH_CHECK = True
        mock_settings.REDIS_SSL_SESSION_REUSE = True
        mock_settings.REDIS_SSL_CONNECTION_POOL_WARMUP = False

        mock_pool = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_redis_class.return_value = mock_client

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        client1 = await manager.get_async_client()
        client2 = await manager.get_async_client()

        assert client1 is client2
        # Ping should only be called once during creation
        assert mock_client.ping.call_count == 1

    @pytest.mark.asyncio
    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.redis_async.ConnectionPool')
    @patch('app.core.redis_manager.manager.redis_async.Redis')
    async def test_async_client_with_ssl_enabled(self, mock_redis_class, mock_pool_class, mock_settings):
        """Test async client creation with SSL enabled."""
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_ENABLE_SSL = True
        mock_settings.REDIS_SSL_CERT_REQS = "none"
        mock_settings.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings.REDIS_ENABLE_HEALTH_CHECK = True
        mock_settings.REDIS_SSL_SESSION_REUSE = True
        mock_settings.REDIS_SSL_CONNECTION_POOL_WARMUP = False

        mock_pool = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_redis_class.return_value = mock_client

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        client = await manager.get_async_client()

        # Verify SSL context was passed
        call_kwargs = mock_pool_class.from_url.call_args[1]
        assert "ssl" in call_kwargs
        assert isinstance(call_kwargs["ssl"], ssl.SSLContext)

        # Verify URL was converted to rediss://
        call_url = mock_pool_class.from_url.call_args[0][0]
        assert call_url.startswith("rediss://")


class TestSyncClientManagement:
    """Test sync Redis client management."""

    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.redis_sync.ConnectionPool')
    @patch('app.core.redis_manager.manager.redis_sync.Redis')
    def test_get_sync_client_creates_client(self, mock_redis_class, mock_pool_class, mock_settings):
        """Test getting sync client creates it if not exists."""
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_ENABLE_SSL = False
        mock_settings.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings.REDIS_ENABLE_HEALTH_CHECK = True

        mock_pool = Mock()
        mock_pool_class.from_url.return_value = mock_pool

        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis_class.return_value = mock_client

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        client = manager.get_sync_client()

        assert client is not None
        mock_client.ping.assert_called_once()

    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.redis_sync.ConnectionPool')
    @patch('app.core.redis_manager.manager.redis_sync.Redis')
    def test_sync_client_with_ssl_enabled(self, mock_redis_class, mock_pool_class, mock_settings):
        """Test sync client creation with SSL enabled."""
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_ENABLE_SSL = True
        mock_settings.REDIS_SSL_CERT_REQS = "none"
        mock_settings.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings.REDIS_ENABLE_HEALTH_CHECK = True

        mock_pool = Mock()
        mock_pool_class.from_url.return_value = mock_pool

        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis_class.return_value = mock_client

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        client = manager.get_sync_client()

        # Verify SSL configuration was passed
        call_kwargs = mock_pool_class.from_url.call_args[1]
        assert "ssl_cert_reqs" in call_kwargs


class TestConnectionPoolWarmup:
    """Test connection pool warmup functionality."""

    @pytest.mark.asyncio
    @patch('app.core.redis_manager.manager.settings')
    async def test_warmup_connection_pool_async(self, mock_settings):
        """Test async connection pool warmup."""
        mock_settings.REDIS_SSL_CONNECTION_POOL_WARMUP = True
        mock_settings.REDIS_SSL_WARMUP_CONNECTIONS = 3
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()

        # Create mock async client
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        manager._async_client = mock_client

        # Run warmup
        await manager._warmup_connection_pool_async()

        # Verify PING was called the expected number of times
        assert mock_client.ping.call_count == 3

    @pytest.mark.asyncio
    @patch('app.core.redis_manager.manager.settings')
    async def test_warmup_handles_errors_gracefully(self, mock_settings):
        """Test warmup handles errors without failing."""
        mock_settings.REDIS_SSL_CONNECTION_POOL_WARMUP = True
        mock_settings.REDIS_SSL_WARMUP_CONNECTIONS = 3

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()

        # Create mock async client that fails
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=Exception("Connection failed"))
        manager._async_client = mock_client

        # Warmup should not raise exception
        await manager._warmup_connection_pool_async()


class TestConnectionCleanup:
    """Test connection cleanup."""

    @pytest.mark.asyncio
    @patch('app.core.redis_manager.manager.settings')
    async def test_close_async_connections(self, mock_settings):
        """Test closing async connections."""
        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()

        # Create mock async client and pool
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        manager._async_client = mock_client

        mock_pool = AsyncMock()
        mock_pool.aclose = AsyncMock()
        manager._async_pool = mock_pool

        await manager.close_async()

        mock_client.aclose.assert_called_once()
        mock_pool.aclose.assert_called_once()
        assert manager._async_client is None
        assert manager._async_pool is None

    @patch('app.core.redis_manager.manager.settings')
    def test_close_sync_connections(self, mock_settings):
        """Test closing sync connections."""
        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()

        # Create mock sync client and pool
        mock_client = Mock()
        mock_client.close = Mock()
        manager._sync_client = mock_client

        mock_pool = Mock()
        mock_pool.disconnect = Mock()
        manager._sync_pool = mock_pool

        manager.close_sync()

        mock_client.close.assert_called_once()
        mock_pool.disconnect.assert_called_once()
        assert manager._sync_client is None
        assert manager._sync_pool is None


class TestPoolStatistics:
    """Test connection pool statistics."""

    @pytest.mark.asyncio
    @patch('app.core.redis_manager.manager.settings')
    async def test_get_async_pool_stats(self, mock_settings):
        """Test getting async pool statistics."""
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        manager._async_pool = AsyncMock()

        stats = await manager.get_pool_stats_async()

        assert stats["status"] == "healthy"
        assert stats["max_connections"] == 20
        assert stats["pool_type"] == "async"

    @patch('app.core.redis_manager.manager.settings')
    def test_get_sync_pool_stats(self, mock_settings):
        """Test getting sync pool statistics."""
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()
        manager._sync_pool = Mock()

        stats = manager.get_pool_stats_sync()

        assert stats["status"] == "healthy"
        assert stats["max_connections"] == 20
        assert stats["pool_type"] == "sync"


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.redis_async.ConnectionPool')
    @patch('app.core.redis_manager.manager.redis_async.Redis')
    async def test_async_client_creation_failure(self, mock_redis_class, mock_pool_class, mock_settings):
        """Test async client creation handles failures."""
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_ENABLE_SSL = False
        mock_settings.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings.REDIS_ENABLE_HEALTH_CHECK = True
        mock_settings.REDIS_SSL_CONNECTION_POOL_WARMUP = False

        # Make ping fail
        mock_pool = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("Connection failed"))
        mock_redis_class.return_value = mock_client

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()

        with pytest.raises(ConnectionError):
            await manager.get_async_client()

    @patch('app.core.redis_manager.manager.settings')
    @patch('app.core.redis_manager.manager.redis_sync.ConnectionPool')
    @patch('app.core.redis_manager.manager.redis_sync.Redis')
    def test_sync_client_creation_failure(self, mock_redis_class, mock_pool_class, mock_settings):
        """Test sync client creation handles failures."""
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REDIS_ENABLE_SSL = False
        mock_settings.REDIS_ENABLE_DECODE_RESPONSES = True
        mock_settings.REDIS_SOCKET_TIMEOUT_SECONDS = 5.0
        mock_settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 2.0
        mock_settings.REDIS_ENABLE_RETRY_ON_TIMEOUT = True
        mock_settings.REDIS_MAX_RETRY_ATTEMPTS = 3
        mock_settings.REDIS_POOL_MAX_CONNECTIONS = 20
        mock_settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
        mock_settings.REDIS_ENABLE_HEALTH_CHECK = True

        # Make ping fail
        mock_pool = Mock()
        mock_pool_class.from_url.return_value = mock_pool

        mock_client = Mock()
        mock_client.ping.side_effect = ConnectionError("Connection failed")
        mock_redis_class.return_value = mock_client

        from app.core.redis_manager.manager import RedisManager

        manager = RedisManager()

        with pytest.raises(ConnectionError):
            manager.get_sync_client()
