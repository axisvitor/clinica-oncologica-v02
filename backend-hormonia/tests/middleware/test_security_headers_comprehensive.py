"""
Comprehensive Security Headers Middleware Tests

Tests all security headers middleware functionality including:
- OWASP security headers implementation
- HSTS configuration and HTTPS enforcement
- CSP (Content Security Policy) validation
- X-Frame-Options, X-Content-Type-Options protection
- Permissions Policy enforcement
- Production vs development configurations
- Error handling and edge cases
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import Response
from starlette.types import ASGIApp

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    create_production_security_middleware
)


class TestSecurityHeadersMiddleware:
    """Test basic SecurityHeadersMiddleware functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

    def test_middleware_initialization_default(self):
        """Test middleware initialization with default values."""
        middleware = SecurityHeadersMiddleware(self.app)

        assert middleware.enable_hsts is True
        assert middleware.hsts_max_age == 31536000  # 1 year
        assert middleware.hsts_include_subdomains is True
        assert middleware.hsts_preload is False
        assert middleware.frame_options == "DENY"
        assert middleware.content_type_options == "nosniff"
        assert middleware.xss_protection == "1; mode=block"
        assert middleware.referrer_policy == "strict-origin-when-cross-origin"

    def test_middleware_initialization_custom(self):
        """Test middleware initialization with custom values."""
        middleware = SecurityHeadersMiddleware(
            self.app,
            enable_hsts=False,
            hsts_max_age=86400,  # 1 day
            hsts_include_subdomains=False,
            hsts_preload=True,
            frame_options="SAMEORIGIN",
            content_type_options="nosniff",
            xss_protection="0",
            referrer_policy="no-referrer",
            csp_policy="default-src 'self'",
            permissions_policy="geolocation=()"
        )

        assert middleware.enable_hsts is False
        assert middleware.hsts_max_age == 86400
        assert middleware.hsts_include_subdomains is False
        assert middleware.hsts_preload is True
        assert middleware.frame_options == "SAMEORIGIN"
        assert middleware.xss_protection == "0"
        assert middleware.referrer_policy == "no-referrer"
        assert middleware.csp_policy == "default-src 'self'"
        assert middleware.permissions_policy == "geolocation=()"

    def test_build_hsts_header_basic(self):
        """Test HSTS header construction with basic configuration."""
        middleware = SecurityHeadersMiddleware(
            self.app,
            hsts_max_age=31536000,
            hsts_include_subdomains=True,
            hsts_preload=False
        )

        hsts_header = middleware._build_hsts_header()
        assert hsts_header == "max-age=31536000; includeSubDomains"

    def test_build_hsts_header_with_preload(self):
        """Test HSTS header construction with preload enabled."""
        middleware = SecurityHeadersMiddleware(
            self.app,
            hsts_max_age=63072000,  # 2 years
            hsts_include_subdomains=True,
            hsts_preload=True
        )

        hsts_header = middleware._build_hsts_header()
        assert hsts_header == "max-age=63072000; includeSubDomains; preload"

    def test_build_hsts_header_minimal(self):
        """Test HSTS header construction with minimal configuration."""
        middleware = SecurityHeadersMiddleware(
            self.app,
            hsts_max_age=86400,
            hsts_include_subdomains=False,
            hsts_preload=False
        )

        hsts_header = middleware._build_hsts_header()
        assert hsts_header == "max-age=86400"

    def test_get_default_csp(self):
        """Test default CSP policy generation."""
        middleware = SecurityHeadersMiddleware(self.app)

        csp = middleware._get_default_csp()

        # Check key CSP directives
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self' 'unsafe-inline'" in csp
        assert "img-src 'self' data: https:" in csp
        assert "font-src 'self' data:" in csp
        assert "connect-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp


