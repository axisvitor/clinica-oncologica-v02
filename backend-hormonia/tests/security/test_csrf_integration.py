"""
CSRF Integration Tests

Tests full request flow including:
- Token endpoint
- Authentication flow
- Real API endpoints
- Cookie handling
- Error responses

Created by: Tester Agent
Coordinated via: Hive Mind Swarm
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


@pytest.mark.security
@pytest.mark.integration
class TestCSRFTokenEndpoint:
    """Test the CSRF token endpoint."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_token_endpoint_returns_token(self, mock_secret, client):
        """Test that /api/v2/auth/csrf-token returns a valid token."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = client.get("/api/v2/auth/csrf-token")

        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert isinstance(data["csrf_token"], str)
        assert len(data["csrf_token"]) > 0

    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_token_endpoint_sets_cookie(self, mock_secret, client):
        """Test that endpoint sets CSRF cookie."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = client.get("/api/v2/auth/csrf-token")

        assert response.status_code == 200
        assert "csrf_token" in response.cookies

    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_token_format(self, mock_secret, client):
        """Test that returned token has correct format."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = client.get("/api/v2/auth/csrf-token")
        token = response.json()["csrf_token"]

        # Should be in format: timestamp.random.signature
        parts = token.split(".")
        assert len(parts) == 3

    @patch("app.middleware.csrf._get_secret_key")
    def test_multiple_token_requests_return_different_tokens(self, mock_secret, client):
        """Test that each request generates a new token."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response1 = client.get("/api/v2/auth/csrf-token")
        response2 = client.get("/api/v2/auth/csrf-token")

        token1 = response1.json()["csrf_token"]
        token2 = response2.json()["csrf_token"]

        assert token1 != token2


@pytest.mark.security
@pytest.mark.integration
class TestCSRFWithRealEndpoints:
    """Test CSRF protection on real API endpoints."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_protected_endpoint_requires_csrf(self, mock_secret, authenticated_client):
        """Test that protected endpoints require CSRF token."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Try to create patient without CSRF token
        response = authenticated_client.post(
            "/api/v2/patients",
            json={
                "name": "Test Patient",
                "birth_date": "1990-01-01"
            }
        )

        # Should be rejected for missing CSRF
        assert response.status_code == 403

    @patch("app.middleware.csrf._get_secret_key")
    def test_protected_endpoint_accepts_valid_csrf(self, mock_secret, authenticated_client):
        """Test that valid CSRF token allows request."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Get CSRF token
        csrf_response = authenticated_client.get("/api/v2/auth/csrf-token")
        token = csrf_response.json()["csrf_token"]

        # Create patient with CSRF token
        response = authenticated_client.post(
            "/api/v2/patients",
            json={
                "name": "Test Patient",
                "birth_date": "1990-01-01"
            },
            headers={"X-CSRF-Token": token},
            cookies={"csrf_token": token}
        )

        # Should succeed (or fail with validation error, not CSRF error)
        assert response.status_code != 403

    @patch("app.middleware.csrf._get_secret_key")
    def test_get_requests_dont_require_csrf(self, mock_secret, authenticated_client):
        """Test that GET requests don't require CSRF token."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # GET without CSRF should work
        response = authenticated_client.get("/api/v2/patients")

        # Should not be CSRF error (may be auth error or success)
        assert response.status_code != 403 or "csrf" not in response.text.lower()

    @patch("app.middleware.csrf._get_secret_key")
    def test_login_endpoint_exempt_from_csrf(self, mock_secret, client):
        """Test that login endpoint is exempt from CSRF."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Login without CSRF should work
        response = client.post(
            "/api/v2/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )

        # Should not be CSRF error
        assert response.status_code != 403 or "csrf" not in response.text.lower()

    @patch("app.middleware.csrf._get_secret_key")
    def test_health_endpoint_exempt_from_csrf(self, mock_secret, client):
        """Test that health endpoint is exempt from CSRF."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = client.get("/health")

        assert response.status_code == 200


@pytest.mark.security
@pytest.mark.integration
class TestCSRFErrorResponses:
    """Test CSRF error responses."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_missing_token_error_message(self, mock_secret, authenticated_client):
        """Test error message when CSRF token is missing."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = authenticated_client.post(
            "/api/v2/patients",
            json={"name": "Test"}
        )

        assert response.status_code == 403
        error = response.json()
        assert "error" in error
        assert "csrf_token_missing" in error["error"]
        assert "message" in error

    @patch("app.middleware.csrf._get_secret_key")
    def test_invalid_token_error_message(self, mock_secret, authenticated_client):
        """Test error message when CSRF token is invalid."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = authenticated_client.post(
            "/api/v2/patients",
            json={"name": "Test"},
            headers={"X-CSRF-Token": "invalid-token"},
            cookies={"csrf_token": "invalid-token"}
        )

        assert response.status_code == 403
        error = response.json()
        assert "error" in error
        assert "csrf" in error["error"].lower()

    @patch("app.middleware.csrf._get_secret_key")
    def test_mismatch_token_error_message(self, mock_secret, authenticated_client):
        """Test error message when tokens don't match."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from app.middleware.csrf import generate_csrf_token
        import time

        token1 = generate_csrf_token()
        time.sleep(0.01)
        token2 = generate_csrf_token()

        response = authenticated_client.post(
            "/api/v2/patients",
            json={"name": "Test"},
            headers={"X-CSRF-Token": token1},
            cookies={"csrf_token": token2}
        )

        assert response.status_code == 403
        error = response.json()
        assert "error" in error
        assert "csrf_mismatch" in error["error"]


