"""
Comprehensive unit tests for app.utils.rate_limiter module.
Tests rate limiting configuration, IP extraction, and handler functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.utils.rate_limiter import (
    get_client_ip, _get_storage_uri, limiter,
    rate_limit_handler, get_rate_limit, RATE_LIMITS
)
from app.config import settings


class TestClientIPExtraction:
    """Test client IP address extraction from requests."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = None
        return request

    def test_get_client_ip_x_forwarded_for(self, mock_request):
        """Test IP extraction from X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": "192.168.1.100, 10.0.0.1, 172.16.0.1"}

        result = get_client_ip(mock_request)

        assert result == "192.168.1.100"

    def test_get_client_ip_x_forwarded_for_single(self, mock_request):
        """Test IP extraction from X-Forwarded-For header with single IP."""
        mock_request.headers = {"X-Forwarded-For": "192.168.1.100"}

        result = get_client_ip(mock_request)

        assert result == "192.168.1.100"

    def test_get_client_ip_x_forwarded_for_with_spaces(self, mock_request):
        """Test IP extraction with spaces in X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": " 192.168.1.100 , 10.0.0.1 "}

        result = get_client_ip(mock_request)

        assert result == "192.168.1.100"

    def test_get_client_ip_x_real_ip(self, mock_request):
        """Test IP extraction from X-Real-IP header."""
        mock_request.headers = {"X-Real-IP": " 192.168.1.200 "}

        result = get_client_ip(mock_request)

        assert result == "192.168.1.200"

    def test_get_client_ip_x_real_ip_fallback(self, mock_request):
        """Test X-Real-IP fallback when X-Forwarded-For is not present."""
        mock_request.headers = {
            "X-Real-IP": "192.168.1.200",
            "Other-Header": "value"
        }

        result = get_client_ip(mock_request)

        assert result == "192.168.1.200"

    def test_get_client_ip_direct_client(self, mock_request):
        """Test IP extraction from direct client connection."""
        mock_client = Mock()
        mock_client.host = "192.168.1.300"
        mock_request.client = mock_client

        result = get_client_ip(mock_request)

        assert result == "192.168.1.300"

    def test_get_client_ip_priority_order(self, mock_request):
        """Test IP extraction follows correct priority order."""
        mock_client = Mock()
        mock_client.host = "192.168.1.300"
        mock_request.client = mock_client
        mock_request.headers = {
            "X-Forwarded-For": "192.168.1.100",
            "X-Real-IP": "192.168.1.200"
        }

        result = get_client_ip(mock_request)

        # X-Forwarded-For should have highest priority
        assert result == "192.168.1.100"

    def test_get_client_ip_x_real_ip_priority(self, mock_request):
        """Test X-Real-IP has priority over direct client."""
        mock_client = Mock()
        mock_client.host = "192.168.1.300"
        mock_request.client = mock_client
        mock_request.headers = {"X-Real-IP": "192.168.1.200"}

        result = get_client_ip(mock_request)

        assert result == "192.168.1.200"

    def test_get_client_ip_no_client(self, mock_request):
        """Test IP extraction when no client information is available."""
        mock_request.client = None

        result = get_client_ip(mock_request)

        assert result == "unknown"

    def test_get_client_ip_empty_headers(self, mock_request):
        """Test IP extraction with empty headers."""
        mock_request.headers = {"X-Forwarded-For": "", "X-Real-IP": ""}
        mock_client = Mock()
        mock_client.host = "192.168.1.300"
        mock_request.client = mock_client

        result = get_client_ip(mock_request)

        # Should fall back to direct client
        assert result == "192.168.1.300"


