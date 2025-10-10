"""
Comprehensive tests for AuthService.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.auth import AuthService
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenData
from app.utils.security import create_access_token, create_refresh_token


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_user_repository():
    """Mock user repository."""
    repository = Mock(spec=UserRepository)
    repository.get_by_email = Mock()
    repository.create = Mock()
    return repository


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def sample_user():
    """Sample user object."""
    user = User()
    user.id = 1
    user.email = "test@example.com"
    user.hashed_password = "$2b$12$test_hash"
    user.full_name = "Test User"
    user.role = "doctor"
    user.is_active = True
    return user


@pytest.fixture
def auth_service(mock_db, mock_user_repository, mock_redis):
    """AuthService instance with mocked dependencies."""
    return AuthService(mock_db, mock_user_repository, mock_redis)


class TestAuthServiceInit:
    """Test AuthService initialization."""

    def test_init_with_redis(self, mock_db, mock_user_repository, mock_redis):
        """Test initialization with Redis client."""
        service = AuthService(mock_db, mock_user_repository, mock_redis)
        assert service.db == mock_db
        assert service.repository == mock_user_repository
        assert service.redis == mock_redis
        assert service.max_attempts == 5
        assert service.max_ip_attempts == 10
        assert service.lockout_window == 300

    def test_init_without_redis(self, mock_db, mock_user_repository):
        """Test initialization without Redis client."""
        service = AuthService(mock_db, mock_user_repository, None)
        assert service.redis is None
        assert not service._fallback_enabled
        assert isinstance(service._blacklisted_tokens, set)
        assert isinstance(service._failed_attempts, dict)


class TestAuthenticateUser:
    """Test user authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_user_empty_credentials(self, auth_service):
        """Test authentication with empty credentials."""
        result = await auth_service.authenticate_user("", "password")
        assert result is None

        result = await auth_service.authenticate_user("test@example.com", "")
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_redis_unavailable(self, mock_db, mock_user_repository):
        """Test authentication when Redis is unavailable."""
        auth_service = AuthService(mock_db, mock_user_repository, None)

        with pytest.raises(RuntimeError, match="Authentication dependencies unavailable"):
            await auth_service.authenticate_user("test@example.com", "password")

    @pytest.mark.asyncio
    async def test_authenticate_user_rate_limited(self, auth_service, mock_redis):
        """Test authentication when rate limited."""
        mock_redis.get.return_value = "6"  # Exceeds max_attempts (5)

        result = await auth_service.authenticate_user("test@example.com", "password", "127.0.0.1")
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service, mock_user_repository, mock_redis):
        """Test authentication with non-existent user."""
        mock_user_repository.get_by_email.return_value = None
        mock_redis.get.return_value = None

        result = await auth_service.authenticate_user("test@example.com", "password", "127.0.0.1")
        assert result is None
        mock_user_repository.get_by_email.assert_called_once_with("test@example.com")

    @pytest.mark.asyncio
    @patch('app.services.auth.verify_password')
    async def test_authenticate_user_invalid_password(self, mock_verify, auth_service,
                                                     mock_user_repository, mock_redis, sample_user):
        """Test authentication with invalid password."""
        mock_user_repository.get_by_email.return_value = sample_user
        mock_verify.return_value = False
        mock_redis.get.return_value = None

        result = await auth_service.authenticate_user("test@example.com", "wrong_password", "127.0.0.1")
        assert result is None
        mock_verify.assert_called_once_with("wrong_password", sample_user.hashed_password)

    @pytest.mark.asyncio
    @patch('app.services.auth.verify_password')
    async def test_authenticate_user_inactive_user(self, mock_verify, auth_service,
                                                  mock_user_repository, mock_redis, sample_user):
        """Test authentication with inactive user."""
        sample_user.is_active = False
        mock_user_repository.get_by_email.return_value = sample_user
        mock_verify.return_value = True
        mock_redis.get.return_value = None

        result = await auth_service.authenticate_user("test@example.com", "password", "127.0.0.1")
        assert result is None

    @pytest.mark.asyncio
    @patch('app.services.auth.verify_password')
    @patch('app.services.auth.cache_user_data')
    async def test_authenticate_user_success(self, mock_cache, mock_verify, auth_service,
                                           mock_user_repository, mock_redis, sample_user):
        """Test successful authentication."""
        mock_user_repository.get_by_email.return_value = sample_user
        mock_verify.return_value = True
        mock_redis.get.return_value = None

        result = await auth_service.authenticate_user("test@example.com", "password", "127.0.0.1")
        assert result == sample_user
        mock_verify.assert_called_once_with("password", sample_user.hashed_password)
        mock_cache.assert_called_once_with(str(sample_user.id), sample_user, ttl=1800)


