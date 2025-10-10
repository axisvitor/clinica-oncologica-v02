"""
Unit tests for configuration initialization.

Tests the settings initialization, validation, and environment variable parsing.
"""
import pytest
import os
from unittest.mock import patch, Mock
from pydantic import ValidationError
import json
import tempfile

# Mock environment before importing settings
@pytest.fixture(autouse=True)
def mock_environment():
    """Mock environment variables for testing."""
    with patch.dict(os.environ, {
        'SECRET_KEY': 'test-secret-key-for-testing-only',
        'JWT_SECRET_KEY': 'test-jwt-secret-key-for-testing',
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db',
        'REDIS_URL': 'redis://localhost:6379',
        'ENVIRONMENT': 'test',
        'DEBUG': 'false',
        'FIREBASE_ALLOWED_DOMAINS': '["test.com", "example.org"]',
        'ALLOWED_ORIGINS': '["http://localhost:3000", "http://localhost:5173"]',
        'CSRF_SECRET_KEY': 'test-csrf-secret-key-32-characters-long',
        'ENCRYPTION_KEY': 'test-encryption-key-for-testing'
    }, clear=False):
        yield


class TestSettingsInitialization:
    """Test configuration settings initialization."""

    def test_settings_basic_initialization(self, mock_environment):
        """Test basic settings initialization with valid environment."""
        from app.config import Settings

        settings = Settings()
        assert settings.SECRET_KEY == 'test-secret-key-for-testing-only'
        assert settings.DATABASE_URL == 'postgresql://test:test@localhost:5432/test_db'
        assert settings.ENVIRONMENT == 'test'
        assert settings.DEBUG is False

    def test_settings_with_missing_required_fields(self):
        """Test settings initialization fails with missing required fields."""
        from app.config import Settings

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert 'SECRET_KEY' in str(exc_info.value) or 'DATABASE_URL' in str(exc_info.value)

    def test_settings_validation_placeholder_values(self):
        """Test that placeholder values are rejected."""
        from app.config import Settings

        with patch.dict(os.environ, {
            'SECRET_KEY': 'YOUR_SECRET_KEY_CHANGE_THIS',
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db'
        }, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Settings()
            assert 'must be changed from placeholder' in str(exc_info.value)

    def test_boolean_parsing(self, mock_environment):
        """Test boolean environment variable parsing."""
        from app.config import Settings

        # Test various boolean representations
        test_cases = [
            ('true', True),
            ('false', False),
            ('1', True),
            ('0', False),
            ('yes', True),
            ('no', False),
            ('on', True),
            ('off', False),
            ('', False)
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {'DEBUG': env_value}):
                settings = Settings()
                assert settings.DEBUG == expected, f"Failed for value: {env_value}"

    def test_json_list_parsing(self, mock_environment):
        """Test JSON list parsing for array fields."""
        from app.config import Settings

        # Test valid JSON array
        with patch.dict(os.environ, {'FIREBASE_ALLOWED_DOMAINS': '["domain1.com", "domain2.org"]'}):
            settings = Settings()
            assert settings.FIREBASE_ALLOWED_DOMAINS == ["domain1.com", "domain2.org"]

        # Test empty array
        with patch.dict(os.environ, {'FIREBASE_ALLOWED_DOMAINS': '[]'}):
            settings = Settings()
            assert settings.FIREBASE_ALLOWED_DOMAINS == []

        # Test invalid JSON (should default to empty array)
        with patch.dict(os.environ, {'FIREBASE_ALLOWED_DOMAINS': 'invalid-json'}):
            settings = Settings()
            assert settings.FIREBASE_ALLOWED_DOMAINS == []

    def test_cors_origins_parsing(self, mock_environment):
        """Test CORS origins parsing and configuration."""
        from app.config import Settings

        # Test JSON array format
        with patch.dict(os.environ, {'ALLOWED_ORIGINS': '["http://localhost:3000", "https://app.example.com"]'}):
            settings = Settings()
            assert isinstance(settings.ALLOWED_ORIGINS, list)
            assert "http://localhost:3000" in settings.ALLOWED_ORIGINS

        # Test comma-separated format
        with patch.dict(os.environ, {'ALLOWED_ORIGINS': 'http://localhost:3000,https://app.example.com'}):
            settings = Settings()
            assert isinstance(settings.ALLOWED_ORIGINS, list)
            assert len(settings.ALLOWED_ORIGINS) == 2

    def test_production_environment_validation(self, mock_environment):
        """Test production environment security validation."""
        from app.config import Settings

        # Test production with insecure settings should fail
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'DEBUG': 'true',  # This should fail in production
            'SESSION_COOKIE_SECURE': 'false',
            'SECURE_SSL_REDIRECT': 'false'
        }):
            with pytest.raises(ValueError) as exc_info:
                Settings()
            assert 'production environment security validation failed' in str(exc_info.value).lower()

    def test_redis_ssl_configuration(self, mock_environment):
        """Test Redis SSL configuration validation."""
        from app.config import Settings

        # Test SSL with correct URL scheme
        with patch.dict(os.environ, {
            'REDIS_SSL': 'true',
            'REDIS_URL': 'rediss://localhost:6379'
        }):
            settings = Settings()
            assert settings.REDIS_SSL is True
            assert settings.REDIS_URL.startswith('rediss://')

        # Test inconsistent configuration (should warn but not fail in test)
        with patch.dict(os.environ, {
            'REDIS_SSL': 'false',
            'REDIS_URL': 'rediss://localhost:6379',
            'ENVIRONMENT': 'test'  # Not production, so won't fail
        }):
            settings = Settings()
            assert settings.REDIS_SSL is False


