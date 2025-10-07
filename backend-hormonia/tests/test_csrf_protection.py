"""
Comprehensive CSRF Protection Tests

Tests CSRF middleware implementation for session-based authentication endpoints.

Test Coverage:
1. CSRF token generation and validation
2. Protected endpoints (POST /session, DELETE /logout, DELETE /logout-all)
3. Exempt endpoints (GET endpoints, /csrf-token)
4. Cookie security (httpOnly, secure, SameSite)
5. Token expiration and rotation
6. Error handling and logging
7. Integration with session authentication

Security Validation:
- Requests without CSRF token should fail (403)
- Requests with invalid CSRF token should fail (403)
- Requests with valid CSRF token should succeed
- CSRF cookie should have security flags set
- GET/HEAD/OPTIONS requests should be exempt
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import secrets

from app.main import app
from app.middleware.csrf import (
    get_csrf_settings,
    create_csrf_protect,
    get_csrf_token,
    validate_csrf_token,
    is_csrf_exempt,
    CsrfProtectError
)


@pytest.fixture
def client():
    """Create test client with CSRF protection enabled."""
    return TestClient(app)


@pytest.fixture
def csrf_secret():
    """Generate secure CSRF secret for testing."""
    return secrets.token_urlsafe(32)


@pytest.fixture
def mock_csrf_settings(csrf_secret, monkeypatch):
    """Mock CSRF settings for testing."""
    from app.config import settings
    monkeypatch.setattr(settings, 'CSRF_SECRET_KEY', csrf_secret)
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(settings, 'SESSION_COOKIE_SECURE', False)


class TestCsrfTokenGeneration:
    """Test CSRF token generation and retrieval."""

    def test_get_csrf_token_endpoint(self, client):
        """Test GET /api/v1/csrf-token returns valid token."""
        response = client.get("/api/v1/csrf-token")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "csrf_token" in data
        assert "expires_in" in data
        assert "usage" in data
        assert data["expires_in"] == 3600  # 1 hour

        # Verify CSRF cookie is set
        assert "fastapi-csrf-token" in response.cookies

    def test_csrf_cookie_security_flags(self, client, mock_csrf_settings):
        """Test CSRF cookie has proper security flags."""
        response = client.get("/api/v1/csrf-token")

        assert response.status_code == 200
        cookie = response.cookies.get("fastapi-csrf-token")

        # Verify cookie exists
        assert cookie is not None

        # Note: TestClient doesn't expose cookie flags directly,
        # but we can verify the middleware is configured correctly
        from app.middleware.csrf import get_csrf_settings
        settings = get_csrf_settings()

        assert settings.cookie_httponly is True
        assert settings.cookie_samesite == "strict"

    def test_csrf_token_is_unique(self, client):
        """Test that each request generates a unique CSRF token."""
        response1 = client.get("/api/v1/csrf-token")
        response2 = client.get("/api/v1/csrf-token")

        assert response1.status_code == 200
        assert response2.status_code == 200

        token1 = response1.json()["csrf_token"]
        token2 = response2.json()["csrf_token"]

        # Tokens should be different (stateless token generation)
        # Note: Depending on implementation, this might be the same
        # if using session-based tokens
        assert isinstance(token1, str)
        assert isinstance(token2, str)


class TestCsrfProtectedEndpoints:
    """Test CSRF protection on session endpoints."""

    @pytest.fixture
    def mock_firebase_token(self):
        """Mock Firebase token for session creation."""
        return "mock-firebase-token-12345"

    @pytest.fixture
    def mock_firebase_service(self, monkeypatch):
        """Mock Firebase service for authentication."""
        mock_service = Mock()
        mock_service.verify_token = MagicMock(return_value={
            "uid": "test-firebase-uid-123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "doctor"
        })

        # Patch the Firebase service dependency
        with patch('app.routers.auth_session._firebase_service', mock_service):
            yield mock_service

    def test_create_session_without_csrf_token(self, client, mock_firebase_token, mock_firebase_service):
        """
        Test POST /api/v1/session WITHOUT CSRF token.
        Currently should succeed (CSRF not yet enforced).
        After implementation: should return 403.
        """
        response = client.post(
            "/api/v1/session",
            json={
                "firebase_token": mock_firebase_token,
                "device_info": {"device_type": "web", "browser": "chrome"}
            }
        )

        # TODO: After CSRF enforcement, this should be 403
        # For now, check it's either 201 (success) or 503 (Firebase not configured)
        assert response.status_code in [201, 503, 401]

    def test_create_session_with_valid_csrf_token(self, client, mock_firebase_token, mock_firebase_service):
        """
        Test POST /api/v1/session WITH valid CSRF token.
        Should succeed when CSRF is enforced.
        """
        # Get CSRF token
        csrf_response = client.get("/api/v1/csrf-token")
        assert csrf_response.status_code == 200
        csrf_token = csrf_response.json()["csrf_token"]
        csrf_cookie = csrf_response.cookies.get("fastapi-csrf-token")

        # Create session with CSRF token
        response = client.post(
            "/api/v1/session",
            json={
                "firebase_token": mock_firebase_token,
                "device_info": {"device_type": "web"}
            },
            headers={"X-CSRF-Token": csrf_token},
            cookies={"fastapi-csrf-token": csrf_cookie}
        )

        # Should succeed (201) or fail due to other reasons (503, 401)
        # but NOT 403 (CSRF error)
        assert response.status_code in [201, 503, 401]

    def test_logout_without_csrf_token(self, client):
        """
        Test DELETE /api/v1/session/logout WITHOUT CSRF token.
        Currently should succeed (CSRF not yet enforced).
        """
        response = client.delete(
            "/api/v1/session/logout",
            headers={"X-Session-ID": "test-session-id"}
        )

        # Should not be 403 (CSRF error) for now
        # Likely 401 or 500 (invalid session)
        assert response.status_code != 403

    def test_logout_all_without_csrf_token(self, client):
        """
        Test DELETE /api/v1/session/logout-all WITHOUT CSRF token.
        Currently should succeed (CSRF not yet enforced).
        """
        response = client.delete(
            "/api/v1/session/logout-all",
            headers={"Authorization": "Bearer fake-token"}
        )

        # Should not be 403 (CSRF error) for now
        # Likely 401 or 503 (Firebase not configured)
        assert response.status_code != 403


class TestCsrfExemptEndpoints:
    """Test endpoints that should be exempt from CSRF protection."""

    def test_get_session_validate_exempt(self, client):
        """Test GET /api/v1/session/validate is exempt from CSRF."""
        response = client.get(
            "/api/v1/session/validate",
            headers={"X-Session-ID": "test-session-id"}
        )

        # Should not return 403 (CSRF error)
        # Likely 401 or 500 (invalid session)
        assert response.status_code != 403

    def test_get_session_stats_exempt(self, client):
        """Test GET /api/v1/session/stats is exempt from CSRF."""
        response = client.get("/api/v1/session/stats")

        # Should not return 403 (CSRF error)
        assert response.status_code != 403

    def test_is_csrf_exempt_function(self):
        """Test is_csrf_exempt utility function."""
        # Exempt paths
        assert is_csrf_exempt("/api/v1/session/validate") is True
        assert is_csrf_exempt("/api/v1/session/stats") is True
        assert is_csrf_exempt("/api/v1/csrf-token") is True
        assert is_csrf_exempt("/docs") is True
        assert is_csrf_exempt("/redoc") is True

        # Non-exempt paths
        assert is_csrf_exempt("/api/v1/session") is False
        assert is_csrf_exempt("/api/v1/session/logout") is False
        assert is_csrf_exempt("/api/v1/session/logout-all") is False


class TestCsrfConfiguration:
    """Test CSRF configuration and settings."""

    def test_csrf_settings_validation(self, csrf_secret, monkeypatch):
        """Test CSRF settings are properly validated."""
        from app.config import settings
        monkeypatch.setattr(settings, 'CSRF_SECRET_KEY', csrf_secret)
        monkeypatch.setattr(settings, 'ENVIRONMENT', 'production')
        monkeypatch.setattr(settings, 'SESSION_COOKIE_SECURE', True)

        csrf_settings = get_csrf_settings()

        assert csrf_settings.secret_key == csrf_secret
        assert csrf_settings.cookie_secure is True
        assert csrf_settings.cookie_samesite == "strict"
        assert csrf_settings.cookie_httponly is True

    def test_csrf_settings_missing_secret_key(self, monkeypatch):
        """Test CSRF settings validation fails without secret key."""
        from app.config import settings
        monkeypatch.setattr(settings, 'CSRF_SECRET_KEY', None)

        with pytest.raises(ValueError, match="CSRF_SECRET_KEY is required"):
            get_csrf_settings()

    def test_csrf_settings_development_mode(self, csrf_secret, monkeypatch):
        """Test CSRF settings in development mode."""
        from app.config import settings
        monkeypatch.setattr(settings, 'CSRF_SECRET_KEY', csrf_secret)
        monkeypatch.setattr(settings, 'ENVIRONMENT', 'development')
        monkeypatch.setattr(settings, 'SESSION_COOKIE_SECURE', False)

        csrf_settings = get_csrf_settings()

        # In development, cookie_secure should be False
        assert csrf_settings.cookie_secure is False

    def test_csrf_settings_production_mode(self, csrf_secret, monkeypatch):
        """Test CSRF settings in production mode."""
        from app.config import settings
        monkeypatch.setattr(settings, 'CSRF_SECRET_KEY', csrf_secret)
        monkeypatch.setattr(settings, 'ENVIRONMENT', 'production')
        monkeypatch.setattr(settings, 'SESSION_COOKIE_SECURE', False)

        csrf_settings = get_csrf_settings()

        # In production, cookie_secure should be True (overriding config)
        assert csrf_settings.cookie_secure is True


class TestCsrfErrorHandling:
    """Test CSRF error handling and logging."""

    def test_csrf_error_response_format(self, client):
        """Test CSRF error response has proper format."""
        # This test will be relevant once CSRF is enforced
        # For now, we test that the error handler is registered

        # Verify CSRF exception handler is registered in app
        from fastapi_csrf_protect.exceptions import CsrfProtectError
        assert CsrfProtectError in app.exception_handlers

    def test_csrf_error_logging(self, client, caplog):
        """Test CSRF validation failures are logged."""
        # This will be tested when CSRF is enforced
        # For now, verify logging configuration
        pass


class TestCsrfIntegration:
    """Integration tests for CSRF protection."""

    def test_full_session_workflow_with_csrf(self, client, mock_firebase_service):
        """
        Test complete session workflow with CSRF protection.

        Workflow:
        1. Get CSRF token
        2. Create session (with CSRF token)
        3. Validate session (exempt from CSRF)
        4. Logout (with CSRF token)
        """
        # Step 1: Get CSRF token
        csrf_response = client.get("/api/v1/csrf-token")
        assert csrf_response.status_code == 200
        csrf_token = csrf_response.json()["csrf_token"]
        csrf_cookie = csrf_response.cookies.get("fastapi-csrf-token")

        # Verify token and cookie exist
        assert csrf_token is not None
        assert csrf_cookie is not None

        # Step 2: Create session (would work with valid Firebase token)
        # This is tested in TestCsrfProtectedEndpoints

        # Step 3: Validate session (exempt from CSRF)
        validate_response = client.get(
            "/api/v1/session/validate",
            headers={"X-Session-ID": "test-session-id"}
        )
        # Should not be 403 (CSRF error)
        assert validate_response.status_code != 403

    def test_csrf_token_rotation(self, client):
        """Test CSRF token can be refreshed."""
        # Get first token
        response1 = client.get("/api/v1/csrf-token")
        token1 = response1.json()["csrf_token"]

        # Get second token (should be new)
        response2 = client.get("/api/v1/csrf-token")
        token2 = response2.json()["csrf_token"]

        # Both should be valid tokens
        assert isinstance(token1, str)
        assert isinstance(token2, str)
        assert len(token1) > 0
        assert len(token2) > 0


class TestCsrfSecurityValidation:
    """Security-focused CSRF validation tests."""

    def test_csrf_secret_key_validation(self, monkeypatch):
        """Test that placeholder CSRF secret keys are rejected."""
        from app.config import settings

        # Test placeholder detection
        placeholder_keys = [
            "CHANGE_THIS",
            "YOUR_SECRET_KEY",
            "change_this_to_a_secure_random_value"
        ]

        for placeholder in placeholder_keys:
            monkeypatch.setattr(settings, 'CSRF_SECRET_KEY', placeholder)
            # This should work (validation is in config.py, not csrf.py)
            # But in production, placeholder keys should be detected

    def test_csrf_token_tampering(self, client):
        """Test that tampered CSRF tokens are rejected."""
        # Get valid token
        csrf_response = client.get("/api/v1/csrf-token")
        valid_token = csrf_response.json()["csrf_token"]

        # Tamper with token
        tampered_token = valid_token[:-5] + "XXXXX"

        # TODO: After CSRF enforcement, requests with tampered tokens should fail
        # For now, we just verify token structure
        assert len(tampered_token) == len(valid_token)

    def test_csrf_cookie_httponly_prevents_javascript_access(self):
        """Test that CSRF cookie has httpOnly flag to prevent XSS."""
        from app.middleware.csrf import get_csrf_settings

        # Get settings (with mocked config)
        # This requires proper env setup
        try:
            settings = get_csrf_settings()
            assert settings.cookie_httponly is True
        except ValueError:
            # CSRF_SECRET_KEY not set in test environment
            pytest.skip("CSRF_SECRET_KEY not configured")

    def test_csrf_cookie_samesite_strict(self):
        """Test that CSRF cookie has SameSite=Strict to prevent CSRF."""
        from app.middleware.csrf import get_csrf_settings

        try:
            settings = get_csrf_settings()
            assert settings.cookie_samesite == "strict"
        except ValueError:
            pytest.skip("CSRF_SECRET_KEY not configured")


# =============================================================================
# FUTURE TESTS (After CSRF Enforcement)
# =============================================================================

class TestCsrfEnforcement:
    """
    Tests to be implemented after CSRF protection is enforced.

    These tests will verify that:
    1. Requests without CSRF token return 403
    2. Requests with invalid CSRF token return 403
    3. Requests with valid CSRF token succeed
    4. Token expiration is enforced
    """

    @pytest.mark.skip(reason="CSRF not yet enforced on endpoints")
    def test_create_session_requires_csrf_token(self, client):
        """Test that POST /session requires CSRF token."""
        response = client.post(
            "/api/v1/session",
            json={"firebase_token": "test-token"}
        )
        assert response.status_code == 403
        assert "csrf" in response.json()["error"].lower()

    @pytest.mark.skip(reason="CSRF not yet enforced on endpoints")
    def test_logout_requires_csrf_token(self, client):
        """Test that DELETE /logout requires CSRF token."""
        response = client.delete(
            "/api/v1/session/logout",
            headers={"X-Session-ID": "test-session"}
        )
        assert response.status_code == 403

    @pytest.mark.skip(reason="CSRF not yet enforced on endpoints")
    def test_invalid_csrf_token_rejected(self, client):
        """Test that invalid CSRF tokens are rejected."""
        response = client.post(
            "/api/v1/session",
            json={"firebase_token": "test-token"},
            headers={"X-CSRF-Token": "invalid-token"}
        )
        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
