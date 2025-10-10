"""
Unit tests for authentication service.

Tests AuthService class including user authentication, token management,
rate limiting, Redis cache operations, and security features.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, Optional
from collections import defaultdict

from app.services.auth import AuthService
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.auth import TokenData
from app.utils.security import get_password_hash


class TestAuthServiceInitialization:
    """Test suite for AuthService initialization."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def mock_user_repository(self):
        """Mock user repository."""
        return Mock(spec=UserRepository)

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_client = AsyncMock()
        redis_client.get = AsyncMock()
        redis_client.set = AsyncMock()
        redis_client.incr = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.delete = AsyncMock()
        return redis_client

    def test_auth_service_initialization(self, mock_db, mock_user_repository, mock_redis):
        """Test AuthService initialization."""
        service = AuthService(
            db=mock_db,
            user_repository=mock_user_repository,
            redis_client=mock_redis
        )

        assert service.db == mock_db
        assert service.repository == mock_user_repository
        assert service.redis == mock_redis
        assert service.max_attempts == 5
        assert service.max_ip_attempts == 10
        assert service.lockout_window == 300
        assert not service._fallback_enabled
        assert isinstance(service._blacklisted_tokens, set)
        assert isinstance(service._failed_attempts, defaultdict)

    def test_auth_service_initialization_without_redis(self, mock_db, mock_user_repository):
        """Test AuthService initialization without Redis."""
        service = AuthService(
            db=mock_db,
            user_repository=mock_user_repository,
            redis_client=None
        )

        assert service.redis is None
        assert not service._fallback_enabled


class TestUserAuthentication:
    """Test suite for user authentication methods."""

    @pytest.fixture
    def auth_service(self, mock_db, mock_user_repository, mock_redis):
        """AuthService instance for testing."""
        return AuthService(
            db=mock_db,
            user_repository=mock_user_repository,
            redis_client=mock_redis
        )

    @pytest.fixture
    def mock_user(self):
        """Mock user model."""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        user.hashed_password = get_password_hash("password123")
        user.is_active = True
        return user

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service, mock_user):
        """Test successful user authentication."""
        email = "test@example.com"
        password = "password123"
        client_ip = "127.0.0.1"

        # Mock repository
        auth_service.repository.get_by_email.return_value = mock_user

        # Mock Redis connection check
        auth_service.redis.ping = AsyncMock(return_value=True)

        # Mock rate limiting
        with patch.object(auth_service, '_is_rate_limited', return_value=False), \
             patch.object(auth_service, '_clear_failed_attempts') as mock_clear, \
             patch('app.services.auth.verify_password', return_value=True), \
             patch('app.services.auth.cache_user_data') as mock_cache:

            result = await auth_service.authenticate_user(email, password, client_ip)

            assert result == mock_user
            auth_service.repository.get_by_email.assert_called_once_with(email)
            mock_clear.assert_called_once_with(email)
            mock_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_empty_credentials(self, auth_service):
        """Test authentication with empty credentials."""
        # Empty email
        result = await auth_service.authenticate_user("", "password", "127.0.0.1")
        assert result is None

        # Empty password
        result = await auth_service.authenticate_user("test@example.com", "", "127.0.0.1")
        assert result is None

        # Both empty
        result = await auth_service.authenticate_user("", "", "127.0.0.1")
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_redis_unavailable(self, auth_service):
        """Test authentication when Redis is unavailable."""
        auth_service.redis = None

        with pytest.raises(RuntimeError) as exc_info:
            await auth_service.authenticate_user("test@example.com", "password", "127.0.0.1")

        assert "Authentication dependencies unavailable: Redis" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_user_rate_limited(self, auth_service):
        """Test authentication when rate limited."""
        email = "test@example.com"
        password = "password123"

        # Mock Redis connection
        auth_service.redis.ping = AsyncMock(return_value=True)

        # Mock rate limiting
        with patch.object(auth_service, '_is_rate_limited', return_value=True):
            result = await auth_service.authenticate_user(email, password, "127.0.0.1")

            assert result is None
            # Repository should not be called
            auth_service.repository.get_by_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service):
        """Test authentication with non-existent user."""
        email = "nonexistent@example.com"
        password = "password123"

        # Mock repository returning None
        auth_service.repository.get_by_email.return_value = None
        auth_service.redis.ping = AsyncMock(return_value=True)

        with patch.object(auth_service, '_is_rate_limited', return_value=False), \
             patch.object(auth_service, '_record_failed_attempt') as mock_record:

            result = await auth_service.authenticate_user(email, password, "127.0.0.1")

            assert result is None
            mock_record.assert_called_once_with(email, "127.0.0.1")

    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_password(self, auth_service, mock_user):
        """Test authentication with invalid password."""
        email = "test@example.com"
        password = "wrongpassword"

        auth_service.repository.get_by_email.return_value = mock_user
        auth_service.redis.ping = AsyncMock(return_value=True)

        with patch.object(auth_service, '_is_rate_limited', return_value=False), \
             patch.object(auth_service, '_record_failed_attempt') as mock_record, \
             patch('app.services.auth.verify_password', return_value=False):

            result = await auth_service.authenticate_user(email, password, "127.0.0.1")

            assert result is None
            mock_record.assert_called_once_with(email, "127.0.0.1")

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(self, auth_service, mock_user):
        """Test authentication with inactive user."""
        email = "test@example.com"
        password = "password123"

        # Mock inactive user
        mock_user.is_active = False
        auth_service.repository.get_by_email.return_value = mock_user
        auth_service.redis.ping = AsyncMock(return_value=True)

        with patch.object(auth_service, '_is_rate_limited', return_value=False), \
             patch('app.services.auth.verify_password', return_value=True):

            result = await auth_service.authenticate_user(email, password, "127.0.0.1")

            assert result is None