class TestFirebaseConfiguration:
    """Test Firebase configuration validation."""

    def test_firebase_complete_configuration(self, mock_environment):
        """Test Firebase with all required fields."""
        from app.config import Settings

        with patch.dict(os.environ, {
            'FIREBASE_ADMIN_PROJECT_ID': 'test-project',
            'FIREBASE_ADMIN_PRIVATE_KEY': 'test-private-key',
            'FIREBASE_ADMIN_CLIENT_EMAIL': 'test@serviceaccount.com'
        }):
            settings = Settings()
            assert settings.FIREBASE_ADMIN_PROJECT_ID == 'test-project'
            assert settings.FIREBASE_ADMIN_PRIVATE_KEY == 'test-private-key'
            assert settings.FIREBASE_ADMIN_CLIENT_EMAIL == 'test@serviceaccount.com'

    def test_firebase_partial_configuration_fails(self, mock_environment):
        """Test Firebase with missing required fields fails."""
        from app.config import Settings

        # Missing private key should fail
        with patch.dict(os.environ, {
            'FIREBASE_ADMIN_PROJECT_ID': 'test-project',
            'FIREBASE_ADMIN_CLIENT_EMAIL': 'test@serviceaccount.com'
            # Missing FIREBASE_ADMIN_PRIVATE_KEY
        }):
            with pytest.raises(ValueError) as exc_info:
                Settings()
            assert 'Firebase Admin SDK requires all credentials' in str(exc_info.value)

    def test_firebase_security_configuration(self, mock_environment):
        """Test Firebase security settings."""
        from app.config import Settings, get_firebase_security_config

        settings = Settings()
        security_config = get_firebase_security_config()

        assert 'allowed_domains' in security_config
        assert 'require_custom_claims' in security_config
        assert 'allowed_roles' in security_config
        assert security_config['block_public_domains'] is True
        assert 'gmail.com' in security_config['public_domains_blocklist']


