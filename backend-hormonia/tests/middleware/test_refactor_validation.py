"""
Validation test for middleware refactoring.
Tests that all middleware modules can be imported correctly.
"""

import sys
from pathlib import Path
import secrets
import pytest

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set up minimal environment variables for testing without leaking globally.
@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    # Generate proper secrets per-test to avoid sharing global state
    monkeypatch.setenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("SECURITY_CSRF_SECRET_KEY", secrets.token_urlsafe(32))


def test_cors_imports():
    """Test that cors.py can be imported and basic functions work."""
    try:
        from app.middleware.cors import configure_cors, validate_cors_origins, is_production

        assert callable(configure_cors), "configure_cors should be callable"
        assert callable(validate_cors_origins), "validate_cors_origins should be callable"
        assert callable(is_production), "is_production should be callable"
        assert is_production() is False, "Should be in development mode"

        print("✅ cors.py imports OK")
        return True
    except Exception as e:
        print(f"❌ cors.py import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_imports():
    """Test that config.py can be imported and provides expected configuration."""
    try:
        from app.middleware.config import (
            get_cors_config,
            CSRF_EXEMPT_PATHS,
            RATE_LIMIT_WHITELIST_IPS,
            RATE_LIMIT_EXEMPT_PATHS,
            SECURITY_HEADERS_CONFIG
        )

        # Test CORS config
        cors_config = get_cors_config()
        assert isinstance(cors_config, dict), "get_cors_config should return a dict"
        assert "allowed_origins" in cors_config, "CORS config should have allowed_origins"
        assert "allow_credentials" in cors_config, "CORS config should have allow_credentials"
        assert "allow_methods" in cors_config, "CORS config should have allow_methods"

        # Test CSRF exempt paths
        assert isinstance(CSRF_EXEMPT_PATHS, set), "CSRF_EXEMPT_PATHS should be a set"
        assert len(CSRF_EXEMPT_PATHS) > 0, "CSRF_EXEMPT_PATHS should not be empty"
        assert "/health" in CSRF_EXEMPT_PATHS, "/health should be CSRF exempt"

        # Test rate limit config
        assert isinstance(RATE_LIMIT_WHITELIST_IPS, set), "RATE_LIMIT_WHITELIST_IPS should be a set"
        assert isinstance(RATE_LIMIT_EXEMPT_PATHS, set), "RATE_LIMIT_EXEMPT_PATHS should be a set"

        # Test security headers config
        assert isinstance(SECURITY_HEADERS_CONFIG, dict), "SECURITY_HEADERS_CONFIG should be a dict"

        print("✅ config.py imports OK")
        print(f"   - CORS config keys: {list(cors_config.keys())}")
        print(f"   - CSRF exempt paths count: {len(CSRF_EXEMPT_PATHS)}")
        return True
    except Exception as e:
        print(f"❌ config.py import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_middleware_imports():
    """Test that enhanced_middleware.py can be imported."""
    try:
        from app.middleware.enhanced_middleware import (
            EnhancedSecurityMiddleware,
            RequestLoggingMiddleware,
        )

        assert EnhancedSecurityMiddleware is not None
        assert RequestLoggingMiddleware is not None

        print("✅ enhanced_middleware.py imports OK")
        return True
    except Exception as e:
        print(f"❌ enhanced_middleware.py import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_middleware_setup_imports():
    """Test that middleware_setup.py can be imported."""
    try:
        from app.core.middleware_setup import setup_middleware

        assert callable(setup_middleware), "setup_middleware should be callable"

        print("✅ middleware_setup.py imports OK")
        return True
    except Exception as e:
        print(f"❌ middleware_setup.py import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_legacy_middleware_imports():
    """Test that legacy middleware.py can still be imported."""
    try:
        from app.middleware import (
            LoggingMiddleware,
            SecurityHeadersMiddleware,
            RateLimitMiddleware,
        )

        assert LoggingMiddleware is not None
        assert SecurityHeadersMiddleware is not None
        assert RateLimitMiddleware is not None

        print("✅ middleware.py (legacy) imports OK")
        return True
    except Exception as e:
        print(f"❌ middleware.py import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("MIDDLEWARE REFACTORING VALIDATION")
    print("=" * 60)
    print()

    results = {
        "cors.py": test_cors_imports(),
        "config.py": test_config_imports(),
        "enhanced_middleware.py": test_enhanced_middleware_imports(),
        "middleware_setup.py": test_middleware_setup_imports(),
        "middleware.py (legacy)": test_legacy_middleware_imports(),
    }

    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    for module, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {module}")

    print()

    all_passed = all(results.values())
    if all_passed:
        print("🎉 All validation tests passed!")
        return 0
    else:
        print("❌ Some validation tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