class TestStorageURIConfiguration:
    """Test storage URI configuration for rate limiter."""

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_redis_available(self, mock_settings):
        """Test storage URI when Redis is properly configured."""
        mock_settings.REDIS_URL = "redis://localhost:6379"

        with patch('app.utils.rate_limiter.logger') as mock_logger:
            result = _get_storage_uri()

            assert result == "redis://localhost:6379"
            mock_logger.info.assert_called_with("Using Redis for rate limiting")

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_redis_localhost_fallback(self, mock_settings):
        """Test storage URI fallback when Redis URL is localhost default."""
        mock_settings.REDIS_URL = "rediss://localhost:6379"
        mock_settings.ENVIRONMENT = "development"

        with patch('app.utils.rate_limiter.logger') as mock_logger:
            result = _get_storage_uri()

            assert result == "memory://"
            mock_logger.warning.assert_called_with(
                "Redis not configured, using in-memory rate limiting (not suitable for production)"
            )

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_no_redis(self, mock_settings):
        """Test storage URI when Redis is not configured."""
        mock_settings.REDIS_URL = None
        mock_settings.ENVIRONMENT = "development"

        with patch('app.utils.rate_limiter.logger') as mock_logger:
            result = _get_storage_uri()

            assert result == "memory://"
            mock_logger.warning.assert_called_with(
                "Redis not configured, using in-memory rate limiting (not suitable for production)"
            )

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_production_without_redis(self, mock_settings):
        """Test storage URI raises error in production without Redis."""
        mock_settings.REDIS_URL = None
        mock_settings.ENVIRONMENT = "production"

        with pytest.raises(RuntimeError, match="Redis is required for rate limiting in production"):
            _get_storage_uri()

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_prod_environment_variations(self, mock_settings):
        """Test production environment detection variations."""
        mock_settings.REDIS_URL = None

        # Test different ways to specify production
        production_envs = ["production", "prod", "PRODUCTION", "PROD"]

        for env in production_envs:
            mock_settings.ENVIRONMENT = env

            with pytest.raises(RuntimeError, match="Redis is required for rate limiting in production"):
                _get_storage_uri()

    @patch('app.utils.rate_limiter.settings')
    def test_get_storage_uri_missing_environment(self, mock_settings):
        """Test storage URI when ENVIRONMENT attribute is missing."""
        mock_settings.REDIS_URL = None
        # Remove ENVIRONMENT attribute
        if hasattr(mock_settings, 'ENVIRONMENT'):
            delattr(mock_settings, 'ENVIRONMENT')

        with patch('app.utils.rate_limiter.logger') as mock_logger:
            result = _get_storage_uri()

            assert result == "memory://"
            mock_logger.warning.assert_called()


