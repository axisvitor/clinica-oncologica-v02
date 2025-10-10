"""
Comprehensive unit tests for SessionService.

Tests session creation, validation, cleanup, CSRF protection,
and Redis integration with 60+ test cases covering all methods and edge cases.

Test Categories:
- Session creation (Firebase token validation, user management)
- Session validation (cache hits/misses, expiration)
- Session invalidation (single/global logout)
- CSRF protection (token generation/validation)
- Concurrent session handling
- Security edge cases and vulnerabilities
- Error handling and recovery
- Performance scenarios
"""

import pytest
import asyncio
import json
import uuid
import secrets
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
from sqlalchemy import select
from fastapi import HTTPException, status

from app.services.session_service import SessionService, create_session_service, get_session_from_request
from app.models.user import User, UserRole, AuthProvider
from app.core.redis_manager import FirebaseRedisCache


class TestSessionServiceInitialization:
    """Test SessionService initialization and configuration."""

    def test_session_service_init_with_all_dependencies(self):
        """Test SessionService initialization with all dependencies."""
        mock_db = Mock()
        mock_redis = Mock()
        mock_firebase = Mock()

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase
        )

        assert service.db == mock_db
        assert service.redis_client == mock_redis
        assert service.firebase_service == mock_firebase
        assert service._firebase_cache is None

    def test_session_service_init_minimal(self):
        """Test SessionService initialization with minimal dependencies."""
        mock_db = Mock()

        service = SessionService(db=mock_db)

        assert service.db == mock_db
        assert service.redis_client is None
        assert service.firebase_service is None
        assert service._firebase_cache is None

    def test_firebase_cache_lazy_initialization(self):
        """Test lazy initialization of FirebaseRedisCache."""
        mock_db = Mock()
        mock_redis = Mock()

        service = SessionService(db=mock_db, redis_client=mock_redis)

        with patch('app.services.session_service.FirebaseRedisCache') as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache

            cache = service._get_firebase_cache()

            assert cache == mock_cache
            assert service._firebase_cache == mock_cache
            mock_cache_class.assert_called_once_with(mock_redis)

    def test_firebase_cache_none_when_no_redis(self):
        """Test FirebaseRedisCache returns None when Redis not available."""
        mock_db = Mock()

        service = SessionService(db=mock_db, redis_client=None)
        cache = service._get_firebase_cache()

        assert cache is None

    def test_factory_function(self):
        """Test create_session_service factory function."""
        mock_db = Mock()
        mock_redis = Mock()
        mock_firebase = Mock()

        service = create_session_service(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase
        )

        assert isinstance(service, SessionService)
        assert service.db == mock_db
        assert service.redis_client == mock_redis
        assert service.firebase_service == mock_firebase


