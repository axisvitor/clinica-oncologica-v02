"""
Comprehensive tests for Security Headers Middleware.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, Response
from starlette.types import ASGIApp

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    create_production_security_middleware
)


@pytest.fixture
def mock_app():
    """Mock ASGI application."""
    return Mock(spec=ASGIApp)


@pytest.fixture
def mock_request():
    """Mock HTTP request."""
    request = Mock(spec=Request)
    request.url = Mock()
    request.url.scheme = "https"
    return request


@pytest.fixture
def mock_response():
    """Mock HTTP response."""
    response = Mock(spec=Response)
    response.headers = {}
    return response


@pytest.fixture
async def mock_call_next(mock_response):
    """Mock call_next function."""
    async def call_next(request):
        return mock_response
    return call_next


class TestSecurityHeadersMiddleware:
    """Test SecurityHeadersMiddleware functionality."""

    def test_init_default_values(self, mock_app):
        """Test middleware initialization with default values."""
        middleware = SecurityHeadersMiddleware(mock_app)

        assert middleware.app == mock_app
        assert middleware.enable_hsts is True
        assert middleware.hsts_max_age == 31536000
        assert middleware.hsts_include_subdomains is True
        assert middleware.hsts_preload is False
        assert middleware.frame_options == "DENY"
        assert middleware.content_type_options == "nosniff"
        assert middleware.xss_protection == "1; mode=block"
        assert middleware.referrer_policy == "strict-origin-when-cross-origin"
        assert middleware.csp_policy is None
        assert middleware.permissions_policy is None

    def test_init_custom_values(self, mock_app):
        """Test middleware initialization with custom values."""
        middleware = SecurityHeadersMiddleware(
            mock_app,
            enable_hsts=False,
            hsts_max_age=3600,
            hsts_include_subdomains=False,
            hsts_preload=True,
            frame_options="SAMEORIGIN",
            content_type_options="custom",
            xss_protection="0",
            referrer_policy="no-referrer",
            csp_policy="default-src 'self'",
            permissions_policy="camera=(), microphone=()"
        )

        assert middleware.enable_hsts is False
        assert middleware.hsts_max_age == 3600
        assert middleware.hsts_include_subdomains is False
        assert middleware.hsts_preload is True
        assert middleware.frame_options == "SAMEORIGIN"
        assert middleware.content_type_options == "custom"
        assert middleware.xss_protection == "0"
        assert middleware.referrer_policy == "no-referrer"
        assert middleware.csp_policy == "default-src 'self'"
        assert middleware.permissions_policy == "camera=(), microphone=()"

    def test_build_hsts_header_default(self, mock_app):
        """Test HSTS header building with default values."""
        middleware = SecurityHeadersMiddleware(mock_app)
        hsts_header = middleware._build_hsts_header()

        assert hsts_header == "max-age=31536000; includeSubDomains"

    def test_build_hsts_header_with_preload(self, mock_app):
        """Test HSTS header building with preload enabled."""
        middleware = SecurityHeadersMiddleware(
            mock_app,
            hsts_preload=True
        )
        hsts_header = middleware._build_hsts_header()

        assert hsts_header == "max-age=31536000; includeSubDomains; preload"

    def test_build_hsts_header_no_subdomains(self, mock_app):
        """Test HSTS header building without subdomains."""
        middleware = SecurityHeadersMiddleware(
            mock_app,
            hsts_include_subdomains=False
        )
        hsts_header = middleware._build_hsts_header()

        assert hsts_header == "max-age=31536000"

    def test_build_hsts_header_custom_max_age(self, mock_app):
        """Test HSTS header building with custom max age."""
        middleware = SecurityHeadersMiddleware(
            mock_app,
            hsts_max_age=3600
        )
        hsts_header = middleware._build_hsts_header()

        assert hsts_header == "max-age=3600; includeSubDomains"

    def test_get_default_csp(self, mock_app):
        """Test default CSP generation."""
        middleware = SecurityHeadersMiddleware(mock_app)
        csp = middleware._get_default_csp()

        expected_parts = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]

        for part in expected_parts:
            assert part in csp

    @pytest.mark.asyncio
    async def test_dispatch_basic_headers(self, mock_app, mock_request, mock_call_next):
        """Test that basic security headers are added."""
        middleware = SecurityHeadersMiddleware(mock_app)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in response.headers

    @pytest.mark.asyncio
    async def test_dispatch_hsts_https(self, mock_app, mock_request, mock_call_next):
        """Test HSTS header is added for HTTPS requests."""
        mock_request.url.scheme = "https"
        middleware = SecurityHeadersMiddleware(mock_app)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Strict-Transport-Security" in response.headers
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    @pytest.mark.asyncio
    async def test_dispatch_no_hsts_http(self, mock_app, mock_request, mock_call_next):
        """Test HSTS header is not added for HTTP requests."""
        mock_request.url.scheme = "http"
        middleware = SecurityHeadersMiddleware(mock_app)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_dispatch_hsts_disabled(self, mock_app, mock_request, mock_call_next):
        """Test HSTS header is not added when disabled."""
        middleware = SecurityHeadersMiddleware(mock_app, enable_hsts=False)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_dispatch_custom_csp(self, mock_app, mock_request, mock_call_next):
        """Test custom CSP policy is used."""
        custom_csp = "default-src 'none'; script-src 'self'"
        middleware = SecurityHeadersMiddleware(mock_app, csp_policy=custom_csp)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Content-Security-Policy"] == custom_csp

    @pytest.mark.asyncio
    async def test_dispatch_permissions_policy(self, mock_app, mock_request, mock_call_next):
        """Test permissions policy header is added when configured."""
        permissions_policy = "camera=(), microphone=(), geolocation=()"
        middleware = SecurityHeadersMiddleware(mock_app, permissions_policy=permissions_policy)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Permissions-Policy"] == permissions_policy

    @pytest.mark.asyncio
    async def test_dispatch_no_permissions_policy(self, mock_app, mock_request, mock_call_next):
        """Test permissions policy header is not added when not configured."""
        middleware = SecurityHeadersMiddleware(mock_app)

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Permissions-Policy" not in response.headers

    @pytest.mark.asyncio
    async def test_dispatch_custom_frame_options(self, mock_app, mock_request, mock_call_next):
        """Test custom frame options."""
        middleware = SecurityHeadersMiddleware(mock_app, frame_options="SAMEORIGIN")

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

    @pytest.mark.asyncio
    async def test_dispatch_custom_xss_protection(self, mock_app, mock_request, mock_call_next):
        """Test custom XSS protection."""
        middleware = SecurityHeadersMiddleware(mock_app, xss_protection="0")

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-XSS-Protection"] == "0"

    @pytest.mark.asyncio
    async def test_dispatch_custom_referrer_policy(self, mock_app, mock_request, mock_call_next):
        """Test custom referrer policy."""
        middleware = SecurityHeadersMiddleware(mock_app, referrer_policy="no-referrer")

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["Referrer-Policy"] == "no-referrer"

    @pytest.mark.asyncio
    async def test_dispatch_preserves_existing_headers(self, mock_app, mock_request, mock_call_next):
        """Test that existing response headers are preserved."""
        # Modify the mock response to have existing headers
        async def call_next_with_headers(request):
            response = Mock(spec=Response)
            response.headers = {"X-Custom-Header": "custom-value"}
            return response

        middleware = SecurityHeadersMiddleware(mock_app)
        response = await middleware.dispatch(mock_request, call_next_with_headers)

        # Existing header should be preserved
        assert response.headers["X-Custom-Header"] == "custom-value"
        # Security headers should be added
        assert response.headers["X-Frame-Options"] == "DENY"


class TestCreateProductionSecurityMiddleware:
    """Test production security middleware factory."""

    def test_create_production_security_middleware_defaults(self, mock_app):
        """Test production middleware creation with defaults."""
        middleware = create_production_security_middleware(mock_app)

        assert isinstance(middleware, SecurityHeadersMiddleware)
        assert middleware.enable_hsts is True
        assert middleware.hsts_max_age == 31536000
        assert middleware.hsts_include_subdomains is True
        assert middleware.hsts_preload is False
        assert middleware.frame_options == "DENY"
        assert middleware.content_type_options == "nosniff"
        assert middleware.xss_protection == "1; mode=block"
        assert middleware.referrer_policy == "strict-origin-when-cross-origin"
        assert middleware.csp_policy is None

        # Check permissions policy
        expected_permissions = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "accelerometer=()"
        ]
        for permission in expected_permissions:
            assert permission in middleware.permissions_policy

    def test_create_production_security_middleware_custom_csp(self, mock_app):
        """Test production middleware creation with custom CSP."""
        custom_csp = "default-src 'self'; script-src 'self' 'unsafe-inline'"
        middleware = create_production_security_middleware(mock_app, custom_csp=custom_csp)

        assert middleware.csp_policy == custom_csp

    @pytest.mark.asyncio
    async def test_production_middleware_integration(self, mock_app, mock_request, mock_call_next):
        """Test production middleware integration."""
        middleware = create_production_security_middleware(mock_app)

        response = await middleware.dispatch(mock_request, mock_call_next)

        # Check all expected headers are present
        expected_headers = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Permissions-Policy",
            "Strict-Transport-Security"  # Should be present for HTTPS
        ]

        for header in expected_headers:
            assert header in response.headers

    def test_production_middleware_strict_permissions(self, mock_app):
        """Test that production middleware has strict permissions policy."""
        middleware = create_production_security_middleware(mock_app)

        # All these features should be disabled
        permissions = middleware.permissions_policy
        assert "geolocation=()" in permissions
        assert "microphone=()" in permissions
        assert "camera=()" in permissions
        assert "payment=()" in permissions
        assert "usb=()" in permissions

    def test_production_middleware_strict_frame_options(self, mock_app):
        """Test that production middleware denies framing."""
        middleware = create_production_security_middleware(mock_app)
        assert middleware.frame_options == "DENY"

    def test_production_middleware_one_year_hsts(self, mock_app):
        """Test that production middleware uses one year HSTS."""
        middleware = create_production_security_middleware(mock_app)
        assert middleware.hsts_max_age == 31536000  # 1 year
        assert middleware.hsts_include_subdomains is True

    def test_production_middleware_conservative_referrer(self, mock_app):
        """Test that production middleware uses conservative referrer policy."""
        middleware = create_production_security_middleware(mock_app)
        assert middleware.referrer_policy == "strict-origin-when-cross-origin"


class TestSecurityHeadersEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_dispatch_exception_handling(self, mock_app, mock_request):
        """Test that exceptions in call_next are properly handled."""
        async def failing_call_next(request):
            raise ValueError("Test error")

        middleware = SecurityHeadersMiddleware(mock_app)

        # Should raise the original exception
        with pytest.raises(ValueError, match="Test error"):
            await middleware.dispatch(mock_request, failing_call_next)

    def test_hsts_header_edge_cases(self, mock_app):
        """Test HSTS header building edge cases."""
        # All options disabled
        middleware = SecurityHeadersMiddleware(
            mock_app,
            hsts_max_age=0,
            hsts_include_subdomains=False,
            hsts_preload=False
        )
        hsts_header = middleware._build_hsts_header()
        assert hsts_header == "max-age=0"

    def test_csp_none_vs_empty_string(self, mock_app):
        """Test CSP handling with None vs empty string."""
        # None should use default
        middleware1 = SecurityHeadersMiddleware(mock_app, csp_policy=None)
        assert middleware1.csp_policy is None

        # Empty string should be preserved
        middleware2 = SecurityHeadersMiddleware(mock_app, csp_policy="")
        assert middleware2.csp_policy == ""

    @pytest.mark.asyncio
    async def test_response_modification_isolation(self, mock_app, mock_request):
        """Test that middleware doesn't interfere with response content."""
        original_content = b"original response content"

        async def call_next_with_content(request):
            response = Mock(spec=Response)
            response.headers = {}
            response.body = original_content
            return response

        middleware = SecurityHeadersMiddleware(mock_app)
        response = await middleware.dispatch(mock_request, call_next_with_content)

        # Content should be unchanged
        assert response.body == original_content
        # Headers should be added
        assert "X-Frame-Options" in response.headers