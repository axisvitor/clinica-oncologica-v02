"""
Tests for Cache Settings Configuration

MEDIUM-008: Verify that TTL configuration works correctly with environment variables.
"""

import pytest

from app.config.settings.cache import CacheSettings, get_cache_settings, get_ttl


class TestCacheSettings:
    """Test cache TTL configuration."""

    def test_default_values(self):
        """Test that default TTL values are set correctly."""
        settings = CacheSettings()

        # Flow & Templates
        assert settings.FLOW_TEMPLATE_TTL == 3600
        assert settings.TEMPLATE_CACHE_TTL == 3600

        # User & Auth
        assert settings.USER_SESSION_TTL == 1800
        assert settings.AUTH_TOKEN_TTL == 86400
        assert settings.REFRESH_TOKEN_TTL == 604800

        # Patient Data
        assert settings.PATIENT_CACHE_TTL == 900
        assert settings.DOCTOR_CACHE_TTL == 1800

        # Quiz
        assert settings.QUIZ_SESSION_TTL == 7200

        # Messages
        assert settings.MESSAGE_CACHE_TTL == 3600

        # Webhooks
        assert settings.WEBHOOK_IDEMPOTENCY_TTL == 3600

        # Rate Limiting
        assert settings.RATE_LIMIT_WINDOW_TTL == 60

        # Reports
        assert settings.REPORT_CACHE_TTL == 1800
        assert settings.ANALYTICS_CACHE_TTL == 300

        # Distributed
        assert settings.DISTRIBUTED_LOCK_TTL == 30
        assert settings.SAGA_STATE_TTL == 3600

    def test_env_variable_override(self, monkeypatch):
        """Test that environment variables override default values."""
        # Set environment variable
        monkeypatch.setenv('CACHE_FLOW_TEMPLATE_TTL', '7200')
        monkeypatch.setenv('CACHE_PATIENT_CACHE_TTL', '1800')
        monkeypatch.setenv('CACHE_AUTH_TOKEN_TTL', '172800')

        # Create new settings instance
        settings = CacheSettings()

        # Verify overrides
        assert settings.FLOW_TEMPLATE_TTL == 7200
        assert settings.PATIENT_CACHE_TTL == 1800
        assert settings.AUTH_TOKEN_TTL == 172800

        # Other values should remain default
        assert settings.USER_SESSION_TTL == 1800
        assert settings.QUIZ_SESSION_TTL == 7200

    def test_all_ttls_positive(self):
        """Test that all TTL values are positive integers."""
        settings = CacheSettings()

        for field_name, field in settings.__fields__.items():
            if field_name.endswith('_TTL'):
                value = getattr(settings, field_name)
                assert isinstance(value, int), f"{field_name} should be int"
                assert value > 0, f"{field_name} should be positive"

    def test_singleton_instance(self):
        """Test that get_cache_settings returns singleton."""
        settings1 = get_cache_settings()
        settings2 = get_cache_settings()

        assert settings1 is settings2, "Should return same instance"

    def test_get_ttl_helper(self):
        """Test get_ttl helper function."""
        # Test existing keys
        assert get_ttl('FLOW_TEMPLATE_TTL') == 3600
        assert get_ttl('PATIENT_CACHE_TTL') == 900

        # Test non-existent key with default
        assert get_ttl('NONEXISTENT_TTL', default=999) == 999

    def test_ttl_hierarchy(self):
        """Test that TTL values follow a logical hierarchy."""
        settings = CacheSettings()

        # Refresh token should be longer than auth token
        assert settings.REFRESH_TOKEN_TTL > settings.AUTH_TOKEN_TTL

        # Auth token should be longer than session
        assert settings.AUTH_TOKEN_TTL > settings.USER_SESSION_TTL

        # Long cache should be longer than medium
        assert settings.LONG_CACHE_TTL > settings.MEDIUM_CACHE_TTL

        # Medium cache should be longer than short
        assert settings.MEDIUM_CACHE_TTL > settings.SHORT_CACHE_TTL

    def test_distributed_lock_ttl_is_short(self):
        """Test that distributed locks have short TTL (prevent deadlocks)."""
        settings = CacheSettings()

        # Distributed locks should be < 1 minute to prevent deadlocks
        assert settings.DISTRIBUTED_LOCK_TTL < 60

    def test_rate_limit_window_is_short(self):
        """Test that rate limit windows are short (prevent long blocks)."""
        settings = CacheSettings()

        # Rate limit windows should be <= 1 minute
        assert settings.RATE_LIMIT_WINDOW_TTL <= 60

    def test_qrcode_ttl_matches_expiration(self):
        """Test that QR code TTL matches typical QR code expiration."""
        settings = CacheSettings()

        # QR codes typically expire in 5 minutes
        assert settings.QRCODE_TTL == 300

    @pytest.mark.parametrize("ttl_name,expected_min,expected_max", [
        ("DISTRIBUTED_LOCK_TTL", 10, 60),      # Locks: 10s-60s
        ("RATE_LIMIT_WINDOW_TTL", 30, 120),    # Rate limits: 30s-2min
        ("ANALYTICS_CACHE_TTL", 60, 600),      # Analytics: 1min-10min
        ("PATIENT_CACHE_TTL", 300, 1800),      # Patients: 5min-30min
        ("FLOW_TEMPLATE_TTL", 1800, 7200),     # Templates: 30min-2h
        ("REFRESH_TOKEN_TTL", 86400, 2592000), # Refresh: 1day-30days
    ])
    def test_ttl_reasonable_ranges(self, ttl_name, expected_min, expected_max):
        """Test that TTL values are within reasonable ranges."""
        settings = CacheSettings()
        value = getattr(settings, ttl_name)

        assert expected_min <= value <= expected_max, (
            f"{ttl_name}={value} should be between {expected_min} and {expected_max}"
        )

    def test_env_prefix_configuration(self):
        """Test that environment variables use CACHE_ prefix."""
        # This is defined in Config class
        settings = CacheSettings()
        assert settings.Config.env_prefix == "CACHE_"

    def test_case_sensitivity(self):
        """Test that environment variables are case-sensitive."""
        assert CacheSettings.Config.case_sensitive is True