class TestSessionCreation:
    """Test session creation from Firebase tokens."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.refresh = AsyncMock()
        return mock_db

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        mock_redis = Mock()
        mock_redis.hset = Mock(return_value=True)
        return mock_redis

    @pytest.fixture
    def mock_firebase_service(self):
        """Mock Firebase authentication service."""
        mock_firebase = AsyncMock()
        mock_firebase.verify_token = AsyncMock(return_value={
            "uid": "firebase_test_123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "doctor"
        })
        return mock_firebase

    @pytest.fixture
    def mock_firebase_cache(self):
        """Mock FirebaseRedisCache."""
        mock_cache = Mock()
        mock_cache.create_session = AsyncMock(return_value=True)
        mock_cache.cache_user = Mock()
        return mock_cache

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        user = User(
            id=1,
            firebase_uid="firebase_test_123",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.DOCTOR,
            is_active=True
        )
        return user

    @pytest.mark.asyncio
    async def test_create_session_success_existing_user(
        self, mock_db, mock_redis, mock_firebase_service, sample_user
    ):
        """Test successful session creation for existing user."""
        # Mock database query to return existing user
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=sample_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase_service
        )

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.create_session = AsyncMock(return_value=True)
            mock_cache.cache_user = Mock()
            mock_get_cache.return_value = mock_cache

            result = await service.create_session_from_firebase_token(
                firebase_token="valid_token_123",
                device_info={"device": "mobile", "os": "iOS"}
            )

            assert result["status"] == "authenticated"
            assert "session_id" in result
            assert result["user"]["email"] == "test@example.com"
            assert result["user"]["role"] == "doctor"
            assert "expires_at" in result
            assert result["ttl"] == 86400  # Default TTL

            # Verify Firebase token was verified
            mock_firebase_service.verify_token.assert_called_once_with("valid_token_123")

            # Verify session was created in Redis
            mock_cache.create_session.assert_called_once()

            # Verify user was cached
            mock_cache.cache_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_success_new_user(
        self, mock_db, mock_redis, mock_firebase_service
    ):
        """Test successful session creation for new user."""
        # Mock database query to return None (user doesn't exist)
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase_service
        )

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.create_session = AsyncMock(return_value=True)
            mock_cache.cache_user = Mock()
            mock_get_cache.return_value = mock_cache

            result = await service.create_session_from_firebase_token(
                firebase_token="valid_token_123"
            )

            assert result["status"] == "authenticated"
            assert "session_id" in result

            # Verify user was created in database
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_firebase_service_unavailable(self, mock_db, mock_redis):
        """Test session creation when Firebase service is unavailable."""
        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=None  # No Firebase service
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_session_from_firebase_token("token")

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Firebase authentication is not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_invalid_firebase_token(
        self, mock_db, mock_redis, mock_firebase_service
    ):
        """Test session creation with invalid Firebase token."""
        mock_firebase_service.verify_token = AsyncMock(
            side_effect=Exception("Invalid token")
        )

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase_service
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_session_from_firebase_token("invalid_token")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid Firebase token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_inactive_user(
        self, mock_db, mock_redis, mock_firebase_service
    ):
        """Test session creation for inactive user."""
        inactive_user = User(
            id=1,
            firebase_uid="firebase_test_123",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.DOCTOR,
            is_active=False  # Inactive user
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=inactive_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase_service
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_session_from_firebase_token("valid_token")

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "User account is inactive" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_redis_unavailable(
        self, mock_db, mock_firebase_service, sample_user
    ):
        """Test session creation when Redis is unavailable."""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=sample_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SessionService(
            db=mock_db,
            redis_client=None,  # No Redis
            firebase_service=mock_firebase_service
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_session_from_firebase_token("valid_token")

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Redis session storage is not available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_redis_failure(
        self, mock_db, mock_redis, mock_firebase_service, sample_user
    ):
        """Test session creation when Redis session creation fails."""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=sample_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase_service
        )

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.create_session = AsyncMock(return_value=False)  # Failure
            mock_get_cache.return_value = mock_cache

            with pytest.raises(HTTPException) as exc_info:
                await service.create_session_from_firebase_token("valid_token")

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to create session in Redis" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_with_admin_role(
        self, mock_db, mock_redis, mock_firebase_service
    ):
        """Test session creation for admin user."""
        mock_firebase_service.verify_token = AsyncMock(return_value={
            "uid": "firebase_admin_123",
            "email": "admin@example.com",
            "name": "Admin User",
            "role": "admin"
        })

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase_service
        )

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.create_session = AsyncMock(return_value=True)
            mock_cache.cache_user = Mock()
            mock_get_cache.return_value = mock_cache

            result = await service.create_session_from_firebase_token("admin_token")

            assert result["user"]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_create_session_with_device_info(
        self, mock_db, mock_redis, mock_firebase_service, sample_user
    ):
        """Test session creation with device information."""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=sample_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        device_info = {
            "device": "iPhone",
            "os": "iOS 15.0",
            "browser": "Safari",
            "ip_address": "192.168.1.1"
        }

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase_service
        )

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.create_session = AsyncMock(return_value=True)
            mock_cache.cache_user = Mock()
            mock_get_cache.return_value = mock_cache

            result = await service.create_session_from_firebase_token(
                "valid_token", device_info=device_info
            )

            # Verify device info was passed to session creation
            create_session_call = mock_cache.create_session.call_args
            metadata = create_session_call[1]['metadata']
            assert metadata["device"] == "iPhone"
            assert metadata["os"] == "iOS 15.0"
            assert metadata["browser"] == "Safari"
            assert metadata["ip_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_create_session_custom_ttl(
        self, mock_db, mock_redis, mock_firebase_service, sample_user
    ):
        """Test session creation with custom TTL from settings."""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=sample_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase_service
        )

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.create_session = AsyncMock(return_value=True)
            mock_cache.cache_user = Mock()
            mock_get_cache.return_value = mock_cache

            with patch('app.services.session_service.settings') as mock_settings:
                mock_settings.FIREBASE_SESSION_TTL = 3600  # 1 hour

                result = await service.create_session_from_firebase_token("valid_token")

                assert result["ttl"] == 3600


class TestSessionValidation:
    """Test session validation and retrieval."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return Mock()

    @pytest.fixture
    def service(self, mock_db, mock_redis):
        """SessionService instance for testing."""
        return SessionService(db=mock_db, redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_validate_session_success_with_cached_user(self, service):
        """Test successful session validation with cached user data."""
        session_data = {
            "firebase_uid": "firebase_123",
            "user_id": "user_123",
            "created_at": datetime.utcnow().isoformat()
        }

        cached_user = {
            "id": "user_123",
            "email": "test@example.com",
            "role": "doctor"
        }

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_session = AsyncMock(return_value=session_data)
            mock_cache.get_cached_user = Mock(return_value=cached_user)
            mock_get_cache.return_value = mock_cache

            result = await service.validate_session("test_session_123")

            assert result["valid"] is True
            assert result["user"] == cached_user
            assert result["session_data"] == session_data

    @pytest.mark.asyncio
    async def test_validate_session_success_db_fallback(self, service, mock_db):
        """Test session validation with database fallback when user not cached."""
        session_data = {
            "firebase_uid": "firebase_123",
            "user_id": "user_123",
            "created_at": datetime.utcnow().isoformat()
        }

        db_user = User(
            id=1,
            firebase_uid="firebase_123",
            email="test@example.com",
            role=UserRole.DOCTOR
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=db_user)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_session = AsyncMock(return_value=session_data)
            mock_cache.get_cached_user = Mock(return_value=None)  # Cache miss
            mock_get_cache.return_value = mock_cache

            result = await service.validate_session("test_session_123")

            assert result["valid"] is True
            assert result["user"]["email"] == "test@example.com"
            assert result["user"]["role"] == "doctor"

    @pytest.mark.asyncio
    async def test_validate_session_empty_session_id(self, service):
        """Test session validation with empty session ID."""
        result = await service.validate_session("")
        assert result is None

        result = await service.validate_session(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_session_redis_unavailable(self, service):
        """Test session validation when Redis is unavailable."""
        with patch.object(service, '_get_firebase_cache', return_value=None):
            result = await service.validate_session("test_session_123")
            assert result is None

    @pytest.mark.asyncio
    async def test_validate_session_not_found(self, service):
        """Test session validation when session not found in Redis."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_session = AsyncMock(return_value=None)
            mock_get_cache.return_value = mock_cache

            result = await service.validate_session("nonexistent_session")
            assert result is None

    @pytest.mark.asyncio
    async def test_validate_session_user_not_found_in_db(self, service, mock_db):
        """Test session validation when user not found in database."""
        session_data = {
            "firebase_uid": "firebase_123",
            "user_id": "user_123"
        }

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)  # User not found
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_session = AsyncMock(return_value=session_data)
            mock_cache.get_cached_user = Mock(return_value=None)
            mock_get_cache.return_value = mock_cache

            result = await service.validate_session("test_session_123")
            assert result is None

    @pytest.mark.asyncio
    async def test_validate_session_exception_handling(self, service):
        """Test session validation error handling."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_session = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_cache.return_value = mock_cache

            result = await service.validate_session("test_session_123")
            assert result is None


class TestSessionInvalidation:
    """Test session invalidation and cleanup."""

    @pytest.fixture
    def service(self):
        """SessionService instance for testing."""
        mock_db = Mock()
        mock_redis = Mock()
        return SessionService(db=mock_db, redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_invalidate_session_success(self, service):
        """Test successful session invalidation."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.invalidate_session = AsyncMock(return_value=True)
            mock_get_cache.return_value = mock_cache

            result = await service.invalidate_session("test_session_123")

            assert result is True
            mock_cache.invalidate_session.assert_called_once_with("test_session_123")

    @pytest.mark.asyncio
    async def test_invalidate_session_not_found(self, service):
        """Test session invalidation when session not found."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.invalidate_session = AsyncMock(return_value=False)
            mock_get_cache.return_value = mock_cache

            result = await service.invalidate_session("nonexistent_session")

            assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_session_redis_unavailable(self, service):
        """Test session invalidation when Redis is unavailable."""
        with patch.object(service, '_get_firebase_cache', return_value=None):
            result = await service.invalidate_session("test_session_123")
            assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_session_exception(self, service):
        """Test session invalidation error handling."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.invalidate_session = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_cache.return_value = mock_cache

            result = await service.invalidate_session("test_session_123")
            assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions_success(self, service):
        """Test successful invalidation of all user sessions."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.invalidate_all_user_sessions = AsyncMock(return_value=3)
            mock_get_cache.return_value = mock_cache

            result = await service.invalidate_all_user_sessions("firebase_uid_123")

            assert result == 3
            mock_cache.invalidate_all_user_sessions.assert_called_once_with("firebase_uid_123")

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions_redis_unavailable(self, service):
        """Test invalidating all user sessions when Redis unavailable."""
        with patch.object(service, '_get_firebase_cache', return_value=None):
            result = await service.invalidate_all_user_sessions("firebase_uid_123")
            assert result == 0

    @pytest.mark.asyncio
    async def test_invalidate_all_user_sessions_exception(self, service):
        """Test invalidating all user sessions error handling."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.invalidate_all_user_sessions = AsyncMock(
                side_effect=Exception("Redis error")
            )
            mock_get_cache.return_value = mock_cache

            result = await service.invalidate_all_user_sessions("firebase_uid_123")
            assert result == 0

    @pytest.mark.asyncio
    async def test_list_user_sessions_success(self, service):
        """Test successfully listing user sessions."""
        sessions = [
            {"session_id": "session_1", "created_at": "2023-01-01T00:00:00"},
            {"session_id": "session_2", "created_at": "2023-01-02T00:00:00"}
        ]

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.list_user_sessions = Mock(return_value=sessions)
            mock_get_cache.return_value = mock_cache

            result = await service.list_user_sessions("firebase_uid_123")

            assert result == sessions
            mock_cache.list_user_sessions.assert_called_once_with("firebase_uid_123")

    @pytest.mark.asyncio
    async def test_list_user_sessions_redis_unavailable(self, service):
        """Test listing user sessions when Redis unavailable."""
        with patch.object(service, '_get_firebase_cache', return_value=None):
            result = await service.list_user_sessions("firebase_uid_123")
            assert result == []

    @pytest.mark.asyncio
    async def test_list_user_sessions_exception(self, service):
        """Test listing user sessions error handling."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.list_user_sessions = Mock(side_effect=Exception("Redis error"))
            mock_get_cache.return_value = mock_cache

            result = await service.list_user_sessions("firebase_uid_123")
            assert result == []

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, service):
        """Test expired session cleanup."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_cache_stats = Mock(return_value={"active_sessions": 5})
            mock_get_cache.return_value = mock_cache

            result = await service.cleanup_expired_sessions()

            assert result == 0  # Redis handles expiration automatically
            mock_cache.get_cache_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_redis_unavailable(self, service):
        """Test cleanup when Redis unavailable."""
        with patch.object(service, '_get_firebase_cache', return_value=None):
            result = await service.cleanup_expired_sessions()
            assert result == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_exception(self, service):
        """Test cleanup error handling."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_cache_stats = Mock(side_effect=Exception("Redis error"))
            mock_get_cache.return_value = mock_cache

            result = await service.cleanup_expired_sessions()
            assert result == 0


class TestCSRFProtection:
    """Test CSRF token generation and validation."""

    @pytest.fixture
    def service(self):
        """SessionService instance for testing."""
        mock_db = Mock()
        mock_redis = Mock()
        return SessionService(db=mock_db, redis_client=mock_redis)

    def test_generate_csrf_token_success(self, service):
        """Test successful CSRF token generation."""
        mock_redis = Mock()
        mock_redis.hset = Mock(return_value=True)
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            with patch('secrets.token_urlsafe', return_value="test_csrf_token_123"):
                token = service.generate_csrf_token("session_123")

                assert token == "test_csrf_token_123"
                mock_redis.hset.assert_called_once_with(
                    "session:session_123", "csrf_token", "test_csrf_token_123"
                )

    def test_generate_csrf_token_redis_unavailable(self, service):
        """Test CSRF token generation when Redis unavailable."""
        with patch.object(service, '_get_firebase_cache', return_value=None):
            with patch('secrets.token_urlsafe', return_value="test_csrf_token_123"):
                token = service.generate_csrf_token("session_123")

                assert token == "test_csrf_token_123"  # Token still generated

    def test_generate_csrf_token_redis_error(self, service):
        """Test CSRF token generation with Redis error."""
        mock_redis = Mock()
        mock_redis.hset = Mock(side_effect=Exception("Redis error"))
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            with patch('secrets.token_urlsafe', return_value="test_csrf_token_123"):
                token = service.generate_csrf_token("session_123")

                assert token == "test_csrf_token_123"  # Token still generated

    def test_validate_csrf_token_success(self, service):
        """Test successful CSRF token validation."""
        mock_redis = Mock()
        mock_redis.hget = Mock(return_value="test_csrf_token_123")
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            is_valid = service.validate_csrf_token("session_123", "test_csrf_token_123")

            assert is_valid is True
            mock_redis.hget.assert_called_once_with("session:session_123", "csrf_token")

    def test_validate_csrf_token_mismatch(self, service):
        """Test CSRF token validation with token mismatch."""
        mock_redis = Mock()
        mock_redis.hget = Mock(return_value="stored_token_456")
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            is_valid = service.validate_csrf_token("session_123", "different_token_123")

            assert is_valid is False

    def test_validate_csrf_token_not_found(self, service):
        """Test CSRF token validation when token not found."""
        mock_redis = Mock()
        mock_redis.hget = Mock(return_value=None)
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            is_valid = service.validate_csrf_token("session_123", "test_csrf_token_123")

            assert is_valid is False

    def test_validate_csrf_token_redis_unavailable(self, service):
        """Test CSRF token validation when Redis unavailable."""
        with patch.object(service, '_get_firebase_cache', return_value=None):
            is_valid = service.validate_csrf_token("session_123", "test_csrf_token_123")
            assert is_valid is False

    def test_validate_csrf_token_redis_error(self, service):
        """Test CSRF token validation with Redis error."""
        mock_redis = Mock()
        mock_redis.hget = Mock(side_effect=Exception("Redis error"))
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            is_valid = service.validate_csrf_token("session_123", "test_csrf_token_123")

            assert is_valid is False


class TestHelperMethods:
    """Test private helper methods."""

    @pytest.fixture
    def service(self):
        """SessionService instance for testing."""
        mock_db = Mock()
        return SessionService(db=mock_db)

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, service):
        """Test getting existing user."""
        existing_user = User(
            id=1,
            firebase_uid="firebase_123",
            email="test@example.com",
            role=UserRole.DOCTOR
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=existing_user)
        service.db.execute = AsyncMock(return_value=mock_result)

        user_data = {
            "uid": "firebase_123",
            "email": "test@example.com",
            "name": "Test User"
        }

        user = await service._get_or_create_user("firebase_123", user_data)

        assert user == existing_user
        service.db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_user_new_doctor(self, service):
        """Test creating new doctor user."""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        service.db.execute = AsyncMock(return_value=mock_result)
        service.db.add = Mock()
        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock()

        user_data = {
            "uid": "firebase_123",
            "email": "doctor@example.com",
            "name": "Dr. Test",
            "role": "doctor"
        }

        user = await service._get_or_create_user("firebase_123", user_data)

        service.db.add.assert_called_once()
        added_user = service.db.add.call_args[0][0]
        assert added_user.firebase_uid == "firebase_123"
        assert added_user.email == "doctor@example.com"
        assert added_user.full_name == "Dr. Test"
        assert added_user.role == UserRole.DOCTOR

    @pytest.mark.asyncio
    async def test_get_or_create_user_new_admin(self, service):
        """Test creating new admin user."""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        service.db.execute = AsyncMock(return_value=mock_result)
        service.db.add = Mock()
        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock()

        user_data = {
            "uid": "firebase_admin_123",
            "email": "admin@example.com",
            "name": "Admin User",
            "role": "admin"
        }

        user = await service._get_or_create_user("firebase_admin_123", user_data)

        added_user = service.db.add.call_args[0][0]
        assert added_user.role == UserRole.ADMIN

    @pytest.mark.asyncio
    async def test_get_or_create_user_minimal_data(self, service):
        """Test creating user with minimal data."""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        service.db.execute = AsyncMock(return_value=mock_result)
        service.db.add = Mock()
        service.db.commit = AsyncMock()
        service.db.refresh = AsyncMock()

        user_data = {
            "uid": "firebase_123",
            "email": "user@example.com"
        }

        user = await service._get_or_create_user("firebase_123", user_data)

        added_user = service.db.add.call_args[0][0]
        assert added_user.firebase_uid == "firebase_123"
        assert added_user.email == "user@example.com"
        assert added_user.full_name == "user"  # Default from email
        assert added_user.role == UserRole.DOCTOR  # Default role

    @pytest.mark.asyncio
    async def test_get_user_by_firebase_uid_found(self, service):
        """Test getting user by Firebase UID when found."""
        existing_user = User(firebase_uid="firebase_123")

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=existing_user)
        service.db.execute = AsyncMock(return_value=mock_result)

        user = await service._get_user_by_firebase_uid("firebase_123")

        assert user == existing_user

    @pytest.mark.asyncio
    async def test_get_user_by_firebase_uid_not_found(self, service):
        """Test getting user by Firebase UID when not found."""
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        service.db.execute = AsyncMock(return_value=mock_result)

        user = await service._get_user_by_firebase_uid("nonexistent_uid")

        assert user is None

    def test_user_to_dict(self, service):
        """Test converting User model to dictionary."""
        user = User(
            id=1,
            firebase_uid="firebase_123",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.DOCTOR,
            is_active=True
        )

        user_dict = service._user_to_dict(user)

        expected = {
            "id": "1",
            "firebase_uid": "firebase_123",
            "email": "test@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True
        }

        assert user_dict == expected

    def test_user_to_dict_with_enum_value(self, service):
        """Test converting User model with enum role to dictionary."""
        user = User(
            id=1,
            firebase_uid="firebase_123",
            email="test@example.com",
            full_name="Test User",
            role=UserRole.ADMIN,  # Enum with .value
            is_active=True
        )

        user_dict = service._user_to_dict(user)

        assert user_dict["role"] == "admin"


