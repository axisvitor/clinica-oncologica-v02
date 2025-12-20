"""
Comprehensive CORS + CSRF Integration Tests

Tests the complete CORS+CSRF security stack with real request flows:
1. Handshake flow (GET /csrf-token -> POST with token)
2. Double Submit Cookie pattern validation
3. Preflight requests with CSRF
4. Session recovery after token expiry
5. Error handling and retry logic

Coverage Goals: 100% for critical security paths
"""

import pytest
import time
from unittest.mock import Mock, patch
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from app.middleware.cors import configure_cors
from app.middleware.csrf import (
    CSRFMiddleware,
    get_csrf_token,
    set_csrf_cookie,
    validate_csrf_token,
    CsrfProtectError,
)


class TestCORSCSRFHandshakeFlow:
    """Test complete CORS+CSRF handshake flow."""

    @patch("app.middleware.cors.settings")
    @patch("app.middleware.csrf.get_csrf_settings")
    def test_complete_handshake_flow_from_allowed_origin(
        self, mock_csrf_settings, mock_cors_settings
    ):
        """Test complete flow: preflight -> GET token -> POST with token."""
        # Setup settings
        mock_cors_settings.APP_ENVIRONMENT = "production"
        mock_cors_settings.get_cors_origins.return_value = ["https://frontend.example.com"]

        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        csrf_settings_mock.cookie_name = "fastapi-csrf-token"
        csrf_settings_mock.token_header_name = "X-CSRF-Token"
        csrf_settings_mock.cookie_secure = True
        csrf_settings_mock.cookie_httponly = True
        csrf_settings_mock.cookie_samesite = "strict"
        csrf_settings_mock.cookie_path = "/"
        csrf_settings_mock.cookie_domain = None
        csrf_settings_mock.token_expires_in = 3600
        mock_csrf_settings.return_value = csrf_settings_mock

        # Create app with both middleware
        app = FastAPI()
        configure_cors(app)
        app.add_middleware(CSRFMiddleware)

        # Step 1: Get CSRF token endpoint
        @app.get("/api/v2/auth/csrf-token")
        def get_token(request: Request, response: Response):
            token = get_csrf_token(request)
            set_csrf_cookie(request, response, token)
            return {"csrf_token": token}

        # Step 2: Protected endpoint
        @app.post("/api/v2/users")
        def create_user(request: Request):
            return {"id": 1, "name": "Test User"}

        client = TestClient(app)

        # Step 1: Preflight request (OPTIONS)
        preflight_response = client.options(
            "/api/v2/users",
            headers={
                "Origin": "https://frontend.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-CSRF-Token",
            },
        )

        assert preflight_response.status_code in [200, 204]
        assert "Access-Control-Allow-Origin" in preflight_response.headers

        # Step 2: Get CSRF token
        token_response = client.get(
            "/api/v2/auth/csrf-token",
            headers={"Origin": "https://frontend.example.com"},
        )

        assert token_response.status_code == 200
        csrf_token = token_response.json()["csrf_token"]
        assert csrf_token
        assert csrf_token.count(".") == 2  # timestamp.random.signature

        # Extract cookie
        csrf_cookie = token_response.cookies.get("fastapi-csrf-token")

        # Step 3: Make POST request with CSRF token
        post_response = client.post(
            "/api/v2/users",
            json={"name": "Test User"},
            headers={
                "Origin": "https://frontend.example.com",
                "X-CSRF-Token": csrf_token,
            },
            cookies={"fastapi-csrf-token": csrf_cookie},
        )

        assert post_response.status_code == 200
        assert post_response.json()["name"] == "Test User"

    @patch("app.middleware.cors.settings")
    @patch("app.middleware.csrf.get_csrf_settings")
    def test_handshake_rejected_from_unknown_origin(
        self, mock_csrf_settings, mock_cors_settings
    ):
        """Test that requests from unknown origins are rejected."""
        mock_cors_settings.APP_ENVIRONMENT = "production"
        mock_cors_settings.get_cors_origins.return_value = ["https://frontend.example.com"]

        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        mock_csrf_settings.return_value = csrf_settings_mock

        app = FastAPI()
        configure_cors(app)

        @app.get("/api/v2/users")
        def get_users():
            return []

        client = TestClient(app)

        # Request from evil origin
        response = client.get(
            "/api/v2/users",
            headers={"Origin": "https://evil.com"},
        )

        # CORS should reject or not include CORS headers
        allowed_origin = response.headers.get("Access-Control-Allow-Origin")
        assert allowed_origin != "https://evil.com"