class TestTokenManagement:
    """Test suite for JWT token management."""

    @pytest.fixture
    def auth_service(self, mock_db, mock_user_repository, mock_redis):
        """AuthService instance for testing."""
        return AuthService(
            db=mock_db,
            user_repository=mock_user_repository,
            redis_client=mock_redis
        )

    def test_create_access_token_success(self, auth_service):
        """Test successful access token creation."""
        data = {"email": "test@example.com", "sub": "user-123"}

        with patch('app.services.auth.create_access_token', return_value="token-123") as mock_create:
            result = auth_service.create_access_token(data)

            assert result == "token-123"
            mock_create.assert_called_once_with(data, None)

    def test_create_access_token_with_expiration(self, auth_service):
        """Test access token creation with custom expiration."""
        data = {"email": "test@example.com"}
        expires_delta = timedelta(hours=1)

        with patch('app.services.auth.create_access_token', return_value="token-123") as mock_create:
            result = auth_service.create_access_token(data, expires_delta)

            assert result == "token-123"
            mock_create.assert_called_once_with(data, expires_delta)

    def test_create_access_token_empty_data(self, auth_service):
        """Test access token creation with empty data."""
        with pytest.raises(ValueError) as exc_info:
            auth_service.create_access_token({})

        assert "Token data cannot be empty" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            auth_service.create_access_token(None)

        assert "Token data cannot be empty" in str(exc_info.value)

    def test_create_refresh_token_success(self, auth_service):
        """Test successful refresh token creation."""
        data = {"email": "test@example.com", "sub": "user-123"}

        with patch('app.services.auth.create_refresh_token', return_value="refresh-token-123") as mock_create:
            result = auth_service.create_refresh_token(data)

            assert result == "refresh-token-123"
            mock_create.assert_called_once_with(data)

    def test_create_refresh_token_empty_data(self, auth_service):
        """Test refresh token creation with empty data."""
        with pytest.raises(ValueError) as exc_info:
            auth_service.create_refresh_token({})

        assert "Token data cannot be empty" in str(exc_info.value)


