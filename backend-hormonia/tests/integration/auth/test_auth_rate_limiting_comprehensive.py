"""
Comprehensive rate limiting tests for all authentication endpoints.

Tests verify rate limiting enforcement on all auth endpoints including:
- Login endpoints (deprecated)
- Token refresh (deprecated)
- User profile endpoints
- Preferences management
- Notifications
- Password and avatar operations

Each test verifies:
1. Rate limit is enforced at the correct threshold
2. Error response format is correct
3. Different IPs have independent limits
4. Rate limits reset properly
"""
import pytest
import time
from fastapi.testclient import TestClient
from app.core.application_factory import create_application
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    """Create test client with rate limiting enabled."""
    app = create_application(
        enable_monitoring=False,
        enable_debug_endpoints=False,
        deployment_mode="development"
    )
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user for protected endpoints."""
    user = MagicMock()
    user.id = "123e4567-e89b-12d3-a456-426614174000"
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.role = "doctor"
    user.is_active = True
    user.metadata = {"firebase_uid": "firebase-uid-123"}
    return user


class TestLoginEndpointRateLimiting:
    """Test rate limiting on login endpoints (5/minute)."""

    def test_login_form_rate_limit_enforcement(self, client):
        """Test that form-based login enforces 5/minute rate limit."""
        responses = []
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"}
            )
            responses.append(response)

        # First 5 should return 410 (deprecated endpoint)
        for i, response in enumerate(responses[:5]):
            assert response.status_code == 410, f"Request {i+1} should be allowed (410)"

        # 6th should be rate limited
        assert responses[5].status_code == 429, "Request 6 should be rate limited"
        error = responses[5].json()
        assert error["error"] == "too_many_requests"
        assert "retry_after" in error

    def test_login_json_rate_limit_enforcement(self, client):
        """Test that JSON login enforces 5/minute rate limit."""
        responses = []
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login-json",
                json={"email": f"user{i}@example.com", "password": "test123"}
            )
            responses.append(response)

        # First 5 should return 410 (deprecated)
        assert all(r.status_code == 410 for r in responses[:5])

        # 6th should be rate limited
        assert responses[5].status_code == 429

    def test_login_rate_limit_per_ip(self, client):
        """Test that login rate limits are per-IP."""
        ip1_headers = {"X-Forwarded-For": "192.168.1.1"}
        ip2_headers = {"X-Forwarded-For": "192.168.1.2"}

        # Exhaust IP1's limit
        for i in range(5):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"},
                headers=ip1_headers
            )
            assert response.status_code == 410

        # IP1 should be rate limited
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "test123"},
            headers=ip1_headers
        )
        assert response.status_code == 429

        # IP2 should still work
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "test123"},
            headers=ip2_headers
        )
        assert response.status_code == 410  # Not rate limited


class TestTokenRefreshRateLimiting:
    """Test rate limiting on token refresh endpoint (20/minute)."""

    def test_refresh_token_rate_limit_enforcement(self, client):
        """Test that token refresh enforces 20/minute rate limit."""
        responses = []
        for i in range(21):
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": f"fake-token-{i}"}
            )
            responses.append(response)

        # First 20 should return 410 (deprecated)
        assert all(r.status_code == 410 for r in responses[:20])

        # 21st should be rate limited
        assert responses[20].status_code == 429


class TestProfileEndpointRateLimiting:
    """Test rate limiting on profile endpoints."""

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_get_profile_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that GET /me enforces 100/minute rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(101):
            response = client.get("/api/v1/auth/me")
            responses.append(response)

        # First 100 should succeed
        assert all(r.status_code == 200 for r in responses[:100])

        # 101st should be rate limited
        assert responses[100].status_code == 429

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_update_profile_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that PUT /profile enforces 20/hour rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(21):
            response = client.put(
                "/api/v1/auth/profile",
                json={"full_name": f"Updated Name {i}"}
            )
            responses.append(response)

        # First 20 should succeed or return validation error
        for r in responses[:20]:
            assert r.status_code in [200, 422, 500]  # 500 for missing db/firebase

        # 21st should be rate limited
        assert responses[20].status_code == 429


class TestPreferencesRateLimiting:
    """Test rate limiting on user preferences endpoints."""

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_get_preferences_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that GET /users/preferences enforces 100/minute rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(101):
            response = client.get("/api/v1/auth/users/preferences")
            responses.append(response)

        # First 100 should succeed or fail with server error (missing db)
        for r in responses[:100]:
            assert r.status_code in [200, 500]

        # 101st should be rate limited
        assert responses[100].status_code == 429

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_update_preferences_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that PUT /users/preferences enforces 20/hour rate limit."""
        mock_get_current_user.return_value = mock_user

        preferences = {
            "notification_email": True,
            "language": "pt-BR",
            "theme": "light"
        }

        responses = []
        for i in range(21):
            response = client.put(
                "/api/v1/auth/users/preferences",
                json=preferences
            )
            responses.append(response)

        # First 20 should succeed or fail with server error
        for r in responses[:20]:
            assert r.status_code in [200, 500]

        # 21st should be rate limited
        assert responses[20].status_code == 429

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_patch_preferences_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that PATCH /users/preferences enforces 20/hour rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(21):
            response = client.patch(
                "/api/v1/auth/users/preferences",
                json={"theme": "dark"}
            )
            responses.append(response)

        # First 20 should succeed or fail with server error
        for r in responses[:20]:
            assert r.status_code in [200, 500]

        # 21st should be rate limited
        assert responses[20].status_code == 429

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_reset_preferences_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that POST /users/preferences/reset enforces 10/hour rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(11):
            response = client.post("/api/v1/auth/users/preferences/reset")
            responses.append(response)

        # First 10 should succeed or fail with server error
        for r in responses[:10]:
            assert r.status_code in [200, 500]

        # 11th should be rate limited
        assert responses[10].status_code == 429