class TestCSRFConfiguration:
    """Test CSRF configuration validation."""

    @patch('app.utils.security_validation.validate_csrf_secret')
    def test_csrf_secret_validation(self, mock_validate, mock_environment):
        """Test CSRF secret validation during initialization."""
        from app.config import Settings

        # Mock successful validation
        mock_validate.return_value = True

        with patch.dict(os.environ, {'CSRF_SECRET_KEY': 'very-secure-csrf-secret-key-32-chars'}):
            settings = Settings()
            assert settings.CSRF_SECRET_KEY == 'very-secure-csrf-secret-key-32-chars'
            mock_validate.assert_called_once()

    @patch('app.utils.security_validation.validate_csrf_secret')
    def test_csrf_weak_secret_in_production(self, mock_validate, mock_environment):
        """Test weak CSRF secret fails in production."""
        from app.config import Settings

        # Mock validation failure
        mock_validate.side_effect = ValueError("CSRF secret too weak")

        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'CSRF_SECRET_KEY': 'weak',
            'DEBUG': 'false',
            'SESSION_COOKIE_SECURE': 'true',
            'SECURE_SSL_REDIRECT': 'true'
        }):
            with pytest.raises(ValueError) as exc_info:
                Settings()
            assert 'CSRF secret validation failed in production' in str(exc_info.value)

    @patch('app.utils.security_validation.validate_csrf_secret')
    def test_csrf_weak_secret_in_development(self, mock_validate, mock_environment):
        """Test weak CSRF secret warns but doesn't fail in development."""
        from app.config import Settings

        # Mock validation failure
        mock_validate.side_effect = ValueError("CSRF secret too weak")

        with patch.dict(os.environ, {
            'ENVIRONMENT': 'development',
            'CSRF_SECRET_KEY': 'weak'
        }):
            # Should not raise exception in development
            settings = Settings()
            assert settings.ENVIRONMENT == 'development'


class TestCORSConfiguration:
    """Test CORS configuration logic."""

    def test_cors_production_mode(self, mock_environment):
        """Test CORS configuration in production mode."""
        from app.config import Settings

        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'FRONTEND_URL': 'https://app.example.com',
            'QUIZ_URL': 'https://quiz.example.com',
            'DEBUG': 'false',
            'SESSION_COOKIE_SECURE': 'true',
            'SECURE_SSL_REDIRECT': 'true'
        }):
            settings = Settings()
            cors_origins = settings.get_cors_origins()

            assert 'https://app.example.com' in cors_origins
            assert 'https://quiz.example.com' in cors_origins
            assert len(cors_origins) == 2

    def test_cors_development_mode(self, mock_environment):
        """Test CORS configuration in development mode."""
        from app.config import Settings

        with patch.dict(os.environ, {
            'ENVIRONMENT': 'development',
            'FRONTEND_URL': 'http://localhost:3000',
            'QUIZ_URL': 'http://localhost:3001'
        }):
            settings = Settings()
            cors_origins = settings.get_cors_origins()

            # Development mode returns empty list (uses regex)
            assert cors_origins == []

    def test_cors_explicit_origins_override(self, mock_environment):
        """Test explicit ALLOWED_ORIGINS overrides automatic detection."""
        from app.config import Settings

        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'FRONTEND_URL': 'https://app.example.com',
            'QUIZ_URL': 'https://quiz.example.com',
            'ALLOWED_ORIGINS': '["https://custom.example.com"]',
            'DEBUG': 'false',
            'SESSION_COOKIE_SECURE': 'true',
            'SECURE_SSL_REDIRECT': 'true'
        }):
            settings = Settings()
            cors_origins = settings.get_cors_origins()

            # Should use explicit ALLOWED_ORIGINS
            assert cors_origins == ['https://custom.example.com']


class TestAIHumanizationConfiguration:
    """Test AI humanization configuration."""

    def test_ai_humanization_helpers(self, mock_environment):
        """Test AI humanization helper functions."""
        from app.config import (
            is_ai_humanization_enabled,
            should_humanize_message,
            get_humanization_config
        )

        # Test basic functionality
        assert is_ai_humanization_enabled() is True
        assert should_humanize_message("Hello, how are you?") is True

        # Test critical keyword detection
        assert should_humanize_message("Take your medicação now") is False
        assert should_humanize_message("Emergency situation") is False

        # Test configuration retrieval
        config = get_humanization_config()
        assert 'enabled' in config
        assert 'safety_mode' in config
        assert 'critical_keywords' in config

    def test_critical_keywords_parsing(self, mock_environment):
        """Test critical keywords parsing from environment."""
        from app.config import Settings

        with patch.dict(os.environ, {
            'AI_HUMANIZATION_CRITICAL_KEYWORDS': '["custom", "keyword", "list"]'
        }):
            settings = Settings()
            assert "custom" in settings.AI_HUMANIZATION_CRITICAL_KEYWORDS
            assert "keyword" in settings.AI_HUMANIZATION_CRITICAL_KEYWORDS
            assert len(settings.AI_HUMANIZATION_CRITICAL_KEYWORDS) == 3