class TestTokenVerification:
    """Test suite for JWT token verification."""

    @pytest.fixture
    def auth_service(self, mock_db, mock_user_repository, mock_redis):
        """AuthService instance for testing."""
        return AuthService(
            db=mock_db,
            user_repository=mock_user_repository,
            redis_client=mock_redis
        )

    @pytest.fixture
    def valid_token_data(self):
        """Valid token data."""
        return TokenData(
            email="test@example.com",
            user_id="user-123",
            exp=int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        )

    def test_verify_token_success(self, auth_service, valid_token_data):
        """Test successful token verification."""
        token = "valid-token-123"

        with patch('app.services.auth.verify_jwt_token', return_value=valid_token_data):
            result = auth_service.verify_token(token)

            assert result == valid_token_data

    def test_verify_token_blacklisted(self, auth_service):
        """Test verification of blacklisted token."""
        token = "blacklisted-token"
        auth_service._blacklisted_tokens.add(token)

        result = auth_service.verify_token(token)
        assert result is None

    def test_verify_token_invalid_format(self, auth_service):
        """Test verification with invalid token format."""
        # Empty token
        result = auth_service.verify_token("")
        assert result is None

        # None token
        result = auth_service.verify_token(None)
        assert result is None

        # Non-string token
        result = auth_service.verify_token(123)
        assert result is None

    def test_verify_token_with_bearer_prefix(self, auth_service, valid_token_data):
        """Test token verification with Bearer prefix."""
        token = "Bearer valid-token-123"

        with patch('app.services.auth.verify_jwt_token', return_value=valid_token_data) as mock_verify:
            result = auth_service.verify_token(token)

            assert result == valid_token_data
            # Should strip Bearer prefix
            mock_verify.assert_called_once_with("valid-token-123", "access")

    def test_verify_token_utility_failure(self, auth_service):
        """Test token verification when utility function fails."""
        token = "invalid-token"

        with patch('app.services.auth.verify_jwt_token', return_value=None):
            result = auth_service.verify_token(token)
            assert result is None

    def test_verify_token_unexpected_exception(self, auth_service):
        """Test token verification with unexpected exception."""
        token = "error-token"

        with patch('app.services.auth.verify_jwt_token', side_effect=Exception("Unexpected error")):
            result = auth_service.verify_token(token)
            assert result is None

    def test_verify_refresh_token(self, auth_service, valid_token_data):
        """Test refresh token verification."""
        token = "refresh-token-123"

        with patch('app.services.auth.verify_jwt_token', return_value=valid_token_data) as mock_verify:
            result = auth_service.verify_token(token, "refresh")

            assert result == valid_token_data
            mock_verify.assert_called_once_with(token, "refresh")

    def test_blacklist_token(self, auth_service):
        """Test token blacklisting."""
        token = "token-to-blacklist"

        auth_service.blacklist_token(token)
        assert token in auth_service._blacklisted_tokens

        # Test with Bearer prefix
        bearer_token = "Bearer token-with-bearer"
        auth_service.blacklist_token(bearer_token)
        assert "token-with-bearer" in auth_service._blacklisted_tokens

        # Test with empty token
        auth_service.blacklist_token("")
        auth_service.blacklist_token(None)
        # Should not crash


class TestUserRetrieval:
    """Test suite for user retrieval from tokens."""

    @pytest.fixture
    def auth_service(self, mock_db, mock_user_repository, mock_redis):
        """AuthService instance for testing."""
        return AuthService(
            db=mock_db,
            user_repository=mock_user_repository,
            redis_client=mock_redis
        )

    @pytest.fixture
    def valid_token_data(self):
        """Valid token data."""
        return TokenData(
            email="test@example.com",
            user_id="user-123",
            exp=int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        )

    @pytest.fixture
    def mock_user(self):
        """Mock user model."""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        user.is_active = True
        return user

    def test_get_user_from_token_data_success(self, auth_service, valid_token_data, mock_user):
        """Test successful user retrieval from token data."""
        auth_service.repository.get_by_email.return_value = mock_user

        result = auth_service._get_user_from_token_data(valid_token_data)

        assert result == mock_user
        auth_service.repository.get_by_email.assert_called_once_with("test@example.com")

    def test_get_user_from_token_data_not_found(self, auth_service, valid_token_data):
        """Test user retrieval when user not found."""
        auth_service.repository.get_by_email.return_value = None

        result = auth_service._get_user_from_token_data(valid_token_data)

        assert result is None

    def test_get_user_from_token_data_inactive(self, auth_service, valid_token_data, mock_user):
        """Test user retrieval with inactive user."""
        mock_user.is_active = False
        auth_service.repository.get_by_email.return_value = mock_user

        result = auth_service._get_user_from_token_data(valid_token_data)

        assert result is None

    def test_get_current_user_success(self, auth_service, valid_token_data, mock_user):
        """Test successful current user retrieval."""
        token = "valid-token"

        with patch.object(auth_service, 'verify_token', return_value=valid_token_data), \
             patch.object(auth_service, '_get_user_from_token_data', return_value=mock_user):

            result = auth_service.get_current_user(token)

            assert result == mock_user

    def test_get_current_user_invalid_token(self, auth_service):
        """Test current user retrieval with invalid token."""
        token = "invalid-token"

        with patch.object(auth_service, 'verify_token', return_value=None):
            result = auth_service.get_current_user(token)

            assert result is None


