"""
Test script to validate modular config structure.
Tests backward compatibility and new modular imports.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_backward_compatibility():
    """Test that old imports still work (backward compatibility)."""
    print("🧪 Testing Backward Compatibility...")

    try:
        from app.config import (
            settings,
            get_settings,
            is_ai_humanization_enabled,
            should_humanize_message,
            get_humanization_config,
            get_firebase_security_config,
        )

        print("  ✅ All imports from app.config work")

        # Test settings access
        assert hasattr(settings, "ENVIRONMENT"), "Missing ENVIRONMENT"
        assert hasattr(settings, "DATABASE_URL"), "Missing DATABASE_URL"
        assert hasattr(settings, "SECRET_KEY"), "Missing SECRET_KEY"
        assert hasattr(settings, "REDIS_URL"), "Missing REDIS_URL"
        assert hasattr(settings, "AI_GEMINI_API_KEY"), "Missing AI_GEMINI_API_KEY"
        print("  ✅ All settings attributes accessible")

        # Test helper functions
        assert callable(get_settings), "get_settings not callable"
        assert callable(is_ai_humanization_enabled), (
            "is_ai_humanization_enabled not callable"
        )
        assert callable(should_humanize_message), "should_humanize_message not callable"
        assert callable(get_humanization_config), "get_humanization_config not callable"
        assert callable(get_firebase_security_config), (
            "get_firebase_security_config not callable"
        )
        print("  ✅ All helper functions callable")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_modular_imports():
    """Test that new modular imports work."""
    print("\n🧪 Testing Modular Imports...")

    try:
        from app.config.settings import Settings, settings

        print("  ✅ Import from app.config.settings works")

        from app.config.settings.base import BaseAppSettings

        print("  ✅ Import from base.py works")

        from app.config.settings.database import DatabaseSettings

        print("  ✅ Import from database.py works")

        from app.config.settings.security import SecuritySettings

        print("  ✅ Import from security.py works")

        from app.config.settings.integrations import IntegrationsSettings

        print("  ✅ Import from integrations.py works")

        from app.config.settings.features import FeaturesSettings

        print("  ✅ Import from features.py works")

        from app.config.settings.monitoring import MonitoringSettings

        print("  ✅ Import from monitoring.py works")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_settings_inheritance():
    """Test that Settings class properly inherits from all modules."""
    print("\n🧪 Testing Settings Inheritance...")

    try:
        from app.config.settings import Settings

        # Check that Settings has fields from all modules
        test_cases = [
            # From base.py
            ("ENVIRONMENT", "base"),
            ("DEBUG", "base"),
            # From database.py
            ("DATABASE_URL", "database"),
            ("REDIS_URL", "database"),
            ("REDIS_MAX_CONNECTIONS", "database"),
            # From security.py
            ("SECRET_KEY", "security"),
            ("JWT_SECRET_KEY", "security"),
            ("FIREBASE_ADMIN_PROJECT_ID", "security"),
            ("CSRF_SECRET_KEY", "security"),
            ("FRONTEND_URL", "security"),
            # From integrations.py
            ("AI_GEMINI_API_KEY", "integrations"),
            ("WHATSAPP_EVOLUTION_API_URL", "integrations"),
            ("CELERY_BROKER_URL", "integrations"),
            ("AI_HUMANIZATION_ENABLED", "integrations"),
            # From features.py
            ("QUIZ_ENABLE_VIA_LINK", "features"),
            ("UPLOAD_DIR", "features"),
            ("DEFAULT_LOCALE", "features"),
            # From monitoring.py
            ("LOG_LEVEL", "monitoring"),
            ("SENTRY_DSN", "monitoring"),
            ("ENABLE_ERROR_TRACKING", "monitoring"),
        ]

        for field_name, module in test_cases:
            assert field_name in Settings.model_fields, (
                f"Missing {field_name} from {module}"
            )
            print(f"  ✅ {field_name} (from {module}.py)")

        print(f"\n  ✅ All {len(test_cases)} fields present from all modules")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_validation_methods():
    """Test that validation methods are accessible."""
    print("\n🧪 Testing Validation Methods...")

    try:
        from app.config.settings import settings

        # Check validation methods exist
        assert hasattr(settings, "validate_firebase_config"), (
            "Missing validate_firebase_config"
        )
        assert hasattr(settings, "validate_cors_config"), "Missing validate_cors_config"
        assert hasattr(settings, "validate_csrf_config"), "Missing validate_csrf_config"
        assert hasattr(settings, "validate_production_config"), (
            "Missing validate_production_config"
        )
        print("  ✅ All validation methods present")

        # Check helper methods
        assert hasattr(settings, "get_cors_origins"), "Missing get_cors_origins"
        assert hasattr(settings, "get_firebase_security_config"), (
            "Missing get_firebase_security_config"
        )
        print("  ✅ All helper methods present")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_settings_values():
    """Test that settings have expected default values."""
    print("\n🧪 Testing Settings Values...")

    try:
        from app.config.settings import settings

        # Test some default values
        assert settings.ALGORITHM == "HS256", (
            f"Expected ALGORITHM='HS256', got '{settings.ALGORITHM}'"
        )
        print(f"  ✅ ALGORITHM = {settings.ALGORITHM}")

        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30, (
            "Expected ACCESS_TOKEN_EXPIRE_MINUTES=30"
        )
        print(
            f"  ✅ ACCESS_TOKEN_EXPIRE_MINUTES = {settings.ACCESS_TOKEN_EXPIRE_MINUTES}"
        )

        assert settings.BCRYPT_ROUNDS == 12, "Expected BCRYPT_ROUNDS=12"
        print(f"  ✅ BCRYPT_ROUNDS = {settings.BCRYPT_ROUNDS}")

        assert settings.REDIS_MAX_CONNECTIONS == 50, "Expected REDIS_MAX_CONNECTIONS=50"
        print(f"  ✅ REDIS_MAX_CONNECTIONS = {settings.REDIS_MAX_CONNECTIONS}")

        assert settings.LOG_LEVEL == "INFO", (
            f"Expected LOG_LEVEL='INFO', got '{settings.LOG_LEVEL}'"
        )
        print(f"  ✅ LOG_LEVEL = {settings.LOG_LEVEL}")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def run_all_tests():
    """Run all test suites."""
    print("=" * 60)
    print("🚀 Testing Modular Config Refactoring")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Backward Compatibility", test_backward_compatibility()))
    results.append(("Modular Imports", test_modular_imports()))
    results.append(("Settings Inheritance", test_settings_inheritance()))
    results.append(("Validation Methods", test_validation_methods()))
    results.append(("Settings Values", test_settings_values()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")

    print("\n" + "-" * 60)
    print(f"  Total: {passed}/{total} tests passed ({passed / total * 100:.0f}%)")
    print("=" * 60)

    if passed == total:
        print("\n🎉 All tests passed! Config refactoring successful!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
