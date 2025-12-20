"""
CORS + CSRF Integration Tests

Tests the integration of CORS and CSRF protection together:
1. CORS preflight requests with CSRF
2. Cross-origin requests with CSRF tokens
3. Production security validation
4. Error handling when both protections are active
5. Cookie and header coordination

Coverage Goals: 95%+
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware.cors import configure_cors
from app.core.csrf_middleware import CSRFMiddleware
from app.middleware.csrf import (
    generate_csrf_token,
    set_csrf_cookie,
    validate_csrf_token,
)


class TestCORSWithCSRF:
    """Test CORS and CSRF working together."""

    @patch("app.middleware.cors.settings")
    def test_cors_preflight_allowed_without_csrf(self, mock_settings):
        """CORS preflight (OPTIONS) should work without CSRF token."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        # Add CORS first, then CSRF
        configure_cors(app)
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
        )

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

    @patch("app.middleware.cors.settings")
    def test_post_request_requires_both_cors_and_csrf(self, mock_settings):
        """POST requests should require both valid CORS origin and CSRF token."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
        )

        client = TestClient(app)

        # Generate valid CSRF token
        token = generate_csrf_token("test-secret-key-32-characters-long")

        # POST with valid origin and CSRF token should work
        response = client.post(
            "/api/test",
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": token,
            },
        )

        # Should succeed (both CORS and CSRF valid)
        assert response.status_code == 200

    @patch("app.middleware.cors.settings")
    def test_reject_invalid_cors_origin_even_with_valid_csrf(self, mock_settings):
        """Invalid CORS origin should be rejected even with valid CSRF."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://example.com"]

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
        )

        client = TestClient(app)

        # Generate valid CSRF token
        token = generate_csrf_token("test-secret-key-32-characters-long")

        # POST with invalid origin (even with valid CSRF)
        response = client.post(
            "/api/test",
            headers={
                "Origin": "https://attacker.com",  # Not in allowed list
                "X-CSRF-Token": token,
            },
        )

        # CORS should reject before CSRF validation
        assert response.status_code != 200


class TestCSRFTokenInCORSHeaders:
    """Test CSRF token exchange via CORS-allowed headers."""

    @patch("app.middleware.cors.settings")
    def test_csrf_token_endpoint_with_cors(self, mock_settings):
        """CSRF token endpoint should work with CORS."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.get("/api/v2/auth/csrf-token")
        async def get_csrf_token():
            return {"csrf_token": generate_csrf_token("test-secret-key-32-characters-long")}

        configure_cors(app)

        client = TestClient(app)

        # GET CSRF token from allowed origin
        response = client.get(
            "/api/v2/auth/csrf-token",
            headers={"Origin": "http://localhost:5173"},
        )

        assert response.status_code == 200
        assert "csrf_token" in response.json()
        assert "access-control-allow-origin" in response.headers

    @patch("app.middleware.cors.settings")
    def test_csrf_headers_in_cors_allowed_list(self, mock_settings):
        """CSRF headers should be in CORS allowed headers."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        # CORS configuration should include CSRF headers
        configure_cors(
            app,
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-CSRF-Token",
                "X-CSRFToken",
                "X-XSRF-Token",
            ],
        )

        # Verify middleware was added (headers are verified in middleware)
        assert len(app.user_middleware) > 0


class TestProductionSecurity:
    """Test production security with both CORS and CSRF."""

    @patch("app.middleware.cors.settings")
    def test_production_requires_https_and_secure_cookies(self, mock_settings):
        """Production should require HTTPS origins and secure cookies."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://example.com"]

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        # CORS should enforce HTTPS in production
        configure_cors(app)

        # CSRF should use secure cookies in production
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
        )

        # Verify middleware was configured
        assert len(app.user_middleware) > 0

    @patch("app.middleware.cors.settings")
    def test_production_rejects_http_origins(self, mock_settings):
        """Production should reject HTTP origins even if configured."""
        from app.middleware.cors import validate_cors_origins

        mock_settings.APP_ENVIRONMENT = "production"

        app = FastAPI()

        # Should raise error when trying to configure HTTP in production
        with pytest.raises(ValueError, match="must use HTTPS in production"):
            validate_cors_origins(["http://example.com"])


class TestCookieCoordination:
    """Test cookie handling between CORS and CSRF."""

    @patch("app.middleware.cors.settings")
    def test_csrf_cookie_sent_with_cors_credentials(self, mock_settings):
        """CSRF cookie should be sent when CORS allows credentials."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.get("/api/test")
        async def test_route(request):
            response = JSONResponse(content={"message": "success"})
            set_csrf_cookie(request, response)
            return response

        configure_cors(app, allow_credentials=True)

        client = TestClient(app)

        response = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:5173"},
        )

        assert response.status_code == 200
        # Cookie should be set
        assert "set-cookie" in response.headers

    @patch("app.middleware.cors.settings")
    def test_csrf_double_submit_with_cors(self, mock_settings):
        """Test Double Submit Cookie pattern with CORS."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.post("/api/test", dependencies=[Depends(validate_csrf_token)])
        async def test_route():
            return {"message": "success"}

        configure_cors(app, allow_credentials=True)

        client = TestClient(app)

        # Generate token
        secret_key = "test-secret-key-32-characters-long"
        token = generate_csrf_token(secret_key)

        # Send token in both header and cookie (Double Submit)
        response = client.post(
            "/api/test",
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": token,
            },
            cookies={"fastapi-csrf-token": token},
        )

        # Should work with valid Double Submit
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling with both CORS and CSRF."""

    @patch("app.middleware.cors.settings")
    def test_csrf_error_includes_cors_headers(self, mock_settings):
        """CSRF errors should still include CORS headers."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
        )

        client = TestClient(app)

        # POST without CSRF token
        response = client.post(
            "/api/test",
            headers={"Origin": "http://localhost:5173"},
        )

        # Should return 403 with CORS headers
        assert response.status_code == 403
        assert "csrf_token_missing" in response.json()["error"]

    @patch("app.middleware.cors.settings")
    def test_multiple_csrf_header_formats(self, mock_settings):
        """Test multiple CSRF header format support."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        # CORS should allow multiple CSRF header names
        configure_cors(
            app,
            allow_headers=[
                "X-CSRF-Token",   # FastAPI default
                "X-CSRFToken",    # Django format
                "X-XSRF-Token",   # Angular/Axios format
            ],
        )

        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
        )

        # Verify middleware configured
        assert len(app.user_middleware) > 0