class TestSecurityHeadersIntegration:
    """Test security headers middleware integration with FastAPI."""

    def setup_method(self):
        """Set up test app with security middleware."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @self.app.post("/api/data")
        async def api_endpoint():
            return {"result": "success"}

    def test_security_headers_http_request(self):
        """Test security headers on HTTP request."""
        # Add middleware
        self.app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(self.app)

        response = client.get("/test")

        assert response.status_code == 200

        # Check security headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in response.headers

        # HSTS should NOT be set for HTTP requests
        assert "Strict-Transport-Security" not in response.headers

    def test_security_headers_custom_csp(self):
        """Test security headers with custom CSP policy."""
        custom_csp = "default-src 'none'; script-src 'self'; style-src 'self'"

        self.app.add_middleware(
            SecurityHeadersMiddleware,
            csp_policy=custom_csp
        )

        client = TestClient(self.app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.headers["Content-Security-Policy"] == custom_csp

    def test_security_headers_custom_permissions_policy(self):
        """Test security headers with custom permissions policy."""
        custom_permissions = "geolocation=(), microphone=(), camera=()"

        self.app.add_middleware(
            SecurityHeadersMiddleware,
            permissions_policy=custom_permissions
        )

        client = TestClient(self.app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.headers["Permissions-Policy"] == custom_permissions

    def test_security_headers_disabled_hsts(self):
        """Test security headers with HSTS disabled."""
        self.app.add_middleware(
            SecurityHeadersMiddleware,
            enable_hsts=False
        )

        client = TestClient(self.app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "Strict-Transport-Security" not in response.headers

    def test_security_headers_different_frame_options(self):
        """Test security headers with different frame options."""
        self.app.add_middleware(
            SecurityHeadersMiddleware,
            frame_options="SAMEORIGIN"
        )

        client = TestClient(self.app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_security_headers_post_request(self):
        """Test security headers on POST requests."""
        self.app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(self.app)
        response = client.post("/api/data", json={"test": "data"})

        assert response.status_code == 200

        # Same security headers should be applied
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Security-Policy" in response.headers


class TestProductionSecurityMiddleware:
    """Test production security middleware factory."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

    def test_create_production_middleware_defaults(self):
        """Test production middleware with default configuration."""
        middleware = create_production_security_middleware(self.app)

        assert isinstance(middleware, SecurityHeadersMiddleware)
        assert middleware.enable_hsts is True
        assert middleware.hsts_max_age == 31536000  # 1 year
        assert middleware.hsts_include_subdomains is True
        assert middleware.hsts_preload is False  # Conservative default
        assert middleware.frame_options == "DENY"
        assert middleware.content_type_options == "nosniff"
        assert middleware.xss_protection == "1; mode=block"
        assert middleware.referrer_policy == "strict-origin-when-cross-origin"

    def test_create_production_middleware_custom_csp(self):
        """Test production middleware with custom CSP."""
        custom_csp = "default-src 'self'; script-src 'self' 'unsafe-eval'"

        middleware = create_production_security_middleware(
            self.app,
            custom_csp=custom_csp
        )

        assert middleware.csp_policy == custom_csp

    def test_production_middleware_permissions_policy(self):
        """Test production middleware includes restrictive permissions policy."""
        middleware = create_production_security_middleware(self.app)

        permissions_policy = middleware.permissions_policy

        # Check that sensitive features are disabled
        assert "geolocation=()" in permissions_policy
        assert "microphone=()" in permissions_policy
        assert "camera=()" in permissions_policy
        assert "payment=()" in permissions_policy
        assert "usb=()" in permissions_policy

    def test_production_middleware_integration(self):
        """Test production middleware integration."""
        # Create and add production middleware
        middleware = create_production_security_middleware(self.app)
        self.app.add_middleware(SecurityHeadersMiddleware, **middleware.__dict__)

        client = TestClient(self.app)
        response = client.get("/test")

        assert response.status_code == 200

        # Verify all security headers are present
        expected_headers = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy"
        ]

        for header in expected_headers:
            assert header in response.headers


