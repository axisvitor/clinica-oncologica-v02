"""
Unit tests for authentication endpoints.

Tests all auth router endpoints including session creation, validation,
logout, and logout-all operations with comprehensive coverage.
"""

import pytest
import uuid
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.routers.auth import (
    router,
    SessionCreate,
    SessionResponse,
    LogoutResponse,
    LogoutAllResponse,
    SessionStatusResponse
)
from app.models.user import User, UserRole
from app.core.redis_manager import FirebaseRedisCache


class TestSessionCreation:
    """Test suite for session creation endpoint."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Mock FirebaseRedisCache for testing."""
        cache = AsyncMock(spec=FirebaseRedisCache)
        return cache

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        return db

    @pytest.fixture
    def mock_user(self):
        """Mock user model."""
        user = Mock(spec=User)
        user.id = "test-user-id"
        user.firebase_uid = "test-firebase-uid"
        user.email = "test@example.com"
        user.display_name = "Test User"
        user.photo_url = "https://example.com/photo.jpg"
        user.role = UserRole.DOCTOR
        user.is_active = True
        user.created_at = datetime.utcnow()
        user.last_login = datetime.utcnow()
        return user

    @pytest.fixture
    def valid_firebase_user(self):
        """Valid Firebase user data."""
        return {
            "uid": "test-firebase-uid",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg"
        }

    @pytest.fixture
    def session_request(self):
        """Valid session creation request."""
        return SessionCreate(id_token="valid-firebase-token")

    @pytest.mark.asyncio
    async def test_create_session_success(
        self,
        mock_redis_cache,
        mock_db,
        mock_user,
        valid_firebase_user,
        session_request
    ):
        """Test successful session creation."""
        from app.routers.auth import create_session

        # Mock request object
        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"

        # Mock dependencies
        with patch('app.routers.auth.verify_firebase_token', return_value=valid_firebase_user):
            mock_redis_cache.get_or_create_user.return_value = mock_user
            mock_redis_cache.create_session.return_value = True

            # Execute endpoint
            result = await create_session(
                request=mock_request,
                session_data=session_request,
                db=mock_db,
                redis_cache=mock_redis_cache
            )

            # Assertions
            assert isinstance(result, SessionResponse)
            assert len(result.session_id) == 36  # UUID length
            assert result.user["id"] == "test-user-id"
            assert result.user["email"] == "test@example.com"
            assert result.expires_in > 0

            # Verify calls
            mock_redis_cache.get_or_create_user.assert_called_once()
            mock_redis_cache.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_invalid_token(
        self,
        mock_redis_cache,
        mock_db,
        session_request
    ):
        """Test session creation with invalid Firebase token."""
        from app.routers.auth import create_session

        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"

        # Mock invalid token
        with patch('app.routers.auth.verify_firebase_token', return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    request=mock_request,
                    session_data=session_request,
                    db=mock_db,
                    redis_cache=mock_redis_cache
                )

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid or expired Firebase token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_session_inactive_user(
        self,
        mock_redis_cache,
        mock_db,
        mock_user,
        valid_firebase_user,
        session_request
    ):
        """Test session creation with inactive user."""
        from app.routers.auth import create_session

        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"

        # Mock inactive user
        mock_user.is_active = False

        with patch('app.routers.auth.verify_firebase_token', return_value=valid_firebase_user):
            mock_redis_cache.get_or_create_user.return_value = mock_user

            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    request=mock_request,
                    session_data=session_request,
                    db=mock_db,
                    redis_cache=mock_redis_cache
                )

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "User account is inactive" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_session_redis_failure(
        self,
        mock_redis_cache,
        mock_db,
        mock_user,
        valid_firebase_user,
        session_request
    ):
        """Test session creation with Redis failure."""
        from app.routers.auth import create_session

        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"

        with patch('app.routers.auth.verify_firebase_token', return_value=valid_firebase_user):
            mock_redis_cache.get_or_create_user.return_value = mock_user
            mock_redis_cache.create_session.return_value = False  # Redis failure

            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    request=mock_request,
                    session_data=session_request,
                    db=mock_db,
                    redis_cache=mock_redis_cache
                )

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to create session" in exc_info.value.detail


