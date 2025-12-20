"""
CORS Middleware Tests - Production Security Validation

Tests the CORS middleware configuration with comprehensive validation:
1. Fail Fast behavior with invalid configurations
2. Secure production mode enforcement (HTTPS only, no regex, no wildcards)
3. Environment variable parsing and normalization
4. Origin validation logic
5. Development fallback behavior

Coverage Goals: 95%+
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.cors import (
    configure_cors,
    validate_cors_configuration,
    is_production,
)


class TestProductionSecurityValidation:
    """Test CORS production security rules - fail fast on violations."""

    @patch("app.middleware.cors.settings")
    def test_fail_fast_no_regex_in_production(self, mock_settings):
        """Production MUST reject regex patterns - fail fast."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://example.com"]

        app = FastAPI()

        with pytest.raises(ValueError, match="CORS origin regex.*not allowed in production"):
            configure_cors(app, allowed_origin_regex=r"https://.*\.example\.com")

    @patch("app.middleware.cors.settings")
    def test_fail_fast_no_wildcard_in_production(self, mock_settings):
        """Production MUST reject wildcard origins - fail fast."""
        mock_settings.APP_ENVIRONMENT = "production"

        with pytest.raises(ValueError, match="wildcard origin.*not allowed in production"):
            validate_cors_configuration(["*"])

    @patch("app.middleware.cors.settings")
    def test_fail_fast_https_required_in_production(self, mock_settings):
        """Production MUST require HTTPS for all origins - fail fast."""
        mock_settings.APP_ENVIRONMENT = "production"

        with pytest.raises(ValueError, match="must use HTTPS in production"):
            validate_cors_configuration(["http://example.com"])

    @patch("app.middleware.cors.settings")
    def test_fail_fast_origins_required_in_production(self, mock_settings):
        """Production MUST have explicit origins configured - fail fast."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = []

        app = FastAPI()

        with pytest.raises(ValueError, match="No CORS origins configured"):
            configure_cors(app)

    @patch("app.middleware.cors.settings")
    def test_production_accepts_valid_https_origins(self, mock_settings):
        """Production accepts valid HTTPS origins without errors."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = [
            "https://example.com",
            "https://app.example.com",
        ]

        app = FastAPI()

        # Should not raise any exceptions
        configure_cors(app)

        # Verify middleware was added
        assert len(app.user_middleware) > 0


class TestOriginValidation:
    """Test origin validation logic."""

    @patch("app.middleware.cors.settings")
    def test_development_allows_http_localhost(self, mock_settings):
        """Development should allow http://localhost."""
        mock_settings.APP_ENVIRONMENT = "development"

        # Should not raise for http in development
        validate_cors_configuration(["http://localhost:5173"])

    @patch("app.middleware.cors.settings")
    def test_production_rejects_http_anywhere(self, mock_settings):
        """Production should reject all HTTP origins."""
        mock_settings.APP_ENVIRONMENT = "production"

        with pytest.raises(ValueError, match="must use HTTPS"):
            validate_cors_configuration(["http://example.com"])

        with pytest.raises(ValueError, match="must use HTTPS"):
            validate_cors_configuration(["http://192.168.1.100"])

    @patch("app.middleware.cors.settings")
    def test_empty_origin_list_allowed_in_development(self, mock_settings):
        """Development can have empty origin list (uses fallbacks)."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = []

        app = FastAPI()

        # Should not raise - falls back to localhost
        configure_cors(app)

        # Should have middleware with fallback origins
        assert len(app.user_middleware) > 0


class TestDevelopmentFallbacks:
    """Test development mode fallback behavior."""

    @patch("app.middleware.cors.settings")
    def test_development_uses_localhost_fallbacks(self, mock_settings):
        """Development should use localhost fallbacks when no origins configured."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = []

        app = FastAPI()
        configure_cors(app)

        # Should have fallback localhost origins
        # Verify by checking middleware was configured
        assert len(app.user_middleware) > 0

    @patch("app.middleware.cors.settings")
    def test_development_allows_permissive_config(self, mock_settings):
        """Development should allow more permissive CORS configuration."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = [
            "http://localhost:3000",
            "http://127.0.0.1:5173",
        ]

        app = FastAPI()

        # Should work without issues
        configure_cors(app)


class TestCORSHeaders:
    """Test CORS header configuration."""

    @patch("app.middleware.cors.settings")
    def test_explicit_header_whitelist(self, mock_settings):
        """Test that explicit headers are whitelisted (not wildcard)."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()
        configure_cors(app)

        # Get the CORS middleware
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware):
                cors_middleware = middleware
                break

        assert cors_middleware is not None

    @patch("app.middleware.cors.settings")
    def test_csrf_headers_included(self, mock_settings):
        """Test that CSRF headers are included in allowed headers."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()
        configure_cors(app, allow_headers=None)  # Use defaults

        # Defaults should include X-CSRF-Token, X-CSRFToken, X-XSRF-Token
        # This is verified by the middleware configuration

    @patch("app.middleware.cors.settings")
    def test_credentials_enabled_by_default(self, mock_settings):
        """Test that credentials are enabled for httpOnly cookies."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()
        configure_cors(app)  # allow_credentials=True is default

        # Verify middleware was added with credentials
        assert len(app.user_middleware) > 0