class TestDoubleSubmitCookieIntegration:
    """Test Double Submit Cookie pattern integration."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_double_submit_cookie_validates_match(self, mock_settings):
        """Test that header and cookie must match."""
        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        csrf_settings_mock.cookie_name = "fastapi-csrf-token"
        csrf_settings_mock.token_header_name = "X-CSRF-Token"
        csrf_settings_mock.cookie_secure = False
        csrf_settings_mock.cookie_httponly = True
        csrf_settings_mock.cookie_samesite = "strict"
        csrf_settings_mock.cookie_path = "/"
        csrf_settings_mock.cookie_domain = None
        csrf_settings_mock.token_expires_in = 3600
        mock_settings.return_value = csrf_settings_mock

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/test")
        def test_endpoint():
            return {"success": True}

        client = TestClient(app)

        # Get token first
        from app.middleware.csrf import generate_csrf_token

        token1 = generate_csrf_token(csrf_settings_mock.secret_key)
        time.sleep(0.1)
        token2 = generate_csrf_token(csrf_settings_mock.secret_key)

        # Try with mismatched tokens (header != cookie)
        response = client.post(
            "/test",
            headers={"X-CSRF-Token": token1},
            cookies={"fastapi-csrf-token": token2},
        )

        # Should reject mismatch
        assert response.status_code == 403
        assert "csrf" in response.json()["error"].lower()

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_double_submit_cookie_accepts_match(self, mock_settings):
        """Test that matching header and cookie are accepted."""
        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        csrf_settings_mock.cookie_name = "fastapi-csrf-token"
        csrf_settings_mock.token_header_name = "X-CSRF-Token"
        csrf_settings_mock.cookie_secure = False
        csrf_settings_mock.cookie_httponly = True
        csrf_settings_mock.cookie_samesite = "strict"
        csrf_settings_mock.cookie_path = "/"
        csrf_settings_mock.cookie_domain = None
        csrf_settings_mock.token_expires_in = 3600
        mock_settings.return_value = csrf_settings_mock

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/test")
        def test_endpoint():
            return {"success": True}

        client = TestClient(app)

        from app.middleware.csrf import generate_csrf_token

        token = generate_csrf_token(csrf_settings_mock.secret_key)

        # Matching tokens
        response = client.post(
            "/test",
            json={"data": "test"},
            headers={"X-CSRF-Token": token},
            cookies={"fastapi-csrf-token": token},
        )

        assert response.status_code == 200


class TestSessionRecoveryIntegration:
    """Test session recovery scenarios."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_token_refresh_after_expiry(self, mock_settings):
        """Test that expired tokens can be refreshed."""
        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        csrf_settings_mock.cookie_name = "fastapi-csrf-token"
        csrf_settings_mock.token_header_name = "X-CSRF-Token"
        csrf_settings_mock.cookie_secure = False
        csrf_settings_mock.cookie_httponly = True
        csrf_settings_mock.cookie_samesite = "strict"
        csrf_settings_mock.cookie_path = "/"
        csrf_settings_mock.cookie_domain = None
        csrf_settings_mock.token_expires_in = 1  # 1 second expiry
        mock_settings.return_value = csrf_settings_mock

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.get("/api/v2/auth/csrf-token")
        def get_token(request: Request, response: Response):
            token = get_csrf_token(request)
            set_csrf_cookie(request, response, token)
            return {"csrf_token": token}

        @app.post("/test")
        def test_endpoint():
            return {"success": True}

        client = TestClient(app)

        # Get initial token
        token_response = client.get("/api/v2/auth/csrf-token")
        old_token = token_response.json()["csrf_token"]

        # Wait for token to expire
        time.sleep(2)

        # Try to use expired token
        response = client.post(
            "/test",
            headers={"X-CSRF-Token": old_token},
            cookies={"fastapi-csrf-token": old_token},
        )

        # Should reject expired token
        assert response.status_code == 403

        # Get new token
        new_token_response = client.get("/api/v2/auth/csrf-token")
        new_token = new_token_response.json()["csrf_token"]

        # Should work with new token
        response = client.post(
            "/test",
            headers={"X-CSRF-Token": new_token},
            cookies={"fastapi-csrf-token": new_token},
        )

        assert response.status_code == 200

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_f5_refresh_preserves_cookie(self, mock_settings):
        """Test that F5 refresh preserves CSRF cookie."""
        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        csrf_settings_mock.cookie_name = "fastapi-csrf-token"
        csrf_settings_mock.token_header_name = "X-CSRF-Token"
        csrf_settings_mock.cookie_secure = False
        csrf_settings_mock.cookie_httponly = True
        csrf_settings_mock.cookie_samesite = "strict"
        csrf_settings_mock.cookie_path = "/"
        csrf_settings_mock.cookie_domain = None
        csrf_settings_mock.token_expires_in = 3600
        mock_settings.return_value = csrf_settings_mock

        app = FastAPI()

        @app.get("/api/v2/auth/csrf-token")
        def get_token(request: Request, response: Response):
            token = get_csrf_token(request)
            set_csrf_cookie(request, response, token)
            return {"csrf_token": token}

        client = TestClient(app)

        # Initial page load - get token
        response1 = client.get("/api/v2/auth/csrf-token")
        token = response1.json()["csrf_token"]
        cookies = response1.cookies

        # Simulate F5 refresh - cookies should be sent back
        response2 = client.get("/api/v2/auth/csrf-token", cookies=cookies)

        # Should get token back (either same or new)
        assert "csrf_token" in response2.json()

        # Cookie should be set again with same or new value
        assert "fastapi-csrf-token" in response2.cookies


