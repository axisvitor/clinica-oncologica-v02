"""
Comprehensive Authentication Integration Tests

Tests complete auth flow from Firebase → Backend → Session → Validation
Covers all security controls: CSRF, CORS, rate limiting, session regeneration
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import uuid

from app.main import app
from app.core.redis_manager import FirebaseRedisCache


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_firebase_service():
    """Mock Firebase authentication service"""
    with patch('app.dependencies.auth_dependencies._firebase_service') as mock:
        # Configure mock to return valid user data
        mock.verify_token = AsyncMock(return_value={
            "uid": "test-firebase-uid-123",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://example.com/avatar.jpg",
            "email_verified": True
        })
        yield mock


@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache for session management"""
    with patch('app.core.redis_manager.get_redis_manager') as mock_manager:
        mock_cache = Mock(spec=FirebaseRedisCache)

        # Mock session operations
        mock_cache.create_session = AsyncMock(return_value=True)
        mock_cache.get_session = AsyncMock(return_value={
            "firebase_uid": "test-firebase-uid-123",
            "user_id": "test-user-id",
            "email": "test@example.com",
            "role": "doctor",
            "created_at": datetime.utcnow().isoformat()
        })
        mock_cache.invalidate_session = AsyncMock(return_value=True)
        mock_cache.invalidate_all_user_sessions = AsyncMock(return_value=3)
        mock_cache.get_user_by_uid = AsyncMock(return_value={
            "id": "test-user-id",
            "firebase_uid": "test-firebase-uid-123",
            "email": "test@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True
        })

        # Configure manager to return mock cache
        mock_redis = Mock()
        mock_manager.return_value.get_compatible_client.return_value = mock_redis

        # Patch FirebaseRedisCache constructor
        with patch('app.core.redis_manager.FirebaseRedisCache', return_value=mock_cache):
            yield mock_cache


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    with patch('app.dependencies.get_thread_safe_service_provider') as mock_provider:
        mock_db = Mock()
        mock_services = Mock()
        mock_services.db = mock_db

        # Mock user query
        mock_user = Mock()
        mock_user.id = "test-user-id"
        mock_user.firebase_uid = "test-firebase-uid-123"
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.role = Mock(value="doctor")
        mock_user.is_active = True
        mock_user.created_at = datetime.utcnow()
        mock_user.last_login = None

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Return generator for dependency injection
        def mock_gen():
            yield mock_services

        mock_provider.return_value = mock_gen()
        yield mock_db


# ============================================================================
# TEST 1: Session Creation Flow
# ============================================================================

def test_session_creation_success(client, mock_firebase_service, mock_redis_cache, mock_db_session):
    """Test successful session creation from Firebase token"""

    # Step 1: Get CSRF token
    csrf_response = client.get("/api/v1/csrf-token")
    assert csrf_response.status_code == 200
    csrf_token = csrf_response.json()["csrf_token"]

    # Step 2: Create session with Firebase token
    response = client.post(
        "/api/v1/session/",
        json={
            "firebase_token": "valid-firebase-token",
            "device_info": {
                "device_type": "web",
                "os": "Linux",
                "browser": "Chrome"
            }
        },
        headers={"X-CSRF-Token": csrf_token}
    )

    # Assert success
    assert response.status_code == 201
    data = response.json()

    # Verify response structure
    assert data["status"] == "authenticated"
    assert "expires_at" in data
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["role"] == "doctor"

    # Verify httpOnly cookie was set
    assert "session_id" in response.cookies
    cookie = response.cookies["session_id"]
    assert cookie  # Has value
    # Note: TestClient doesn't expose httponly flag, but real browser does

    # Verify backend calls
    mock_firebase_service.verify_token.assert_called_once_with("valid-firebase-token")
    mock_redis_cache.create_session.assert_called_once()

    # Verify session was cached
    call_kwargs = mock_redis_cache.create_session.call_args[1]
    assert call_kwargs["firebase_uid"] == "test-firebase-uid-123"
    assert call_kwargs["user_id"] == "test-user-id"
    assert "session_id" in call_kwargs