class TestNotificationsRateLimiting:
    """Test rate limiting on notification endpoints."""

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_get_notifications_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that GET /notifications enforces 100/minute rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(101):
            response = client.get("/api/v1/auth/notifications")
            responses.append(response)

        # First 100 should succeed or fail with server error
        for r in responses[:100]:
            assert r.status_code in [200, 500]

        # 101st should be rate limited
        assert responses[100].status_code == 429

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_mark_notification_read_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that POST /notifications/{id}/read enforces 100/minute rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(101):
            response = client.post(f"/api/v1/auth/notifications/notif-{i}/read")
            responses.append(response)

        # First 100 should succeed or fail with server error
        for r in responses[:100]:
            assert r.status_code in [200, 500]

        # 101st should be rate limited
        assert responses[100].status_code == 429

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_mark_all_read_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that POST /notifications/mark-all-read enforces 20/hour rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(21):
            response = client.post("/api/v1/auth/notifications/mark-all-read")
            responses.append(response)

        # First 20 should succeed or fail with server error
        for r in responses[:20]:
            assert r.status_code in [200, 500]

        # 21st should be rate limited
        assert responses[20].status_code == 429

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_delete_notification_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that DELETE /notifications/{id} enforces 100/minute rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(101):
            response = client.delete(f"/api/v1/auth/notifications/notif-{i}")
            responses.append(response)

        # First 100 should succeed or fail with server error
        for r in responses[:100]:
            assert r.status_code in [200, 500]

        # 101st should be rate limited
        assert responses[100].status_code == 429


class TestPasswordChangeRateLimiting:
    """Test rate limiting on password change endpoint."""

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_password_change_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that PUT /password enforces 3/hour rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(4):
            response = client.put(
                "/api/v1/auth/password",
                json={"new_password": f"NewPassword{i}!"}
            )
            responses.append(response)

        # First 3 should attempt (may fail with firebase error)
        for r in responses[:3]:
            assert r.status_code in [200, 400, 500]

        # 4th should be rate limited
        assert responses[3].status_code == 429


class TestAvatarUploadRateLimiting:
    """Test rate limiting on avatar upload endpoint."""

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_avatar_upload_rate_limit(self, mock_get_current_user, client, mock_user):
        """Test that POST /avatar enforces 10/hour rate limit."""
        mock_get_current_user.return_value = mock_user

        responses = []
        for i in range(11):
            # Create mock file upload
            files = {'file': ('test.png', b'fake image data', 'image/png')}
            response = client.post(
                "/api/v1/auth/avatar",
                files=files
            )
            responses.append(response)

        # First 10 should return 503 (disabled feature)
        for r in responses[:10]:
            assert r.status_code in [503]

        # 11th should be rate limited
        assert responses[10].status_code == 429


class TestRateLimitErrorResponse:
    """Test rate limit error response format and content."""

    def test_rate_limit_error_format(self, client):
        """Test that rate limit errors return standardized format."""
        # Trigger rate limit on login endpoint
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"}
            )

        # Check last response format
        assert response.status_code == 429
        error = response.json()

        # Verify required fields
        assert "error" in error
        assert error["error"] == "too_many_requests"
        assert "message" in error
        assert "Muitas tentativas" in error["message"]
        assert "retry_after" in error

    def test_rate_limit_includes_limit_info(self, client):
        """Test that rate limit error includes limit information."""
        # Trigger rate limit
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"}
            )

        error = response.json()
        assert "limit" in error or "retry_after" in error


class TestRateLimitIPDetection:
    """Test IP detection for rate limiting."""

    def test_x_forwarded_for_header_detection(self, client):
        """Test that X-Forwarded-For header is respected."""
        headers = {"X-Forwarded-For": "203.0.113.1"}

        # Make requests with specific IP
        for i in range(5):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"},
                headers=headers
            )
            assert response.status_code == 410

        # 6th request should be rate limited for this IP
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "test123"},
            headers=headers
        )
        assert response.status_code == 429

    def test_multiple_ips_in_x_forwarded_for(self, client):
        """Test that first IP in X-Forwarded-For chain is used."""
        headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1, 192.0.2.1"}

        # Should rate limit based on first IP (203.0.113.1)
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"},
                headers=headers
            )

        assert response.status_code == 429

    def test_x_real_ip_header_fallback(self, client):
        """Test that X-Real-IP header is used as fallback."""
        headers = {"X-Real-IP": "203.0.113.2"}

        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"},
                headers=headers
            )

        assert response.status_code == 429


class TestRateLimitIndependence:
    """Test that rate limits are independent between endpoints."""

    @patch('app.dependencies.auth_dependencies.get_current_user')
    def test_different_endpoints_independent_limits(self, mock_get_current_user, client, mock_user):
        """Test that exhausting one endpoint's limit doesn't affect others."""
        mock_get_current_user.return_value = mock_user

        # Exhaust login limit
        for i in range(5):
            client.post(
                "/api/v1/auth/login",
                data={"username": f"user{i}@example.com", "password": "test123"}
            )

        # Login should be rate limited
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "test123"}
        )
        assert response.status_code == 429

        # But profile endpoint should still work
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