class TestTokenOperations:
    """Test token creation and verification."""

    def test_create_access_token(self, auth_service):
        """Test access token creation."""
        data = {"sub": "test@example.com"}
        token = auth_service.create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_empty_data(self, auth_service):
        """Test access token creation with empty data."""
        with pytest.raises(ValueError, match="Token data cannot be empty"):
            auth_service.create_access_token({})

    def test_create_refresh_token(self, auth_service):
        """Test refresh token creation."""
        data = {"sub": "test@example.com"}
        token = auth_service.create_refresh_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token_empty_data(self, auth_service):
        """Test refresh token creation with empty data."""
        with pytest.raises(ValueError, match="Token data cannot be empty"):
            auth_service.create_refresh_token({})

    @patch('app.services.auth.verify_jwt_token')
    def test_verify_token_valid(self, mock_verify, auth_service):
        """Test valid token verification."""
        token_data = TokenData(email="test@example.com")
        mock_verify.return_value = token_data

        result = auth_service.verify_token("valid_token")
        assert result == token_data
        mock_verify.assert_called_once_with("valid_token", "access")

    def test_verify_token_empty(self, auth_service):
        """Test empty token verification."""
        result = auth_service.verify_token("")
        assert result is None

        result = auth_service.verify_token(None)
        assert result is None

    def test_verify_token_blacklisted(self, auth_service):
        """Test blacklisted token verification."""
        token = "blacklisted_token"
        auth_service._blacklisted_tokens.add(token)

        result = auth_service.verify_token(token)
        assert result is None

    @patch('app.services.auth.verify_jwt_token')
    def test_verify_token_invalid(self, mock_verify, auth_service):
        """Test invalid token verification."""
        mock_verify.return_value = None

        result = auth_service.verify_token("invalid_token")
        assert result is None

    def test_blacklist_token(self, auth_service):
        """Test token blacklisting."""
        token = "Bearer test_token"
        auth_service.blacklist_token(token)
        assert "test_token" in auth_service._blacklisted_tokens

    def test_blacklist_empty_token(self, auth_service):
        """Test blacklisting empty token."""
        auth_service.blacklist_token("")
        auth_service.blacklist_token(None)
        # Should not raise any error


class TestUserCreation:
    """Test user creation."""

    def test_create_user_success(self, auth_service, mock_user_repository, sample_user):
        """Test successful user creation."""
        mock_user_repository.get_by_email.return_value = None
        mock_user_repository.create.return_value = sample_user

        with patch('app.services.auth.get_password_hash') as mock_hash, \
             patch('app.services.auth.cache_user_data') as mock_cache:
            mock_hash.return_value = "hashed_password"

            result = auth_service.create_user("test@example.com", "password123", "Test User")

            assert result == sample_user
            mock_hash.assert_called_once_with("password123")
            mock_cache.assert_called_once_with(str(sample_user.id), sample_user, ttl=1800)

    def test_create_user_empty_email(self, auth_service):
        """Test user creation with empty email."""
        with pytest.raises(ValueError, match="Email cannot be empty"):
            auth_service.create_user("", "password123", "Test User")

    def test_create_user_short_password(self, auth_service):
        """Test user creation with short password."""
        with pytest.raises(ValueError, match="Password must be at least 8 characters long"):
            auth_service.create_user("test@example.com", "short", "Test User")

    def test_create_user_empty_name(self, auth_service):
        """Test user creation with empty name."""
        with pytest.raises(ValueError, match="Full name cannot be empty"):
            auth_service.create_user("test@example.com", "password123", "")

    def test_create_user_existing_email(self, auth_service, mock_user_repository, sample_user):
        """Test user creation with existing email."""
        mock_user_repository.get_by_email.return_value = sample_user

        with pytest.raises(ValueError, match="User with this email already exists"):
            auth_service.create_user("test@example.com", "password123", "Test User")