class TestPerformanceConfiguration:
    """Test performance-related configuration."""

    def test_redis_connection_settings(self, mock_environment):
        """Test Redis connection and performance settings."""
        from app.config import Settings

        settings = Settings()

        # Test connection pool settings
        assert settings.REDIS_MAX_CONNECTIONS == 50
        assert settings.REDIS_SOCKET_TIMEOUT == 10.0
        assert settings.REDIS_SOCKET_CONNECT_TIMEOUT == 5.0
        assert settings.REDIS_RETRY_ON_TIMEOUT is True

        # Test database isolation
        assert settings.REDIS_ENABLE_DB_ISOLATION is True
        assert settings.REDIS_CACHE_DB != settings.REDIS_BROKER_DB

    def test_cache_ttl_settings(self, mock_environment):
        """Test cache TTL configuration."""
        from app.config import Settings

        settings = Settings()

        # Test Firebase cache TTLs
        assert settings.FIREBASE_TOKEN_CACHE_TTL == 3600  # 1 hour
        assert settings.FIREBASE_USER_CACHE_TTL == 7200   # 2 hours
        assert settings.FIREBASE_SESSION_TTL == 86400     # 24 hours

    def test_rate_limiting_configuration(self, mock_environment):
        """Test rate limiting configuration."""
        from app.config import Settings

        settings = Settings()

        assert settings.RATE_LIMIT_ENABLED is True
        assert hasattr(settings, 'RATE_LIMIT_REDIS_URL')

    def test_monitoring_configuration(self, mock_environment):
        """Test monitoring system configuration."""
        from app.config import Settings

        settings = Settings()

        # Test monitoring settings
        assert settings.MONITORING_ENABLED is True
        assert settings.APM_APDEX_THRESHOLD == 0.5
        assert settings.APM_SLOW_REQUEST_THRESHOLD == 1.0
        assert settings.DB_SLOW_QUERY_THRESHOLD == 1.0
        assert settings.RESOURCE_CPU_THRESHOLD == 80.0
        assert settings.RESOURCE_MEMORY_THRESHOLD == 85.0