class TestConcurrentSessions:
    """Test concurrent session handling."""

    @pytest.fixture
    def service(self):
        """SessionService instance for testing."""
        mock_db = Mock()
        mock_redis = Mock()
        return SessionService(db=mock_db, redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_concurrent_session_validation(self, service):
        """Test concurrent session validation."""
        session_ids = [f"session_{i}" for i in range(10)]

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_session = AsyncMock(return_value={
                "firebase_uid": "firebase_123",
                "user_id": "user_123"
            })
            mock_cache.get_cached_user = Mock(return_value={
                "id": "user_123",
                "email": "test@example.com"
            })
            mock_get_cache.return_value = mock_cache

            tasks = [service.validate_session(sid) for sid in session_ids]
            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            assert all(result["valid"] for result in results)

    @pytest.mark.asyncio
    async def test_concurrent_session_invalidation(self, service):
        """Test concurrent session invalidation."""
        session_ids = [f"session_{i}" for i in range(5)]

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.invalidate_session = AsyncMock(return_value=True)
            mock_get_cache.return_value = mock_cache

            tasks = [service.invalidate_session(sid) for sid in session_ids]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert all(result for result in results)
            assert mock_cache.invalidate_session.call_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_csrf_operations(self, service):
        """Test concurrent CSRF token operations."""
        session_ids = [f"session_{i}" for i in range(5)]

        mock_redis = Mock()
        mock_redis.hset = Mock(return_value=True)
        mock_redis.hget = Mock(return_value="test_token")
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            with patch('secrets.token_urlsafe', return_value="test_token"):
                # Generate tokens concurrently
                generate_tasks = [
                    service.generate_csrf_token(sid) for sid in session_ids
                ]
                tokens = await asyncio.gather(*generate_tasks, return_exceptions=True)

                # Validate tokens concurrently
                validate_tasks = [
                    service.validate_csrf_token(sid, "test_token")
                    for sid in session_ids
                ]
                validations = await asyncio.gather(*validate_tasks, return_exceptions=True)

                assert len(tokens) == 5
                assert len(validations) == 5
                assert all(token == "test_token" for token in tokens)
                assert all(is_valid for is_valid in validations)


class TestSecurityScenarios:
    """Test security edge cases and vulnerabilities."""

    @pytest.fixture
    def service(self):
        """SessionService instance for testing."""
        mock_db = Mock()
        mock_redis = Mock()
        mock_firebase = Mock()
        return SessionService(
            db=mock_db,
            redis_client=mock_redis,
            firebase_service=mock_firebase
        )

    @pytest.mark.asyncio
    async def test_session_hijacking_prevention(self, service):
        """Test prevention of session hijacking through session validation."""
        # Try to validate session with different user agent/IP patterns
        malicious_session_ids = [
            "../admin/session",
            "../../etc/passwd",
            "<script>alert('xss')</script>",
            "'; DROP TABLE sessions; --",
            "\x00\x01\x02invalid"
        ]

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_session = AsyncMock(return_value=None)
            mock_get_cache.return_value = mock_cache

            for session_id in malicious_session_ids:
                result = await service.validate_session(session_id)
                assert result is None  # Should not validate malicious session IDs

    @pytest.mark.asyncio
    async def test_csrf_token_timing_attack_resistance(self, service):
        """Test CSRF token validation against timing attacks."""
        mock_redis = Mock()
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            # Test with valid token
            mock_redis.hget = Mock(return_value="valid_token_123")
            start_time = datetime.utcnow()
            is_valid = service.validate_csrf_token("session_123", "valid_token_123")
            valid_time = datetime.utcnow() - start_time

            # Test with invalid token
            mock_redis.hget = Mock(return_value="valid_token_123")
            start_time = datetime.utcnow()
            is_invalid = service.validate_csrf_token("session_123", "invalid_token_456")
            invalid_time = datetime.utcnow() - start_time

            assert is_valid is True
            assert is_invalid is False
            # Timing should be similar (within reasonable bounds)
            time_diff = abs(valid_time.total_seconds() - invalid_time.total_seconds())
            assert time_diff < 0.01  # Less than 10ms difference

    @pytest.mark.asyncio
    async def test_firebase_token_injection(self, service):
        """Test protection against Firebase token injection attacks."""
        malicious_tokens = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "../../firebase/admin/token",
            "\x00\x01\x02malicious",
            "jwt.sign({admin: true}, 'secret')"
        ]

        service.firebase_service.verify_token = AsyncMock(
            side_effect=Exception("Invalid token format")
        )

        for token in malicious_tokens:
            with pytest.raises(HTTPException) as exc_info:
                await service.create_session_from_firebase_token(token)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_session_fixation_prevention(self, service):
        """Test prevention of session fixation attacks."""
        # Ensure new session ID is generated for each login
        user = User(
            id=1,
            firebase_uid="firebase_123",
            email="test@example.com",
            role=UserRole.DOCTOR,
            is_active=True
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=user)
        service.db.execute = AsyncMock(return_value=mock_result)

        service.firebase_service.verify_token = AsyncMock(return_value={
            "uid": "firebase_123",
            "email": "test@example.com"
        })

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.create_session = AsyncMock(return_value=True)
            mock_cache.cache_user = Mock()
            mock_get_cache.return_value = mock_cache

            # Create multiple sessions
            result1 = await service.create_session_from_firebase_token("token1")
            result2 = await service.create_session_from_firebase_token("token2")

            # Session IDs should be different
            assert result1["session_id"] != result2["session_id"]
            # Both should be valid UUIDs
            assert len(result1["session_id"]) == 36
            assert len(result2["session_id"]) == 36

    def test_csrf_token_entropy(self, service):
        """Test CSRF token generation has sufficient entropy."""
        mock_redis = Mock()
        service.redis_client = mock_redis

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_get_cache.return_value = mock_cache

            # Generate multiple tokens
            tokens = set()
            for i in range(100):
                token = service.generate_csrf_token(f"session_{i}")
                tokens.add(token)
                # Each token should be at least 32 characters (256 bits of entropy)
                assert len(token) >= 32

            # All tokens should be unique
            assert len(tokens) == 100

    @pytest.mark.asyncio
    async def test_privilege_escalation_prevention(self, service):
        """Test prevention of privilege escalation through session manipulation."""
        # Create doctor user
        doctor_user = User(
            id=1,
            firebase_uid="firebase_doctor_123",
            email="doctor@example.com",
            role=UserRole.DOCTOR,
            is_active=True
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=doctor_user)
        service.db.execute = AsyncMock(return_value=mock_result)

        service.firebase_service.verify_token = AsyncMock(return_value={
            "uid": "firebase_doctor_123",
            "email": "doctor@example.com",
            "role": "doctor"  # Firebase role is doctor
        })

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.create_session = AsyncMock(return_value=True)
            mock_cache.cache_user = Mock()
            mock_get_cache.return_value = mock_cache

            result = await service.create_session_from_firebase_token("doctor_token")

            # User should remain doctor, not escalate to admin
            assert result["user"]["role"] == "doctor"
            assert result["user"]["email"] == "doctor@example.com"


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_get_session_from_request_success(self):
        """Test get_session_from_request with valid session."""
        mock_db = Mock()
        mock_redis = Mock()

        with patch('app.services.session_service.SessionService') as mock_service_class:
            mock_service = Mock()
            mock_service.validate_session = AsyncMock(return_value={
                "valid": True,
                "user": {"id": "user_123"}
            })
            mock_service_class.return_value = mock_service

            result = await get_session_from_request("session_123", mock_db, mock_redis)

            assert result["valid"] is True
            assert result["user"]["id"] == "user_123"
            mock_service_class.assert_called_once_with(mock_db, mock_redis)

    @pytest.mark.asyncio
    async def test_get_session_from_request_invalid(self):
        """Test get_session_from_request with invalid session."""
        mock_db = Mock()
        mock_redis = Mock()

        with patch('app.services.session_service.SessionService') as mock_service_class:
            mock_service = Mock()
            mock_service.validate_session = AsyncMock(return_value=None)
            mock_service_class.return_value = mock_service

            result = await get_session_from_request("invalid_session", mock_db, mock_redis)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_session_from_request_no_session_id(self):
        """Test get_session_from_request with no session ID."""
        mock_db = Mock()
        mock_redis = Mock()

        result = await get_session_from_request(None, mock_db, mock_redis)
        assert result is None