class TestCacheSettingsIntegration:
    """Integration tests for cache settings."""

    def test_redis_settings_included(self):
        """Test that Redis connection settings are included."""
        settings = CacheSettings()

        assert hasattr(settings, 'REDIS_MAX_CONNECTIONS')
        assert hasattr(settings, 'REDIS_SOCKET_TIMEOUT')
        assert hasattr(settings, 'REDIS_SOCKET_CONNECT_TIMEOUT')

        # Verify reasonable values
        assert settings.REDIS_MAX_CONNECTIONS > 0
        assert settings.REDIS_SOCKET_TIMEOUT > 0
        assert settings.REDIS_SOCKET_CONNECT_TIMEOUT > 0

    def test_all_major_components_covered(self):
        """Test that all major system components have TTL config."""
        settings = CacheSettings()

        # Required components
        required_ttls = [
            'FLOW_TEMPLATE_TTL',
            'USER_SESSION_TTL',
            'AUTH_TOKEN_TTL',
            'PATIENT_CACHE_TTL',
            'QUIZ_SESSION_TTL',
            'MESSAGE_CACHE_TTL',
            'WEBHOOK_IDEMPOTENCY_TTL',
            'RATE_LIMIT_WINDOW_TTL',
            'REPORT_CACHE_TTL',
            'SAGA_STATE_TTL',
            'DISTRIBUTED_LOCK_TTL',
        ]

        for ttl in required_ttls:
            assert hasattr(settings, ttl), f"Missing required TTL: {ttl}"
            assert getattr(settings, ttl) > 0

    def test_backward_compatibility(self):
        """Test backward compatibility with old TTL constants."""
        # If code was using old constants, get_ttl should work
        ttl = get_ttl('PATIENT_CACHE_TTL')
        assert isinstance(ttl, int)
        assert ttl > 0
