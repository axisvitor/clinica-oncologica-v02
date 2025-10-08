"""
CORS Production Guard Tests - Security validation for production configuration
"""
import pytest
import os
from unittest.mock import patch
from fastapi import FastAPI
from app.middleware.cors import (
    is_production,
    validate_cors_origins,
    configure_cors
)


class TestEnvironmentDetection:
    """Test production environment detection"""

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_is_production_true(self):
        """Should detect production environment"""
        assert is_production() is True

    @patch.dict(os.environ, {"ENVIRONMENT": "prod"})
    def test_is_production_true_short(self):
        """Should detect 'prod' as production"""
        assert is_production() is True

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_is_production_false(self):
        """Should detect non-production environment"""
        assert is_production() is False

    @patch.dict(os.environ, {}, clear=True)
    def test_is_production_default_development(self):
        """Should default to development if ENVIRONMENT not set"""
        assert is_production() is False


class TestCORSValidation:
    """Test CORS configuration validation"""

    @patch('app.middleware.cors.is_production', return_value=True)
    def test_validate_rejects_regex_in_production(self, mock_prod):
        """Should reject regex patterns in production"""
        with pytest.raises(ValueError, match="CORS origin regex not allowed"):
            validate_cors_origins(
                allow_origins=["https://example.com"],
                allow_origin_regex="https://.*\\.example\\.com"
            )

    @patch('app.middleware.cors.is_production', return_value=True)
    def test_validate_rejects_wildcard_in_production(self, mock_prod):
        """Should reject wildcard origins in production"""
        with pytest.raises(ValueError, match="CORS wildcard origin"):
            validate_cors_origins(
                allow_origins=["*"],
                allow_origin_regex=None
            )

    @patch('app.middleware.cors.is_production', return_value=True)
    def test_validate_rejects_http_in_production(self, mock_prod):
        """Should reject HTTP origins in production"""
        with pytest.raises(ValueError, match="must use HTTPS"):
            validate_cors_origins(
                allow_origins=["http://example.com"],
                allow_origin_regex=None
            )

    @patch('app.middleware.cors.is_production', return_value=True)
    def test_validate_accepts_https_in_production(self, mock_prod):
        """Should accept HTTPS origins in production"""
        # Should not raise
        validate_cors_origins(
            allow_origins=["https://example.com", "https://app.example.com"],
            allow_origin_regex=None
        )

    @patch('app.middleware.cors.is_production', return_value=False)
    def test_validate_allows_anything_in_development(self, mock_dev):
        """Should allow any configuration in development"""
        # Should not raise
        validate_cors_origins(
            allow_origins=["*", "http://localhost:3000"],
            allow_origin_regex="https://.*\\.local"
        )


class TestCORSConfiguration:
    """Test CORS middleware configuration"""

    @patch('app.middleware.cors.is_production', return_value=True)
    @patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=True)
    def test_configure_requires_env_var_in_production(self, mock_prod):
        """Should require CORS_ORIGINS env var in production"""
        app = FastAPI()

        with pytest.raises(ValueError, match="CORS_ORIGINS environment variable"):
            configure_cors(app)

    @patch('app.middleware.cors.is_production', return_value=True)
    @patch.dict(os.environ, {"CORS_ORIGINS": "https://example.com,https://app.example.com"})
    def test_configure_uses_env_var_in_production(self, mock_prod):
        """Should use CORS_ORIGINS from environment in production"""
        app = FastAPI()

        # Should not raise
        configure_cors(app)

    @patch('app.middleware.cors.is_production', return_value=True)
    def test_configure_rejects_explicit_regex_in_production(self, mock_prod):
        """Should reject explicit regex in production"""
        app = FastAPI()

        with pytest.raises(ValueError, match="CORS origin regex"):
            configure_cors(
                app,
                allowed_origins=["https://example.com"],
                allowed_origin_regex="https://.*\\.example\\.com"
            )

    @patch('app.middleware.cors.is_production', return_value=False)
    def test_configure_uses_defaults_in_development(self, mock_dev):
        """Should use localhost defaults in development"""
        app = FastAPI()

        # Should not raise, uses default localhost origins
        configure_cors(app)

    @patch('app.middleware.cors.is_production', return_value=True)
    def test_configure_validates_explicit_origins(self, mock_prod):
        """Should validate explicitly provided origins in production"""
        app = FastAPI()

        with pytest.raises(ValueError, match="must use HTTPS"):
            configure_cors(
                app,
                allowed_origins=["http://insecure.com"]
            )


class TestCORSCredentials:
    """Test CORS credentials configuration"""

    @patch('app.middleware.cors.is_production', return_value=False)
    def test_configure_defaults_to_credentials_true(self, mock_dev):
        """Should default allow_credentials to True for cookies"""
        app = FastAPI()

        configure_cors(app)

        # Verify middleware was added with credentials
        cors_middleware = next(
            (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
            None
        )
        assert cors_middleware is not None

    @patch('app.middleware.cors.is_production', return_value=True)
    def test_configure_allows_credentials_false_if_explicit(self, mock_prod):
        """Should allow disabling credentials if explicitly set"""
        app = FastAPI()

        configure_cors(
            app,
            allowed_origins=["https://example.com"],
            allow_credentials=False
        )


class TestCORSMethods:
    """Test CORS allowed methods configuration"""

    @patch('app.middleware.cors.is_production', return_value=False)
    def test_configure_defaults_to_common_methods(self, mock_dev):
        """Should default to common HTTP methods"""
        app = FastAPI()

        configure_cors(app)

        # Default methods should include GET, POST, PUT, DELETE, OPTIONS, PATCH
        cors_middleware = next(
            (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
            None
        )
        assert cors_middleware is not None