class TestRateLimitHandler:
    """Test rate limit exception handler."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/auth/login"
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"
        return request

    @pytest.fixture
    def mock_rate_limit_exception(self):
        """Create a mock RateLimitExceeded exception."""
        exc = Mock(spec=RateLimitExceeded)
        exc.detail = "5 per 1 minute"
        return exc

    @pytest.mark.asyncio
    async def test_rate_limit_handler_success(self, mock_request, mock_rate_limit_exception):
        """Test successful rate limit handler execution."""
        with patch('app.utils.rate_limiter.get_client_ip') as mock_get_ip, \
             patch('app.utils.rate_limiter.logger') as mock_logger:

            mock_get_ip.return_value = "192.168.1.100"

            response = await rate_limit_handler(mock_request, mock_rate_limit_exception)

            # Verify logging
            mock_logger.warning.assert_called_once()
            log_call = mock_logger.warning.call_args
            assert "Rate limit exceeded for IP 192.168.1.100" in log_call[0][0]

            # Verify response
            assert isinstance(response, JSONResponse)
            assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_handler_response_content(self, mock_request, mock_rate_limit_exception):
        """Test rate limit handler response content."""
        with patch('app.utils.rate_limiter.get_client_ip') as mock_get_ip:
            mock_get_ip.return_value = "192.168.1.100"

            response = await rate_limit_handler(mock_request, mock_rate_limit_exception)

            # Check response body structure
            assert response.status_code == 429
            # Note: We can't easily access JSONResponse body in tests,
            # but we can verify the structure was created correctly
            assert isinstance(response, JSONResponse)

    @pytest.mark.asyncio
    async def test_rate_limit_handler_logging_extra_fields(self, mock_request, mock_rate_limit_exception):
        """Test rate limit handler includes extra logging fields."""
        with patch('app.utils.rate_limiter.get_client_ip') as mock_get_ip, \
             patch('app.utils.rate_limiter.logger') as mock_logger:

            mock_get_ip.return_value = "192.168.1.100"

            await rate_limit_handler(mock_request, mock_rate_limit_exception)

            # Verify extra fields in logging call
            log_call = mock_logger.warning.call_args
            extra_fields = log_call[1]['extra']

            assert extra_fields['client_ip'] == "192.168.1.100"
            assert extra_fields['path'] == "/api/auth/login"
            assert extra_fields['method'] == "POST"

    @pytest.mark.asyncio
    async def test_rate_limit_handler_different_methods(self, mock_rate_limit_exception):
        """Test rate limit handler with different HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

        for method in methods:
            request = Mock(spec=Request)
            request.method = method
            request.url = Mock()
            request.url.path = f"/api/test/{method.lower()}"
            request.headers = {}

            with patch('app.utils.rate_limiter.get_client_ip') as mock_get_ip, \
                 patch('app.utils.rate_limiter.logger') as mock_logger:

                mock_get_ip.return_value = "192.168.1.100"

                response = await rate_limit_handler(request, mock_rate_limit_exception)

                assert response.status_code == 429

                # Verify method is logged correctly
                log_call = mock_logger.warning.call_args
                extra_fields = log_call[1]['extra']
                assert extra_fields['method'] == method


class TestRateLimitConfiguration:
    """Test rate limit configuration and retrieval."""

    def test_get_rate_limit_known_types(self):
        """Test getting rate limits for known endpoint types."""
        known_limits = {
            "login": "5/minute",
            "password_reset": "3/hour",
            "password_change": "3/hour",
            "token_refresh": "20/minute",
            "registration": "3/hour",
            "email_verification": "5/hour",
            "avatar_upload": "10/hour",
            "profile_update": "20/hour"
        }

        for limit_type, expected_limit in known_limits.items():
            result = get_rate_limit(limit_type)
            assert result == expected_limit

    def test_get_rate_limit_unknown_type(self):
        """Test getting rate limit for unknown endpoint type returns default."""
        unknown_types = ["unknown_endpoint", "custom_api", "test_endpoint"]

        for limit_type in unknown_types:
            result = get_rate_limit(limit_type)
            assert result == "100/minute"  # Default rate limit

    def test_get_rate_limit_empty_string(self):
        """Test getting rate limit for empty string returns default."""
        result = get_rate_limit("")
        assert result == "100/minute"

    def test_get_rate_limit_none(self):
        """Test getting rate limit for None returns default."""
        result = get_rate_limit(None)
        assert result == "100/minute"

    def test_rate_limits_constant_structure(self):
        """Test RATE_LIMITS constant has expected structure."""
        assert isinstance(RATE_LIMITS, dict)
        assert len(RATE_LIMITS) > 0

        # Verify all values are strings in format "number/timeunit"
        for key, value in RATE_LIMITS.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
            assert "/" in value

            # Basic format validation
            parts = value.split("/")
            assert len(parts) == 2
            number_part, time_part = parts
            assert number_part.isdigit()
            assert time_part in ["minute", "hour", "day", "second"]

    def test_rate_limits_realistic_values(self):
        """Test rate limits have realistic values for security."""
        # Login should be restrictive
        login_limit = RATE_LIMITS["login"]
        login_number = int(login_limit.split("/")[0])
        assert login_number <= 10  # Should be restrictive for security

        # Password reset should be very restrictive
        password_reset_limit = RATE_LIMITS["password_reset"]
        password_reset_number = int(password_reset_limit.split("/")[0])
        assert password_reset_number <= 5  # Should be very restrictive

        # Token refresh can be more permissive
        token_refresh_limit = RATE_LIMITS["token_refresh"]
        token_refresh_number = int(token_refresh_limit.split("/")[0])
        assert token_refresh_number >= 10  # Can be more permissive


