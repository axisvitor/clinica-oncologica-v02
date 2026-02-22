import pytest
import os
from unittest.mock import patch
# Import Settings inside tests to avoid pre-loading with wrong env vars
from app.config.settings import Settings

class TestProductionConfig:
    """Tests for production configuration validation."""

    def test_production_secret_key_entropy(self):
        """
        Test that production environment rejects weak secret keys.
        This verifies that SecuritySettings.validate_production_config logic is preserved.
        """
        # Mock environment variables for production
        env_vars = {
            "APP_ENVIRONMENT": "production",
            "APP_ENABLE_DEBUG": "false",
            "SECURITY_SECRET_KEY": "a" * 32,  # 32 chars but low entropy (fails entropy check)
            "SECURITY_ENCRYPTION_KEY": "b" * 32,
            # Use a STRONG CSRF key to ensure the failure comes from SECRET_KEY, not CSRF
            # 32 bytes hex = 64 chars, plenty of entropy
            "SECURITY_CSRF_SECRET_KEY": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890", 
            "SESSION_ENABLE_COOKIE_SECURE": "true",
            "SESSION_ENABLE_COOKIE_HTTPONLY": "true",
            "SECURITY_ENABLE_SSL_REDIRECT": "true",
            # Add other required fields to pass basic validation
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "ENCRYPTION_KEY_CURRENT": "valid-key-for-other-validators",
            "HASH_SALT": "valid-salt",
            "FIREBASE_ADMIN_PROJECT_ID": "mock",
            "FIREBASE_ADMIN_PRIVATE_KEY": "mock",
            "FIREBASE_ADMIN_CLIENT_EMAIL": "mock",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # We expect a ValueError because the SECRET_KEY is weak
            # The match string verifies it's specifically about entropy
            with pytest.raises(ValueError, match="insufficient entropy"):
                Settings()

    def test_production_debug_false(self):
        """Test that DEBUG must be False in production."""
        env_vars = {
            "APP_ENVIRONMENT": "production",
            "APP_ENABLE_DEBUG": "true",  # Invalid for production
            "SECURITY_SECRET_KEY": "s" * 64, # Mock strong key length
            "SESSION_ENABLE_COOKIE_SECURE": "true",
            "SECURITY_ENABLE_SSL_REDIRECT": "true",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "ENCRYPTION_KEY_CURRENT": "valid-key-for-other-validators",
            "HASH_SALT": "valid-salt",
            "FIREBASE_ADMIN_PROJECT_ID": "mock",
            "FIREBASE_ADMIN_PRIVATE_KEY": "mock",
            "FIREBASE_ADMIN_CLIENT_EMAIL": "mock",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="APP_ENABLE_DEBUG=True is not allowed"):
                Settings()

    def test_production_secure_cookies(self):
        """Test that Secure Cookies are required in production."""
        env_vars = {
            "APP_ENVIRONMENT": "production",
            "APP_ENABLE_DEBUG": "false",
            "SESSION_ENABLE_COOKIE_SECURE": "false", # Invalid
            "SECURITY_SECRET_KEY": "s" * 64,
            "SECURITY_ENABLE_SSL_REDIRECT": "true",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "ENCRYPTION_KEY_CURRENT": "valid-key-for-other-validators",
            "HASH_SALT": "valid-salt",
            "FIREBASE_ADMIN_PROJECT_ID": "mock",
            "FIREBASE_ADMIN_PRIVATE_KEY": "mock",
            "FIREBASE_ADMIN_CLIENT_EMAIL": "mock",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="SESSION_ENABLE_COOKIE_SECURE must be True"):
                Settings()
