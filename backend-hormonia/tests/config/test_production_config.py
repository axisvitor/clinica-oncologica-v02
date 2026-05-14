import os
from unittest.mock import patch

import pytest

# Import Settings inside tests to avoid pre-loading with wrong env vars
from app.config.settings import Settings


def _strong_secret(prefix: str) -> str:
    return f"{prefix}-A7f3K9m2Q8r5T1v6W4x0YzB2cD4eF6gH8iJ0kL2mN4pQ6rS8tU"


def _required_production_env(**overrides: str) -> dict[str, str]:
    env = {
        "APP_ENVIRONMENT": "production",
        "APP_ENABLE_DEBUG": "false",
        "ALLOW_AI_SIMULATION": "false",
        "SECURITY_SECRET_KEY": _strong_secret("security"),
        "ENCRYPTION_KEY_CURRENT": _strong_secret("fernet"),
        "PHI_ENCRYPTION_KEY": _strong_secret("phi"),
        "HASH_SALT": _strong_secret("salt"),
        "SECURITY_CSRF_SECRET_KEY": _strong_secret("csrf"),
        "SESSION_ENABLE_COOKIE_SECURE": "true",
        "SESSION_ENABLE_COOKIE_HTTPONLY": "true",
        "SECURITY_ENABLE_SSL_REDIRECT": "true",
        "DATABASE_URL": "postgresql+psycopg://user:pass@db.example.invalid/app?sslmode=require&sslminversion=TLSv1.2",
        "REDIS_URL": "redis://localhost:6379/0",
        "FIREBASE_ADMIN_PROJECT_ID": "mock",
        "FIREBASE_ADMIN_PRIVATE_KEY": "mock",
        "FIREBASE_ADMIN_CLIENT_EMAIL": "mock@example.invalid",
        "WHATSAPP_WUZAPI_TOKEN": _strong_secret("wuzapi"),
        "AI_GEMINI_API_KEY": _strong_secret("gemini"),
    }
    env.update(overrides)
    return env


class TestProductionConfig:
    """Tests for production configuration validation."""

    def test_production_secret_key_entropy(self):
        """
        Test that production environment rejects weak secret keys.
        This verifies that SecuritySettings.validate_production_config logic is preserved.
        """
        env_vars = _required_production_env(
            SECURITY_SECRET_KEY="a" * 32,  # 32 chars but low entropy (fails entropy check)
        )

        with patch.dict(os.environ, env_vars, clear=True):
            # We expect a ValueError because the SECRET_KEY is weak.
            # The match string verifies it's specifically about entropy.
            with pytest.raises(ValueError, match="insufficient entropy"):
                Settings(_env_file=None)

    def test_production_debug_false(self):
        """Test that DEBUG must be False in production."""
        env_vars = _required_production_env(
            APP_ENABLE_DEBUG="true",  # Invalid for production
        )

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="APP_ENABLE_DEBUG=True is not allowed"):
                Settings(_env_file=None)

    def test_production_secure_cookies(self):
        """Test that Secure Cookies are required in production."""
        env_vars = _required_production_env(
            SESSION_ENABLE_COOKIE_SECURE="false",  # Invalid
        )

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="SESSION_ENABLE_COOKIE_SECURE must be True"):
                Settings(_env_file=None)
