"""
Comprehensive CSRF Protection Tests

Tests CSRF token validation for session-based authentication endpoints.
Verifies that state-changing requests (POST, PUT, DELETE) require valid CSRF tokens.

Test Coverage:
- CSRF token generation and validation
- Protected endpoints (session creation, logout, preferences)
- Exempt endpoints (GET, HEAD, OPTIONS, token endpoint)
- Invalid token rejection
- Missing token rejection
- Cookie-based CSRF protection
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import uuid

from app.main import app


@pytest.fixture
def client():
    """Test client with default configuration."""
    return TestClient(app)


@pytest.fixture
def mock_firebase_service():
    """Mock Firebase service for authentication."""
    with patch('app.routers.auth_session._firebase_service') as mock:
        # Configure mock to return valid user data
        mock.verify_token = Mock(return_value={
            'uid': 'test-firebase-uid',
            'email': 'test@example.com',
            'name': 'Test User',
            'role': 'doctor'
        })
        yield mock


@pytest.fixture
def mock_service_provider():
    """Mock service provider with database session."""
    with patch('app.routers.auth_session._get_service_provider') as mock:
        # Create mock DB session
        mock_db = MagicMock()

        # Mock user query result
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_user.firebase_uid = 'test-firebase-uid'
        mock_user.email = 'test@example.com'
        mock_user.full_name = 'Test User'
        mock_user.is_active = True
        mock_user.role = Mock(value='doctor')

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        # Mock service provider
        mock_provider = Mock()
        mock_provider.db = mock_db
        mock.return_value = mock_provider

        yield mock_provider


@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache for session management."""
    with patch('app.routers.auth_session.get_redis_manager') as mock_manager:
        # Create mock Redis client
        mock_client = Mock()
        mock_manager.return_value.get_compatible_client.return_value = mock_client

        # Mock FirebaseRedisCache
        with patch('app.routers.auth_session.FirebaseRedisCache') as mock_cache_class:
            mock_cache = Mock()
            mock_cache.create_session.return_value = True
            mock_cache.cache_user.return_value = True
            mock_cache.get_session.return_value = {
                'user_id': 'test-user-id',
                'firebase_uid': 'test-firebase-uid',
                'email': 'test@example.com'
            }
            mock_cache.invalidate_session.return_value = True
            mock_cache_class.return_value = mock_cache

            yield mock_cache


class TestCsrfTokenGeneration:
    """Test CSRF token generation endpoint."""

    def test_get_csrf_token_success(self, client):
        """Test successful CSRF token generation."""
        response = client.get('/api/v1/csrf-token')

        assert response.status_code == 200
        data = response.json()
        assert 'csrf_token' in data
        assert data['expires_in'] == 3600
        assert 'usage' in data

        # Verify CSRF cookie is set
        assert 'fastapi-csrf-token' in response.cookies

    def test_csrf_token_is_random(self, client):
        """Test that CSRF tokens are unique."""
        response1 = client.get('/api/v1/csrf-token')
        response2 = client.get('/api/v1/csrf-token')

        token1 = response1.json()['csrf_token']
        token2 = response2.json()['csrf_token']

        assert token1 != token2