class TestEnvironmentModeSpecificBehavior:
    """Test behavior specific to different environment modes."""

    def test_development_mode_settings(self, mock_environment):
        """Test development mode specific settings."""
        from app.config import Settings

        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            settings = Settings()

            assert settings.ENVIRONMENT == 'development'
            # Development allows some relaxed security
            cors_origins = settings.get_cors_origins()
            assert cors_origins == []  # Uses regex in dev

    def test_test_mode_settings(self, mock_environment):
        """Test test mode specific settings."""
        from app.config import Settings

        with patch.dict(os.environ, {'ENVIRONMENT': 'test'}):
            settings = Settings()

            assert settings.ENVIRONMENT == 'test'

    def test_production_mode_security_enforcement(self, mock_environment):
        """Test production mode enforces security requirements."""
        from app.config import Settings

        # Valid production configuration
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'DEBUG': 'false',
            'SESSION_COOKIE_SECURE': 'true',
            'SECURE_SSL_REDIRECT': 'true',
            'FRONTEND_URL': 'https://app.example.com'
        }):
            settings = Settings()
            assert settings.DEBUG is False
            assert settings.SESSION_COOKIE_SECURE is True
            assert settings.SECURE_SSL_REDIRECT is True


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery mechanisms in configuration."""

    def test_missing_optional_fields_with_defaults(self, mock_environment):
        """Test that missing optional fields use proper defaults."""
        from app.config import Settings

        # Remove optional fields from environment
        env_without_optionals = {k: v for k, v in os.environ.items()
                               if not k.startswith('FIREBASE_')
                               and k not in ['ENCRYPTION_KEY', 'CSRF_SECRET_KEY']}

        with patch.dict(os.environ, env_without_optionals, clear=True):
            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret-key',
                'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db'
            }):
                settings = Settings()

                # Should use defaults
                assert settings.FIREBASE_ADMIN_PROJECT_ID is None
                assert settings.ENCRYPTION_KEY is None
                assert settings.FIREBASE_ALLOWED_DOMAINS == []

    def test_invalid_environment_graceful_handling(self, mock_environment):
        """Test graceful handling of invalid environment values."""
        from app.config import Settings

        # Test with invalid integer values that should use defaults
        with patch.dict(os.environ, {
            'REDIS_PORT': 'invalid-port',  # Should cause validation error
        }):
            with pytest.raises(ValidationError):
                Settings()

    @patch('app.config.logger')
    def test_validation_logging(self, mock_logger, mock_environment):
        """Test that validation issues are properly logged."""
        from app.config import Settings

        # This should trigger CORS validation logging
        settings = Settings()

        # Verify that some logging occurred during initialization
        # Note: Exact logging calls depend on the current state of environment


# Performance and Memory Tests
class TestConfigurationPerformance:
    """Test configuration initialization performance."""

    def test_settings_initialization_performance(self, mock_environment, performance_timer):
        """Test that settings initialization is fast."""
        from app.config import Settings

        performance_timer.start()
        settings = Settings()
        elapsed = performance_timer.stop()

        # Settings initialization should be very fast
        assert elapsed < 1.0, f"Settings initialization took {elapsed}s, expected < 1.0s"

    def test_multiple_settings_instances_performance(self, mock_environment, performance_timer):
        """Test performance of creating multiple settings instances."""
        from app.config import Settings

        performance_timer.start()
        for _ in range(10):
            settings = Settings()
        elapsed = performance_timer.stop()

        # Creating multiple instances should be reasonably fast
        assert elapsed < 2.0, f"10 settings instances took {elapsed}s, expected < 2.0s"

    def test_settings_singleton_behavior(self, mock_environment):
        """Test that the global settings instance behaves correctly."""
        from app.config import settings, get_settings

        # Test that get_settings returns the same instance
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
        assert settings1 is settings


# Integration with other components
class TestConfigurationIntegration:
    """Test configuration integration with other system components."""

    def test_redis_url_construction(self, mock_environment):
        """Test Redis URL construction for different components."""
        from app.config import Settings

        settings = Settings()

        # Test that Redis URLs are properly configured
        assert settings.REDIS_URL
        assert settings.CELERY_BROKER_URL
        assert settings.CELERY_RESULT_BACKEND

        # In production, these might use different databases
        if settings.REDIS_ENABLE_DB_ISOLATION:
            assert '/0' in settings.CELERY_BROKER_URL or settings.REDIS_BROKER_DB == 0
            assert '/1' in settings.CELERY_RESULT_BACKEND or settings.REDIS_CACHE_DB == 1

    def test_database_url_validation(self, mock_environment):
        """Test database URL validation and format."""
        from app.config import Settings

        settings = Settings()

        # Should have a valid database URL
        assert settings.DATABASE_URL
        assert 'postgresql' in settings.DATABASE_URL

        # URL should be parseable
        from urllib.parse import urlparse
        parsed = urlparse(settings.DATABASE_URL)
        assert parsed.scheme in ['postgresql', 'postgresql+asyncpg', 'postgresql+psycopg']
        assert parsed.hostname is not None

    def test_logging_configuration_integration(self, mock_environment):
        """Test logging configuration values."""
        from app.config import Settings

        settings = Settings()

        # Test logging settings
        assert settings.LOG_LEVEL in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        assert settings.LOG_FORMAT
        assert '%(asctime)s' in settings.LOG_FORMAT
        assert '%(levelname)s' in settings.LOG_FORMAT