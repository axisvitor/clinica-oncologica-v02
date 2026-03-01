"""
Tests for cache settings configuration.

Verifies current CacheSettings contract and environment overrides.
"""

import pytest

from app.config.settings.cache import CacheSettings, get_cache_settings, get_ttl


class TestCacheSettings:
    """Test cache TTL configuration."""

    def test_default_values(self):
        """Default TTL values should match the current settings model."""
        settings = CacheSettings()

        # Flow & templates
        assert settings.CACHE_FLOW_TEMPLATE_TTL_SECONDS == 3600
        assert settings.CACHE_TEMPLATE_CACHE_TTL_SECONDS == 3600

        # User & auth
        assert settings.CACHE_USER_SESSION_TTL_SECONDS == 1800
        assert settings.CACHE_AUTH_TOKEN_TTL_SECONDS == 86400
        assert settings.CACHE_REFRESH_TOKEN_TTL_SECONDS == 604800

        # Patient data
        assert settings.CACHE_PATIENT_CACHE_TTL_SECONDS == 900
        assert settings.CACHE_DOCTOR_CACHE_TTL_SECONDS == 1800

        # Quiz
        assert settings.CACHE_QUIZ_SESSION_TTL_SECONDS == 7200

        # Messages
        assert settings.CACHE_MESSAGE_CACHE_TTL_SECONDS == 3600

        # Webhooks
        assert settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS == 3600

        # Rate limiting
        assert settings.CACHE_RATE_LIMIT_WINDOW_TTL_SECONDS == 60

        # Reports / analytics
        assert settings.CACHE_REPORT_CACHE_TTL_SECONDS == 1800
        assert settings.CACHE_ANALYTICS_CACHE_TTL_SECONDS == 300

        # Distributed
        assert settings.CACHE_DISTRIBUTED_LOCK_TTL_SECONDS == 30
        assert settings.CACHE_SAGA_STATE_TTL_SECONDS == 3600

    def test_env_variable_override(self, monkeypatch):
        """Environment variables should override defaults."""
        monkeypatch.setenv("CACHE_FLOW_TEMPLATE_TTL_SECONDS", "7200")
        monkeypatch.setenv("CACHE_PATIENT_CACHE_TTL_SECONDS", "1800")
        monkeypatch.setenv("CACHE_AUTH_TOKEN_TTL_SECONDS", "172800")

        settings = CacheSettings()

        assert settings.CACHE_FLOW_TEMPLATE_TTL_SECONDS == 7200
        assert settings.CACHE_PATIENT_CACHE_TTL_SECONDS == 1800
        assert settings.CACHE_AUTH_TOKEN_TTL_SECONDS == 172800

        # Unchanged defaults
        assert settings.CACHE_USER_SESSION_TTL_SECONDS == 1800
        assert settings.CACHE_QUIZ_SESSION_TTL_SECONDS == 7200

    def test_all_ttls_positive(self):
        """Every TTL field should be a positive integer."""
        settings = CacheSettings()

        for field_name in settings.model_fields:
            if field_name.endswith("_TTL") or field_name.endswith("_TTL_SECONDS"):
                value = getattr(settings, field_name)
                assert isinstance(value, int), f"{field_name} should be int"
                assert value > 0, f"{field_name} should be positive"

    def test_singleton_instance(self):
        """get_cache_settings should return a singleton instance."""
        settings1 = get_cache_settings()
        settings2 = get_cache_settings()
        assert settings1 is settings2

    def test_get_ttl_helper(self):
        """get_ttl should return configured values by exact key."""
        assert get_ttl("CACHE_FLOW_TEMPLATE_TTL_SECONDS") == 3600
        assert get_ttl("CACHE_PATIENT_CACHE_TTL_SECONDS") == 900
        assert get_ttl("NONEXISTENT_TTL", default=999) == 999

    def test_ttl_hierarchy(self):
        """Core TTL hierarchy should remain logically ordered."""
        settings = CacheSettings()
        assert settings.CACHE_REFRESH_TOKEN_TTL_SECONDS > settings.CACHE_AUTH_TOKEN_TTL_SECONDS
        assert settings.CACHE_AUTH_TOKEN_TTL_SECONDS > settings.CACHE_USER_SESSION_TTL_SECONDS
        assert settings.LONG_CACHE_TTL > settings.MEDIUM_CACHE_TTL
        assert settings.MEDIUM_CACHE_TTL > settings.SHORT_CACHE_TTL

    def test_distributed_lock_ttl_is_short(self):
        """Distributed locks must stay short to avoid deadlocks."""
        settings = CacheSettings()
        assert settings.CACHE_DISTRIBUTED_LOCK_TTL_SECONDS < 60

    def test_rate_limit_window_is_short(self):
        """Rate-limit windows should remain short."""
        settings = CacheSettings()
        assert settings.CACHE_RATE_LIMIT_WINDOW_TTL_SECONDS <= 60

    def test_qrcode_ttl_matches_expiration(self):
        """QR code cache TTL should remain at 5 minutes."""
        settings = CacheSettings()
        assert settings.CACHE_QRCODE_TTL_SECONDS == 300

    @pytest.mark.parametrize(
        "ttl_name,expected_min,expected_max",
        [
            ("CACHE_DISTRIBUTED_LOCK_TTL_SECONDS", 10, 60),     # Locks: 10s-60s
            ("CACHE_RATE_LIMIT_WINDOW_TTL_SECONDS", 30, 120),   # Rate limits: 30s-2min
            ("CACHE_ANALYTICS_CACHE_TTL_SECONDS", 60, 600),     # Analytics: 1min-10min
            ("CACHE_PATIENT_CACHE_TTL_SECONDS", 300, 1800),     # Patients: 5min-30min
            ("CACHE_FLOW_TEMPLATE_TTL_SECONDS", 1800, 7200),    # Templates: 30min-2h
            ("CACHE_REFRESH_TOKEN_TTL_SECONDS", 86400, 2592000),  # Refresh: 1day-30days
        ],
    )
    def test_ttl_reasonable_ranges(self, ttl_name, expected_min, expected_max):
        """TTL values should stay in reasonable operational ranges."""
        settings = CacheSettings()
        value = getattr(settings, ttl_name)
        assert expected_min <= value <= expected_max

    def test_model_config(self):
        """Settings model config should enforce expected behavior."""
        assert CacheSettings.model_config.get("case_sensitive") is True
        assert CacheSettings.model_config.get("extra") == "ignore"


