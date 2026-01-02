"""
CORS + CSRF Integration Tests

Tests the integration of CORS and CSRF protection together.
Updated for simplified middleware implementation.
"""

from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestCORSWithCSRF:
    """Test CORS and CSRF working together."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_settings = MagicMock()
        self.mock_settings.APP_ENVIRONMENT = "development"
        self.mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]
        self.mock_settings.SECURITY_CSRF_SECRET_KEY = "test-secret-key-32-characters-long-for-testing"

    @patch("app.core.cors.settings")
    def test_cors_preflight_allowed_without_csrf(self, mock_settings):
        """CORS preflight (OPTIONS) should work without CSRF token."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)

        client = TestClient(app)

        # OPTIONS request should work without CSRF
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should return 200 with CORS headers
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    @patch("app.core.cors.settings")
    def test_cors_allows_configured_origins(self, mock_settings):
        """CORS should allow configured origins."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)

        client = TestClient(app)

        response = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:5173"},
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


class TestCSRFMiddleware:
    """Test CSRF middleware functionality."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_token_generation(self, mock_get_secret):
        """Test CSRF token generation."""
        mock_get_secret.return_value = "test-secret-key-32-characters-long-for-testing"

        from app.middleware.csrf import generate_csrf_token, validate_csrf_token

        token = generate_csrf_token()
        assert token is not None
        assert "." in token  # Format: timestamp.random.signature

        # Token should be valid
        assert validate_csrf_token(token) is True

    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_token_validation(self, mock_get_secret):
        """Test CSRF token validation."""
        mock_get_secret.return_value = "test-secret-key-32-characters-long-for-testing"

        from app.middleware.csrf import generate_csrf_token, validate_csrf_token

        token = generate_csrf_token()

        # Valid token
        assert validate_csrf_token(token) is True

        # Invalid token
        assert validate_csrf_token("invalid-token") is False
        assert validate_csrf_token("a.b.c") is False  # Wrong signature

    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_exempt_paths(self, mock_get_secret):
        """Test CSRF exempt paths."""
        mock_get_secret.return_value = "test-secret-key-32-characters-long-for-testing"

        from app.middleware.csrf import is_csrf_exempt

        # GET requests are always exempt
        assert is_csrf_exempt("/api/test", "GET") is True
        assert is_csrf_exempt("/api/test", "OPTIONS") is True
        assert is_csrf_exempt("/api/test", "HEAD") is True

        # Specific paths are exempt
        assert is_csrf_exempt("/health", "POST") is True
        assert is_csrf_exempt("/docs", "POST") is True
        assert is_csrf_exempt("/api/v2/auth/csrf-token", "POST") is True

        # Regular POST paths are NOT exempt
        assert is_csrf_exempt("/api/test", "POST") is False


class TestIntegration:
    """Integration tests for CORS + CSRF."""

    @patch("app.core.cors.settings")
    @patch("app.middleware.csrf._get_secret_key")
    def test_full_request_flow(self, mock_get_secret, mock_cors_settings):
        """Test full request flow with both CORS and CSRF."""
        mock_cors_settings.APP_ENVIRONMENT = "development"
        mock_cors_settings.get_cors_origins.return_value = ["http://localhost:5173"]
        mock_get_secret.return_value = "test-secret-key-32-characters-long-for-testing"

        from app.core.cors import configure_cors
        from app.middleware.csrf import CSRFMiddleware, generate_csrf_token

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        # Add CSRF middleware first (executes later)
        app.add_middleware(CSRFMiddleware)

        # Add CORS last (executes first)
        configure_cors(app)

        client = TestClient(app)

        # Generate valid token
        token = generate_csrf_token()

        # POST with valid CORS and CSRF should work
        response = client.post(
            "/api/test",
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": token,
            },
            cookies={"csrf_token": token},  # Double Submit Cookie
        )

        # Should succeed
        assert response.status_code == 200

    @patch("app.core.cors.settings")
    @patch("app.middleware.csrf._get_secret_key")
    def test_missing_csrf_token_rejected(self, mock_get_secret, mock_cors_settings):
        """Test that missing CSRF token is rejected."""
        mock_cors_settings.APP_ENVIRONMENT = "development"
        mock_cors_settings.get_cors_origins.return_value = ["http://localhost:5173"]
        mock_get_secret.return_value = "test-secret-key-32-characters-long-for-testing"

        from app.core.cors import configure_cors
        from app.middleware.csrf import CSRFMiddleware

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        app.add_middleware(CSRFMiddleware)
        configure_cors(app)

        client = TestClient(app)

        # POST without CSRF token
        response = client.post(
            "/api/test",
            headers={"Origin": "http://localhost:5173"},
        )

        # Should be rejected
        assert response.status_code == 403
        assert "csrf_token_missing" in response.json()["error"]

    @patch("app.core.cors.settings")
    @patch("app.middleware.csrf._get_secret_key")
    def test_health_endpoint_exempt(self, mock_get_secret, mock_cors_settings):
        """Test that health endpoint is exempt from CSRF."""
        mock_cors_settings.APP_ENVIRONMENT = "development"
        mock_cors_settings.get_cors_origins.return_value = ["http://localhost:5173"]
        mock_get_secret.return_value = "test-secret-key-32-characters-long-for-testing"

        from app.core.cors import configure_cors
        from app.middleware.csrf import CSRFMiddleware

        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        app.add_middleware(CSRFMiddleware)
        configure_cors(app)

        client = TestClient(app)

        # Health check should work without CSRF
        response = client.get("/health")
        assert response.status_code == 200