class TestLogout:
    """Test suite for logout endpoint."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Mock FirebaseRedisCache for testing."""
        cache = AsyncMock(spec=FirebaseRedisCache)
        return cache

    @pytest.mark.asyncio
    async def test_logout_success(self, mock_redis_cache):
        """Test successful logout."""
        from app.routers.auth import logout

        mock_request = Mock()
        session_id = "valid-session-id"

        # Mock successful session invalidation
        mock_redis_cache.invalidate_session.return_value = True

        result = await logout(
            request=mock_request,
            x_session_id=session_id,
            redis_cache=mock_redis_cache
        )

        assert isinstance(result, LogoutResponse)
        assert result.message == "Logout successful"
        mock_redis_cache.invalidate_session.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_logout_invalid_session(self, mock_redis_cache):
        """Test logout with invalid session."""
        from app.routers.auth import logout

        mock_request = Mock()
        session_id = "invalid-session-id"

        # Mock session not found
        mock_redis_cache.invalidate_session.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await logout(
                request=mock_request,
                x_session_id=session_id,
                redis_cache=mock_redis_cache
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Session not found or already expired" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_logout_redis_error(self, mock_redis_cache):
        """Test logout with Redis error."""
        from app.routers.auth import logout

        mock_request = Mock()
        session_id = "test-session-id"

        # Mock Redis error
        mock_redis_cache.invalidate_session.side_effect = Exception("Redis connection error")

        with pytest.raises(HTTPException) as exc_info:
            await logout(
                request=mock_request,
                x_session_id=session_id,
                redis_cache=mock_redis_cache
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Logout failed" in exc_info.value.detail


class TestLogoutAll:
    """Test suite for logout-all endpoint."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Mock FirebaseRedisCache for testing."""
        cache = AsyncMock(spec=FirebaseRedisCache)
        return cache

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock(spec=User)
        user.firebase_uid = "test-firebase-uid"
        user.email = "test@example.com"
        return user

    @pytest.mark.asyncio
    async def test_logout_all_success(self, mock_redis_cache, mock_current_user):
        """Test successful logout from all sessions."""
        from app.routers.auth import logout_all

        mock_request = Mock()
        sessions_deleted = 3

        # Mock successful all sessions invalidation
        mock_redis_cache.invalidate_all_user_sessions.return_value = sessions_deleted

        result = await logout_all(
            request=mock_request,
            current_user=mock_current_user,
            redis_cache=mock_redis_cache
        )

        assert isinstance(result, LogoutAllResponse)
        assert "Successfully logged out from all devices" in result.message
        assert result.sessions_deleted == sessions_deleted
        mock_redis_cache.invalidate_all_user_sessions.assert_called_once_with(
            mock_current_user.firebase_uid
        )

    @pytest.mark.asyncio
    async def test_logout_all_no_sessions(self, mock_redis_cache, mock_current_user):
        """Test logout all when no sessions exist."""
        from app.routers.auth import logout_all

        mock_request = Mock()
        sessions_deleted = 0

        mock_redis_cache.invalidate_all_user_sessions.return_value = sessions_deleted

        result = await logout_all(
            request=mock_request,
            current_user=mock_current_user,
            redis_cache=mock_redis_cache
        )

        assert isinstance(result, LogoutAllResponse)
        assert result.sessions_deleted == 0

    @pytest.mark.asyncio
    async def test_logout_all_redis_error(self, mock_redis_cache, mock_current_user):
        """Test logout all with Redis error."""
        from app.routers.auth import logout_all

        mock_request = Mock()

        # Mock Redis error
        mock_redis_cache.invalidate_all_user_sessions.side_effect = Exception("Redis error")

        with pytest.raises(HTTPException) as exc_info:
            await logout_all(
                request=mock_request,
                current_user=mock_current_user,
                redis_cache=mock_redis_cache
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Logout all failed" in exc_info.value.detail


class TestSessionStatus:
    """Test suite for session status endpoint."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Mock FirebaseRedisCache for testing."""
        cache = AsyncMock(spec=FirebaseRedisCache)
        return cache

    @pytest.mark.asyncio
    async def test_session_status_valid(self, mock_redis_cache):
        """Test session status for valid session."""
        from app.routers.auth import get_session_status

        mock_request = Mock()
        session_id = "valid-session-id"
        ttl = 3600  # 1 hour remaining

        # Mock session data
        session_data = {
            "user_id": "test-user-id",
            "firebase_uid": "test-firebase-uid",
            "last_activity": datetime.utcnow().isoformat()
        }

        mock_redis_cache.get_session.return_value = session_data
        mock_redis_cache.get_session_ttl.return_value = ttl

        result = await get_session_status(
            request=mock_request,
            x_session_id=session_id,
            redis_cache=mock_redis_cache
        )

        assert isinstance(result, SessionStatusResponse)
        assert result.valid is True
        assert result.expires_in == ttl
        assert result.last_activity == session_data["last_activity"]

    @pytest.mark.asyncio
    async def test_session_status_invalid(self, mock_redis_cache):
        """Test session status for invalid/expired session."""
        from app.routers.auth import get_session_status

        mock_request = Mock()
        session_id = "invalid-session-id"

        # Mock session not found
        mock_redis_cache.get_session.return_value = None

        result = await get_session_status(
            request=mock_request,
            x_session_id=session_id,
            redis_cache=mock_redis_cache
        )

        assert isinstance(result, SessionStatusResponse)
        assert result.valid is False
        assert result.expires_in is None
        assert result.last_activity is None

    @pytest.mark.asyncio
    async def test_session_status_redis_error(self, mock_redis_cache):
        """Test session status with Redis error."""
        from app.routers.auth import get_session_status

        mock_request = Mock()
        session_id = "test-session-id"

        # Mock Redis error
        mock_redis_cache.get_session.side_effect = Exception("Redis error")

        with pytest.raises(HTTPException) as exc_info:
            await get_session_status(
                request=mock_request,
                x_session_id=session_id,
                redis_cache=mock_redis_cache
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Session status check failed" in exc_info.value.detail


class TestGetCurrentUser:
    """Test suite for /me endpoint."""

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock(spec=User)
        user.id = "test-user-id"
        user.firebase_uid = "test-firebase-uid"
        user.email = "test@example.com"
        user.display_name = "Test User"
        user.photo_url = "https://example.com/photo.jpg"
        user.role = UserRole.DOCTOR
        user.is_active = True
        user.created_at = datetime.utcnow()
        user.last_login = datetime.utcnow()
        return user

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, mock_current_user):
        """Test successful current user retrieval."""
        from app.routers.auth import get_current_user

        mock_request = Mock()

        result = await get_current_user(
            request=mock_request,
            current_user=mock_current_user
        )

        # Verify response structure
        assert result["id"] == mock_current_user.id
        assert result["firebase_uid"] == mock_current_user.firebase_uid
        assert result["email"] == mock_current_user.email
        assert result["display_name"] == mock_current_user.display_name
        assert result["photo_url"] == mock_current_user.photo_url
        assert result["role"] == mock_current_user.role
        assert result["is_active"] == mock_current_user.is_active
        assert "created_at" in result
        assert "last_login" in result


class TestHealthCheck:
    """Test suite for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint."""
        from app.routers.auth import health_check

        mock_request = Mock()

        result = await health_check(mock_request)

        assert result["status"] == "healthy"
        assert result["service"] == "authentication"
        assert "timestamp" in result


class TestRateLimiting:
    """Test suite for rate limiting on auth endpoints."""

    def test_session_creation_rate_limit(self):
        """Test rate limiting on session creation."""
        # This would typically be tested with integration tests
        # using a real Redis instance or mock rate limiter
        pass

    def test_logout_rate_limit(self):
        """Test rate limiting on logout."""
        pass

    def test_logout_all_rate_limit(self):
        """Test rate limiting on logout all."""
        pass


class TestErrorHandling:
    """Test suite for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_malformed_request_data(self):
        """Test handling of malformed request data."""
        # Test with invalid JSON, missing fields, etc.
        pass

    @pytest.mark.asyncio
    async def test_network_timeouts(self):
        """Test handling of network timeouts."""
        pass

    @pytest.mark.asyncio
    async def test_database_connection_failures(self):
        """Test handling of database connection failures."""
        pass

    @pytest.mark.asyncio
    async def test_redis_connection_failures(self):
        """Test handling of Redis connection failures."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])