"""
Standalone tests for Security Headers Middleware

This test file can be run independently without the full test configuration.
Run with: pytest test_security_headers_standalone.py -v
"""

import os
import sys

# Set minimal environment variables for testing
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing"

# Add backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, backend_dir)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    create_production_security_middleware,
)


def test_basic_import():
    """Test that the module can be imported."""
    assert SecurityHeadersMiddleware is not None
    assert create_production_security_middleware is not None


def test_x_frame_options_header():
    """Test that X-Frame-Options header is set correctly."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    print("[PASS] X-Frame-Options header test passed")


def test_x_content_type_options_header():
    """Test that X-Content-Type-Options header is set correctly."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    print("[PASS] X-Content-Type-Options header test passed")


def test_x_xss_protection_header():
    """Test that X-XSS-Protection header is set correctly."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    print("[PASS] X-XSS-Protection header test passed")


def test_referrer_policy_header():
    """Test that Referrer-Policy header is set correctly."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    print("[PASS] Referrer-Policy header test passed")


def test_content_security_policy_header():
    """Test that Content-Security-Policy header is set correctly."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    print("[PASS] Content-Security-Policy header test passed")


def test_hsts_header_with_https():
    """Test that HSTS header is set for HTTPS requests."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=True,
        hsts_max_age=31536000,
        hsts_include_subdomains=True,
    )
    client = TestClient(app, base_url="https://testserver")

    response = client.get("/test")
    assert response.status_code == 200
    assert "Strict-Transport-Security" in response.headers

    hsts = response.headers["Strict-Transport-Security"]
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts
    print("[PASS] HSTS header (HTTPS) test passed")


def test_hsts_header_not_set_for_http():
    """Test that HSTS header is NOT set for HTTP requests."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=True,
    )
    client = TestClient(app, base_url="http://testserver")

    response = client.get("/test")
    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers
    print("[PASS] HSTS header (HTTP) test passed")


def test_all_headers_present():
    """Test that all required security headers are present."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200

    # Verify all critical security headers
    required_headers = [
        "X-Frame-Options",
        "X-Content-Type-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Content-Security-Policy",
    ]

    for header in required_headers:
        assert header in response.headers, f"Missing security header: {header}"

    print("[PASS] All required security headers present")


def test_production_middleware_factory():
    """Test that production middleware factory creates correct configuration."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    middleware = create_production_security_middleware(app)

    assert middleware.enable_hsts is True
    assert middleware.hsts_max_age == 31536000
    assert middleware.hsts_include_subdomains is True
    assert middleware.frame_options == "DENY"
    assert middleware.content_type_options == "nosniff"
    assert middleware.xss_protection == "1; mode=block"
    assert middleware.referrer_policy == "strict-origin-when-cross-origin"
    print("[PASS] Production middleware factory test passed")


def test_permissions_policy_header():
    """Test that Permissions-Policy header is set when configured."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    app.add_middleware(
        SecurityHeadersMiddleware,
        permissions_policy="geolocation=(), camera=()",
    )
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200
    assert "Permissions-Policy" in response.headers
    assert response.headers["Permissions-Policy"] == "geolocation=(), camera=()"
    print("[PASS] Permissions-Policy header test passed")


def test_custom_csp_policy():
    """Test custom Content-Security-Policy configuration."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"status": "ok"})

    custom_csp = "default-src 'self'; script-src 'self' 'unsafe-inline'"
    app.add_middleware(
        SecurityHeadersMiddleware,
        csp_policy=custom_csp,
    )
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" in csp
    print("[PASS] Custom CSP policy test passed")


if __name__ == "__main__":
    """Run tests directly with pytest or as a script."""
    print("\n" + "=" * 70)
    print("Security Headers Middleware - Standalone Tests")
    print("=" * 70 + "\n")

    # Run all test functions
    test_functions = [
        test_basic_import,
        test_x_frame_options_header,
        test_x_content_type_options_header,
        test_x_xss_protection_header,
        test_referrer_policy_header,
        test_content_security_policy_header,
        test_hsts_header_with_https,
        test_hsts_header_not_set_for_http,
        test_all_headers_present,
        test_production_middleware_factory,
        test_permissions_policy_header,
        test_custom_csp_policy,
    ]

    passed = 0
    failed = 0

    for test_func in test_functions:
        try:
            print(f"\n{test_func.__name__}:")
            print(f"  {test_func.__doc__.strip()}")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  [FAIL] ERROR: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 70 + "\n")

    sys.exit(0 if failed == 0 else 1)