class TestUserCreation:
    """Test suite for user creation."""

    @pytest.fixture
    def auth_service(self, mock_db, mock_user_repository, mock_redis):
        """AuthService instance for testing."""
        return AuthService(
            db=mock_db,
            user_repository=mock_user_repository,
            redis_client=mock_redis
        )

    @pytest.fixture
    def mock_user(self):
        """Mock user model."""
        user = Mock(spec=User)
        user.id = "new-user-123"
        user.email = "newuser@example.com"
        user.full_name = "New User"
        user.role = "doctor"
        return user

    def test_create_user_success(self, auth_service, mock_user):
        """Test successful user creation."""
        email = "newuser@example.com"
        password = "password123"
        full_name = "New User"
        role = "doctor"

        # Mock repository methods
        auth_service.repository.get_by_email.return_value = None  # User doesn't exist
        auth_service.repository.create.return_value = mock_user

        with patch('app.services.auth.get_password_hash', return_value="hashed-password"), \
             patch('app.services.auth.cache_user_data') as mock_cache:

            result = auth_service.create_user(email, password, full_name, role)

            assert result == mock_user

            # Verify calls
            auth_service.repository.get_by_email.assert_called_once_with(email.lower())
            auth_service.repository.create.assert_called_once()
            mock_cache.assert_called_once()

            # Verify user data
            create_call = auth_service.repository.create.call_args[0][0]
            assert create_call["email"] == email.lower()
            assert create_call["hashed_password"] == "hashed-password"
            assert create_call["full_name"] == full_name
            assert create_call["role"] == role

    def test_create_user_empty_email(self, auth_service):
        """Test user creation with empty email."""
        with pytest.raises(ValueError) as exc_info:
            auth_service.create_user("", "password123", "Full Name", "doctor")

        assert "Email cannot be empty" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            auth_service.create_user("   ", "password123", "Full Name", "doctor")

        assert "Email cannot be empty" in str(exc_info.value)

    def test_create_user_weak_password(self, auth_service):
        """Test user creation with weak password."""
        with pytest.raises(ValueError) as exc_info:
            auth_service.create_user("test@example.com", "weak", "Full Name", "doctor")

        assert "Password must be at least 8 characters long" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            auth_service.create_user("test@example.com", "", "Full Name", "doctor")

        assert "Password must be at least 8 characters long" in str(exc_info.value)

    def test_create_user_empty_name(self, auth_service):
        """Test user creation with empty name."""
        with pytest.raises(ValueError) as exc_info:
            auth_service.create_user("test@example.com", "password123", "", "doctor")

        assert "Full name cannot be empty" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            auth_service.create_user("test@example.com", "password123", "   ", "doctor")

        assert "Full name cannot be empty" in str(exc_info.value)

    def test_create_user_already_exists(self, auth_service, mock_user):
        """Test user creation when user already exists."""
        email = "existing@example.com"

        # Mock existing user
        auth_service.repository.get_by_email.return_value = mock_user

        with pytest.raises(ValueError) as exc_info:
            auth_service.create_user(email, "password123", "Full Name", "doctor")

        assert "User with this email already exists" in str(exc_info.value)