class TestSecurityHeadersErrorHandling:
    """Test error handling and edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()

        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @self.app.get("/error")
        async def error_endpoint():
            raise Exception("Test error")

    def test_middleware_dispatch_with_mock_request(self):
        """Test middleware dispatch method directly."""
        middleware = SecurityHeadersMiddleware(self.app)

        # Create mock request and response
        mock_request = MagicMock()
        mock_request.url.scheme = "https"

        mock_response = Response()

        # Mock call_next
        async def mock_call_next(request):
            return mock_response

        # Test dispatch
        async def run_dispatch():
            result = await middleware.dispatch(mock_request, mock_call_next)
            return result

        import asyncio
        result = asyncio.run(run_dispatch())

        # Check that headers were added
        assert "X-Frame-Options" in result.headers
        assert "X-Content-Type-Options" in result.headers

    def test_hsts_header_building_edge_cases(self):
        """Test HSTS header building with edge cases."""
        # Test with very long max age
        middleware = SecurityHeadersMiddleware(
            self.app,
            hsts_max_age=999999999,
            hsts_include_subdomains=True,
            hsts_preload=True
        )

        hsts_header = middleware._build_hsts_header()
        assert "max-age=999999999" in hsts_header
        assert "includeSubDomains" in hsts_header
        assert "preload" in hsts_header

    def test_default_csp_completeness(self):
        """Test that default CSP covers all major directives."""
        middleware = SecurityHeadersMiddleware(self.app)
        csp = middleware._get_default_csp()

        # Check for comprehensive coverage
        required_directives = [
            "default-src",
            "script-src",
            "style-src",
            "img-src",
            "font-src",
            "connect-src",
            "frame-ancestors",
            "base-uri",
            "form-action"
        ]

        for directive in required_directives:
            assert directive in csp

    def test_security_headers_none_values(self):
        """Test middleware with None values for optional parameters."""
        middleware = SecurityHeadersMiddleware(
            self.app,
            csp_policy=None,
            permissions_policy=None
        )

        # Should use defaults
        assert middleware.csp_policy is None
        assert middleware.permissions_policy is None

    def test_middleware_with_different_request_schemes(self):
        """Test middleware behavior with different URL schemes."""
        middleware = SecurityHeadersMiddleware(self.app)

        # Test HTTP request (no HSTS)
        mock_request_http = MagicMock()
        mock_request_http.url.scheme = "http"

        mock_response = Response()

        async def mock_call_next(request):
            return mock_response

        async def test_http():
            result = await middleware.dispatch(mock_request_http, mock_call_next)
            return result

        import asyncio
        result_http = asyncio.run(test_http())

        # Should not have HSTS header for HTTP
        assert "Strict-Transport-Security" not in result_http.headers

    def test_security_headers_with_various_configurations(self):
        """Test various security header configurations."""
        configurations = [
            {
                "frame_options": "SAMEORIGIN",
                "xss_protection": "0",
                "referrer_policy": "no-referrer"
            },
            {
                "frame_options": "ALLOW-FROM https://example.com",
                "content_type_options": "nosniff",
                "referrer_policy": "same-origin"
            }
        ]

        for config in configurations:
            middleware = SecurityHeadersMiddleware(self.app, **config)

            # Verify configuration was applied
            for key, value in config.items():
                assert getattr(middleware, key) == value


class TestSecurityHeadersCompliance:
    """Test security headers compliance with standards."""

    def test_owasp_recommended_headers(self):
        """Test that OWASP recommended headers are implemented."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        client = TestClient(app)
        response = client.get("/test")

        # OWASP recommended headers
        owasp_headers = {
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-Content-Type-Options": ["nosniff"],
            "X-XSS-Protection": ["1; mode=block", "0"],
            "Strict-Transport-Security": None,  # Only for HTTPS
            "Content-Security-Policy": None,  # Should be present
            "Referrer-Policy": ["strict-origin-when-cross-origin", "no-referrer", "same-origin"]
        }

        for header, allowed_values in owasp_headers.items():
            if header == "Strict-Transport-Security":
                # Only present for HTTPS
                continue
            elif header == "Content-Security-Policy":
                assert header in response.headers
            elif allowed_values:
                assert header in response.headers
                assert response.headers[header] in allowed_values
            else:
                assert header in response.headers

    def test_medical_application_security_requirements(self):
        """Test security headers meet medical application requirements."""
        # Use production configuration for medical application
        app = FastAPI()
        middleware = create_production_security_middleware(app)
        app.add_middleware(SecurityHeadersMiddleware, **middleware.__dict__)

        @app.get("/patient-data")
        async def patient_data():
            return {"patient": "data"}

        client = TestClient(app)
        response = client.get("/patient-data")

        # Medical applications should have strict security
        assert response.headers["X-Frame-Options"] == "DENY"  # Prevent clickjacking
        assert response.headers["X-Content-Type-Options"] == "nosniff"  # Prevent MIME sniffing
        assert "Content-Security-Policy" in response.headers  # XSS protection

        # Check CSP is restrictive
        csp = response.headers["Content-Security-Policy"]
        assert "'self'" in csp  # Only allow same-origin by default
        assert "frame-ancestors 'none'" in csp  # Prevent framing

    def test_permissions_policy_restrictive(self):
        """Test that permissions policy is appropriately restrictive."""
        middleware = create_production_security_middleware(MagicMock())

        permissions_policy = middleware.permissions_policy

        # Should deny access to sensitive browser features
        sensitive_features = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()"
        ]

        for feature in sensitive_features:
            assert feature in permissions_policy


if __name__ == "__main__":
    pytest.main([__file__])
