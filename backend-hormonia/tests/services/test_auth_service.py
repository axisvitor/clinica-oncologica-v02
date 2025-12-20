"""
AuthService Unit Tests

Comprehensive tests for the authentication service layer including:
- Token creation and verification
- Rate limiting
- User management
- Password operations
- Caching behavior
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock
from sqlalchemy.orm import Session

from app.services.auth import AuthService
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.auth import TokenData


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_user_repository(mocker):
    """Create mock user repository."""
    repo = mocker.MagicMock(spec=UserRepository)
    repo.get_by_email = mocker.MagicMock(return_value=None)
    repo.create = mocker.MagicMock()
    return repo


@pytest.fixture
def mock_async_redis(mocker):
    """Create mock async Redis client."""
    redis = mocker.MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def auth_service(db_session: Session, mock_user_repository, mock_async_redis):
    """Create AuthService instance with mocked dependencies."""
    return AuthService(
        db=db_session,
        user_repository=mock_user_repository,
        redis_client=mock_async_redis
    )


@pytest.fixture
def auth_service_no_redis(db_session: Session, mock_user_repository):
    """Create AuthService instance without Redis."""
    return AuthService(
        db=db_session,
        user_repository=mock_user_repository,
        redis_client=None
    )


# ============================================================================
# Token Creation Tests
# ============================================================================

class TestTokenCreation:
    """Test suite for JWT token creation."""

    def test_create_access_token_success(self, auth_service: AuthService):
        """Test creating access token with valid data."""
        data = {"sub": "test@example.com", "user_id": str(uuid4())}

        token = auth_service.create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long

    def test_create_access_token_with_expiration(self, auth_service: AuthService):
        """Test creating access token with custom expiration."""
        data = {"sub": "test@example.com"}
        expires = timedelta(hours=2)

        token = auth_service.create_access_token(data, expires_delta=expires)

        assert token is not None

    def test_create_access_token_empty_data_raises_error(self, auth_service: AuthService):
        """Test creating access token with empty data raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            auth_service.create_access_token({})

    def test_create_access_token_none_data_raises_error(self, auth_service: AuthService):
        """Test creating access token with None data raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            auth_service.create_access_token(None)

    def test_create_refresh_token_success(self, auth_service: AuthService):
        """Test creating refresh token with valid data."""
        data = {"sub": "test@example.com"}

        token = auth_service.create_refresh_token(data)

        assert token is not None
        assert isinstance(token, str)

    def test_create_refresh_token_empty_data_raises_error(self, auth_service: AuthService):
        """Test creating refresh token with empty data raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            auth_service.create_refresh_token({})


# ============================================================================
# Token Verification Tests
# ============================================================================

class TestTokenVerification:
    """Test suite for JWT token verification."""

    def test_verify_token_valid(self, auth_service: AuthService):
        """Test verifying a valid token."""
        data = {"sub": "test@example.com"}
        token = auth_service.create_access_token(data)

        result = auth_service.verify_token(token)

        assert result is not None
        assert isinstance(result, TokenData)
        assert result.email == "test@example.com"

    def test_verify_token_with_bearer_prefix(self, auth_service: AuthService):
        """Test verifying token with 'Bearer ' prefix."""
        data = {"sub": "test@example.com"}
        token = auth_service.create_access_token(data)

        result = auth_service.verify_token(f"Bearer {token}")

        assert result is not None
        assert result.email == "test@example.com"

    def test_verify_token_invalid(self, auth_service: AuthService):
        """Test verifying an invalid token returns None."""
        result = auth_service.verify_token("invalid_token_string")

        assert result is None

    def test_verify_token_empty_string(self, auth_service: AuthService):
        """Test verifying empty string returns None."""
        result = auth_service.verify_token("")

        assert result is None

    def test_verify_token_none(self, auth_service: AuthService):
        """Test verifying None returns None."""
        result = auth_service.verify_token(None)

        assert result is None

    def test_verify_token_whitespace_only(self, auth_service: AuthService):
        """Test verifying whitespace-only string returns None."""
        result = auth_service.verify_token("   ")

        assert result is None

    def test_verify_token_blacklisted(self, auth_service: AuthService):
        """Test verifying blacklisted token returns None."""
        data = {"sub": "test@example.com"}
        token = auth_service.create_access_token(data)

        # Blacklist the token
        auth_service.blacklist_token(token)

        result = auth_service.verify_token(token)

        assert result is None

    def test_verify_refresh_token(self, auth_service: AuthService):
        """Test verifying refresh token type."""
        data = {"sub": "test@example.com"}
        token = auth_service.create_refresh_token(data)

        result = auth_service.verify_token(token, token_type="refresh")

        assert result is not None


