"""
Comprehensive tests for CORS middleware configuration.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.cors import (
    is_production, validate_cors_origins, configure_cors
)


class TestIsProduction:
    """Test production environment detection."""

    def test_is_production_development(self):
        """Test development environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert is_production() is False

    def test_is_production_dev(self):
        """Test dev environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            assert is_production() is False

    def test_is_production_production(self):
        """Test production environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert is_production() is True

    def test_is_production_prod(self):
        """Test prod environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            assert is_production() is True

    def test_is_production_case_insensitive(self):
        """Test case insensitive environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "PRODUCTION"}):
            assert is_production() is True

        with patch.dict(os.environ, {"ENVIRONMENT": "Production"}):
            assert is_production() is True

    def test_is_production_default_development(self):
        """Test default to development when no environment set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_production() is False

    def test_is_production_unknown_environment(self):
        """Test unknown environment defaults to development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
            assert is_production() is False


class TestValidateCorsOrigins:
    """Test CORS origins validation."""

    def test_validate_cors_origins_development_no_restrictions(self):
        """Test no restrictions in development mode."""
        with patch('app.middleware.cors.is_production', return_value=False):
            # Should not raise any exceptions
            validate_cors_origins(["*"], ".*")
            validate_cors_origins(["http://localhost:3000"], None)

    def test_validate_cors_origins_production_regex_forbidden(self):
        """Test regex forbidden in production."""
        with patch('app.middleware.cors.is_production', return_value=True):
            with pytest.raises(ValueError, match="CORS origin regex not allowed in production"):
                validate_cors_origins(["https://example.com"], ".*")

    def test_validate_cors_origins_production_wildcard_forbidden(self):
        """Test wildcard forbidden in production."""
        with patch('app.middleware.cors.is_production', return_value=True):
            with pytest.raises(ValueError, match="CORS wildcard origin \\(\\*\\) not allowed in production"):
                validate_cors_origins(["*"], None)

    def test_validate_cors_origins_production_http_forbidden(self):
        """Test HTTP origins forbidden in production."""
        with patch('app.middleware.cors.is_production', return_value=True):
            with pytest.raises(ValueError, match="CORS origin 'http://example.com' must use HTTPS in production"):
                validate_cors_origins(["http://example.com"], None)

    def test_validate_cors_origins_production_valid_https(self):
        """Test valid HTTPS origins in production."""
        with patch('app.middleware.cors.is_production', return_value=True):
            # Should not raise any exceptions
            validate_cors_origins(["https://example.com", "https://app.example.com"], None)

    def test_validate_cors_origins_production_mixed_origins(self):
        """Test mixed origins in production (should fail on first HTTP)."""
        with patch('app.middleware.cors.is_production', return_value=True):
            with pytest.raises(ValueError, match="CORS origin 'http://bad.com' must use HTTPS in production"):
                validate_cors_origins(["https://good.com", "http://bad.com"], None)

    def test_validate_cors_origins_production_empty_list(self):
        """Test empty origins list in production."""
        with patch('app.middleware.cors.is_production', return_value=True):
            # Should not raise any exceptions for empty list
            validate_cors_origins([], None)


