"""
Comprehensive unit tests for Auth Service

Tests authentication, token management, rate limiting, and all security features
with focus on achieving 90%+ code coverage.
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any, Set
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

# Import the service and dependencies - adjust path based on actual structure
try:
    from app.services.auth import AuthService
    from app.repositories.user import UserRepository
    from app.models.user import User
    from app.schemas.auth import TokenData, UserResponse
except ImportError:
    # Fallback for different project structures
    try:
        from services.auth import AuthService
        from repositories.user import UserRepository
        from models.user import User
        from schemas.auth import TokenData, UserResponse
    except ImportError:
        # Fallback when schemas don't exist - create mock classes
        from services.auth import AuthService
        from repositories.user import UserRepository
        from models.user import User

        class TokenData:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class UserResponse:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = Mock(spec=Session)
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.query = Mock()
    return session


@pytest.fixture
def mock_user_repository():
    """Mock user repository."""
    repo = Mock(spec=UserRepository)
    return repo


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with async support."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def auth_service(mock_db_session, mock_user_repository, mock_redis_client):
    """Auth service instance with mocked dependencies."""
    service = AuthService(
        db=mock_db_session,
        user_repository=mock_user_repository,
        redis_client=mock_redis_client
    )
    return service


@pytest.fixture
def sample_user():
    """Sample user for testing."""
    user = Mock(spec=User)
    user.id = "test-user-id"
    user.email = "test@example.com"
    user.hashed_password = "$2b$12$hash"
    user.full_name = "Test User"
    user.role = "doctor"
    user.is_active = True
    return user


@pytest.fixture
def sample_token_data():
    """Sample token data for testing."""
    return TokenData(
        email="test@example.com",
        exp=1234567890,
        token_type="access"
    )


class TestAuthServiceInitialization:
    """Test auth service initialization and configuration."""

    def test_service_initialization(self, mock_db_session, mock_user_repository, mock_redis_client):
        """Test service initialization with dependencies."""
        service = AuthService(mock_db_session, mock_user_repository, mock_redis_client)

        assert service.db == mock_db_session
        assert service.repository == mock_user_repository
        assert service.redis == mock_redis_client
        assert service.max_attempts == 5
        assert service.max_ip_attempts == 10
        assert service.lockout_window == 300

    def test_service_initialization_without_redis(self, mock_db_session, mock_user_repository):
        """Test service initialization without Redis client."""
        service = AuthService(mock_db_session, mock_user_repository, None)

        assert service.redis is None
        assert service._fallback_enabled is False

    def test_service_initialization_in_memory_structures(self, auth_service):
        """Test in-memory structures are properly initialized."""
        assert isinstance(auth_service._blacklisted_tokens, set)
        assert isinstance(auth_service._failed_attempts, defaultdict)
        assert len(auth_service._blacklisted_tokens) == 0


class TestAuthServiceUserAuthentication:
    """Test user authentication functionality."""

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service, mock_user_repository, sample_user):
        """Test successful user authentication."""
        # Arrange
        mock_user_repository.get_by_email.return_value = sample_user
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value=None)  # No rate limiting

        with patch('app.services.auth.verify_password', return_value=True), \
             patch('app.services.auth.cache_user_data') as mock_cache:

            # Act
            result = await auth_service.authenticate_user("test@example.com", "password123")

            # Assert
            assert result == sample_user
            mock_user_repository.get_by_email.assert_called_once_with("test@example.com")
            mock_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_empty_credentials(self, auth_service):
        """Test authentication with empty credentials."""
        # Act & Assert
        result = await auth_service.authenticate_user("", "password")
        assert result is None

        result = await auth_service.authenticate_user("email", "")
        assert result is None

        result = await auth_service.authenticate_user(None, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_redis_unavailable(self, auth_service):
        """Test authentication when Redis is unavailable."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=False)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Authentication dependencies unavailable: Redis"):
            await auth_service.authenticate_user("test@example.com", "password123")

    @pytest.mark.asyncio
    async def test_authenticate_user_rate_limited(self, auth_service):
        """Test authentication blocked by rate limiting."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value="10")  # Exceeded attempts

        # Act
        result = await auth_service.authenticate_user("test@example.com", "password123", "192.168.1.1")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service, mock_user_repository):
        """Test authentication with non-existent user."""
        # Arrange
        mock_user_repository.get_by_email.return_value = None
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value=None)

        # Act
        result = await auth_service.authenticate_user("nonexistent@example.com", "password123")

        # Assert
        assert result is None
        mock_user_repository.get_by_email.assert_called_once_with("nonexistent@example.com")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, auth_service, mock_user_repository, sample_user):
        """Test authentication with wrong password."""
        # Arrange
        mock_user_repository.get_by_email.return_value = sample_user
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value=None)

        with patch('app.services.auth.verify_password', return_value=False):
            # Act
            result = await auth_service.authenticate_user("test@example.com", "wrongpassword")

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self, auth_service, mock_user_repository, sample_user):
        """Test authentication with inactive user."""
        # Arrange
        sample_user.is_active = False
        mock_user_repository.get_by_email.return_value = sample_user
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value=None)

        with patch('app.services.auth.verify_password', return_value=True):
            # Act
            result = await auth_service.authenticate_user("test@example.com", "password123")

            # Assert
            assert result is None


class TestAuthServiceTokenManagement:
    """Test token creation and verification."""

    def test_create_access_token_success(self, auth_service):
        """Test successful access token creation."""
        # Arrange
        data = {"email": "test@example.com", "sub": "user-id"}

        with patch('app.services.auth.create_access_token', return_value="mock-token") as mock_create:
            # Act
            result = auth_service.create_access_token(data)

            # Assert
            assert result == "mock-token"
            mock_create.assert_called_once_with(data, None)

    def test_create_access_token_with_expiry(self, auth_service):
        """Test access token creation with custom expiry."""
        # Arrange
        data = {"email": "test@example.com"}
        expires_delta = timedelta(hours=2)

        with patch('app.services.auth.create_access_token', return_value="mock-token") as mock_create:
            # Act
            result = auth_service.create_access_token(data, expires_delta)

            # Assert
            assert result == "mock-token"
            mock_create.assert_called_once_with(data, expires_delta)

    def test_create_access_token_empty_data(self, auth_service):
        """Test access token creation with empty data."""
        # Act & Assert
        with pytest.raises(ValueError, match="Token data cannot be empty"):
            auth_service.create_access_token({})

        with pytest.raises(ValueError, match="Token data cannot be empty"):
            auth_service.create_access_token(None)

    def test_create_refresh_token_success(self, auth_service):
        """Test successful refresh token creation."""
        # Arrange
        data = {"email": "test@example.com", "sub": "user-id"}

        with patch('app.services.auth.create_refresh_token', return_value="mock-refresh-token") as mock_create:
            # Act
            result = auth_service.create_refresh_token(data)

            # Assert
            assert result == "mock-refresh-token"
            mock_create.assert_called_once_with(data)

    def test_create_refresh_token_empty_data(self, auth_service):
        """Test refresh token creation with empty data."""
        # Act & Assert
        with pytest.raises(ValueError, match="Token data cannot be empty"):
            auth_service.create_refresh_token({})

    def test_verify_token_success(self, auth_service, sample_token_data):
        """Test successful token verification."""
        # Arrange
        token = "valid-token"

        with patch('app.services.auth.verify_jwt_token', return_value=sample_token_data) as mock_verify:
            # Act
            result = auth_service.verify_token(token)

            # Assert
            assert result == sample_token_data
            mock_verify.assert_called_once_with(token, "access")

    def test_verify_token_with_bearer_prefix(self, auth_service, sample_token_data):
        """Test token verification with Bearer prefix."""
        # Arrange
        token = "Bearer valid-token"

        with patch('app.services.auth.verify_jwt_token', return_value=sample_token_data) as mock_verify:
            # Act
            result = auth_service.verify_token(token)

            # Assert
            assert result == sample_token_data
            mock_verify.assert_called_once_with("valid-token", "access")

    def test_verify_token_blacklisted(self, auth_service):
        """Test verification of blacklisted token."""
        # Arrange
        token = "blacklisted-token"
        auth_service._blacklisted_tokens.add(token)

        # Act
        result = auth_service.verify_token(token)

        # Assert
        assert result is None

    def test_verify_token_invalid_format(self, auth_service):
        """Test verification of invalid token formats."""
        # Act & Assert
        assert auth_service.verify_token("") is None
        assert auth_service.verify_token("   ") is None
        assert auth_service.verify_token(None) is None
        assert auth_service.verify_token(123) is None

    def test_verify_token_verification_fails(self, auth_service):
        """Test token verification when verification fails."""
        # Arrange
        token = "invalid-token"

        with patch('app.services.auth.verify_jwt_token', return_value=None):
            # Act
            result = auth_service.verify_token(token)

            # Assert
            assert result is None

    def test_verify_token_exception(self, auth_service):
        """Test token verification with exception."""
        # Arrange
        token = "error-token"

        with patch('app.services.auth.verify_jwt_token', side_effect=Exception("Verification error")):
            # Act
            result = auth_service.verify_token(token)

            # Assert
            assert result is None

    def test_blacklist_token(self, auth_service):
        """Test token blacklisting."""
        # Arrange
        token = "token-to-blacklist"

        # Act
        auth_service.blacklist_token(token)

        # Assert
        assert token in auth_service._blacklisted_tokens

    def test_blacklist_token_with_bearer_prefix(self, auth_service):
        """Test blacklisting token with Bearer prefix."""
        # Arrange
        token = "Bearer token-to-blacklist"

        # Act
        auth_service.blacklist_token(token)

        # Assert
        assert "token-to-blacklist" in auth_service._blacklisted_tokens

    def test_blacklist_empty_token(self, auth_service):
        """Test blacklisting empty token."""
        # Act
        auth_service.blacklist_token("")
        auth_service.blacklist_token(None)

        # Assert
        assert len(auth_service._blacklisted_tokens) == 0


class TestAuthServiceUserManagement:
    """Test user management functionality."""

    def test_get_current_user_success(self, auth_service, sample_user, sample_token_data):
        """Test successful current user retrieval."""
        # Arrange
        token = "valid-token"

        with patch.object(auth_service, 'verify_token', return_value=sample_token_data), \
             patch.object(auth_service, '_get_user_from_token_data', return_value=sample_user):

            # Act
            result = auth_service.get_current_user(token)

            # Assert
            assert result == sample_user

    def test_get_current_user_invalid_token(self, auth_service):
        """Test current user retrieval with invalid token."""
        # Arrange
        token = "invalid-token"

        with patch.object(auth_service, 'verify_token', return_value=None):
            # Act
            result = auth_service.get_current_user(token)

            # Assert
            assert result is None

    def test_get_user_from_token_data_success(self, auth_service, mock_user_repository, sample_user, sample_token_data):
        """Test user retrieval from token data."""
        # Arrange
        mock_user_repository.get_by_email.return_value = sample_user

        # Act
        result = auth_service._get_user_from_token_data(sample_token_data)

        # Assert
        assert result == sample_user
        mock_user_repository.get_by_email.assert_called_once_with("test@example.com")

    def test_get_user_from_token_data_user_not_found(self, auth_service, mock_user_repository, sample_token_data):
        """Test user retrieval when user not found."""
        # Arrange
        mock_user_repository.get_by_email.return_value = None

        # Act
        result = auth_service._get_user_from_token_data(sample_token_data)

        # Assert
        assert result is None

    def test_get_user_from_token_data_inactive_user(self, auth_service, mock_user_repository, sample_user, sample_token_data):
        """Test user retrieval with inactive user."""
        # Arrange
        sample_user.is_active = False
        mock_user_repository.get_by_email.return_value = sample_user

        # Act
        result = auth_service._get_user_from_token_data(sample_token_data)

        # Assert
        assert result is None

    def test_create_user_success(self, auth_service, mock_user_repository, sample_user):
        """Test successful user creation."""
        # Arrange
        mock_user_repository.get_by_email.return_value = None  # User doesn't exist
        mock_user_repository.create.return_value = sample_user

        with patch('app.services.auth.get_password_hash', return_value="hashed_password"), \
             patch('app.services.auth.cache_user_data') as mock_cache:

            # Act
            result = auth_service.create_user("test@example.com", "password123", "Test User", "doctor")

            # Assert
            assert result == sample_user
            mock_user_repository.create.assert_called_once()
            mock_cache.assert_called_once()

    def test_create_user_validation_errors(self, auth_service):
        """Test user creation with validation errors."""
        # Act & Assert
        with pytest.raises(ValueError, match="Email cannot be empty"):
            auth_service.create_user("", "password123", "Test User")

        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            auth_service.create_user("test@example.com", "short", "Test User")

        with pytest.raises(ValueError, match="Full name cannot be empty"):
            auth_service.create_user("test@example.com", "password123", "")

    def test_create_user_already_exists(self, auth_service, mock_user_repository, sample_user):
        """Test user creation when user already exists."""
        # Arrange
        mock_user_repository.get_by_email.return_value = sample_user

        # Act & Assert
        with pytest.raises(ValueError, match="User with this email already exists"):
            auth_service.create_user("test@example.com", "password123", "Test User")


class TestAuthServiceRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_success(self, auth_service):
        """Test rate limiting check with Redis available."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value=None)  # No attempts recorded

        # Act
        result = await auth_service._is_rate_limited("test@example.com", "192.168.1.1")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_email_exceeded(self, auth_service):
        """Test rate limiting when email attempts exceeded."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value="6")  # Exceeded max_attempts (5)

        # Act
        result = await auth_service._is_rate_limited("test@example.com", "192.168.1.1")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_ip_exceeded(self, auth_service):
        """Test rate limiting when IP attempts exceeded."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(side_effect=[None, "15"])  # IP exceeded max_ip_attempts (10)

        # Act
        result = await auth_service._is_rate_limited("test@example.com", "192.168.1.1")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_unavailable(self, auth_service):
        """Test rate limiting when Redis is unavailable."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=False)

        # Act
        result = await auth_service._is_rate_limited("test@example.com", "192.168.1.1")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_error(self, auth_service):
        """Test rate limiting when Redis raises error."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(side_effect=Exception("Redis error"))

        # Act
        result = await auth_service._is_rate_limited("test@example.com", "192.168.1.1")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_record_failed_attempt_redis(self, auth_service):
        """Test recording failed attempt with Redis."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.incr = AsyncMock(side_effect=[1, 1])  # First attempt for both email and IP
        auth_service.redis.expire = AsyncMock(return_value=True)

        # Act
        await auth_service._record_failed_attempt("test@example.com", "192.168.1.1")

        # Assert
        auth_service.redis.incr.assert_has_calls([
            call("rate_limit:email:test@example.com"),
            call("rate_limit:ip:192.168.1.1")
        ])
        auth_service.redis.expire.assert_has_calls([
            call("rate_limit:email:test@example.com", 300),
            call("rate_limit:ip:192.168.1.1", 300)
        ])

    @pytest.mark.asyncio
    async def test_record_failed_attempt_redis_unavailable(self, auth_service):
        """Test recording failed attempt when Redis is unavailable."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=False)

        # Act
        await auth_service._record_failed_attempt("test@example.com", "192.168.1.1")

        # Assert - Should not raise error, just log warning

    @pytest.mark.asyncio
    async def test_clear_failed_attempts_redis(self, auth_service):
        """Test clearing failed attempts with Redis."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.delete = AsyncMock(return_value=1)

        # Act
        await auth_service._clear_failed_attempts("test@example.com")

        # Assert
        auth_service.redis.delete.assert_called_once_with("rate_limit:email:test@example.com")

    @pytest.mark.asyncio
    async def test_clear_failed_attempts_redis_error(self, auth_service):
        """Test clearing failed attempts when Redis raises error."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.delete = AsyncMock(side_effect=Exception("Redis error"))

        # Act
        await auth_service._clear_failed_attempts("test@example.com")

        # Assert - Should not raise error

    def test_is_rate_limited_memory_fallback(self, auth_service):
        """Test in-memory rate limiting fallback."""
        # Arrange
        auth_service._fallback_enabled = True
        now = datetime.utcnow()
        auth_service._failed_attempts["test@example.com"] = {
            'count': 6,  # Exceeded limit
            'last_attempt': now - timedelta(seconds=100),  # Within lockout window
            'ip_attempts': defaultdict(int)
        }

        # Act
        result = auth_service._is_rate_limited_memory("test@example.com")

        # Assert
        assert result is True

    def test_is_rate_limited_memory_expired_window(self, auth_service):
        """Test in-memory rate limiting with expired window."""
        # Arrange
        auth_service._fallback_enabled = True
        now = datetime.utcnow()
        auth_service._failed_attempts["test@example.com"] = {
            'count': 6,
            'last_attempt': now - timedelta(seconds=400),  # Outside lockout window
            'ip_attempts': defaultdict(int)
        }

        # Act
        result = auth_service._is_rate_limited_memory("test@example.com")

        # Assert
        assert result is False

    def test_record_failed_attempt_memory(self, auth_service):
        """Test recording failed attempt in memory."""
        # Arrange
        email = "test@example.com"
        ip = "192.168.1.1"

        # Act
        auth_service._record_failed_attempt_memory(email, ip)

        # Assert
        assert auth_service._failed_attempts[email]['count'] == 1
        assert auth_service._failed_attempts[email]['ip_attempts'][ip] == 1
        assert auth_service._failed_attempts[email]['last_attempt'] is not None