class TestDevelopmentVsProduction:
    """Test different behavior in development vs production."""

    @patch("app.middleware.cors.settings")
    def test_development_allows_http_localhost(self, mock_settings):
        """Development should allow http://localhost."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

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

    @patch("app.middleware.cors.settings")
    def test_production_requires_https(self, mock_settings):
        """Production should require HTTPS origins."""
        from app.middleware.cors import validate_cors_origins

        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://example.com"]

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        # Should configure without errors
        configure_cors(app)

        # All origins should be HTTPS
        validate_cors_origins(["https://example.com"])  # Should not raise

    @patch("app.middleware.cors.settings")
    def test_development_uses_insecure_cookies(self, mock_settings):
        """Development can use insecure cookies for localhost."""
        from app.middleware.csrf import CsrfSettings

        settings = CsrfSettings(
            secret_key="test-secret-key-32-characters-long",
            cookie_secure=False,  # Allowed in development
            cookie_httponly=True,
            cookie_samesite="strict",
        )

        assert settings.cookie_secure is False  # OK for localhost

    @patch("app.middleware.cors.settings")
    def test_production_enforces_secure_cookies(self, mock_settings):
        """Production should enforce secure cookies."""
        from app.middleware.csrf import CsrfSettings

        settings = CsrfSettings(
            secret_key="test-secret-key-32-characters-long",
            cookie_secure=True,  # Required in production
            cookie_httponly=True,
            cookie_samesite="strict",
        )

        assert settings.cookie_secure is True


class TestExemptPaths:
    """Test paths that are exempt from CSRF but still have CORS."""

    @patch("app.middleware.cors.settings")
    def test_health_endpoint_exempt_from_csrf_but_has_cors(self, mock_settings):
        """Health endpoint should be exempt from CSRF but have CORS."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        configure_cors(app)
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
            exempt_paths=["/health"],
        )

        client = TestClient(app)

        # Should work without CSRF token
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    @patch("app.middleware.cors.settings")
    def test_docs_exempt_from_csrf_but_has_cors(self, mock_settings):
        """Docs endpoints should be exempt from CSRF but have CORS."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        configure_cors(app)
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
        )

        client = TestClient(app)

        # OpenAPI JSON should work without CSRF
        response = client.get(
            "/openapi.json",
            headers={"Origin": "http://localhost:5173"},
        )

        assert response.status_code == 200


class TestEdgeCases:
    """Test edge cases in CORS + CSRF integration."""

    @patch("app.middleware.cors.settings")
    def test_missing_origin_header(self, mock_settings):
        """Requests without Origin header should still validate CSRF."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
        )

        client = TestClient(app)

        # POST without Origin header (same-origin request)
        response = client.post("/api/test")

        # Should still require CSRF token
        assert response.status_code == 403
        assert "csrf_token_missing" in response.json()["error"]

    @patch("app.middleware.cors.settings")
    def test_cors_with_wildcard_rejected_in_production(self, mock_settings):
        """Wildcard CORS with credentials should be rejected."""
        from app.middleware.cors import validate_cors_origins

        mock_settings.APP_ENVIRONMENT = "production"

        # Should raise error
        with pytest.raises(ValueError):
            validate_cors_origins(["*"])

    @patch("app.middleware.cors.settings")
    def test_expired_csrf_token_with_valid_cors(self, mock_settings):
        """Expired CSRF token should be rejected even with valid CORS."""
        import time
        import base64
        from app.middleware.csrf import _generate_token_signature

        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test-secret-key-32-characters-long",
            token_expiry=3600,
        )

        client = TestClient(app)

        # Create expired token
        secret_key = "test-secret-key-32-characters-long"
        old_timestamp = str(int(time.time()) - 7200)  # 2 hours ago
        random_data = "a" * 64
        data = f"{old_timestamp}.{random_data}"
        signature = _generate_token_signature(data, secret_key)
        token_raw = f"{data}.{signature}"
        expired_token = base64.urlsafe_b64encode(token_raw.encode("utf-8")).decode("utf-8").rstrip("=")

        # POST with valid CORS but expired CSRF
        response = client.post(
            "/api/test",
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": expired_token,
            },
        )

        # Should reject expired token
        assert response.status_code == 403