class TestRateLimiting:
    """Test suite for rate limiting functionality."""

    @pytest.fixture
    def auth_service(self, mock_db, mock_user_repository, mock_redis):
        """AuthService instance for testing."""
        return AuthService(
            db=mock_db,
            user_repository=mock_user_repository,
            redis_client=mock_redis
        )

    @pytest.mark.asyncio
    async def test_redis_is_connected_success(self, auth_service):
        """Test Redis connection check success."""
        auth_service.redis.ping = AsyncMock(return_value=True)

        result = await auth_service._redis_is_connected()
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_is_connected_failure(self, auth_service):
        """Test Redis connection check failure."""
        auth_service.redis.ping = AsyncMock(side_effect=Exception("Connection failed"))

        result = await auth_service._redis_is_connected()
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_is_connected_no_ping_method(self, auth_service):
        """Test Redis connection check with client without ping method."""
        # Mock client with get method but no ping
        auth_service.redis = AsyncMock()
        del auth_service.redis.ping
        auth_service.redis.get = AsyncMock(return_value=None)

        result = await auth_service._redis_is_connected()
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_is_connected_no_methods(self, auth_service):
        """Test Redis connection check with client without required methods."""
        auth_service.redis = Mock()  # No async methods

        result = await auth_service._redis_is_connected()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_success(self, auth_service):
        """Test rate limiting check with Redis."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Mock Redis responses
        auth_service.redis.ping = AsyncMock(return_value=True)

        with patch.object(auth_service, '_is_rate_limited_redis', return_value=False) as mock_redis_check:
            result = await auth_service._is_rate_limited(email, client_ip)

            assert result is False
            mock_redis_check.assert_called_once_with(email, client_ip)

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_unavailable(self, auth_service):
        """Test rate limiting check when Redis unavailable."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        auth_service.redis = None

        result = await auth_service._is_rate_limited(email, client_ip)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_email_exceeded(self, auth_service):
        """Test rate limiting when email attempts exceeded."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Mock Redis returning exceeded attempts
        auth_service.redis.get = AsyncMock(return_value="6")  # Exceeds max_attempts (5)

        result = await auth_service._is_rate_limited_redis(email, client_ip)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_ip_exceeded(self, auth_service):
        """Test rate limiting when IP attempts exceeded."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Mock Redis responses
        auth_service.redis.get = AsyncMock(side_effect=["3", "11"])  # Email OK, IP exceeded

        result = await auth_service._is_rate_limited_redis(email, client_ip)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_within_limits(self, auth_service):
        """Test rate limiting when within limits."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Mock Redis responses within limits
        auth_service.redis.get = AsyncMock(side_effect=["2", "5"])  # Both within limits

        result = await auth_service._is_rate_limited_redis(email, client_ip)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_no_ip(self, auth_service):
        """Test rate limiting without IP address."""
        email = "test@example.com"

        # Mock Redis response for email only
        auth_service.redis.get = AsyncMock(return_value="2")

        result = await auth_service._is_rate_limited_redis(email, None)
        assert result is False

    @pytest.mark.asyncio
    async def test_record_failed_attempt_redis_success(self, auth_service):
        """Test recording failed attempt in Redis."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Mock Redis operations
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.incr = AsyncMock(side_effect=[1, 1])  # First attempt for both
        auth_service.redis.expire = AsyncMock(return_value=True)

        await auth_service._record_failed_attempt(email, client_ip)

        # Verify Redis calls
        assert auth_service.redis.incr.call_count == 2
        assert auth_service.redis.expire.call_count == 2

    @pytest.mark.asyncio
    async def test_record_failed_attempt_redis_subsequent(self, auth_service):
        """Test recording subsequent failed attempts."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Mock Redis operations for subsequent attempts
        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.incr = AsyncMock(side_effect=[3, 2])  # Not first attempts
        auth_service.redis.expire = AsyncMock()

        await auth_service._record_failed_attempt(email, client_ip)

        # Should not set TTL for subsequent attempts
        auth_service.redis.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_failed_attempt_redis_unavailable(self, auth_service):
        """Test recording failed attempt when Redis unavailable."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        auth_service.redis = None

        # Should not raise exception
        await auth_service._record_failed_attempt(email, client_ip)

    @pytest.mark.asyncio
    async def test_clear_failed_attempts_redis(self, auth_service):
        """Test clearing failed attempts from Redis."""
        email = "test@example.com"

        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.delete = AsyncMock(return_value=1)

        await auth_service._clear_failed_attempts(email)

        auth_service.redis.delete.assert_called_once_with(f"rate_limit:email:{email}")

    @pytest.mark.asyncio
    async def test_clear_failed_attempts_redis_error(self, auth_service):
        """Test clearing failed attempts with Redis error."""
        email = "test@example.com"

        auth_service.redis.ping = AsyncMock(return_value=True)
        auth_service.redis.delete = AsyncMock(side_effect=Exception("Redis error"))

        # Should not raise exception
        await auth_service._clear_failed_attempts(email)

    def test_is_rate_limited_memory_within_window(self, auth_service):
        """Test memory-based rate limiting within window."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Set up failed attempts within window
        now = datetime.utcnow()
        auth_service._failed_attempts[email] = {
            'count': 3,
            'last_attempt': now - timedelta(seconds=100),  # Within 300s window
            'ip_attempts': defaultdict(int, {client_ip: 2})
        }

        result = auth_service._is_rate_limited_memory(email, client_ip)
        assert result is False

    def test_is_rate_limited_memory_exceeded_email(self, auth_service):
        """Test memory-based rate limiting with exceeded email attempts."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Set up failed attempts exceeding limit
        now = datetime.utcnow()
        auth_service._failed_attempts[email] = {
            'count': 6,  # Exceeds max_attempts (5)
            'last_attempt': now - timedelta(seconds=100),
            'ip_attempts': defaultdict(int, {client_ip: 2})
        }

        result = auth_service._is_rate_limited_memory(email, client_ip)
        assert result is True

    def test_is_rate_limited_memory_exceeded_ip(self, auth_service):
        """Test memory-based rate limiting with exceeded IP attempts."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Set up IP attempts exceeding limit
        now = datetime.utcnow()
        auth_service._failed_attempts[email] = {
            'count': 3,
            'last_attempt': now - timedelta(seconds=100),
            'ip_attempts': defaultdict(int, {client_ip: 12})  # Exceeds max_ip_attempts (10)
        }

        result = auth_service._is_rate_limited_memory(email, client_ip)
        assert result is True

    def test_is_rate_limited_memory_expired_window(self, auth_service):
        """Test memory-based rate limiting with expired window."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Set up failed attempts outside window
        now = datetime.utcnow()
        auth_service._failed_attempts[email] = {
            'count': 6,  # Would exceed, but window expired
            'last_attempt': now - timedelta(seconds=400),  # Outside 300s window
            'ip_attempts': defaultdict(int, {client_ip: 12})
        }

        result = auth_service._is_rate_limited_memory(email, client_ip)
        assert result is False

        # Should reset counts
        assert auth_service._failed_attempts[email]['count'] == 0
        assert len(auth_service._failed_attempts[email]['ip_attempts']) == 0

    def test_record_failed_attempt_memory(self, auth_service):
        """Test recording failed attempt in memory."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Initial state
        assert email not in auth_service._failed_attempts

        auth_service._record_failed_attempt_memory(email, client_ip)

        # Verify attempt recorded
        attempts = auth_service._failed_attempts[email]
        assert attempts['count'] == 1
        assert attempts['ip_attempts'][client_ip] == 1
        assert attempts['last_attempt'] is not None

    def test_record_failed_attempt_memory_reset_expired(self, auth_service):
        """Test recording failed attempt with expired previous attempts."""
        email = "test@example.com"
        client_ip = "127.0.0.1"

        # Set up expired attempts
        expired_time = datetime.utcnow() - timedelta(seconds=400)
        auth_service._failed_attempts[email] = {
            'count': 5,
            'last_attempt': expired_time,
            'ip_attempts': defaultdict(int, {client_ip: 8})
        }

        auth_service._record_failed_attempt_memory(email, client_ip)

        # Should reset and start fresh
        attempts = auth_service._failed_attempts[email]
        assert attempts['count'] == 1
        assert attempts['ip_attempts'][client_ip] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])