# ============================================================================
# Token Blacklist Tests
# ============================================================================

class TestTokenBlacklist:
    """Test suite for token blacklisting."""

    def test_blacklist_token(self, auth_service: AuthService):
        """Test blacklisting a token."""
        token = "test_token_123"

        auth_service.blacklist_token(token)

        assert token in auth_service._blacklisted_tokens

    def test_blacklist_token_with_bearer_prefix(self, auth_service: AuthService):
        """Test blacklisting token strips Bearer prefix."""
        token = "test_token_456"

        auth_service.blacklist_token(f"Bearer {token}")

        assert token in auth_service._blacklisted_tokens

    def test_blacklist_empty_token(self, auth_service: AuthService):
        """Test blacklisting empty token does nothing."""
        initial_count = len(auth_service._blacklisted_tokens)

        auth_service.blacklist_token("")

        assert len(auth_service._blacklisted_tokens) == initial_count

    def test_blacklist_none_token(self, auth_service: AuthService):
        """Test blacklisting None token does nothing."""
        initial_count = len(auth_service._blacklisted_tokens)

        auth_service.blacklist_token(None)

        assert len(auth_service._blacklisted_tokens) == initial_count


# ============================================================================
# Get Current User Tests
# ============================================================================

class TestGetCurrentUser:
    """Test suite for getting current user from token."""

    def test_get_current_user_valid_token(
        self,
        auth_service: AuthService,
        mock_user_repository,
        test_user: User
    ):
        """Test getting current user with valid token."""
        mock_user_repository.get_by_email.return_value = test_user

        data = {"sub": test_user.email}
        token = auth_service.create_access_token(data)

        result = auth_service.get_current_user(token)

        assert result is not None
        assert result.email == test_user.email

    def test_get_current_user_invalid_token(self, auth_service: AuthService):
        """Test getting current user with invalid token returns None."""
        result = auth_service.get_current_user("invalid_token")

        assert result is None

    def test_get_current_user_user_not_found(
        self,
        auth_service: AuthService,
        mock_user_repository
    ):
        """Test getting current user when user doesn't exist returns None."""
        mock_user_repository.get_by_email.return_value = None

        data = {"sub": "nonexistent@example.com"}
        token = auth_service.create_access_token(data)

        result = auth_service.get_current_user(token)

        assert result is None

    def test_get_current_user_inactive_user(
        self,
        auth_service: AuthService,
        mock_user_repository,
        db_session: Session
    ):
        """Test getting current user when user is inactive returns None."""
        inactive_user = User(
            id=uuid4(),
            email="inactive@example.com",
            full_name="Inactive User",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            is_active=False
        )
        mock_user_repository.get_by_email.return_value = inactive_user

        data = {"sub": inactive_user.email}
        token = auth_service.create_access_token(data)

        result = auth_service.get_current_user(token)

        assert result is None


# ============================================================================
# User Creation Tests
# ============================================================================

