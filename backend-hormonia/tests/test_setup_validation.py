"""
Test Setup Validation

This test module validates that the test infrastructure is properly configured
and all critical imports work correctly.
"""

import pytest
import os
import sys
from pathlib import Path


class TestEnvironmentSetup:
    """Test environment configuration and setup."""

    def test_environment_variables(self):
        """Test that test environment variables are set."""
        # These should be set by conftest.py or .env.test
        expected_vars = [
            "ENVIRONMENT",
            "DATABASE_URL",
            "SECRET_KEY"
        ]

        missing_vars = []
        for var in expected_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        assert not missing_vars, f"Missing environment variables: {missing_vars}"

    def test_python_path(self):
        """Test that the app directory is in Python path."""
        app_path = str(Path(__file__).parent.parent / "app")
        assert any(app_path in p for p in sys.path), "App directory not in Python path"


class TestCriticalImports:
    """Test that critical modules can be imported."""

    def test_config_import(self):
        """Test app.config import."""
        from app.config import settings
        assert settings is not None

    def test_models_import(self):
        """Test model imports."""
        from app.models.user import User, UserRole
        assert User is not None
        assert UserRole is not None

    def test_services_import(self):
        """Test services import."""
        from app.services import ServiceProvider
        assert ServiceProvider is not None

    def test_auth_dependencies_import(self):
        """Test auth dependencies import."""
        from app.dependencies.auth_dependencies import get_current_user
        assert get_current_user is not None

    def test_redis_manager_import(self):
        """Test Redis manager import."""
        from app.core.redis_manager import FirebaseRedisCache
        assert FirebaseRedisCache is not None

    def test_jwt_helper_import(self):
        """Test JWT helper import."""
        from tests.helpers.jwt_helper import jwt_helper
        assert jwt_helper is not None


class TestDatabaseSetup:
    """Test database configuration for tests."""

    def test_database_url_configured(self):
        """Test that database URL is configured for testing."""
        from app.config import settings
        db_url = settings.DATABASE_URL

        # Should use test database (SQLite or test PostgreSQL)
        assert db_url is not None
        assert "test" in db_url.lower() or "sqlite" in db_url.lower()

    def test_test_engine_creation(self, test_engine):
        """Test that test engine can be created."""
        assert test_engine is not None

    def test_db_session_creation(self, db_session):
        """Test that database session can be created."""
        assert db_session is not None


class TestRedisSetup:
    """Test Redis configuration for tests."""

    def test_redis_configuration(self):
        """Test Redis configuration."""
        from app.config import settings
        redis_url = settings.REDIS_URL

        assert redis_url is not None
        # Should use test Redis database (different index)
        assert "/1" in redis_url or "test" in redis_url.lower()

    def test_mock_redis_creation(self, mock_redis):
        """Test that mock Redis can be created."""
        assert mock_redis is not None
        assert hasattr(mock_redis, 'get')
        assert hasattr(mock_redis, 'set')


class TestWhatsAppIntegration:
    """Test WhatsApp integration modules."""

    def test_whatsapp_queue_schemas_import(self):
        """Test WhatsApp queue schemas import."""
        try:
            from app.integrations.whatsapp.queue.schemas import MessageRequest, MessageResponse
            assert MessageRequest is not None
            assert MessageResponse is not None
        except ImportError as e:
            pytest.skip(f"WhatsApp queue schemas not available: {e}")

    def test_whatsapp_queue_manager_import(self):
        """Test WhatsApp queue manager import."""
        try:
            from app.integrations.whatsapp.queue.manager import QueueManager
            assert QueueManager is not None
        except ImportError as e:
            pytest.skip(f"WhatsApp queue manager not available: {e}")


class TestApplicationFactory:
    """Test application factory."""

    def test_application_factory_import(self):
        """Test application factory import."""
        from app.core.application_factory import create_application
        assert create_application is not None

    def test_create_test_application(self):
        """Test creating application for testing."""
        from app.core.application_factory import create_application

        app = create_application(
            enable_monitoring=False,
            enable_debug_endpoints=True,
            deployment_mode="development"
        )

        assert app is not None
        assert app.title is not None


class TestMiddleware:
    """Test middleware imports."""

    def test_cors_middleware_import(self):
        """Test CORS middleware import."""
        from app.middleware.cors import cors_middleware
        assert cors_middleware is not None

    def test_security_headers_middleware_import(self):
        """Test security headers middleware import."""
        from app.middleware.security_headers import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware is not None


class TestFixtures:
    """Test pytest fixtures."""

    def test_test_user_fixtures(self, test_doctor_firebase_uid, test_admin_firebase_uid):
        """Test user fixtures."""
        assert test_doctor_firebase_uid is not None
        assert test_admin_firebase_uid is not None

    def test_credentials_fixtures(self, doctor_a_credentials, admin_credentials):
        """Test credentials fixtures."""
        assert doctor_a_credentials is not None
        assert admin_credentials is not None
        assert "token" in doctor_a_credentials
        assert "token" in admin_credentials

    def test_http_client_fixture(self, http_client):
        """Test HTTP client fixture."""
        assert http_client is not None

    def test_auth_headers_fixture(self, auth_headers):
        """Test auth headers fixture."""
        assert auth_headers is not None
        assert callable(auth_headers)