class TestConfigureCors:
    """Test CORS middleware configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = Mock(spec=FastAPI)
        self.app.add_middleware = Mock()

    def test_configure_cors_development_defaults(self):
        """Test CORS configuration with development defaults."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app)

            app.add_middleware.assert_called_once()
            call_args = app.add_middleware.call_args

            assert call_args[0][0] == CORSMiddleware
            kwargs = call_args[1]

            # Check development origins
            expected_origins = [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001"
            ]
            assert kwargs["allow_origins"] == expected_origins
            assert kwargs["allow_credentials"] is True
            assert "GET" in kwargs["allow_methods"]
            assert "POST" in kwargs["allow_methods"]

    def test_configure_cors_production_env_origins(self):
        """Test CORS configuration with production environment origins."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        cors_origins = "https://app.example.com,https://admin.example.com"

        with patch('app.middleware.cors.is_production', return_value=True), \
             patch.dict(os.environ, {"CORS_ORIGINS": cors_origins}):

            configure_cors(app)

            call_args = app.add_middleware.call_args[1]
            expected_origins = ["https://app.example.com", "https://admin.example.com"]
            assert call_args["allow_origins"] == expected_origins

    def test_configure_cors_production_no_env_origins(self):
        """Test CORS configuration fails in production without env origins."""
        app = Mock(spec=FastAPI)

        with patch('app.middleware.cors.is_production', return_value=True), \
             patch.dict(os.environ, {}, clear=True):

            with pytest.raises(ValueError, match="CORS_ORIGINS environment variable must be set in production"):
                configure_cors(app)

    def test_configure_cors_custom_origins(self):
        """Test CORS configuration with custom origins."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        custom_origins = ["https://custom.com", "https://api.custom.com"]

        with patch('app.middleware.cors.is_production', return_value=True):
            configure_cors(app, allowed_origins=custom_origins)

            call_args = app.add_middleware.call_args[1]
            assert call_args["allow_origins"] == custom_origins

    def test_configure_cors_custom_methods(self):
        """Test CORS configuration with custom methods."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        custom_methods = ["GET", "POST"]

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app, allow_methods=custom_methods)

            call_args = app.add_middleware.call_args[1]
            assert call_args["allow_methods"] == custom_methods

    def test_configure_cors_custom_headers(self):
        """Test CORS configuration with custom headers."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        custom_headers = ["authorization", "content-type"]

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app, allow_headers=custom_headers)

            call_args = app.add_middleware.call_args[1]
            assert call_args["allow_headers"] == custom_headers

    def test_configure_cors_default_headers(self):
        """Test CORS configuration with default headers."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app)

            call_args = app.add_middleware.call_args[1]
            expected_headers = [
                "authorization",
                "content-type",
                "x-csrf-token",
                "x-requested-with",
                "accept",
                "origin"
            ]
            assert call_args["allow_headers"] == expected_headers

    def test_configure_cors_credentials_disabled(self):
        """Test CORS configuration with credentials disabled."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app, allow_credentials=False)

            call_args = app.add_middleware.call_args[1]
            assert call_args["allow_credentials"] is False

    def test_configure_cors_expose_headers(self):
        """Test CORS configuration includes expose headers."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app)

            call_args = app.add_middleware.call_args[1]
            expected_expose = ["content-type", "x-csrf-token", "x-total-count", "x-page", "x-per-page"]
            assert call_args["expose_headers"] == expected_expose

    def test_configure_cors_max_age(self):
        """Test CORS configuration includes max age."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app)

            call_args = app.add_middleware.call_args[1]
            assert call_args["max_age"] == 3600

    def test_configure_cors_production_validation_called(self):
        """Test that production validation is called."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=True), \
             patch('app.middleware.cors.validate_cors_origins') as mock_validate, \
             patch.dict(os.environ, {"CORS_ORIGINS": "https://example.com"}):

            configure_cors(app)
            mock_validate.assert_called_once()

    @patch('builtins.print')
    def test_configure_cors_production_logging(self, mock_print):
        """Test production logging output."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=True), \
             patch.dict(os.environ, {"CORS_ORIGINS": "https://example.com"}):

            configure_cors(app)
            mock_print.assert_called_with("✅ CORS configured for PRODUCTION with 1 explicit origins")

    @patch('builtins.print')
    def test_configure_cors_development_logging(self, mock_print):
        """Test development logging output."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app)
            mock_print.assert_called_with("⚠️  CORS configured for DEVELOPMENT with 4 origins")

    def test_configure_cors_whitespace_in_env_origins(self):
        """Test CORS origins with whitespace are properly handled."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        cors_origins = " https://app.example.com , https://admin.example.com , "

        with patch('app.middleware.cors.is_production', return_value=True), \
             patch.dict(os.environ, {"CORS_ORIGINS": cors_origins}):

            configure_cors(app)

            call_args = app.add_middleware.call_args[1]
            expected_origins = ["https://app.example.com", "https://admin.example.com"]
            assert call_args["allow_origins"] == expected_origins

    def test_configure_cors_empty_env_origins(self):
        """Test CORS configuration with empty env origins string."""
        app = Mock(spec=FastAPI)

        with patch('app.middleware.cors.is_production', return_value=True), \
             patch.dict(os.environ, {"CORS_ORIGINS": "   ,  ,  "}):

            with pytest.raises(ValueError, match="CORS_ORIGINS environment variable must be set in production"):
                configure_cors(app)

    def test_configure_cors_origin_regex_in_development(self):
        """Test CORS configuration allows regex in development."""
        app = Mock(spec=FastAPI)
        app.add_middleware = Mock()

        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app, allowed_origin_regex=r"https://.*\.example\.com")

            call_args = app.add_middleware.call_args[1]
            assert call_args["allow_origin_regex"] == r"https://.*\.example\.com"

    def test_configure_cors_origin_regex_validation_error(self):
        """Test CORS configuration validates regex in production."""
        app = Mock(spec=FastAPI)

        with patch('app.middleware.cors.is_production', return_value=True):
            with pytest.raises(ValueError, match="CORS origin regex not allowed in production"):
                configure_cors(app, allowed_origins=["https://example.com"],
                             allowed_origin_regex=r"https://.*\.example\.com")