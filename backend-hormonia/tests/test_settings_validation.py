"""Tests for settings validation — startup guardrails.

SEC-04: APP_ENABLE_DEBUG=True must be blocked in production/staging environments.

These tests import BaseAppSettings directly from the base module to avoid
triggering the module-level Settings() instantiation in app/config/settings/__init__.py.
Pydantic BaseSettings reads environment variables at instantiation time, so
patch.dict(os.environ, ...) controls which values the class sees when constructed.
"""
import os
import pytest
from unittest.mock import patch

# Import BaseAppSettings directly from the base module.
# This bypasses app/config/settings/__init__.py which has a module-level
# settings = Settings() call that would fail with a clean env.
from app.config.settings.base import BaseAppSettings


class TestDebugFlagValidation:
    """SEC-04: APP_ENABLE_DEBUG=True must be blocked in production/staging."""

    def test_debug_true_in_production_raises_value_error(self):
        """APP_ENABLE_DEBUG=True + APP_ENVIRONMENT=production = ValueError."""
        env = {
            "APP_ENVIRONMENT": "production",
            "APP_ENABLE_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValueError, match="APP_ENABLE_DEBUG=True is not allowed"):
                BaseAppSettings()

    def test_debug_true_in_prod_alias_raises_value_error(self):
        """APP_ENABLE_DEBUG=True + APP_ENVIRONMENT=prod = ValueError (short alias)."""
        env = {
            "APP_ENVIRONMENT": "prod",
            "APP_ENABLE_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValueError, match="APP_ENABLE_DEBUG=True is not allowed"):
                BaseAppSettings()

    def test_debug_true_in_staging_raises_value_error(self):
        """APP_ENABLE_DEBUG=True + APP_ENVIRONMENT=staging = ValueError."""
        env = {
            "APP_ENVIRONMENT": "staging",
            "APP_ENABLE_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValueError, match="APP_ENABLE_DEBUG=True is not allowed"):
                BaseAppSettings()

    def test_debug_false_in_production_succeeds(self):
        """APP_ENABLE_DEBUG=False + APP_ENVIRONMENT=production = OK."""
        env = {
            "APP_ENVIRONMENT": "production",
            "APP_ENABLE_DEBUG": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            s = BaseAppSettings()
            assert s.APP_ENABLE_DEBUG is False

    def test_debug_true_in_development_succeeds(self):
        """APP_ENABLE_DEBUG=True + APP_ENVIRONMENT=development = OK (default)."""
        env = {
            "APP_ENVIRONMENT": "development",
            "APP_ENABLE_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            s = BaseAppSettings()
            assert s.APP_ENABLE_DEBUG is True

    def test_debug_true_in_dev_alias_succeeds(self):
        """APP_ENABLE_DEBUG=True + APP_ENVIRONMENT=dev = OK (short alias)."""
        env = {
            "APP_ENVIRONMENT": "dev",
            "APP_ENABLE_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            s = BaseAppSettings()
            assert s.APP_ENABLE_DEBUG is True

    def test_debug_true_in_test_succeeds(self):
        """APP_ENABLE_DEBUG=True + APP_ENVIRONMENT=test = OK."""
        env = {
            "APP_ENVIRONMENT": "test",
            "APP_ENABLE_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            s = BaseAppSettings()
            assert s.APP_ENABLE_DEBUG is True

    def test_debug_true_in_testing_alias_succeeds(self):
        """APP_ENABLE_DEBUG=True + APP_ENVIRONMENT=testing = OK (alias)."""
        env = {
            "APP_ENVIRONMENT": "testing",
            "APP_ENABLE_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            s = BaseAppSettings()
            assert s.APP_ENABLE_DEBUG is True

    def test_debug_false_in_development_succeeds(self):
        """APP_ENABLE_DEBUG=False + APP_ENVIRONMENT=development = OK."""
        env = {
            "APP_ENVIRONMENT": "development",
            "APP_ENABLE_DEBUG": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            s = BaseAppSettings()
            assert s.APP_ENABLE_DEBUG is False

    def test_error_message_contains_fix_instructions(self):
        """Error message provides clear instructions on how to fix the issue."""
        env = {
            "APP_ENVIRONMENT": "production",
            "APP_ENABLE_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValueError, match="APP_ENABLE_DEBUG=False"):
                BaseAppSettings()
