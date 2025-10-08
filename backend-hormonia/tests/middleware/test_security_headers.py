"""
Integration tests for Security Headers Middleware.

Tests comprehensive OWASP security headers implementation.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    RateLimitHeadersMiddleware,
    RequestIDMiddleware
)


@pytest.fixture
def app():
    """Create FastAPI app with security middleware."""
    app = FastAPI()

    # Add security middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=True,
        enable_csp=True,
        enable_frame_options=True
    )
    app.add_middleware(RateLimitHeadersMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/secure")
    async def secure_endpoint():
        return {"data": "sensitive"}

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""

    def test_content_type_options_header(self, client):
        """Test X-Content-Type-Options header is set."""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_frame_options_header(self, client):
        """Test X-Frame-Options header is set."""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_xss_protection_header(self, client):
        """Test X-XSS-Protection header is set."""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_csp_header(self, client):
        """Test Content-Security-Policy header is set."""
        response = client.get("/test")
        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        csp = response.headers.get("Content-Security-Policy")
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "style-src" in csp

    def test_referrer_policy_header(self, client):
        """Test Referrer-Policy header is set."""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy_header(self, client):
        """Test Permissions-Policy header is set."""
        response = client.get("/test")
        assert response.status_code == 200
        assert "Permissions-Policy" in response.headers
        policy = response.headers.get("Permissions-Policy")
        assert "geolocation=()" in policy
        assert "microphone=()" in policy
        assert "camera=()" in policy

    def test_server_header_removed(self, client):
        """Test server header is removed."""
        response = client.get("/test")
        assert response.status_code == 200
        assert "server" not in response.headers.keys()

    def test_security_version_header(self, client):
        """Test custom security version header."""
        response = client.get("/test")
        assert response.status_code == 200
        assert response.headers.get("X-Security-Headers-Version") == "1.0"

    def test_https_headers_not_set_on_http(self, client):
        """Test HSTS header is not set on HTTP."""
        response = client.get("/test")
        assert response.status_code == 200
        # HSTS should not be set on non-HTTPS
        assert "Strict-Transport-Security" not in response.headers

    def test_all_endpoints_have_headers(self, client):
        """Test all endpoints have security headers."""
        endpoints = ["/test", "/secure"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200

            # Check essential security headers
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers
            assert "X-XSS-Protection" in response.headers
            assert "Content-Security-Policy" in response.headers
            assert "Referrer-Policy" in response.headers
            assert "Permissions-Policy" in response.headers


class TestRequestIDMiddleware:
    """Test request ID middleware."""

    def test_request_id_generation(self, client):
        """Test request ID is generated."""
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None
        assert len(request_id) == 36  # UUID format

    def test_request_id_forwarding(self, client):
        """Test request ID is forwarded if provided."""
        custom_id = "custom-request-id-12345"
        response = client.get("/test", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == custom_id

    def test_unique_request_ids(self, client):
        """Test each request gets unique ID."""
        ids = []
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == 200
            request_id = response.headers.get("X-Request-ID")
            assert request_id not in ids
            ids.append(request_id)


class TestRateLimitHeadersMiddleware:
    """Test rate limit headers middleware."""

    def test_rate_limit_headers_not_present_by_default(self, client):
        """Test rate limit headers are not present without state."""
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers
        assert "X-RateLimit-Remaining" not in response.headers
        assert "X-RateLimit-Reset" not in response.headers

    def test_rate_limit_headers_with_state(self, app, client):
        """Test rate limit headers are added when state is present."""
        @app.middleware("http")
        async def add_rate_limit_state(request: Request, call_next):
            # Simulate rate limiter adding state
            request.state.rate_limit_info = {
                "limit": 100,
                "remaining": 95,
                "reset": 1234567890
            }
            response = await call_next(request)
            return response

        response = client.get("/test")
        assert response.status_code == 200
        assert response.headers.get("X-RateLimit-Limit") == "100"
        assert response.headers.get("X-RateLimit-Remaining") == "95"
        assert response.headers.get("X-RateLimit-Reset") == "1234567890"


class TestMiddlewareIntegration:
    """Test middleware integration and ordering."""

    def test_all_middleware_active(self, client):
        """Test all middleware are active together."""
        response = client.get("/test")
        assert response.status_code == 200

        # From SecurityHeadersMiddleware
        assert "X-Content-Type-Options" in response.headers
        assert "Content-Security-Policy" in response.headers

        # From RequestIDMiddleware
        assert "X-Request-ID" in response.headers

    def test_middleware_error_handling(self, app, client):
        """Test middleware handles errors gracefully."""
        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        response = client.get("/error")
        assert response.status_code == 500

        # Security headers should still be present
        assert "X-Content-Type-Options" in response.headers
        assert "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_performance(self, client):
        """Test middleware doesn't significantly impact performance."""
        import time

        # Warm up
        client.get("/test")

        # Measure response time
        start = time.time()
        for _ in range(100):
            response = client.get("/test")
            assert response.status_code == 200

        elapsed = time.time() - start
        avg_time = elapsed / 100

        # Should be fast (less than 10ms per request)
        assert avg_time < 0.01