class TestAuthServiceRedisConnection:
    """Test Redis connection handling."""

    @pytest.mark.asyncio
    async def test_redis_is_connected_with_ping(self, auth_service):
        """Test Redis connection check with ping method."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)

        # Act
        result = await auth_service._redis_is_connected()

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_is_connected_with_get(self, auth_service):
        """Test Redis connection check with get method."""
        # Arrange
        auth_service.redis = AsyncMock()
        del auth_service.redis.ping  # Remove ping method
        auth_service.redis.get = AsyncMock(return_value=None)

        # Act
        result = await auth_service._redis_is_connected()

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_is_connected_no_methods(self, auth_service):
        """Test Redis connection check with no valid methods."""
        # Arrange
        auth_service.redis = object()  # Object with no ping or get methods

        # Act
        result = await auth_service._redis_is_connected()

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_is_connected_exception(self, auth_service):
        """Test Redis connection check with exception."""
        # Arrange
        auth_service.redis.ping = AsyncMock(side_effect=Exception("Connection error"))

        # Act
        result = await auth_service._redis_is_connected()

        # Assert
        assert result is False


class TestAuthServiceEdgeCases:
    """Test edge cases and security scenarios."""

    @pytest.mark.asyncio
    async def test_authenticate_user_email_normalization(self, auth_service, mock_user_repository, sample_user):
        """Test email normalization during authentication."""
        # Arrange
        mock_user_repository.get_by_email.return_value = sample_user
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value=None)

        with patch('app.services.auth.verify_password', return_value=True), \
             patch('app.services.auth.cache_user_data'):

            # Act
            result = await auth_service.authenticate_user("  TEST@EXAMPLE.COM  ", "password123")

            # Assert
            assert result == sample_user
            mock_user_repository.get_by_email.assert_called_once_with("test@example.com")

    def test_create_user_email_normalization(self, auth_service, mock_user_repository, sample_user):
        """Test email normalization during user creation."""
        # Arrange
        mock_user_repository.get_by_email.return_value = None
        mock_user_repository.create.return_value = sample_user

        with patch('app.services.auth.get_password_hash', return_value="hashed"), \
             patch('app.services.auth.cache_user_data'):

            # Act
            result = auth_service.create_user("  TEST@EXAMPLE.COM  ", "password123", "  Test User  ")

            # Assert
            mock_user_repository.get_by_email.assert_called_once_with("test@example.com")
            # Verify create was called with normalized data
            create_call_args = mock_user_repository.create.call_args[0][0]
            assert create_call_args["email"] == "test@example.com"
            assert create_call_args["full_name"] == "Test User"

    def test_verify_token_refresh_type(self, auth_service, sample_token_data):
        """Test token verification with refresh token type."""
        # Arrange
        token = "refresh-token"

        with patch('app.services.auth.verify_jwt_token', return_value=sample_token_data) as mock_verify:
            # Act
            result = auth_service.verify_token(token, "refresh")

            # Assert
            assert result == sample_token_data
            mock_verify.assert_called_once_with(token, "refresh")

    @pytest.mark.asyncio
    async def test_rate_limiting_ip_only(self, auth_service):
        """Test rate limiting with IP address only (no email)."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(side_effect=[None, "15"])  # IP exceeded

        # Act
        result = await auth_service._is_rate_limited("test@example.com", "192.168.1.1")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_record_failed_attempt_no_ip(self, auth_service):
        """Test recording failed attempt without IP address."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.incr = AsyncMock(return_value=1)
        auth_service.redis.expire = AsyncMock(return_value=True)

        # Act
        await auth_service._record_failed_attempt("test@example.com", None)

        # Assert
        auth_service.redis.incr.assert_called_once_with("rate_limit:email:test@example.com")
        # IP-related calls should not be made
        assert auth_service.redis.incr.call_count == 1

    def test_blacklist_token_with_expiry(self, auth_service):
        """Test token blacklisting with expiry timestamp."""
        # Arrange
        token = "token-with-expiry"
        exp_timestamp = 1234567890

        # Act
        auth_service.blacklist_token(token, exp_timestamp)

        # Assert
        assert token in auth_service._blacklisted_tokens


class TestAuthServiceLogging:
    """Test logging behavior in Auth Service."""

    @pytest.mark.asyncio
    async def test_authentication_success_logging(self, auth_service, mock_user_repository, sample_user):
        """Test successful authentication logging."""
        # Arrange
        mock_user_repository.get_by_email.return_value = sample_user
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value=None)

        with patch('app.services.auth.verify_password', return_value=True), \
             patch('app.services.auth.cache_user_data'), \
             patch('app.services.auth.logger') as mock_logger:

            # Act
            await auth_service.authenticate_user("test@example.com", "password123")

            # Assert
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_authentication_failure_logging(self, auth_service, mock_user_repository):
        """Test authentication failure logging."""
        # Arrange
        mock_user_repository.get_by_email.return_value = None
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value=None)

        with patch('app.services.auth.logger') as mock_logger:
            # Act
            await auth_service.authenticate_user("test@example.com", "password123")

            # Assert
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_rate_limit_warning_logging(self, auth_service):
        """Test rate limit warning logging."""
        # Arrange
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.get = AsyncMock(return_value="10")

        with patch('app.services.auth.logger') as mock_logger:
            # Act
            await auth_service._is_rate_limited("test@example.com", "192.168.1.1")

            # Assert
            mock_logger.warning.assert_called()

    def test_token_verification_logging(self, auth_service):
        """Test token verification logging."""
        with patch('app.services.auth.verify_jwt_token', return_value=None), \
             patch('app.services.auth.logger') as mock_logger:

            # Act
            auth_service.verify_token("invalid-token")

            # Assert
            mock_logger.warning.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])