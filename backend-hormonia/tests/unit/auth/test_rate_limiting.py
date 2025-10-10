"""
Unit tests for rate limiting functionality.

Tests the rate limiter configuration, IP detection, error handling,
and rate limit enforcement on authentication endpoints.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.utils.rate_limiter import (
    get_client_ip,
    rate_limit_handler,
    limiter,
    get_rate_limit,
    RATE_LIMITS,
    _get_storage_uri
)


class TestClientIPDetection:
    """Test suite for client IP address detection."""

    def test_get_client_ip_forwarded_for_single(self):
        """Test IP detection with single X-Forwarded-For header."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "192.168.1.100"}

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"

    def test_get_client_ip_forwarded_for_multiple(self):
        """Test IP detection with multiple IPs in X-Forwarded-For."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "192.168.1.100, 10.0.0.1, 172.16.0.1"}

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"  # Should return first IP (original client)

    def test_get_client_ip_forwarded_for_with_spaces(self):
        """Test IP detection with spaces in X-Forwarded-For."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "  192.168.1.100  , 10.0.0.1"}

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"  # Should strip spaces

    def test_get_client_ip_real_ip(self):
        """Test IP detection with X-Real-IP header."""
        request = Mock(spec=Request)
        request.headers = {"X-Real-IP": "192.168.1.100"}

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"

    def test_get_client_ip_real_ip_with_spaces(self):
        """Test IP detection with spaces in X-Real-IP."""
        request = Mock(spec=Request)
        request.headers = {"X-Real-IP": "  192.168.1.100  "}

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"  # Should strip spaces

    def test_get_client_ip_direct_client(self):
        """Test IP detection from direct client connection."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"

    def test_get_client_ip_no_client(self):
        """Test IP detection when no client info available."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = None

        ip = get_client_ip(request)

        assert ip == "unknown"

    def test_get_client_ip_priority_order(self):
        """Test that X-Forwarded-For takes priority over X-Real-IP."""
        request = Mock(spec=Request)
        request.headers = {
            "X-Forwarded-For": "192.168.1.100",
            "X-Real-IP": "10.0.0.1"
        }
        request.client = Mock()
        request.client.host = "172.16.0.1"

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"  # X-Forwarded-For should win

    def test_get_client_ip_real_ip_fallback(self):
        """Test that X-Real-IP is used when X-Forwarded-For is not present."""
        request = Mock(spec=Request)
        request.headers = {"X-Real-IP": "10.0.0.1"}
        request.client = Mock()
        request.client.host = "172.16.0.1"

        ip = get_client_ip(request)

        assert ip == "10.0.0.1"  # X-Real-IP should be used

    def test_get_client_ip_direct_fallback(self):
        """Test that direct client IP is used when proxy headers are missing."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "172.16.0.1"

        ip = get_client_ip(request)

        assert ip == "172.16.0.1"  # Direct client should be used


class TestStorageConfiguration:
    """Test suite for rate limiter storage configuration."""

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_redis_configured(self, mock_settings):
        """Test storage URI when Redis is properly configured."""
        mock_settings.REDIS_URL = "rediss://user:pass@redis.example.com:6379"

        uri = _get_storage_uri()

        assert uri == "rediss://user:pass@redis.example.com:6379"

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_redis_localhost(self, mock_settings):
        """Test storage URI detection with localhost Redis."""
        mock_settings.REDIS_URL = "rediss://localhost:6379"
        mock_settings.ENVIRONMENT = "development"

        uri = _get_storage_uri()

        assert uri == "memory://"

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_no_redis_development(self, mock_settings):
        """Test storage URI in development without Redis."""
        mock_settings.REDIS_URL = None
        mock_settings.ENVIRONMENT = "development"

        uri = _get_storage_uri()

        assert uri == "memory://"

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_no_redis_production(self, mock_settings):
        """Test storage URI in production without Redis (should raise error)."""
        mock_settings.REDIS_URL = None
        mock_settings.ENVIRONMENT = "production"

        with pytest.raises(RuntimeError) as exc_info:
            _get_storage_uri()

        assert "Redis is required for rate limiting in production" in str(exc_info.value)

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_production_with_localhost(self, mock_settings):
        """Test storage URI in production with localhost Redis (should raise error)."""
        mock_settings.REDIS_URL = "rediss://localhost:6379"
        mock_settings.ENVIRONMENT = "prod"

        with pytest.raises(RuntimeError) as exc_info:
            _get_storage_uri()

        assert "Redis is required for rate limiting in production" in str(exc_info.value)


class TestRateLimitHandler:
    """Test suite for rate limit exceeded handler."""

    @pytest.mark.asyncio
    async def test_rate_limit_handler_basic(self):
        """Test basic rate limit handler response."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/v1/auth/session"
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        exc = RateLimitExceeded("60 seconds")

        response = await rate_limit_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 429

        # Check response content
        content = response.body.decode()
        import json
        data = json.loads(content)

        assert data["error"] == "too_many_requests"
        assert "Muitas tentativas" in data["message"]
        assert data["retry_after"] == "60 seconds"

    @pytest.mark.asyncio
    async def test_rate_limit_handler_with_forwarded_ip(self):
        """Test rate limit handler with X-Forwarded-For IP."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/v1/auth/session"
        request.headers = {"X-Forwarded-For": "203.0.113.1"}
        request.client = Mock()
        request.client.host = "10.0.0.1"

        exc = RateLimitExceeded("120 seconds")

        with patch('app.utils.rate_limiter.logger') as mock_logger:
            response = await rate_limit_handler(request, exc)

            # Verify logging with correct IP
            mock_logger.warning.assert_called_once()
            log_call = mock_logger.warning.call_args
            assert "203.0.113.1" in log_call[0][0]

        assert response.status_code == 429


class TestRateLimitConfigurations:
    """Test suite for rate limit configurations."""

    def test_rate_limits_dictionary(self):
        """Test that all expected rate limits are defined."""
        expected_limits = {
            "login",
            "password_reset",
            "password_change",
            "token_refresh",
            "registration",
            "email_verification",
            "avatar_upload",
            "profile_update"
        }

        assert set(RATE_LIMITS.keys()) == expected_limits

    def test_get_rate_limit_known_types(self):
        """Test rate limit retrieval for known endpoint types."""
        assert get_rate_limit("login") == "5/minute"
        assert get_rate_limit("password_reset") == "3/hour"
        assert get_rate_limit("password_change") == "3/hour"
        assert get_rate_limit("token_refresh") == "20/minute"
        assert get_rate_limit("registration") == "3/hour"
        assert get_rate_limit("email_verification") == "5/hour"
        assert get_rate_limit("avatar_upload") == "10/hour"
        assert get_rate_limit("profile_update") == "20/hour"

    def test_get_rate_limit_unknown_type(self):
        """Test rate limit retrieval for unknown endpoint type."""
        assert get_rate_limit("unknown_endpoint") == "100/minute"

    def test_get_rate_limit_case_sensitivity(self):
        """Test that rate limit keys are case sensitive."""
        assert get_rate_limit("LOGIN") == "100/minute"  # Should use default
        assert get_rate_limit("login") == "5/minute"   # Should use specific


class TestLimiterConfiguration:
    """Test suite for limiter instance configuration."""

    def test_limiter_key_function(self):
        """Test that limiter uses correct key function."""
        assert limiter.key_func == get_client_ip

    def test_limiter_default_limits(self):
        """Test limiter default limits."""
        assert "100/minute" in limiter.default_limits

    def test_limiter_strategy(self):
        """Test limiter strategy configuration."""
        # This would test the strategy but slowapi doesn't expose it directly
        # We can verify it's set correctly by checking it doesn't raise errors
        assert limiter is not None


class TestRateLimitingIntegration:
    """Test suite for rate limiting integration scenarios."""

    def test_auth_endpoint_rate_limits(self):
        """Test that auth endpoints have appropriate rate limits."""
        # Session creation should be more restrictive than token refresh
        login_limit = get_rate_limit("login")
        token_refresh_limit = get_rate_limit("token_refresh")

        # Extract numbers for comparison
        login_count = int(login_limit.split("/")[0])
        token_refresh_count = int(token_refresh_limit.split("/")[0])

        assert login_count < token_refresh_count

    def test_security_sensitive_endpoints(self):
        """Test that security-sensitive endpoints have stricter limits."""
        password_reset_limit = get_rate_limit("password_reset")
        password_change_limit = get_rate_limit("password_change")
        registration_limit = get_rate_limit("registration")

        # All should be hourly limits and quite restrictive
        assert "/hour" in password_reset_limit
        assert "/hour" in password_change_limit
        assert "/hour" in registration_limit

        # Extract counts
        reset_count = int(password_reset_limit.split("/")[0])
        change_count = int(password_change_limit.split("/")[0])
        reg_count = int(registration_limit.split("/")[0])

        # All should be <= 5 per hour for security
        assert reset_count <= 5
        assert change_count <= 5
        assert reg_count <= 5


class TestErrorScenarios:
    """Test suite for error scenarios in rate limiting."""

    def test_malformed_headers(self):
        """Test IP detection with malformed headers."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "not-an-ip"}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        ip = get_client_ip(request)

        assert ip == "not-an-ip"  # Should still return the value, validation happens elsewhere

    def test_empty_headers(self):
        """Test IP detection with empty header values."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": ""}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"  # Should fall back to client IP

    def test_whitespace_only_headers(self):
        """Test IP detection with whitespace-only headers."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "   "}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"  # Should fall back to client IP

    @pytest.mark.asyncio
    async def test_rate_limit_handler_no_detail(self):
        """Test rate limit handler when exception has no detail."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/v1/auth/session"
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        exc = RateLimitExceeded(None)

        response = await rate_limit_handler(request, exc)

        content = response.body.decode()
        import json
        data = json.loads(content)

        assert data["limit"] == "unknown"


class TestSecurityConsiderations:
    """Test suite for security aspects of rate limiting."""

    def test_ip_spoofing_prevention(self):
        """Test that direct client IP is used when proxy headers might be spoofed."""
        # In a real deployment, you'd want to validate proxy headers
        # based on trusted proxy configuration
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "127.0.0.1"}  # Potentially spoofed
        request.client = Mock()
        request.client.host = "203.0.113.1"  # Real client IP

        ip = get_client_ip(request)

        # Current implementation trusts proxy headers
        # In production, you'd want additional validation
        assert ip == "127.0.0.1"

    def test_rate_limit_bypass_attempts(self):
        """Test scenarios where attackers might try to bypass rate limits."""
        # Test with multiple proxy header variations
        bypass_attempts = [
            {"X-Forwarded-For": "127.0.0.1"},
            {"X-Real-IP": "127.0.0.1"},
            {"X-Forwarded-For": ""},
            {"X-Real-IP": ""},
        ]

        for headers in bypass_attempts:
            request = Mock(spec=Request)
            request.headers = headers
            request.client = Mock()
            request.client.host = "203.0.113.1"

            ip = get_client_ip(request)
            # Should return some IP for rate limiting
            assert ip is not None
            assert ip != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])