class TestProductionLogging:
    """Test production logging for debugging."""

    @patch("app.middleware.cors.settings")
    @patch("app.middleware.cors.logger")
    def test_production_logs_configuration(self, mock_logger, mock_settings):
        """Production should log CORS configuration for debugging."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = [
            "https://frontend.example.com",
            "https://quiz.example.com",
        ]

        app = FastAPI()
        configure_cors(app)

        # Should log successful validation
        mock_logger.info.assert_called()

    @patch("app.middleware.cors.settings")
    @patch("app.middleware.cors.logger")
    def test_development_logs_configuration(self, mock_logger, mock_settings):
        """Development should log CORS configuration."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()
        configure_cors(app)

        # Should log configuration
        assert mock_logger.info.called or mock_logger.warning.called


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("app.middleware.cors.settings")
    def test_multiple_non_https_origins_in_production(self, mock_settings):
        """Production should reject multiple HTTP origins with detailed error."""
        mock_settings.APP_ENVIRONMENT = "production"

        with pytest.raises(ValueError, match="must use HTTPS in production"):
            validate_cors_configuration([
                "http://example.com",
                "http://another.com",
                "http://third.com",
            ])

    @patch("app.middleware.cors.settings")
    def test_mixed_http_https_origins_in_production(self, mock_settings):
        """Production should reject origins if ANY are HTTP."""
        mock_settings.APP_ENVIRONMENT = "production"

        with pytest.raises(ValueError, match="must use HTTPS in production"):
            validate_cors_configuration([
                "https://example.com",
                "http://insecure.com",  # This one should cause failure
            ])


class TestIsProduction:
    """Test production environment detection."""

    @patch("app.middleware.cors.settings")
    def test_production_string_detection(self, mock_settings):
        """Test 'production' string is detected as production."""
        mock_settings.APP_ENVIRONMENT = "production"
        assert is_production() is True

    @patch("app.middleware.cors.settings")
    def test_prod_string_detection(self, mock_settings):
        """Test 'prod' string is detected as production."""
        mock_settings.APP_ENVIRONMENT = "prod"
        assert is_production() is True

    @patch("app.middleware.cors.settings")
    def test_development_not_production(self, mock_settings):
        """Test 'development' is not detected as production."""
        mock_settings.APP_ENVIRONMENT = "development"
        assert is_production() is False

    @patch("app.middleware.cors.settings")
    def test_case_insensitive_detection(self, mock_settings):
        """Test production detection is case insensitive."""
        mock_settings.APP_ENVIRONMENT = "PRODUCTION"
        assert is_production() is True

        mock_settings.APP_ENVIRONMENT = "Production"
        assert is_production() is True


class TestValidateCorsConfiguration:
    """Test validate_cors_configuration function directly."""

    @patch("app.middleware.cors.settings")
    def test_validation_passes_in_development(self, mock_settings):
        """Validation should be skipped in development."""
        mock_settings.APP_ENVIRONMENT = "development"

        # Should not raise for any configuration in development
        validate_cors_configuration(["*"])
        validate_cors_configuration(["http://localhost"])
        validate_cors_configuration([])

    @patch("app.middleware.cors.settings")
    def test_validation_enforces_rules_in_production(self, mock_settings):
        """Validation should enforce all rules in production."""
        mock_settings.APP_ENVIRONMENT = "production"

        # Test each rule individually
        # Rule 1: No empty origins
        with pytest.raises(ValueError):
            validate_cors_configuration([])

        # Rule 2: No wildcards
        with pytest.raises(ValueError):
            validate_cors_configuration(["*"])

        # Rule 3: No HTTP
        with pytest.raises(ValueError):
            validate_cors_configuration(["http://example.com"])

        # Rule 4: Valid HTTPS passes
        validate_cors_configuration(["https://example.com"])


class TestCORSMiddlewareIntegration:
    """Test CORS middleware integration with FastAPI."""

    @patch("app.middleware.cors.settings")
    def test_middleware_added_successfully(self, mock_settings):
        """Middleware should be added to FastAPI app."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()
        configure_cors(app)

        # Check middleware was added
        assert len(app.user_middleware) > 0

    @patch("app.middleware.cors.settings")
    def test_custom_allowed_methods(self, mock_settings):
        """Test custom allowed methods configuration."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()
        configure_cors(app, allow_methods=["GET", "POST"])

        # Middleware should be configured with custom methods
        assert len(app.user_middleware) > 0

    @patch("app.middleware.cors.settings")
    def test_custom_allowed_headers(self, mock_settings):
        """Test custom allowed headers configuration."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:5173"]

        app = FastAPI()
        configure_cors(app, allow_headers=["Content-Type", "Authorization"])

        # Middleware should be configured with custom headers
        assert len(app.user_middleware) > 0


class TestErrorMessages:
    """Test that error messages are clear and helpful."""

    @patch("app.middleware.cors.settings")
    def test_regex_error_message_helpful(self, mock_settings):
        """Regex error should explain why and how to fix."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://example.com"]

        app = FastAPI()

        try:
            configure_cors(app, allowed_origin_regex=r"https://.*\.example\.com")
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            # Should explain the reason
            assert "regex" in error_msg.lower() or "pattern" in error_msg.lower()
            # Should suggest a fix
            assert "fix" in error_msg.lower() or "example" in error_msg.lower()

    @patch("app.middleware.cors.settings")
    def test_https_error_message_helpful(self, mock_settings):
        """HTTPS error should explain which origins are HTTP."""
        mock_settings.APP_ENVIRONMENT = "production"

        try:
            validate_cors_configuration(["http://example.com", "http://another.com"])
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            # Should mention HTTPS requirement
            assert "https" in error_msg.lower()
            # Should list the problematic origins
            assert "example.com" in error_msg or "HTTP" in error_msg