class TestUserCreation:
    """Test suite for user creation."""

    def test_create_user_success(
        self,
        auth_service: AuthService,
        mock_user_repository,
        db_session: Session
    ):
        """Test creating a new user successfully."""
        new_user = User(
            id=uuid4(),
            email="new@example.com",
            full_name="New User",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            is_active=True
        )
        mock_user_repository.get_by_email.return_value = None
        mock_user_repository.create.return_value = new_user

        result = auth_service.create_user(
            email="new@example.com",
            password="SecurePass123!",
            full_name="New User"
        )

        assert result is not None
        mock_user_repository.create.assert_called_once()

    def test_create_user_empty_email_raises_error(self, auth_service: AuthService):
        """Test creating user with empty email raises ValueError."""
        with pytest.raises(ValueError, match="Email cannot be empty"):
            auth_service.create_user(
                email="",
                password="SecurePass123!",
                full_name="Test User"
            )

    def test_create_user_empty_password_raises_error(self, auth_service: AuthService):
        """Test creating user with empty password raises ValueError."""
        with pytest.raises(ValueError, match="Password must be at least"):
            auth_service.create_user(
                email="test@example.com",
                password="",
                full_name="Test User"
            )

    def test_create_user_short_password_raises_error(self, auth_service: AuthService):
        """Test creating user with short password raises ValueError."""
        with pytest.raises(ValueError, match="Password must be at least"):
            auth_service.create_user(
                email="test@example.com",
                password="short",
                full_name="Test User"
            )

    def test_create_user_empty_name_raises_error(self, auth_service: AuthService):
        """Test creating user with empty name raises ValueError."""
        with pytest.raises(ValueError, match="Full name cannot be empty"):
            auth_service.create_user(
                email="test@example.com",
                password="SecurePass123!",
                full_name=""
            )

    def test_create_user_duplicate_email_raises_error(
        self,
        auth_service: AuthService,
        mock_user_repository,
        test_user: User
    ):
        """Test creating user with existing email raises ValueError."""
        mock_user_repository.get_by_email.return_value = test_user

        with pytest.raises(ValueError, match="already exists"):
            auth_service.create_user(
                email=test_user.email,
                password="SecurePass123!",
                full_name="Another User"
            )

    def test_create_user_normalizes_email(
        self,
        auth_service: AuthService,
        mock_user_repository
    ):
        """Test creating user normalizes email to lowercase."""
        new_user = User(
            id=uuid4(),
            email="test@example.com",
            full_name="Test User",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            is_active=True
        )
        mock_user_repository.get_by_email.return_value = None
        mock_user_repository.create.return_value = new_user

        auth_service.create_user(
            email="  TEST@EXAMPLE.COM  ",
            password="SecurePass123!",
            full_name="Test User"
        )

        # Verify get_by_email was called with lowercase, trimmed email
        mock_user_repository.get_by_email.assert_called_with("test@example.com")


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Test suite for authentication rate limiting."""

    @pytest.mark.asyncio
    async def test_is_rate_limited_no_attempts(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test not rate limited when no failed attempts."""
        mock_async_redis.get.return_value = None

        result = await auth_service._is_rate_limited("test@example.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_under_threshold(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test not rate limited when under max attempts."""
        mock_async_redis.get.return_value = "3"  # Under max of 5

        result = await auth_service._is_rate_limited("test@example.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_rate_limited_at_threshold(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test rate limited when at max attempts."""
        mock_async_redis.get.return_value = "5"  # At max

        result = await auth_service._is_rate_limited("test@example.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_over_threshold(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test rate limited when over max attempts."""
        mock_async_redis.get.return_value = "10"  # Over max

        result = await auth_service._is_rate_limited("test@example.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_ip_at_threshold(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test IP-based rate limiting."""
        # First call for email (under limit)
        # Second call for IP (at limit)
        mock_async_redis.get.side_effect = ["3", "10"]

        result = await auth_service._is_rate_limited(
            "test@example.com",
            client_ip="192.168.1.1"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_without_redis(
        self,
        auth_service_no_redis: AuthService
    ):
        """Test rate limiting skipped when Redis unavailable."""
        result = await auth_service_no_redis._is_rate_limited("test@example.com")

        # Should return False (not rate limited) when Redis unavailable
        assert result is False

    @pytest.mark.asyncio
    async def test_record_failed_attempt_increments_counter(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test recording failed attempt increments counter."""
        mock_async_redis.incr.return_value = 1

        await auth_service._record_failed_attempt("test@example.com")

        mock_async_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_failed_attempt_sets_ttl_on_first(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test recording first failed attempt sets TTL."""
        mock_async_redis.incr.return_value = 1  # First attempt

        await auth_service._record_failed_attempt("test@example.com")

        mock_async_redis.expire.assert_called()

    @pytest.mark.asyncio
    async def test_record_failed_attempt_with_ip(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test recording failed attempt with IP address."""
        mock_async_redis.incr.side_effect = [1, 1]  # Email and IP counters

        await auth_service._record_failed_attempt(
            "test@example.com",
            client_ip="192.168.1.1"
        )

        assert mock_async_redis.incr.call_count == 2

    @pytest.mark.asyncio
    async def test_clear_failed_attempts(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test clearing failed attempts."""
        await auth_service._clear_failed_attempts("test@example.com")

        mock_async_redis.delete.assert_called()


# ============================================================================
# Memory Fallback Tests
# ============================================================================

class TestMemoryFallback:
    """Test suite for in-memory fallback rate limiting."""

    def test_rate_limited_memory_no_attempts(
        self,
        auth_service: AuthService
    ):
        """Test memory rate limiting with no previous attempts."""
        result = auth_service._is_rate_limited_memory("test@example.com")

        assert result is False

    def test_rate_limited_memory_at_threshold(
        self,
        auth_service: AuthService
    ):
        """Test memory rate limiting at threshold."""
        email = "test@example.com"

        # Manually set up failed attempts
        auth_service._failed_attempts[email]['count'] = 5
        auth_service._failed_attempts[email]['last_attempt'] = datetime.utcnow()

        result = auth_service._is_rate_limited_memory(email)

        assert result is True

    def test_rate_limited_memory_expired_window(
        self,
        auth_service: AuthService
    ):
        """Test memory rate limiting resets after window expires."""
        email = "test@example.com"

        # Set up failed attempts that are old
        auth_service._failed_attempts[email]['count'] = 5
        auth_service._failed_attempts[email]['last_attempt'] = (
            datetime.utcnow() - timedelta(minutes=10)  # Older than 5-minute window
        )

        result = auth_service._is_rate_limited_memory(email)

        # Should reset and return False
        assert result is False

    def test_record_failed_attempt_memory(
        self,
        auth_service: AuthService
    ):
        """Test recording failed attempt in memory."""
        email = "test@example.com"

        auth_service._record_failed_attempt_memory(email)

        assert auth_service._failed_attempts[email]['count'] == 1
        assert auth_service._failed_attempts[email]['last_attempt'] is not None

    def test_record_failed_attempt_memory_increments(
        self,
        auth_service: AuthService
    ):
        """Test recording multiple failed attempts increments counter."""
        email = "test@example.com"

        for _ in range(3):
            auth_service._record_failed_attempt_memory(email)

        assert auth_service._failed_attempts[email]['count'] == 3


# ============================================================================
# Redis Connection Tests
# ============================================================================

class TestRedisConnection:
    """Test suite for Redis connection handling."""

    @pytest.mark.asyncio
    async def test_redis_is_connected_with_ping(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test Redis connection check with ping."""
        mock_async_redis.ping.return_value = True

        result = await auth_service._redis_is_connected()

        assert result is True

    @pytest.mark.asyncio
    async def test_redis_is_connected_ping_fails(
        self,
        auth_service: AuthService,
        mock_async_redis
    ):
        """Test Redis connection check when ping fails."""
        mock_async_redis.ping.side_effect = Exception("Connection refused")

        result = await auth_service._redis_is_connected()

        assert result is False

    @pytest.mark.asyncio
    async def test_redis_is_connected_no_client(
        self,
        auth_service_no_redis: AuthService
    ):
        """Test Redis connection check with no client."""
        result = await auth_service_no_redis._redis_is_connected()

        assert result is False