class TestGetCurrentUser:
    """Test getting current user from token."""

    @patch('app.services.auth.TokenData')
    def test_get_current_user_success(self, mock_token_data, auth_service, sample_user):
        """Test successful current user retrieval."""
        token_data = TokenData(email="test@example.com")

        with patch.object(auth_service, 'verify_token') as mock_verify, \
             patch.object(auth_service, '_get_user_from_token_data') as mock_get_user:
            mock_verify.return_value = token_data
            mock_get_user.return_value = sample_user

            result = auth_service.get_current_user("valid_token")
            assert result == sample_user

    def test_get_current_user_invalid_token(self, auth_service):
        """Test current user retrieval with invalid token."""
        with patch.object(auth_service, 'verify_token') as mock_verify:
            mock_verify.return_value = None

            result = auth_service.get_current_user("invalid_token")
            assert result is None


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_unavailable(self, mock_db, mock_user_repository):
        """Test rate limiting when Redis is unavailable."""
        auth_service = AuthService(mock_db, mock_user_repository, None)

        result = await auth_service._is_rate_limited("test@example.com", "127.0.0.1")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_email_exceeded(self, auth_service, mock_redis):
        """Test rate limiting when email attempts exceeded."""
        mock_redis.get.return_value = "6"  # Exceeds max_attempts (5)

        result = await auth_service._is_rate_limited_redis("test@example.com", "127.0.0.1")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_ip_exceeded(self, auth_service, mock_redis):
        """Test rate limiting when IP attempts exceeded."""
        def mock_get_side_effect(key):
            if "email" in key:
                return "3"  # Below email limit
            elif "ip" in key:
                return "11"  # Exceeds IP limit (10)
            return None

        mock_redis.get.side_effect = mock_get_side_effect

        result = await auth_service._is_rate_limited_redis("test@example.com", "127.0.0.1")
        assert result is True

    @pytest.mark.asyncio
    async def test_record_failed_attempt_redis(self, auth_service, mock_redis):
        """Test recording failed attempt in Redis."""
        await auth_service._record_failed_attempt_redis("test@example.com", "127.0.0.1")

        # Check email key was incremented
        mock_redis.incr.assert_any_call("rate_limit:email:test@example.com")
        # Check IP key was incremented
        mock_redis.incr.assert_any_call("rate_limit:ip:127.0.0.1")

    @pytest.mark.asyncio
    async def test_clear_failed_attempts(self, auth_service, mock_redis):
        """Test clearing failed attempts."""
        await auth_service._clear_failed_attempts("test@example.com")

        mock_redis.delete.assert_called_once_with("rate_limit:email:test@example.com")

    @pytest.mark.asyncio
    async def test_redis_is_connected_ping(self, auth_service, mock_redis):
        """Test Redis connection check with ping method."""
        mock_redis.ping.return_value = True

        result = await auth_service._redis_is_connected()
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_is_connected_get(self, auth_service):
        """Test Redis connection check with get method."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock()
        del mock_redis.ping  # Remove ping method
        auth_service.redis = mock_redis

        result = await auth_service._redis_is_connected()
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_is_connected_error(self, auth_service, mock_redis):
        """Test Redis connection check with error."""
        mock_redis.ping.side_effect = Exception("Connection failed")

        result = await auth_service._redis_is_connected()
        assert result is False


class TestMemoryFallback:
    """Test in-memory fallback functionality."""

    def test_is_rate_limited_memory(self, auth_service):
        """Test in-memory rate limiting."""
        # Simulate max attempts reached
        email = "test@example.com"
        auth_service._failed_attempts[email] = {
            'count': 5,
            'last_attempt': datetime.utcnow(),
            'ip_attempts': {'127.0.0.1': 3}
        }

        result = auth_service._is_rate_limited_memory(email, "127.0.0.1")
        assert result is True

    def test_is_rate_limited_memory_expired(self, auth_service):
        """Test in-memory rate limiting with expired window."""
        email = "test@example.com"
        old_time = datetime.utcnow() - timedelta(seconds=400)  # Beyond lockout window
        auth_service._failed_attempts[email] = {
            'count': 5,
            'last_attempt': old_time,
            'ip_attempts': {'127.0.0.1': 3}
        }

        result = auth_service._is_rate_limited_memory(email, "127.0.0.1")
        assert result is False

    def test_record_failed_attempt_memory(self, auth_service):
        """Test recording failed attempt in memory."""
        email = "test@example.com"
        ip = "127.0.0.1"

        auth_service._record_failed_attempt_memory(email, ip)

        assert auth_service._failed_attempts[email]['count'] == 1
        assert auth_service._failed_attempts[email]['ip_attempts'][ip] == 1
        assert auth_service._failed_attempts[email]['last_attempt'] is not None

    def test_record_failed_attempt_memory_reset(self, auth_service):
        """Test recording failed attempt in memory with reset."""
        email = "test@example.com"
        old_time = datetime.utcnow() - timedelta(seconds=400)  # Beyond lockout window
        auth_service._failed_attempts[email] = {
            'count': 3,
            'last_attempt': old_time,
            'ip_attempts': {'127.0.0.1': 2}
        }

        auth_service._record_failed_attempt_memory(email, "127.0.0.1")

        # Should reset and start fresh
        assert auth_service._failed_attempts[email]['count'] == 1
        assert auth_service._failed_attempts[email]['ip_attempts']['127.0.0.1'] == 1