"""
Comprehensive Backend Tests for Redis Session Management

Tests all aspects of the session-based authentication system:
1. Session creation with httpOnly cookie
2. Session validation via cookie
3. Logout clears Redis + cookie
4. Logout-all invalidates multiple sessions
5. Redis failure fallback
6. Concurrent session handling
7. Session expiration (24h TTL)

Target: 80%+ code coverage for auth_session.py
"""
import pytest
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import HTTPException, status, Response
from fastapi.security import HTTPAuthorizationCredentials
from app.routers.auth_session import (
    SessionCreateRequest,
    SessionResponse,
    SessionValidationResponse,
    LogoutResponse,
    SessionListResponse,
    CacheStatsResponse,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for session tests"""
    client = Mock()
    client.ping = Mock(return_value=True)
    client.get = Mock(return_value=None)
    client.setex = Mock(return_value=True)
    client.delete = Mock(return_value=1)
    client.scan_iter = Mock(return_value=iter([]))
    client.ttl = Mock(return_value=86400)
    return client


@pytest.fixture
def mock_firebase_cache(mock_redis_client):
    """Mock FirebaseRedisCache instance"""
    with patch('app.routers.auth_session.get_redis_manager') as mock_manager:
        mock_instance = Mock()
        mock_instance.get_compatible_client.return_value = mock_redis_client
        mock_manager.return_value = mock_instance

        from app.core.redis_manager import FirebaseRedisCache
        cache = FirebaseRedisCache(mock_redis_client)
        yield cache


@pytest.fixture
def mock_firebase_service():
    """Mock Firebase Auth Service"""
    service = Mock()
    service.verify_token = AsyncMock(return_value={
        "uid": "test_firebase_uid",
        "email": "test@example.com",
        "name": "Test User",
        "role": "doctor"
    })
    return service


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    db = Mock()
    db.execute = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def mock_service_provider(mock_db_session):
    """Mock ServiceProvider"""
    provider = Mock()
    provider.db = mock_db_session
    return provider


@pytest.fixture
def mock_user():
    """Mock User model"""
    from app.models.user import User, UserRole

    user = Mock(spec=User)
    user.id = uuid.uuid4()
    user.firebase_uid = "test_firebase_uid"
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.role = UserRole.DOCTOR
    user.is_active = True
    return user


@pytest.fixture
def mock_fastapi_response():
    """Mock FastAPI Response object"""
    response = Mock(spec=Response)
    response.set_cookie = Mock()
    response.delete_cookie = Mock()
    return response


# =============================================================================
# TEST SESSION CREATION
# =============================================================================

class TestSessionCreation:
    """Test session creation endpoint"""

    @pytest.mark.asyncio
    async def test_create_session_success(
        self,
        mock_firebase_service,
        mock_firebase_cache,
        mock_service_provider,
        mock_user,
        mock_fastapi_response
    ):
        """Test successful session creation with httpOnly cookie"""
        from app.routers.auth_session import create_session, _firebase_service

        # Setup
        request_data = SessionCreateRequest(
            firebase_token="valid_firebase_token",
            device_info={"device_type": "desktop", "browser": "Chrome"}
        )

        # Mock Firebase service
        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            # Mock database query
            result = Mock()
            result.scalar_one_or_none.return_value = mock_user
            mock_service_provider.db.execute.return_value = result

            # Mock Redis session creation
            mock_firebase_cache.create_session = AsyncMock(return_value=True)
            mock_firebase_cache.cache_user = Mock()

            with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
                mock_manager = Mock()
                mock_manager.get_compatible_client.return_value = Mock()
                mock_get_redis.return_value = mock_manager

                with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                    # Execute
                    response = await create_session(
                        request=request_data,
                        response=mock_fastapi_response,
                        services=mock_service_provider
                    )

                    # Assertions
                    assert isinstance(response, SessionResponse)
                    assert response.status == "authenticated"
                    assert response.user["email"] == "test@example.com"

                    # Verify httpOnly cookie was set
                    mock_fastapi_response.set_cookie.assert_called_once()
                    cookie_call = mock_fastapi_response.set_cookie.call_args
                    assert cookie_call[1]["key"] == "session_id"
                    assert cookie_call[1]["httponly"] is True
                    assert cookie_call[1]["secure"] is True
                    assert cookie_call[1]["samesite"] == "strict"

    @pytest.mark.asyncio
    async def test_create_session_firebase_not_configured(
        self,
        mock_service_provider,
        mock_fastapi_response
    ):
        """Test session creation fails when Firebase is not configured"""
        from app.routers.auth_session import create_session

        request_data = SessionCreateRequest(firebase_token="test_token")

        with patch('app.routers.auth_session._firebase_service', None):
            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    request=request_data,
                    response=mock_fastapi_response,
                    services=mock_service_provider
                )

            assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Firebase authentication is not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_invalid_firebase_token(
        self,
        mock_firebase_service,
        mock_service_provider,
        mock_fastapi_response
    ):
        """Test session creation fails with invalid Firebase token"""
        from app.routers.auth_session import create_session

        request_data = SessionCreateRequest(firebase_token="invalid_token")

        # Mock Firebase service to raise exception
        mock_firebase_service.verify_token = AsyncMock(
            side_effect=Exception("Invalid token")
        )

        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    request=request_data,
                    response=mock_fastapi_response,
                    services=mock_service_provider
                )

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid Firebase token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_inactive_user(
        self,
        mock_firebase_service,
        mock_firebase_cache,
        mock_service_provider,
        mock_user,
        mock_fastapi_response
    ):
        """Test session creation fails for inactive user"""
        from app.routers.auth_session import create_session

        request_data = SessionCreateRequest(firebase_token="valid_token")

        # Set user as inactive
        mock_user.is_active = False

        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            result = Mock()
            result.scalar_one_or_none.return_value = mock_user
            mock_service_provider.db.execute.return_value = result

            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    request=request_data,
                    response=mock_fastapi_response,
                    services=mock_service_provider
                )

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "User account is inactive" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_session_redis_failure(
        self,
        mock_firebase_service,
        mock_firebase_cache,
        mock_service_provider,
        mock_user,
        mock_fastapi_response
    ):
        """Test session creation handles Redis failure"""
        from app.routers.auth_session import create_session

        request_data = SessionCreateRequest(firebase_token="valid_token")

        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            result = Mock()
            result.scalar_one_or_none.return_value = mock_user
            mock_service_provider.db.execute.return_value = result

            # Mock Redis failure
            mock_firebase_cache.create_session = AsyncMock(return_value=False)

            with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
                mock_manager = Mock()
                mock_manager.get_compatible_client.return_value = Mock()
                mock_get_redis.return_value = mock_manager

                with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                    with pytest.raises(HTTPException) as exc_info:
                        await create_session(
                            request=request_data,
                            response=mock_fastapi_response,
                            services=mock_service_provider
                        )

                    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                    assert "Failed to create session in Redis" in str(exc_info.value.detail)


# =============================================================================
# TEST SESSION VALIDATION
# =============================================================================

class TestSessionValidation:
    """Test session validation endpoint"""

    @pytest.mark.asyncio
    async def test_validate_session_cookie_success(
        self,
        mock_firebase_cache,
        mock_service_provider,
        mock_user
    ):
        """Test session validation via httpOnly cookie"""
        from app.routers.auth_session import validate_session

        session_id = str(uuid.uuid4())
        session_data = {
            "firebase_uid": "test_firebase_uid",
            "user_id": str(mock_user.id),
            "created_at": datetime.utcnow().isoformat()
        }

        # Mock Redis session retrieval
        mock_firebase_cache.get_session = AsyncMock(return_value=session_data)
        mock_firebase_cache.get_cached_user = Mock(return_value={
            "id": str(mock_user.id),
            "firebase_uid": mock_user.firebase_uid,
            "email": mock_user.email,
            "full_name": mock_user.full_name,
            "role": "doctor",
            "is_active": True
        })

        with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
            mock_manager = Mock()
            mock_manager.get_compatible_client.return_value = Mock()
            mock_get_redis.return_value = mock_manager

            with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                # Execute with cookie
                response = await validate_session(
                    session_id=session_id,
                    x_session_id=None,
                    services=mock_service_provider
                )

                # Assertions
                assert isinstance(response, SessionValidationResponse)
                assert response.valid is True
                assert response.user["email"] == mock_user.email

    @pytest.mark.asyncio
    async def test_validate_session_header_fallback(
        self,
        mock_firebase_cache,
        mock_service_provider,
        mock_user
    ):
        """Test session validation via X-Session-ID header (fallback)"""
        from app.routers.auth_session import validate_session

        session_id = str(uuid.uuid4())
        session_data = {
            "firebase_uid": "test_firebase_uid",
            "user_id": str(mock_user.id)
        }

        mock_firebase_cache.get_session = AsyncMock(return_value=session_data)
        mock_firebase_cache.get_cached_user = Mock(return_value={
            "id": str(mock_user.id),
            "firebase_uid": mock_user.firebase_uid,
            "email": mock_user.email,
            "full_name": mock_user.full_name,
            "role": "doctor",
            "is_active": True
        })

        with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
            mock_manager = Mock()
            mock_manager.get_compatible_client.return_value = Mock()
            mock_get_redis.return_value = mock_manager

            with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                # Execute with header only
                response = await validate_session(
                    session_id=None,
                    x_session_id=session_id,
                    services=mock_service_provider
                )

                assert response.valid is True

    @pytest.mark.asyncio
    async def test_validate_session_no_credentials(
        self,
        mock_service_provider
    ):
        """Test session validation returns invalid when no session provided"""
        from app.routers.auth_session import validate_session

        response = await validate_session(
            session_id=None,
            x_session_id=None,
            services=mock_service_provider
        )

        assert isinstance(response, SessionValidationResponse)
        assert response.valid is False

    @pytest.mark.asyncio
    async def test_validate_session_expired(
        self,
        mock_firebase_cache,
        mock_service_provider
    ):
        """Test session validation returns invalid for expired session"""
        from app.routers.auth_session import validate_session

        session_id = str(uuid.uuid4())

        # Mock expired session (returns None)
        mock_firebase_cache.get_session = AsyncMock(return_value=None)

        with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
            mock_manager = Mock()
            mock_manager.get_compatible_client.return_value = Mock()
            mock_get_redis.return_value = mock_manager

            with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                response = await validate_session(
                    session_id=session_id,
                    x_session_id=None,
                    services=mock_service_provider
                )

                assert response.valid is False


# =============================================================================
# TEST LOGOUT (SINGLE SESSION)
# =============================================================================

class TestLogout:
    """Test single session logout endpoint"""

    @pytest.mark.asyncio
    async def test_logout_success(
        self,
        mock_firebase_cache,
        mock_service_provider,
        mock_fastapi_response
    ):
        """Test successful logout clears Redis + cookie"""
        from app.routers.auth_session import logout_session

        session_id = str(uuid.uuid4())

        # Mock successful Redis deletion
        mock_firebase_cache.invalidate_session = AsyncMock(return_value=True)

        with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
            mock_manager = Mock()
            mock_manager.get_compatible_client.return_value = Mock()
            mock_get_redis.return_value = mock_manager

            with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                response = await logout_session(
                    response=mock_fastapi_response,
                    session_id=session_id,
                    x_session_id=None,
                    services=mock_service_provider
                )

                # Assertions
                assert isinstance(response, LogoutResponse)
                assert response.success is True
                assert response.sessions_deleted == 1

                # Verify cookie was cleared
                mock_fastapi_response.delete_cookie.assert_called_once()
                cookie_call = mock_fastapi_response.delete_cookie.call_args
                assert cookie_call[1]["key"] == "session_id"
                assert cookie_call[1]["httponly"] is True
                assert cookie_call[1]["secure"] is True

    @pytest.mark.asyncio
    async def test_logout_no_session(
        self,
        mock_service_provider,
        mock_fastapi_response
    ):
        """Test logout with no active session"""
        from app.routers.auth_session import logout_session

        response = await logout_session(
            response=mock_fastapi_response,
            session_id=None,
            x_session_id=None,
            services=mock_service_provider
        )

        assert isinstance(response, LogoutResponse)
        assert response.success is False
        assert response.sessions_deleted == 0
        assert "No active session found" in response.message

    @pytest.mark.asyncio
    async def test_logout_already_expired(
        self,
        mock_firebase_cache,
        mock_service_provider,
        mock_fastapi_response
    ):
        """Test logout with already expired session"""
        from app.routers.auth_session import logout_session

        session_id = str(uuid.uuid4())

        # Mock Redis returning False (session already expired)
        mock_firebase_cache.invalidate_session = AsyncMock(return_value=False)

        with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
            mock_manager = Mock()
            mock_manager.get_compatible_client.return_value = Mock()
            mock_get_redis.return_value = mock_manager

            with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                response = await logout_session(
                    response=mock_fastapi_response,
                    session_id=session_id,
                    x_session_id=None,
                    services=mock_service_provider
                )

                assert response.success is False
                assert response.sessions_deleted == 0
                assert "already expired" in response.message.lower()

                # Cookie should still be cleared
                mock_fastapi_response.delete_cookie.assert_called_once()


# =============================================================================
# TEST LOGOUT-ALL (MULTIPLE SESSIONS)
# =============================================================================

class TestLogoutAll:
    """Test logout-all endpoint"""

    @pytest.mark.asyncio
    async def test_logout_all_success(
        self,
        mock_firebase_service,
        mock_firebase_cache,
        mock_service_provider
    ):
        """Test successful logout-all invalidates multiple sessions"""
        from app.routers.auth_session import logout_all_sessions

        # Mock credentials
        credentials = Mock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "valid_firebase_token"

        # Mock Firebase verification
        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            # Mock Redis deletion of multiple sessions
            mock_firebase_cache.invalidate_all_user_sessions = AsyncMock(return_value=3)

            with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
                mock_manager = Mock()
                mock_manager.get_compatible_client.return_value = Mock()
                mock_get_redis.return_value = mock_manager

                with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                    response = await logout_all_sessions(
                        credentials=credentials,
                        services=mock_service_provider
                    )

                    # Assertions
                    assert isinstance(response, LogoutResponse)
                    assert response.success is True
                    assert response.sessions_deleted == 3
                    assert "All 3 sessions logged out" in response.message

    @pytest.mark.asyncio
    async def test_logout_all_firebase_not_configured(
        self,
        mock_service_provider
    ):
        """Test logout-all fails when Firebase is not configured"""
        from app.routers.auth_session import logout_all_sessions

        credentials = Mock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "test_token"

        with patch('app.routers.auth_session._firebase_service', None):
            with pytest.raises(HTTPException) as exc_info:
                await logout_all_sessions(
                    credentials=credentials,
                    services=mock_service_provider
                )

            assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# =============================================================================
# TEST CONCURRENT SESSION HANDLING
# =============================================================================

class TestConcurrentSessions:
    """Test concurrent session operations"""

    @pytest.mark.asyncio
    async def test_list_active_sessions(
        self,
        mock_firebase_service,
        mock_firebase_cache,
        mock_service_provider
    ):
        """Test listing all active sessions for a user"""
        from app.routers.auth_session import list_active_sessions

        credentials = Mock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "valid_token"

        # Mock multiple active sessions
        sessions = [
            {
                "session_id": "session_1",
                "created_at": datetime.utcnow().isoformat(),
                "device_type": "desktop"
            },
            {
                "session_id": "session_2",
                "created_at": datetime.utcnow().isoformat(),
                "device_type": "mobile"
            }
        ]

        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            mock_firebase_cache.list_user_sessions = Mock(return_value=sessions)

            with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
                mock_manager = Mock()
                mock_manager.get_compatible_client.return_value = Mock()
                mock_get_redis.return_value = mock_manager

                with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                    response = await list_active_sessions(
                        credentials=credentials,
                        services=mock_service_provider
                    )

                    assert isinstance(response, SessionListResponse)
                    assert response.total == 2
                    assert len(response.sessions) == 2


# =============================================================================
# TEST SESSION EXPIRATION
# =============================================================================

class TestSessionExpiration:
    """Test session expiration (24h TTL)"""

    @pytest.mark.asyncio
    async def test_session_ttl_set_correctly(
        self,
        mock_firebase_service,
        mock_firebase_cache,
        mock_service_provider,
        mock_user,
        mock_fastapi_response
    ):
        """Test session is created with correct 24h TTL"""
        from app.routers.auth_session import create_session

        request_data = SessionCreateRequest(firebase_token="valid_token")

        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            result = Mock()
            result.scalar_one_or_none.return_value = mock_user
            mock_service_provider.db.execute.return_value = result

            # Capture create_session call
            mock_firebase_cache.create_session = AsyncMock(return_value=True)
            mock_firebase_cache.cache_user = Mock()

            with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
                mock_manager = Mock()
                mock_manager.get_compatible_client.return_value = Mock()
                mock_get_redis.return_value = mock_manager

                with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                    with patch('app.routers.auth_session.settings') as mock_settings:
                        mock_settings.FIREBASE_SESSION_TTL = 86400  # 24 hours

                        response = await create_session(
                            request=request_data,
                            response=mock_fastapi_response,
                            services=mock_service_provider
                        )

                        # Verify session was created (TTL is checked internally)
                        mock_firebase_cache.create_session.assert_called_once()

                        # Verify cookie max_age is 24 hours
                        cookie_call = mock_fastapi_response.set_cookie.call_args
                        assert cookie_call[1]["max_age"] == 86400


# =============================================================================
# TEST CACHE STATS
# =============================================================================

class TestCacheStats:
    """Test cache statistics endpoint"""

    @pytest.mark.asyncio
    async def test_get_cache_stats(
        self,
        mock_firebase_cache,
        mock_service_provider
    ):
        """Test retrieving cache performance statistics"""
        from app.routers.auth_session import get_cache_stats

        stats = {
            "token_cache_ttl": 3600,
            "user_cache_ttl": 7200,
            "session_ttl": 86400,
            "active_sessions": 5,
            "redis_connection": "healthy"
        }

        mock_firebase_cache.get_cache_stats = Mock(return_value=stats)

        with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
            mock_manager = Mock()
            mock_manager.get_compatible_client.return_value = Mock()
            mock_get_redis.return_value = mock_manager

            with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                response = await get_cache_stats(services=mock_service_provider)

                assert isinstance(response, CacheStatsResponse)
                assert response.stats["active_sessions"] == 5
                assert response.stats["redis_connection"] == "healthy"


# =============================================================================
# TEST ERROR HANDLING
# =============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_create_session_db_error(
        self,
        mock_firebase_service,
        mock_service_provider,
        mock_fastapi_response
    ):
        """Test session creation handles database errors gracefully"""
        from app.routers.auth_session import create_session

        request_data = SessionCreateRequest(firebase_token="valid_token")

        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            # Mock database error
            mock_service_provider.db.execute.side_effect = Exception("Database error")

            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    request=request_data,
                    response=mock_fastapi_response,
                    services=mock_service_provider
                )

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_validate_session_redis_error(
        self,
        mock_firebase_cache,
        mock_service_provider
    ):
        """Test session validation handles Redis errors gracefully"""
        from app.routers.auth_session import validate_session

        session_id = str(uuid.uuid4())

        # Mock Redis error
        mock_firebase_cache.get_session = AsyncMock(side_effect=Exception("Redis error"))

        with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
            mock_manager = Mock()
            mock_manager.get_compatible_client.return_value = Mock()
            mock_get_redis.return_value = mock_manager

            with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                response = await validate_session(
                    session_id=session_id,
                    x_session_id=None,
                    services=mock_service_provider
                )

                # Should return invalid instead of raising exception
                assert response.valid is False


# =============================================================================
# INTEGRATION TEST
# =============================================================================

class TestSessionIntegration:
    """Integration test for full session lifecycle"""

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(
        self,
        mock_firebase_service,
        mock_firebase_cache,
        mock_service_provider,
        mock_user,
        mock_fastapi_response
    ):
        """Test complete session lifecycle: create -> validate -> logout"""
        from app.routers.auth_session import (
            create_session,
            validate_session,
            logout_session
        )

        # Step 1: Create session
        request_data = SessionCreateRequest(firebase_token="valid_token")

        with patch('app.routers.auth_session._firebase_service', mock_firebase_service):
            result = Mock()
            result.scalar_one_or_none.return_value = mock_user
            mock_service_provider.db.execute.return_value = result

            mock_firebase_cache.create_session = AsyncMock(return_value=True)
            mock_firebase_cache.cache_user = Mock()

            with patch('app.routers.auth_session.get_redis_manager') as mock_get_redis:
                mock_manager = Mock()
                mock_manager.get_compatible_client.return_value = Mock()
                mock_get_redis.return_value = mock_manager

                with patch('app.routers.auth_session.FirebaseRedisCache', return_value=mock_firebase_cache):
                    # Create
                    create_response = await create_session(
                        request=request_data,
                        response=mock_fastapi_response,
                        services=mock_service_provider
                    )
                    assert create_response.status == "authenticated"

                    # Extract session_id from cookie call
                    session_id = mock_fastapi_response.set_cookie.call_args[1]["value"]

                    # Step 2: Validate session
                    mock_firebase_cache.get_session = AsyncMock(return_value={
                        "firebase_uid": "test_firebase_uid",
                        "user_id": str(mock_user.id)
                    })
                    mock_firebase_cache.get_cached_user = Mock(return_value={
                        "id": str(mock_user.id),
                        "firebase_uid": "test_firebase_uid",
                        "email": "test@example.com",
                        "full_name": "Test User",
                        "role": "doctor",
                        "is_active": True
                    })

                    validate_response = await validate_session(
                        session_id=session_id,
                        x_session_id=None,
                        services=mock_service_provider
                    )
                    assert validate_response.valid is True

                    # Step 3: Logout
                    mock_firebase_cache.invalidate_session = AsyncMock(return_value=True)

                    logout_response = await logout_session(
                        response=mock_fastapi_response,
                        session_id=session_id,
                        x_session_id=None,
                        services=mock_service_provider
                    )
                    assert logout_response.success is True
                    assert logout_response.sessions_deleted == 1