class TestCacheSettingsIntegration:
    """Integration tests for cache settings."""

    def test_redis_settings_included(self):
        """Redis connection settings should be present and valid."""
        settings = CacheSettings()

        assert hasattr(settings, "REDIS_MAX_CONNECTIONS")
        assert hasattr(settings, "REDIS_SOCKET_TIMEOUT")
        assert hasattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT")

        assert settings.REDIS_MAX_CONNECTIONS > 0
        assert settings.REDIS_SOCKET_TIMEOUT > 0
        assert settings.REDIS_SOCKET_CONNECT_TIMEOUT > 0

    def test_all_major_components_covered(self):
        """All major cache components should have configured TTLs."""
        settings = CacheSettings()

        required_ttls = [
            "CACHE_FLOW_TEMPLATE_TTL_SECONDS",
            "CACHE_USER_SESSION_TTL_SECONDS",
            "CACHE_AUTH_TOKEN_TTL_SECONDS",
            "CACHE_PATIENT_CACHE_TTL_SECONDS",
            "CACHE_QUIZ_SESSION_TTL_SECONDS",
            "CACHE_MESSAGE_CACHE_TTL_SECONDS",
            "CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS",
            "CACHE_RATE_LIMIT_WINDOW_TTL_SECONDS",
            "CACHE_REPORT_CACHE_TTL_SECONDS",
            "CACHE_SAGA_STATE_TTL_SECONDS",
            "CACHE_DISTRIBUTED_LOCK_TTL_SECONDS",
        ]

        for ttl_name in required_ttls:
            assert hasattr(settings, ttl_name), f"Missing required TTL: {ttl_name}"
            assert getattr(settings, ttl_name) > 0

    def test_exact_key_required_in_get_ttl(self):
        """Legacy key names should not resolve unless explicitly present."""
        assert get_ttl("PATIENT_CACHE_TTL", default=123) == 123
