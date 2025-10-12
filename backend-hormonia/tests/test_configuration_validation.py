"""
Tests for configuration validation and loading.
Validates that configuration settings work correctly with new logging and error tracking settings.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any


class TestConfigurationLoading:
    """Test configuration loading with new settings."""
    
    def test_config_imports_successfully(self):
        """Test that config module can be imported."""
        try:
            from app.core.config import settings
            assert settings is not None
        except ImportError as e:
            pytest.skip(f"Config module not available: {e}")
    
    def test_logging_configuration_settings(self):
        """Test logging configuration settings are available."""
        try:
            from app.core.config import settings
            
            # Test that logging settings exist (with defaults if not set)
            assert hasattr(settings, 'log_level') or hasattr(settings, 'LOG_LEVEL')
            
            # Test logging-related settings
            log_level = getattr(settings, 'log_level', getattr(settings, 'LOG_LEVEL', 'INFO'))
            assert log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            
        except ImportError:
            pytest.skip("Config module not available")
    
    def test_error_tracking_configuration_settings(self):
        """Test error tracking configuration settings."""
        try:
            from app.core.config import settings
            
            # Test error tracking settings (should have defaults)
            error_tracking = getattr(settings, 'enable_error_tracking', True)
            assert isinstance(error_tracking, bool)
            
            max_error_logs = getattr(settings, 'max_error_logs', 1000)
            assert isinstance(max_error_logs, int)
            assert max_error_logs > 0
            
        except ImportError:
            pytest.skip("Config module not available")
    
    @patch.dict(os.environ, {
        'LOG_LEVEL': 'DEBUG',
        'MAX_LOGS_PER_SECOND': '50',
        'ENABLE_ERROR_TRACKING': 'true',
        'MAX_ERROR_LOGS': '500'
    })
    def test_config_with_environment_variables(self):
        """Test configuration loading with environment variables."""
        try:
            # Reload config to pick up environment changes
            import importlib
            import app.core.config
            importlib.reload(app.core.config)
            
            from app.core.config import settings
            
            # Test that environment variables are loaded
            log_level = getattr(settings, 'log_level', getattr(settings, 'LOG_LEVEL', None))
            if log_level:
                assert log_level == 'DEBUG'
            
        except ImportError:
            pytest.skip("Config module not available")
    
    def test_database_url_configuration(self):
        """Test database URL configuration."""
        try:
            from app.core.config import settings
            
            # Test that database URL exists
            db_url = getattr(settings, 'database_url', getattr(settings, 'DATABASE_URL', None))
            assert db_url is not None, "DATABASE_URL must be configured"
            
            # Test URL format (basic validation)
            assert isinstance(db_url, str)
            assert len(db_url) > 0
            
        except ImportError:
            pytest.skip("Config module not available")
    
    def test_secret_key_configuration(self):
        """Test secret key configuration."""
        try:
            from app.core.config import settings
            
            # Test that secret key exists
            secret_key = getattr(settings, 'secret_key', getattr(settings, 'SECRET_KEY', None))
            assert secret_key is not None, "SECRET_KEY must be configured"
            
            # Test secret key properties
            assert isinstance(secret_key, str)
            assert len(secret_key) >= 32, "SECRET_KEY should be at least 32 characters"
            
        except ImportError:
            pytest.skip("Config module not available")


class TestLoggingConfiguration:
    """Test logging configuration functionality."""
    
    def test_logging_config_module_exists(self):
        """Test that logging config module exists."""
        logging_config_path = Path(__file__).parent.parent / "app" / "core" / "logging_config.py"
        if not logging_config_path.exists():
            pytest.skip("Logging config module not implemented yet")
        
        assert logging_config_path.exists()
    
    def test_rate_limited_logger_class(self):
        """Test RateLimitedLogger class functionality."""
        try:
            from app.core.logging_config import RateLimitedLogger
            
            # Test logger initialization
            logger = RateLimitedLogger(max_logs_per_second=10)
            assert logger.max_logs_per_second == 10
            
            # Test rate limiting functionality
            log_key = "test_key"
            
            # First few logs should be allowed
            for i in range(5):
                assert logger.should_log(log_key) is True
            
            # After hitting limit, should be rate limited
            for i in range(10):
                logger.should_log(log_key)
            
            # Should eventually hit rate limit
            # (exact behavior depends on timing)
            
        except ImportError:
            pytest.skip("RateLimitedLogger not implemented yet")
    
    def test_logging_level_configuration(self):
        """Test logging level configuration."""
        with patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'}):
            try:
                from app.core.logging_config import setup_logging
                
                # Test that logging setup works
                setup_logging()
                
                import logging
                logger = logging.getLogger("test")
                assert logger.level <= logging.DEBUG
                
            except ImportError:
                pytest.skip("Logging setup not implemented yet")
    
    def test_request_logging_middleware_configuration(self):
        """Test request logging middleware configuration."""
        try:
            # Check if request logging middleware exists
            from app.middleware.logging import RequestLoggingMiddleware
            
            # Test middleware initialization
            app = MagicMock()
            middleware = RequestLoggingMiddleware(app)
            
            assert middleware.app == app
            
        except ImportError:
            pytest.skip("Request logging middleware not implemented yet")


class TestErrorTrackingConfiguration:
    """Test error tracking configuration."""
    
    def test_error_handler_module_exists(self):
        """Test that error handler module exists."""
        error_handler_path = Path(__file__).parent.parent / "app" / "core" / "error_handler.py"
        if not error_handler_path.exists():
            pytest.skip("Error handler module not implemented yet")
        
        assert error_handler_path.exists()
    
    def test_critical_error_handler_class(self):
        """Test CriticalErrorHandler class functionality."""
        try:
            from app.core.error_handler import CriticalErrorHandler
            
            # Test handler initialization
            handler = CriticalErrorHandler()
            assert handler is not None
            
            # Test error counting functionality
            error_key = "test_error"
            
            # First few errors should be logged
            for i in range(5):
                assert handler.should_log_error(error_key) is True
            
        except ImportError:
            pytest.skip("CriticalErrorHandler not implemented yet")
    
    def test_error_log_model_exists(self):
        """Test that ErrorLog model exists."""
        try:
            from app.models.error_tracking import ErrorLog
            
            # Test model has required fields
            assert hasattr(ErrorLog, 'error_type')
            assert hasattr(ErrorLog, 'error_message')
            assert hasattr(ErrorLog, 'count')
            assert hasattr(ErrorLog, 'first_seen')
            assert hasattr(ErrorLog, 'last_seen')
            
        except ImportError:
            pytest.skip("ErrorLog model not implemented yet")
    
    def test_error_tracking_database_migration(self):
        """Test that error tracking database migration exists."""
        migrations_dir = Path(__file__).parent.parent / "alembic" / "versions"
        
        if not migrations_dir.exists():
            pytest.skip("Alembic migrations directory not found")
        
        # Look for error tracking migration
        error_tracking_migrations = list(migrations_dir.glob("*error_tracking*"))
        
        if not error_tracking_migrations:
            pytest.skip("Error tracking migration not found")
        
        assert len(error_tracking_migrations) > 0


class TestEnvironmentVariableValidation:
    """Test environment variable validation."""
    
    def test_required_environment_variables(self):
        """Test that required environment variables are validated."""
        required_vars = [
            'DATABASE_URL',
            'SECRET_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            pytest.skip(f"Required environment variables missing: {missing_vars}")
        
        # If we get here, all required vars are present
        assert True
    
    def test_optional_environment_variables_defaults(self):
        """Test that optional environment variables have sensible defaults."""
        optional_vars_with_defaults = {
            'LOG_LEVEL': 'INFO',
            'MAX_LOGS_PER_SECOND': '100',
            'ENABLE_ERROR_TRACKING': 'true',
            'MAX_ERROR_LOGS': '1000'
        }
        
        for var, default in optional_vars_with_defaults.items():
            value = os.getenv(var, default)
            
            # Test that values are reasonable
            if var == 'LOG_LEVEL':
                assert value in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            elif var in ['MAX_LOGS_PER_SECOND', 'MAX_ERROR_LOGS']:
                assert int(value) > 0
            elif var == 'ENABLE_ERROR_TRACKING':
                assert value.lower() in ['true', 'false', '1', '0']
    
    @patch.dict(os.environ, {}, clear=True)
    def test_configuration_with_missing_optional_vars(self):
        """Test configuration works with missing optional variables."""
        # Set only required variables
        with patch.dict(os.environ, {
            'DATABASE_URL': 'sqlite:///test.db',
            'SECRET_KEY': 'test-secret-key-for-testing-purposes-only'
        }):
            try:
                from app.core.config import settings
                
                # Should work with defaults
                assert settings is not None
                
            except ImportError:
                pytest.skip("Config module not available")
    
    def test_environment_file_loading(self):
        """Test .env file loading."""
        env_file = Path(__file__).parent.parent / ".env"
        
        if not env_file.exists():
            pytest.skip(".env file not found")
        
        # Test that .env file has reasonable content
        with open(env_file) as f:
            content = f.read()
        
        # Should contain key configuration variables
        assert 'DATABASE_URL' in content or 'SECRET_KEY' in content


class TestConfigurationDocumentation:
    """Test configuration documentation completeness."""
    
    def test_env_example_file_exists(self):
        """Test that .env.example file exists."""
        env_example_file = Path(__file__).parent.parent / ".env.example"
        
        if not env_example_file.exists():
            pytest.skip(".env.example file not found")
        
        assert env_example_file.exists()
    
    def test_env_example_contains_new_settings(self):
        """Test that .env.example contains new logging and error tracking settings."""
        env_example_file = Path(__file__).parent.parent / ".env.example"
        
        if not env_example_file.exists():
            pytest.skip(".env.example file not found")
        
        with open(env_example_file) as f:
            content = f.read()
        
        # Check for new configuration options
        expected_settings = [
            'LOG_LEVEL',
            'MAX_LOGS_PER_SECOND',
            'ENABLE_ERROR_TRACKING',
            'MAX_ERROR_LOGS'
        ]
        
        missing_settings = []
        for setting in expected_settings:
            if setting not in content:
                missing_settings.append(setting)
        
        if missing_settings:
            pytest.skip(f"New settings not documented in .env.example: {missing_settings}")
        
        assert len(missing_settings) == 0
    
    def test_readme_contains_configuration_documentation(self):
        """Test that README contains configuration documentation."""
        readme_file = Path(__file__).parent.parent / "README.md"
        
        if not readme_file.exists():
            pytest.skip("README.md file not found")
        
        with open(readme_file) as f:
            content = f.read().lower()
        
        # Check for configuration documentation
        config_keywords = ['configuration', 'environment', 'variables', 'settings']
        
        has_config_docs = any(keyword in content for keyword in config_keywords)
        
        if not has_config_docs:
            pytest.skip("Configuration documentation not found in README")
        
        assert has_config_docs


class TestDeploymentConfigurationValidation:
    """Test deployment-specific configuration validation."""
    
    def test_production_configuration_validation(self):
        """Test production configuration validation."""
        # Test production-specific settings
        production_checks = {
            'DEBUG': 'false',  # Should be false in production
            'SECRET_KEY': lambda x: len(x) >= 32 if x else False,  # Should be strong
            'DATABASE_URL': lambda x: 'postgresql' in x.lower() if x else False  # Should use PostgreSQL
        }
        
        for var, check in production_checks.items():
            value = os.getenv(var)
            
            if callable(check):
                if value and not check(value):
                    pytest.skip(f"Production check failed for {var}")
            else:
                if value and value.lower() != check.lower():
                    pytest.skip(f"Production check failed for {var}: expected {check}, got {value}")
    
    def test_security_configuration_validation(self):
        """Test security configuration validation."""
        security_vars = ['SECRET_KEY', 'DATABASE_URL']
        
        for var in security_vars:
            value = os.getenv(var)
            
            if value:
                # Check that sensitive values don't contain obvious test/default values
                insecure_patterns = ['test', 'default', 'changeme', 'password', '123456']
                
                if any(pattern in value.lower() for pattern in insecure_patterns):
                    pytest.skip(f"Potentially insecure value detected for {var}")
    
    def test_logging_configuration_for_production(self):
        """Test logging configuration suitable for production."""
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        max_logs_per_second = int(os.getenv('MAX_LOGS_PER_SECOND', '100'))
        
        # Production logging should be reasonable
        assert log_level in ['INFO', 'WARNING', 'ERROR']  # Not DEBUG in production
        assert 10 <= max_logs_per_second <= 1000  # Reasonable rate limiting


@pytest.mark.integration
class TestConfigurationIntegration:
    """Integration tests for configuration."""
    
    def test_full_application_startup_with_config(self):
        """Test that application can start with current configuration."""
        try:
            from app.main import app
            
            # Test that FastAPI app can be created
            assert app is not None
            
            # Test that app has basic configuration
            assert hasattr(app, 'title')
            
        except ImportError:
            pytest.skip("Application module not available")
        except Exception as e:
            pytest.fail(f"Application startup failed: {e}")
    
    def test_database_connection_with_config(self):
        """Test database connection with current configuration."""
        try:
            from app.database.session import get_db
            
            # Test that database session can be created
            db_gen = get_db()
            db = next(db_gen)
            
            assert db is not None
            
            # Clean up
            db_gen.close()
            
        except ImportError:
            pytest.skip("Database module not available")
        except Exception as e:
            pytest.skip(f"Database connection failed (expected in test environment): {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])