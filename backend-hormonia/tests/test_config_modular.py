"""
Tests for modular configuration public surface.
"""

from app.config import (
    settings,
    get_settings,
    is_ai_humanization_enabled,
    should_humanize_message,
    get_humanization_config,
    get_firebase_security_config,
)
from app.config.settings import Settings


def test_public_config_imports_and_helpers() -> None:
    """Public config exports should stay importable and callable."""
    assert settings is get_settings()
    assert callable(is_ai_humanization_enabled)
    assert callable(should_humanize_message)
    assert callable(get_humanization_config)
    assert callable(get_firebase_security_config)


def test_settings_contains_core_fields() -> None:
    """Main Settings model should expose core fields from all modules."""
    required_fields = [
        "APP_ENVIRONMENT",
        "DATABASE_URL",
        "REDIS_URL",
        "SECURITY_SECRET_KEY",
        "SECURITY_CSRF_SECRET_KEY",
        "SECURITY_ALGORITHM",
        "AI_GEMINI_API_KEY",
        "AUTH_BCRYPT_ROUNDS",
        "QUIZ_ENABLE_VIA_LINK",
        "LOGGING_LEVEL",
    ]
    for field in required_fields:
        assert field in Settings.model_fields, f"Missing field: {field}"


def test_settings_exposes_validation_and_helper_methods() -> None:
    """Runtime settings object should provide expected validation helpers."""
    for method in [
        "validate_ai_config",
        "validate_cors_headers",
        "validate_csrf_config",
        "validate_production_config",
        "validate_required_environment_variables",
        "get_cors_origins",
        "get_firebase_security_config",
        "get_humanization_config",
    ]:
        assert hasattr(settings, method), f"Missing method: {method}"


def test_settings_security_defaults_are_sane() -> None:
    """Critical security-related values should be initialized with sane defaults."""
    assert settings.SECURITY_ALGORITHM
    assert settings.AUTH_BCRYPT_ROUNDS >= 10
    assert settings.LOGGING_LEVEL
