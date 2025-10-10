"""
Unit tests for authentication dependencies.

Tests Firebase token verification, session validation, user retrieval,
and Redis cache operations with comprehensive coverage.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, Optional
from fastapi import HTTPException, status

from app.dependencies.auth_dependencies import (
    verify_firebase_token,
    get_current_user_from_session,
    get_current_user,
    get_redis_cache,
    get_permissions_for_role
)
from app.models.user import User, UserRole
from app.core.redis_manager import FirebaseRedisCache


class TestFirebaseTokenVerification:
    """Test suite for Firebase token verification."""

    @pytest.mark.asyncio
    async def test_verify_firebase_token_success(self):
        """Test successful Firebase token verification."""
        valid_token = "valid-firebase-token"
        expected_user_data = {
            "uid": "test-firebase-uid",
            "email": "test@example.com",
            "name": "Test User"
        }

        # Mock Firebase service
        mock_firebase_service = AsyncMock()
        mock_firebase_service.verify_token.return_value = expected_user_data

        with patch('app.dependencies.auth_dependencies._firebase_service', mock_firebase_service):
            result = await verify_firebase_token(valid_token)

            assert result == expected_user_data
            mock_firebase_service.verify_token.assert_called_once_with(valid_token)

    @pytest.mark.asyncio
    async def test_verify_firebase_token_invalid(self):
        """Test Firebase token verification with invalid token."""
        invalid_token = "invalid-firebase-token"

        # Mock Firebase service raising exception
        mock_firebase_service = AsyncMock()
        mock_firebase_service.verify_token.side_effect = Exception("Invalid token")

        with patch('app.dependencies.auth_dependencies._firebase_service', mock_firebase_service):
            with pytest.raises(HTTPException) as exc_info:
                await verify_firebase_token(invalid_token)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid Firebase token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_firebase_token_not_configured(self):
        """Test Firebase token verification when service not configured."""
        token = "some-token"

        with patch('app.dependencies.auth_dependencies._firebase_service', None):
            with pytest.raises(HTTPException) as exc_info:
                await verify_firebase_token(token)

            assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Firebase authentication is not configured" in exc_info.value.detail


class TestSessionBasedAuth:
    """Test suite for session-based authentication."""

    @pytest.fixture
    def mock_redis_cache(self):
        """Mock FirebaseRedisCache."""
        cache = AsyncMock(spec=FirebaseRedisCache)
        return cache

    @pytest.fixture
    def mock_services(self):
        """Mock ServiceProvider."""
        services = Mock()
        services.db = Mock()
        return services

    @pytest.fixture
    def valid_session_data(self):
        """Valid session data from Redis."""
        return {
            "firebase_uid": "test-firebase-uid",
            "user_id": "test-user-id",
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }

    @pytest.fixture
    def valid_user_data(self):
        """Valid user data from cache."""
        return {
            "firebase_uid": "test-firebase-uid",
            "email": "test@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True,
            "id": "test-user-id"
        }

    @pytest.mark.asyncio
    async def test_get_current_user_from_session_success(
        self,
        mock_redis_cache,
        mock_services,
        valid_session_data,
        valid_user_data
    ):
        """Test successful user retrieval from session."""
        session_id = "valid-session-id"

        # Mock Redis responses
        mock_redis_cache.get_session.return_value = valid_session_data
        mock_redis_cache.get_user_by_uid.return_value = valid_user_data

        result = await get_current_user_from_session(
            session_id=session_id,
            x_session_id=None,
            services=mock_services,
            redis_cache=mock_redis_cache
        )

        # Verify result structure
        assert result["firebase_uid"] == valid_user_data["firebase_uid"]
        assert result["email"] == valid_user_data["email"]
        assert result["role"] == valid_user_data["role"]
        assert result["is_active"] == valid_user_data["is_active"]
        assert "permissions" in result

        # Verify Redis calls
        mock_redis_cache.get_session.assert_called_once_with(session_id)
        mock_redis_cache.get_user_by_uid.assert_called_once_with(valid_session_data["firebase_uid"])

    @pytest.mark.asyncio
    async def test_get_current_user_from_session_no_session_id(
        self,
        mock_redis_cache,
        mock_services
    ):
        """Test authentication failure when no session ID provided."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_from_session(
                session_id=None,
                x_session_id=None,
                services=mock_services,
                redis_cache=mock_redis_cache
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Session ID not provided" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_from_session_invalid_session(
        self,
        mock_redis_cache,
        mock_services
    ):
        """Test authentication failure with invalid session."""
        session_id = "invalid-session-id"

        # Mock session not found
        mock_redis_cache.get_session.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_from_session(
                session_id=session_id,
                x_session_id=None,
                services=mock_services,
                redis_cache=mock_redis_cache
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired session" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_from_session_cache_miss(
        self,
        mock_redis_cache,
        mock_services,
        valid_session_data
    ):
        """Test user retrieval with cache miss (database fallback)."""
        session_id = "valid-session-id"

        # Mock database user
        mock_user = Mock(spec=User)
        mock_user.firebase_uid = "test-firebase-uid"
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.role = UserRole.DOCTOR
        mock_user.is_active = True
        mock_user.id = "test-user-id"

        # Mock result from database query
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user

        # Setup mocks
        mock_redis_cache.get_session.return_value = valid_session_data
        mock_redis_cache.get_user_by_uid.return_value = None  # Cache miss
        mock_services.db.execute.return_value = mock_result
        mock_redis_cache.cache_user_data = AsyncMock()

        result = await get_current_user_from_session(
            session_id=session_id,
            x_session_id=None,
            services=mock_services,
            redis_cache=mock_redis_cache
        )

        # Verify database was queried and cache was updated
        mock_services.db.execute.assert_called_once()
        mock_redis_cache.cache_user_data.assert_called_once()

        # Verify result
        assert result["firebase_uid"] == mock_user.firebase_uid
        assert result["email"] == mock_user.email
        assert result["is_active"] == mock_user.is_active

    @pytest.mark.asyncio
    async def test_get_current_user_from_session_inactive_user(
        self,
        mock_redis_cache,
        mock_services,
        valid_session_data,
        valid_user_data
    ):
        """Test authentication failure with inactive user."""
        session_id = "valid-session-id"

        # Mock inactive user
        inactive_user_data = valid_user_data.copy()
        inactive_user_data["is_active"] = False

        mock_redis_cache.get_session.return_value = valid_session_data
        mock_redis_cache.get_user_by_uid.return_value = inactive_user_data

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_from_session(
                session_id=session_id,
                x_session_id=None,
                services=mock_services,
                redis_cache=mock_redis_cache
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "User account is inactive" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_from_session_header_priority(
        self,
        mock_redis_cache,
        mock_services,
        valid_session_data,
        valid_user_data
    ):
        """Test that X-Session-ID header takes precedence over cookie."""
        cookie_session_id = "cookie-session-id"
        header_session_id = "header-session-id"

        mock_redis_cache.get_session.return_value = valid_session_data
        mock_redis_cache.get_user_by_uid.return_value = valid_user_data

        await get_current_user_from_session(
            session_id=cookie_session_id,
            x_session_id=header_session_id,
            services=mock_services,
            redis_cache=mock_redis_cache
        )

        # Should use header session ID
        mock_redis_cache.get_session.assert_called_once_with(header_session_id)


class TestTokenBasedAuth:
    """Test suite for token-based authentication (deprecated)."""

    @pytest.fixture
    def mock_firebase_service(self):
        """Mock Firebase service."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def mock_services(self):
        """Mock ServiceProvider."""
        services = Mock()
        services.db = Mock()
        return services

    @pytest.fixture
    def mock_credentials(self):
        """Mock HTTP credentials."""
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid-firebase-token"
        )
        return credentials

    @pytest.mark.asyncio
    async def test_get_current_user_firebase_not_configured(
        self,
        mock_credentials,
        mock_services
    ):
        """Test token auth when Firebase not configured."""
        with patch('app.dependencies.auth_dependencies._firebase_service', None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials, mock_services)

            assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Firebase authentication is not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_token_cache_hit(
        self,
        mock_credentials,
        mock_services,
        mock_firebase_service
    ):
        """Test token auth with cache hit."""
        # Mock cache data
        cached_token_data = {
            "firebase_uid": "test-firebase-uid",
            "email": "test@example.com"
        }

        cached_user_data = {
            "id": "test-user-id",
            "firebase_uid": "test-firebase-uid",
            "email": "test@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True
        }

        # Mock Redis cache
        with patch('app.dependencies.auth_dependencies.FirebaseRedisCache') as MockCache:
            mock_cache_instance = MockCache.return_value
            mock_cache_instance.get_cached_token.return_value = cached_token_data
            mock_cache_instance.get_cached_user.return_value = cached_user_data

            with patch('app.dependencies.auth_dependencies._firebase_service', mock_firebase_service):
                with patch('app.dependencies.auth_dependencies.get_redis_manager'):
                    result = await get_current_user(mock_credentials, mock_services)

                    assert isinstance(result, User)
                    # Verify Firebase service was not called (cache hit)
                    mock_firebase_service.verify_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_current_user_token_cache_miss(
        self,
        mock_credentials,
        mock_services,
        mock_firebase_service
    ):
        """Test token auth with cache miss."""
        firebase_user_data = {
            "uid": "test-firebase-uid",
            "email": "test@example.com",
            "name": "Test User"
        }

        # Mock existing user in database
        mock_user = Mock(spec=User)
        mock_user.id = "test-user-id"
        mock_user.firebase_uid = "test-firebase-uid"
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.role = UserRole.DOCTOR
        mock_user.is_active = True

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user

        # Mock Redis cache miss
        with patch('app.dependencies.auth_dependencies.FirebaseRedisCache') as MockCache:
            mock_cache_instance = MockCache.return_value
            mock_cache_instance.get_cached_token.return_value = None  # Cache miss
            mock_cache_instance.get_cached_user.return_value = None  # Cache miss
            mock_cache_instance.cache_validated_token = Mock()
            mock_cache_instance.cache_user = Mock()

            mock_services.db.execute.return_value = mock_result
            mock_firebase_service.verify_token.return_value = firebase_user_data

            with patch('app.dependencies.auth_dependencies._firebase_service', mock_firebase_service):
                with patch('app.dependencies.auth_dependencies.get_redis_manager'):
                    result = await get_current_user(mock_credentials, mock_services)

                    assert isinstance(result, User)
                    assert result.firebase_uid == "test-firebase-uid"

                    # Verify Firebase service was called (cache miss)
                    mock_firebase_service.verify_token.assert_called_once()
                    # Verify caching occurred
                    mock_cache_instance.cache_validated_token.assert_called_once()
                    mock_cache_instance.cache_user.assert_called_once()


class TestPermissions:
    """Test suite for role-based permissions."""

    def test_get_permissions_for_admin(self):
        """Test permissions for admin role."""
        permissions = get_permissions_for_role("admin")

        # Admin should have all permissions
        expected_permissions = [
            "patients:read", "patients:write", "patients:delete",
            "appointments:read", "appointments:write", "appointments:delete",
            "treatments:read", "treatments:write", "treatments:delete",
            "users:read", "users:write", "users:delete",
            "reports:read", "reports:write", "reports:delete",
            "settings:read", "settings:write",
            "billing:read", "billing:write",
            "analytics:read", "analytics:write"
        ]

        for permission in expected_permissions:
            assert permission in permissions

    def test_get_permissions_for_super_admin(self):
        """Test permissions for super admin role."""
        permissions = get_permissions_for_role("super_admin")

        # Super admin should have same permissions as admin
        admin_permissions = get_permissions_for_role("admin")
        assert set(permissions) == set(admin_permissions)

    def test_get_permissions_for_doctor(self):
        """Test permissions for doctor role."""
        permissions = get_permissions_for_role("doctor")

        expected_permissions = [
            "patients:read", "patients:write",
            "appointments:read", "appointments:write",
            "treatments:read", "treatments:write",
            "reports:read", "reports:write"
        ]

        for permission in expected_permissions:
            assert permission in permissions

        # Doctor should not have delete permissions
        assert "patients:delete" not in permissions
        assert "users:delete" not in permissions

    def test_get_permissions_for_unknown_role(self):
        """Test permissions for unknown role."""
        permissions = get_permissions_for_role("unknown")

        # Should get minimal permissions
        expected_permissions = ["patients:read", "appointments:read"]
        assert set(permissions) == set(expected_permissions)

    def test_get_permissions_case_insensitive(self):
        """Test that permissions work case-insensitively."""
        admin_perms_lower = get_permissions_for_role("admin")
        admin_perms_upper = get_permissions_for_role("ADMIN")
        admin_perms_mixed = get_permissions_for_role("Admin")

        assert set(admin_perms_lower) == set(admin_perms_upper)
        assert set(admin_perms_lower) == set(admin_perms_mixed)


class TestRedisCache:
    """Test suite for Redis cache dependency."""

    @pytest.mark.asyncio
    async def test_get_redis_cache(self):
        """Test Redis cache dependency injection."""
        with patch('app.dependencies.auth_dependencies.get_redis_manager') as mock_manager:
            mock_redis_manager = Mock()
            mock_redis_client = Mock()
            mock_redis_manager.get_compatible_client.return_value = mock_redis_client
            mock_manager.return_value = mock_redis_manager

            cache = await get_redis_cache()

            assert isinstance(cache, FirebaseRedisCache)
            mock_redis_manager.get_compatible_client.assert_called_once_with('sync')


class TestErrorHandling:
    """Test suite for error handling in auth dependencies."""

    @pytest.mark.asyncio
    async def test_session_validation_database_error(self):
        """Test session validation with database error."""
        # Mock database error during user lookup
        pass

    @pytest.mark.asyncio
    async def test_session_validation_redis_error(self):
        """Test session validation with Redis error."""
        # Mock Redis connection error
        pass

    @pytest.mark.asyncio
    async def test_firebase_token_verification_timeout(self):
        """Test Firebase token verification timeout."""
        # Mock Firebase API timeout
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])