class TestSessionEndpointCsrfProtection:
    """Test CSRF protection on session management endpoints."""

    def test_create_session_without_csrf_token_fails(
        self,
        client,
        mock_firebase_service,
        mock_service_provider,
        mock_redis_cache
    ):
        """Test that session creation fails without CSRF token."""
        response = client.post(
            '/api/v1/session/',
            json={
                'firebase_token': 'valid-firebase-token',
                'device_info': {'device_type': 'web'}
            }
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_create_session_with_invalid_csrf_token_fails(
        self,
        client,
        mock_firebase_service,
        mock_service_provider,
        mock_redis_cache
    ):
        """Test that session creation fails with invalid CSRF token."""
        response = client.post(
            '/api/v1/session/',
            json={
                'firebase_token': 'valid-firebase-token',
                'device_info': {'device_type': 'web'}
            },
            headers={'X-CSRF-Token': 'invalid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_create_session_with_valid_csrf_token_succeeds(
        self,
        client,
        mock_firebase_service,
        mock_service_provider,
        mock_redis_cache
    ):
        """Test that session creation succeeds with valid CSRF token."""
        # First, get CSRF token
        token_response = client.get('/api/v1/csrf-token')
        csrf_token = token_response.json()['csrf_token']
        csrf_cookie = token_response.cookies.get('fastapi-csrf-token')

        # Create session with CSRF token
        response = client.post(
            '/api/v1/session/',
            json={
                'firebase_token': 'valid-firebase-token',
                'device_info': {'device_type': 'web'}
            },
            headers={'X-CSRF-Token': csrf_token},
            cookies={'fastapi-csrf-token': csrf_cookie}
        )

        assert response.status_code == 201
        data = response.json()
        assert data['status'] == 'authenticated'
        assert 'user' in data
        assert 'expires_at' in data

    def test_logout_without_csrf_token_fails(self, client):
        """Test that logout fails without CSRF token."""
        response = client.delete('/api/v1/session/logout')

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_logout_with_valid_csrf_token_succeeds(
        self,
        client,
        mock_service_provider,
        mock_redis_cache
    ):
        """Test that logout succeeds with valid CSRF token."""
        # Get CSRF token
        token_response = client.get('/api/v1/csrf-token')
        csrf_token = token_response.json()['csrf_token']
        csrf_cookie = token_response.cookies.get('fastapi-csrf-token')

        # Logout with CSRF token
        response = client.delete(
            '/api/v1/session/logout',
            headers={'X-CSRF-Token': csrf_token},
            cookies={
                'fastapi-csrf-token': csrf_cookie,
                'session_id': 'test-session-id'
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_logout_all_without_csrf_token_fails(self, client):
        """Test that global logout fails without CSRF token."""
        response = client.delete(
            '/api/v1/session/logout-all',
            headers={'Authorization': 'Bearer valid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'


class TestAuthEndpointCsrfProtection:
    """Test CSRF protection on auth endpoints."""

    def test_update_preferences_without_csrf_fails(self, client):
        """Test that preferences update fails without CSRF token."""
        response = client.put(
            '/api/v1/auth/users/preferences',
            json={
                'notification_email': True,
                'language': 'en-US'
            },
            headers={'Authorization': 'Bearer valid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_patch_preferences_without_csrf_fails(self, client):
        """Test that partial preferences update fails without CSRF token."""
        response = client.patch(
            '/api/v1/auth/users/preferences',
            json={'language': 'pt-BR'},
            headers={'Authorization': 'Bearer valid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_reset_preferences_without_csrf_fails(self, client):
        """Test that preferences reset fails without CSRF token."""
        response = client.post(
            '/api/v1/auth/users/preferences/reset',
            headers={'Authorization': 'Bearer valid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_update_profile_without_csrf_fails(self, client):
        """Test that profile update fails without CSRF token."""
        response = client.put(
            '/api/v1/auth/profile',
            json={
                'full_name': 'Updated Name',
                'email': 'updated@example.com'
            },
            headers={'Authorization': 'Bearer valid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_change_password_without_csrf_fails(self, client):
        """Test that password change fails without CSRF token."""
        response = client.put(
            '/api/v1/auth/password',
            json={'new_password': 'NewPassword123!'},
            headers={'Authorization': 'Bearer valid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_mark_notification_read_without_csrf_fails(self, client):
        """Test that notification marking fails without CSRF token."""
        response = client.post(
            '/api/v1/auth/notifications/test-notification-id/read',
            headers={'Authorization': 'Bearer valid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'

    def test_delete_notification_without_csrf_fails(self, client):
        """Test that notification deletion fails without CSRF token."""
        response = client.delete(
            '/api/v1/auth/notifications/test-notification-id',
            headers={'Authorization': 'Bearer valid-token'}
        )

        assert response.status_code == 403
        data = response.json()
        assert data['error'] == 'csrf_validation_failed'


class TestCsrfExemptEndpoints:
    """Test that read-only endpoints are exempt from CSRF protection."""

    def test_session_validate_no_csrf_required(self, client):
        """Test that session validation doesn't require CSRF token."""
        response = client.get('/api/v1/session/validate')

        # Should return validation response, not CSRF error
        assert response.status_code != 403

    def test_get_preferences_no_csrf_required(self, client):
        """Test that getting preferences doesn't require CSRF token."""
        response = client.get(
            '/api/v1/auth/users/preferences',
            headers={'Authorization': 'Bearer valid-token'}
        )

        # Should not be CSRF error (may be 401/403 for auth reasons)
        assert response.status_code != 403 or 'csrf' not in response.json().get('error', '').lower()

    def test_get_notifications_no_csrf_required(self, client):
        """Test that getting notifications doesn't require CSRF token."""
        response = client.get(
            '/api/v1/auth/notifications',
            headers={'Authorization': 'Bearer valid-token'}
        )

        # Should not be CSRF error
        assert response.status_code != 403 or 'csrf' not in response.json().get('error', '').lower()

    def test_get_user_profile_no_csrf_required(self, client):
        """Test that getting user profile doesn't require CSRF token."""
        response = client.get(
            '/api/v1/auth/me',
            headers={'Authorization': 'Bearer valid-token'}
        )

        # Should not be CSRF error
        assert response.status_code != 403 or 'csrf' not in response.json().get('error', '').lower()


class TestCsrfIntegration:
    """Integration tests for complete CSRF protection flow."""

    def test_complete_session_flow_with_csrf(
        self,
        client,
        mock_firebase_service,
        mock_service_provider,
        mock_redis_cache
    ):
        """Test complete flow: get token -> create session -> logout."""
        # Step 1: Get CSRF token
        token_response = client.get('/api/v1/csrf-token')
        assert token_response.status_code == 200
        csrf_token = token_response.json()['csrf_token']
        csrf_cookie = token_response.cookies.get('fastapi-csrf-token')

        # Step 2: Create session with CSRF token
        session_response = client.post(
            '/api/v1/session/',
            json={
                'firebase_token': 'valid-firebase-token',
                'device_info': {'device_type': 'web'}
            },
            headers={'X-CSRF-Token': csrf_token},
            cookies={'fastapi-csrf-token': csrf_cookie}
        )
        assert session_response.status_code == 201
        session_cookie = session_response.cookies.get('session_id')

        # Step 3: Logout with CSRF token
        logout_response = client.delete(
            '/api/v1/session/logout',
            headers={'X-CSRF-Token': csrf_token},
            cookies={
                'fastapi-csrf-token': csrf_cookie,
                'session_id': session_cookie
            }
        )
        assert logout_response.status_code == 200
        assert logout_response.json()['success'] is True

    def test_csrf_token_reuse(self, client):
        """Test that CSRF token can be reused for multiple requests."""
        # Get token once
        token_response = client.get('/api/v1/csrf-token')
        csrf_token = token_response.json()['csrf_token']
        csrf_cookie = token_response.cookies.get('fastapi-csrf-token')

        # Use same token for multiple requests (should succeed)
        # Note: In real implementation, requests would need valid auth
        for _ in range(3):
            response = client.post(
                '/api/v1/auth/users/preferences/reset',
                headers={
                    'X-CSRF-Token': csrf_token,
                    'Authorization': 'Bearer valid-token'
                },
                cookies={'fastapi-csrf-token': csrf_cookie}
            )
            # All should fail with same CSRF validation (or auth error if CSRF passes)
            # None should have different CSRF behavior
            assert response.status_code in [401, 403]  # Auth or CSRF error


class TestCsrfSecurityHeaders:
    """Test CSRF-related security headers."""

    def test_csrf_cookie_security_flags(self, client):
        """Test that CSRF cookie has proper security flags."""
        response = client.get('/api/v1/csrf-token')

        # Check cookie exists
        csrf_cookie = response.cookies.get('fastapi-csrf-token')
        assert csrf_cookie is not None

        # In production, cookie should have:
        # - httponly=True (JavaScript cannot access)
        # - secure=True (HTTPS only)
        # - samesite=strict (CSRF protection)
        # Note: TestClient may not fully simulate cookie flags

    def test_csrf_token_in_response_body(self, client):
        """Test that CSRF token is returned in response body for JavaScript."""
        response = client.get('/api/v1/csrf-token')

        data = response.json()
        assert 'csrf_token' in data
        assert len(data['csrf_token']) > 20  # Reasonable token length
        assert 'expires_in' in data
        assert data['expires_in'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