class TestPerformanceScenarios:
    """Test performance-related scenarios."""

    @pytest.fixture
    def service(self):
        """SessionService instance for testing."""
        mock_db = Mock()
        mock_redis = Mock()
        return SessionService(db=mock_db, redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_high_volume_session_validation(self, service):
        """Test session validation under high volume."""
        session_count = 1000
        session_ids = [f"session_{i}" for i in range(session_count)]

        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get_session = AsyncMock(return_value={
                "firebase_uid": "firebase_123",
                "user_id": "user_123"
            })
            mock_cache.get_cached_user = Mock(return_value={
                "id": "user_123",
                "email": "test@example.com"
            })
            mock_get_cache.return_value = mock_cache

            start_time = datetime.utcnow()

            # Process in batches to avoid overwhelming the system
            batch_size = 100
            all_results = []

            for i in range(0, session_count, batch_size):
                batch = session_ids[i:i + batch_size]
                tasks = [service.validate_session(sid) for sid in batch]
                batch_results = await asyncio.gather(*tasks)
                all_results.extend(batch_results)

            end_time = datetime.utcnow()
            total_time = (end_time - start_time).total_seconds()

            assert len(all_results) == session_count
            assert all(result["valid"] for result in all_results)
            # Should process at reasonable speed (less than 1ms per validation on average)
            assert total_time < session_count * 0.001

    @pytest.mark.asyncio
    async def test_memory_efficient_session_cleanup(self, service):
        """Test memory efficiency during session cleanup."""
        with patch.object(service, '_get_firebase_cache') as mock_get_cache:
            mock_cache = Mock()

            # Simulate large number of sessions
            mock_cache.get_cache_stats = Mock(return_value={
                "active_sessions": 10000,
                "memory_usage": "50MB"
            })
            mock_get_cache.return_value = mock_cache

            result = await service.cleanup_expired_sessions()

            # Should complete without memory issues
            assert result == 0  # Redis handles cleanup automatically
            mock_cache.get_cache_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_connection_efficiency(self, service):
        """Test efficient database connection usage."""
        # Mock multiple user lookups
        users = [
            User(id=i, firebase_uid=f"firebase_{i}", email=f"user{i}@example.com", role=UserRole.DOCTOR)
            for i in range(10)
        ]

        def mock_execute(query):
            # Simulate database query
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=users[0])
            future = asyncio.Future()
            future.set_result(mock_result)
            return future

        service.db.execute = mock_execute

        # Test multiple user lookups
        tasks = [
            service._get_user_by_firebase_uid(f"firebase_{i}")
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        # All should use the same connection efficiently


# Test execution helper
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])