class TestErrorHandlingIntegration:
    """Test error handling in CORS+CSRF integration."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_missing_csrf_token_error_message(self, mock_settings):
        """Test clear error message when CSRF token is missing."""
        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        csrf_settings_mock.cookie_name = "fastapi-csrf-token"
        csrf_settings_mock.token_header_name = "X-CSRF-Token"
        csrf_settings_mock.cookie_secure = False
        csrf_settings_mock.cookie_httponly = True
        csrf_settings_mock.cookie_samesite = "strict"
        csrf_settings_mock.cookie_path = "/"
        csrf_settings_mock.cookie_domain = None
        csrf_settings_mock.token_expires_in = 3600
        mock_settings.return_value = csrf_settings_mock

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/test")
        def test_endpoint():
            return {"success": True}

        client = TestClient(app)

        # POST without CSRF token
        response = client.post("/test", json={"data": "test"})

        assert response.status_code == 403
        error_data = response.json()
        assert "csrf" in error_data["error"].lower()
        assert "message" in error_data

    @patch("app.middleware.cors.settings")
    @patch("app.middleware.csrf.get_csrf_settings")
    def test_cors_preflight_failure_message(
        self, mock_csrf_settings, mock_cors_settings
    ):
        """Test clear error when CORS preflight fails."""
        mock_cors_settings.APP_ENVIRONMENT = "production"
        mock_cors_settings.get_cors_origins.return_value = ["https://allowed.com"]

        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        mock_csrf_settings.return_value = csrf_settings_mock

        app = FastAPI()
        configure_cors(app)

        @app.get("/test")
        def test_endpoint():
            return {"data": []}

        client = TestClient(app)

        # Request from disallowed origin
        response = client.get(
            "/test",
            headers={"Origin": "https://evil.com"},
        )

        # CORS headers should not reflect evil origin
        allowed_origin = response.headers.get("Access-Control-Allow-Origin")
        assert allowed_origin != "https://evil.com"


class TestPerformanceIntegration:
    """Test performance of CORS+CSRF under load."""

    @patch("app.middleware.cors.settings")
    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_requests_with_different_tokens(
        self, mock_csrf_settings, mock_cors_settings
    ):
        """Test handling of concurrent requests with different CSRF tokens."""
        import concurrent.futures

        mock_cors_settings.APP_ENVIRONMENT = "development"
        mock_cors_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        csrf_settings_mock = Mock()
        csrf_settings_mock.secret_key = "test-secret-key-32-characters-long"
        csrf_settings_mock.cookie_name = "fastapi-csrf-token"
        csrf_settings_mock.token_header_name = "X-CSRF-Token"
        csrf_settings_mock.cookie_secure = False
        csrf_settings_mock.cookie_httponly = True
        csrf_settings_mock.cookie_samesite = "strict"
        csrf_settings_mock.cookie_path = "/"
        csrf_settings_mock.cookie_domain = None
        csrf_settings_mock.token_expires_in = 3600
        mock_csrf_settings.return_value = csrf_settings_mock

        app = FastAPI()
        configure_cors(app)
        app.add_middleware(CSRFMiddleware)

        @app.post("/test")
        def test_endpoint():
            return {"success": True}

        from app.middleware.csrf import generate_csrf_token

        # Generate multiple tokens
        tokens = [
            generate_csrf_token(csrf_settings_mock.secret_key) for _ in range(10)
        ]

        def make_request(token):
            client = TestClient(app)
            return client.post(
                "/test",
                json={"data": "test"},
                headers={
                    "Origin": "http://localhost:5173",
                    "X-CSRF-Token": token,
                },
                cookies={"fastapi-csrf-token": token},
            )

        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, token) for token in tokens]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == 10