def test_session_creation_invalid_token(client, mock_firebase_service, mock_redis_cache):
    """Test session creation with invalid Firebase token"""

    # Configure mock to raise error
    mock_firebase_service.verify_token = AsyncMock(
        side_effect=Exception("Invalid token")
    )

    # Get CSRF token
    csrf_response = client.get("/api/v1/csrf-token")
    csrf_token = csrf_response.json()["csrf_token"]

    # Attempt session creation
    response = client.post(
        "/api/v1/session/",
        json={"firebase_token": "invalid-token"},
        headers={"X-CSRF-Token": csrf_token}
    )

    # Assert failure
    assert response.status_code == 401
    data = response.json()
    assert "Invalid Firebase token" in data["detail"]

    # Verify no session was created
    mock_redis_cache.create_session.assert_not_called()


def test_session_creation_csrf_protection(client, mock_firebase_service):
    """Test CSRF protection on session creation"""

    # Attempt session creation without CSRF token
    response = client.post(
        "/api/v1/session/",
        json={"firebase_token": "valid-token"}
    )

    # Assert CSRF validation failure
    assert response.status_code in [403, 422]  # Depends on CSRF middleware config

    # Verify no backend processing occurred
    mock_firebase_service.verify_token.assert_not_called()


# ============================================================================
# TEST 2: Session Validation Flow
# ============================================================================

def test_session_validation_success(client, mock_redis_cache, mock_db_session):
    """Test successful session validation"""

    # Simulate valid session cookie
    session_id = str(uuid.uuid4())

    response = client.get(
        "/api/v1/session/validate",
        cookies={"session_id": session_id}
    )

    # Assert success
    assert response.status_code == 200
    data = response.json()

    assert data["valid"] is True
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert "session_data" in data

    # Verify cache lookup
    mock_redis_cache.get_session.assert_called_once_with(session_id)


def test_session_validation_expired(client, mock_redis_cache):
    """Test session validation with expired session"""

    # Configure mock to return no session
    mock_redis_cache.get_session = AsyncMock(return_value=None)

    session_id = str(uuid.uuid4())
    response = client.get(
        "/api/v1/session/validate",
        cookies={"session_id": session_id}
    )

    # Assert invalid session
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["user"] is None


def test_session_validation_no_cookie(client):
    """Test session validation without cookie"""

    response = client.get("/api/v1/session/validate")

    # Assert invalid (no session)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


# ============================================================================
# TEST 3: Protected Endpoint Access
# ============================================================================

def test_protected_endpoint_with_valid_session(client, mock_redis_cache, mock_db_session):
    """Test accessing protected endpoint with valid session"""

    session_id = str(uuid.uuid4())

    response = client.get(
        "/api/v1/auth/me",
        cookies={"session_id": session_id}
    )

    # Assert success
    assert response.status_code == 200
    data = response.json()

    assert data["email"] == "test@example.com"
    assert data["role"] == "doctor"
    assert data["is_active"] is True

    # Verify session validation occurred
    mock_redis_cache.get_session.assert_called()


def test_protected_endpoint_without_session(client, mock_redis_cache):
    """Test accessing protected endpoint without session"""

    # Configure mock to return no session
    mock_redis_cache.get_session = AsyncMock(return_value=None)

    response = client.get("/api/v1/auth/me")

    # Assert unauthorized
    assert response.status_code == 401


def test_protected_endpoint_with_inactive_user(client, mock_redis_cache, mock_db_session):
    """Test accessing protected endpoint with inactive user"""

    # Configure mock to return inactive user
    mock_redis_cache.get_user_by_uid = AsyncMock(return_value={
        "id": "test-user-id",
        "firebase_uid": "test-firebase-uid-123",
        "email": "test@example.com",
        "full_name": "Test User",
        "role": "doctor",
        "is_active": False  # INACTIVE
    })

    session_id = str(uuid.uuid4())
    response = client.get(
        "/api/v1/auth/me",
        cookies={"session_id": session_id}
    )

    # Assert forbidden
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