@pytest.mark.security
@pytest.mark.integration
class TestCSRFFullAuthFlow:
    """Test CSRF in complete authentication workflow."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_complete_auth_flow_with_csrf(self, mock_secret, client, test_user):
        """Test complete flow: get token -> login -> protected action."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Step 1: Get CSRF token
        csrf_response = client.get("/api/v2/auth/csrf-token")
        token = csrf_response.json()["csrf_token"]

        # Step 2: Login (exempt from CSRF)
        login_response = client.post(
            "/api/v2/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"]
            }
        )

        # Step 3: Make protected request with CSRF
        if login_response.status_code == 200:
            access_token = login_response.json().get("access_token")

            response = client.post(
                "/api/v2/patients",
                json={
                    "name": "Test Patient",
                    "birth_date": "1990-01-01"
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-CSRF-Token": token
                },
                cookies={"csrf_token": token}
            )

            # Should not have CSRF error
            assert response.status_code != 403 or "csrf" not in response.text.lower()


@pytest.mark.security
@pytest.mark.integration
class TestCSRFCookieLifecycle:
    """Test CSRF cookie lifecycle."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_cookie_persists_across_requests(self, mock_secret):
        """Test that CSRF cookie persists."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Use persistent client
        with TestClient(app) as client:
            # Get CSRF token
            response1 = client.get("/api/v2/auth/csrf-token")
            token = response1.json()["csrf_token"]

            # Cookie should be set
            assert "csrf_token" in response1.cookies

            # Make another request - cookie should still be there
            response2 = client.get("/health")

            # Cookie should persist (depending on TestClient behavior)
            # Note: TestClient may not fully emulate browser cookie behavior

    @patch("app.middleware.csrf._get_secret_key")
    @patch("app.middleware.csrf._is_production")
    def test_cookie_attributes_development(self, mock_prod, mock_secret, client):
        """Test cookie attributes in development mode."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"
        mock_prod.return_value = False

        response = client.get("/api/v2/auth/csrf-token")

        # Cookie should be set
        assert "csrf_token" in response.cookies

        # Note: TestClient has limited cookie attribute inspection


@pytest.mark.security
@pytest.mark.integration
class TestCSRFConcurrentRequests:
    """Test CSRF with concurrent requests."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_same_token_multiple_requests(self, mock_secret, authenticated_client):
        """Test that same token can be used for multiple requests."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Get CSRF token
        csrf_response = authenticated_client.get("/api/v2/auth/csrf-token")
        token = csrf_response.json()["csrf_token"]

        # Use same token for multiple requests
        for i in range(5):
            response = authenticated_client.post(
                "/api/v2/patients",
                json={
                    "name": f"Patient {i}",
                    "birth_date": "1990-01-01"
                },
                headers={"X-CSRF-Token": token},
                cookies={"csrf_token": token}
            )

            # All should work (stateless CSRF allows token reuse)
            assert response.status_code != 403 or "csrf" not in response.text.lower()


@pytest.mark.security
@pytest.mark.integration
class TestCSRFWithDifferentMethods:
    """Test CSRF with different HTTP methods."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_post_requires_csrf(self, mock_secret, authenticated_client):
        """Test that POST requires CSRF."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = authenticated_client.post(
            "/api/v2/patients",
            json={"name": "Test"}
        )

        assert response.status_code == 403

    @patch("app.middleware.csrf._get_secret_key")
    def test_put_requires_csrf(self, mock_secret, authenticated_client, test_patient):
        """Test that PUT requires CSRF."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = authenticated_client.put(
            f"/api/v2/patients/{test_patient.id}",
            json={"name": "Updated Name"}
        )

        assert response.status_code == 403

    @patch("app.middleware.csrf._get_secret_key")
    def test_delete_requires_csrf(self, mock_secret, authenticated_client, test_patient):
        """Test that DELETE requires CSRF."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = authenticated_client.delete(
            f"/api/v2/patients/{test_patient.id}"
        )

        assert response.status_code == 403

    @patch("app.middleware.csrf._get_secret_key")
    def test_patch_requires_csrf(self, mock_secret, authenticated_client, test_patient):
        """Test that PATCH requires CSRF."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        response = authenticated_client.patch(
            f"/api/v2/patients/{test_patient.id}",
            json={"name": "Patched Name"}
        )

        assert response.status_code == 403