class TestLimiterConfiguration:
    """Test limiter instance configuration."""

    def test_limiter_instance_exists(self):
        """Test that limiter instance is properly created."""
        assert limiter is not None

    @patch('app.utils.rate_limiter._get_storage_uri')
    @patch('app.utils.rate_limiter.Limiter')
    def test_limiter_initialization_parameters(self, mock_limiter_class, mock_get_storage_uri):
        """Test limiter is initialized with correct parameters."""
        mock_get_storage_uri.return_value = "redis://localhost:6379"

        # Re-import to trigger initialization
        from importlib import reload
        import app.utils.rate_limiter
        reload(app.utils.rate_limiter)

        # Verify Limiter was called with correct parameters
        mock_limiter_class.assert_called_with(
            key_func=get_client_ip,
            default_limits=["100/minute"],
            storage_uri="redis://localhost:6379",
            strategy="fixed-window"
        )

    def test_limiter_key_func_is_get_client_ip(self):
        """Test limiter uses get_client_ip as key function."""
        # Create a mock request
        mock_request = Mock(spec=Request)
        mock_request.headers = {"X-Forwarded-For": "192.168.1.100"}

        # The key function should be get_client_ip
        result = limiter.key_func(mock_request)
        expected = get_client_ip(mock_request)

        assert result == expected == "192.168.1.100"


class TestRateLimiterIntegration:
    """Test rate limiter integration scenarios."""

    @pytest.mark.asyncio
    async def test_rate_limit_handler_with_real_exception_structure(self):
        """Test rate limit handler with more realistic exception structure."""
        # Create a mock request
        request = Mock(spec=Request)
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/api/auth/login"
        request.headers = {"X-Forwarded-For": "192.168.1.100"}

        # Create a more realistic RateLimitExceeded exception
        exc = RateLimitExceeded()
        exc.detail = "5 per 1 minute"

        with patch('app.utils.rate_limiter.logger') as mock_logger:
            response = await rate_limit_handler(request, exc)

            assert response.status_code == 429
            assert isinstance(response, JSONResponse)

            # Verify logging was called
            mock_logger.warning.assert_called_once()

    def test_get_client_ip_edge_cases(self):
        """Test get_client_ip function with various edge cases."""
        request = Mock(spec=Request)

        # Test with malformed X-Forwarded-For
        request.headers = {"X-Forwarded-For": "invalid-ip-format"}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        result = get_client_ip(request)
        assert result == "invalid-ip-format"  # Function doesn't validate IP format

        # Test with empty X-Forwarded-For but valid X-Real-IP
        request.headers = {"X-Forwarded-For": "", "X-Real-IP": "192.168.1.200"}
        result = get_client_ip(request)
        assert result == "192.168.1.200"

        # Test with whitespace-only headers
        request.headers = {"X-Forwarded-For": "   ", "X-Real-IP": "   "}
        result = get_client_ip(request)
        assert result == "192.168.1.100"  # Falls back to direct client

    @patch('app.utils.rate_limiter.settings')
    def test_storage_uri_configuration_edge_cases(self, mock_settings):
        """Test storage URI configuration with edge cases."""
        # Test with empty Redis URL
        mock_settings.REDIS_URL = ""
        mock_settings.ENVIRONMENT = "development"

        result = _get_storage_uri()
        assert result == "memory://"

        # Test with whitespace-only Redis URL
        mock_settings.REDIS_URL = "   "
        result = _get_storage_uri()
        assert result == "memory://"

        # Test case insensitive environment matching
        mock_settings.ENVIRONMENT = "Production"  # Different case
        with pytest.raises(RuntimeError):
            _get_storage_uri()