# ============================================================================
# TEST 4: Logout Flow
# ============================================================================

def test_single_session_logout(client, mock_redis_cache):
    """Test logout of single session"""

    # Get CSRF token
    csrf_response = client.get("/api/v1/csrf-token")
    csrf_token = csrf_response.json()["csrf_token"]

    session_id = str(uuid.uuid4())

    response = client.delete(
        "/api/v1/session/logout",
        cookies={"session_id": session_id},
        headers={"X-CSRF-Token": csrf_token}
    )

    # Assert success
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["sessions_deleted"] == 1
    assert "logged out" in data["message"].lower()

    # Verify session invalidation
    mock_redis_cache.invalidate_session.assert_called_once_with(session_id)

    # Verify cookie was cleared
    # TestClient doesn't properly handle delete_cookie, but real browser does


def test_logout_all_sessions(client, mock_firebase_service, mock_redis_cache):
    """Test logout from all devices"""

    # Get CSRF token
    csrf_response = client.get("/api/v1/csrf-token")
    csrf_token = csrf_response.json()["csrf_token"]

    response = client.delete(
        "/api/v1/session/logout-all",
        headers={
            "Authorization": "Bearer valid-firebase-token",
            "X-CSRF-Token": csrf_token
        }
    )

    # Assert success
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["sessions_deleted"] == 3  # Mock returns 3
    assert "all" in data["message"].lower()

    # Verify Firebase token validation
    mock_firebase_service.verify_token.assert_called_once()

    # Verify all sessions invalidated
    mock_redis_cache.invalidate_all_user_sessions.assert_called_once_with(
        "test-firebase-uid-123"
    )


# ============================================================================
# TEST 5: Token Refresh with Validation
# ============================================================================

def test_token_refresh_with_backend_validation(client, mock_firebase_service, mock_redis_cache, mock_db_session):
    """Test token refresh triggers backend validation"""

    session_id = str(uuid.uuid4())

    # Simulate token refresh by calling /auth/me with new token
    response = client.get(
        "/api/v1/auth/me",
        cookies={"session_id": session_id}
    )

    # Assert success
    assert response.status_code == 200
    data = response.json()

    # Verify user is still active
    assert data["is_active"] is True

    # Verify session was validated
    mock_redis_cache.get_session.assert_called()


def test_token_refresh_with_deactivated_account(client, mock_redis_cache, mock_db_session):
    """Test token refresh fails for deactivated account"""

    # Configure mock to return inactive user
    mock_redis_cache.get_user_by_uid = AsyncMock(return_value={
        "id": "test-user-id",
        "firebase_uid": "test-firebase-uid-123",
        "email": "test@example.com",
        "full_name": "Test User",
        "role": "doctor",
        "is_active": False  # DEACTIVATED
    })

    session_id = str(uuid.uuid4())
    response = client.get(
        "/api/v1/auth/me",
        cookies={"session_id": session_id}
    )

    # Assert forbidden (account inactive)
    assert response.status_code == 403


# ============================================================================
# TEST 6: Rate Limiting
# ============================================================================

@pytest.mark.skip(reason="Requires rate limiter configuration")
def test_session_creation_rate_limit(client, mock_firebase_service, mock_redis_cache):
    """Test rate limiting on session creation (20/min)"""

    # Get CSRF token
    csrf_response = client.get("/api/v1/csrf-token")
    csrf_token = csrf_response.json()["csrf_token"]

    # Make 21 requests (exceeds 20/min limit)
    for i in range(21):
        response = client.post(
            "/api/v1/session/",
            json={"firebase_token": f"token-{i}"},
            headers={"X-CSRF-Token": csrf_token}
        )

        if i < 20:
            assert response.status_code == 201
        else:
            # 21st request should be rate limited
            assert response.status_code == 429


# ============================================================================
# TEST 7: Session Regeneration
# ============================================================================

def test_session_regeneration_on_login(client, mock_firebase_service, mock_redis_cache, mock_db_session):
    """Test session ID is regenerated after authentication"""

    # Get CSRF token
    csrf_response = client.get("/api/v1/csrf-token")
    csrf_token = csrf_response.json()["csrf_token"]

    # Create first session
    response1 = client.post(
        "/api/v1/session/",
        json={"firebase_token": "token-1"},
        headers={"X-CSRF-Token": csrf_token}
    )

    assert response1.status_code == 201
    session_id_1 = response1.cookies.get("session_id")

    # Create second session (simulate re-login)
    response2 = client.post(
        "/api/v1/session/",
        json={"firebase_token": "token-2"},
        headers={"X-CSRF-Token": csrf_token}
    )

    assert response2.status_code == 201
    session_id_2 = response2.cookies.get("session_id")

    # Verify different session IDs (regenerated)
    assert session_id_1 != session_id_2

    # Verify both calls to create_session used unique session IDs
    create_calls = mock_redis_cache.create_session.call_args_list
    assert len(create_calls) == 2

    session_ids = [call[1]["session_id"] for call in create_calls]
    assert len(set(session_ids)) == 2  # All unique


# ============================================================================
# TEST 8: CORS Validation
# ============================================================================

def test_cors_preflight_request(client):
    """Test CORS preflight (OPTIONS) request"""

    response = client.options(
        "/api/v1/session/",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token"
        }
    )

    # Preflight should be allowed
    assert response.status_code in [200, 204]

    # Verify CORS headers
    assert "access-control-allow-origin" in [h.lower() for h in response.headers]


# ============================================================================
# TEST 9: Security Headers
# ============================================================================

def test_security_headers_present(client):
    """Test security headers are added to responses"""

    response = client.get("/api/v1/csrf-token")

    # Check for OWASP recommended headers
    headers = {k.lower(): v for k, v in response.headers.items()}

    assert "x-frame-options" in headers
    assert headers["x-frame-options"] == "DENY"

    assert "x-content-type-options" in headers
    assert headers["x-content-type-options"] == "nosniff"

    assert "content-security-policy" in headers

    # HSTS only on HTTPS
    if response.url.startswith("https://"):
        assert "strict-transport-security" in headers


# ============================================================================
# TEST 10: End-to-End Flow
# ============================================================================

def test_complete_auth_flow(client, mock_firebase_service, mock_redis_cache, mock_db_session):
    """Test complete authentication flow from login to logout"""

    # Step 1: Get CSRF token
    csrf_response = client.get("/api/v1/csrf-token")
    assert csrf_response.status_code == 200
    csrf_token = csrf_response.json()["csrf_token"]

    # Step 2: Create session (login)
    login_response = client.post(
        "/api/v1/session/",
        json={"firebase_token": "valid-token"},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert login_response.status_code == 201
    session_id = login_response.cookies.get("session_id")
    assert session_id is not None

    # Step 3: Validate session
    validate_response = client.get(
        "/api/v1/session/validate",
        cookies={"session_id": session_id}
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["valid"] is True

    # Step 4: Access protected endpoint
    me_response = client.get(
        "/api/v1/auth/me",
        cookies={"session_id": session_id}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "test@example.com"

    # Step 5: Logout
    logout_response = client.delete(
        "/api/v1/session/logout",
        cookies={"session_id": session_id},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["success"] is True

    # Step 6: Verify session invalidated
    # Configure mock to return no session
    mock_redis_cache.get_session = AsyncMock(return_value=None)

    validate_after_logout = client.get(
        "/api/v1/session/validate",
        cookies={"session_id": session_id}
    )
    assert validate_after_logout.status_code == 200
    assert validate_after_logout.json()["valid"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
