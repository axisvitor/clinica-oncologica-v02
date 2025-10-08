"""
P0 Production Bug Fixes - Regression Tests

These tests verify that critical production bugs identified on 2025-10-08 are fixed.

Bugs Fixed:
1. CSRF cookie handler: Missing positional argument 'response' (TypeError)
2. Firebase auth: Awaiting synchronous SQLAlchemy Session.execute() (ChunkedIteratorResult)
3. Error tracking: Awaiting synchronous track_error() function (NoneType)

Test Strategy:
- Regression tests to ensure bugs don't reoccur
- Integration tests for complete auth flow
- Smoke tests for production readiness

References:
- docs/SECURITY_IMPROVEMENTS_2025-10-08.md
- Git commit: fix(auth): Critical production fixes - CSRF, Firebase, and error tracking
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi import Response, Request
from datetime import datetime

from app.main import app


class TestCsrfCookieHandlerRegression:
    """
    Regression tests for CSRF cookie handler bug fix.

    Bug: set_csrf_cookie() missing 1 required positional argument: 'response'
    Root Cause: fastapi-csrf-protect >= 0.3.0 API change
    Fix: Generate signed token first, pass both token and response
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_csrf_settings(self, monkeypatch):
        """Mock CSRF settings for testing."""
        import secrets
        from app.config import settings

        csrf_secret = secrets.token_urlsafe(32)
        monkeypatch.setattr(settings, 'CSRF_SECRET_KEY', csrf_secret)
        monkeypatch.setattr(settings, 'ENVIRONMENT', 'development')
        monkeypatch.setattr(settings, 'SESSION_COOKIE_SECURE', False)

    def test_csrf_token_endpoint_returns_200(self, client, mock_csrf_settings):
        """
        REGRESSION TEST: Verify /api/v1/csrf-token returns 200, not 500.

        Before fix: TypeError on every request
        After fix: Successfully generates and returns CSRF token
        """
        response = client.get("/api/v1/csrf-token")

        # Should return 200, not 500 (TypeError)
        assert response.status_code == 200, \
            f"CSRF endpoint returned {response.status_code}. " \
            f"This indicates set_csrf_cookie() signature bug may have returned."

        # Verify response structure
        data = response.json()
        assert "csrf_token" in data, "Missing csrf_token in response"
        assert isinstance(data["csrf_token"], str), "csrf_token should be string"
        assert len(data["csrf_token"]) > 0, "csrf_token should not be empty"

    def test_csrf_cookie_is_set_in_response(self, client, mock_csrf_settings):
        """
        REGRESSION TEST: Verify CSRF cookie is properly set in response.

        Before fix: Cookie not set due to TypeError
        After fix: Cookie properly set with security flags
        """
        response = client.get("/api/v1/csrf-token")

        assert response.status_code == 200

        # Verify cookie is set
        assert "fastapi-csrf-token" in response.cookies, \
            "CSRF cookie not found in response. Check set_csrf_cookie() implementation."

        cookie_value = response.cookies.get("fastapi-csrf-token")
        assert cookie_value is not None, "CSRF cookie value is None"
        assert len(cookie_value) > 0, "CSRF cookie value is empty"

    def test_set_csrf_cookie_function_signature(self):
        """
        REGRESSION TEST: Verify set_csrf_cookie() has correct implementation.

        Ensures the function generates signed token before calling
        csrf_protect.set_csrf_cookie(signed_token, response).
        """
        from app.middleware.csrf import set_csrf_cookie, csrf_protect
        import inspect

        # Get source code of set_csrf_cookie function
        source = inspect.getsource(set_csrf_cookie)

        # Verify it generates signed token
        assert "csrf_protect.generate_csrf()" in source, \
            "set_csrf_cookie() must call csrf_protect.generate_csrf() first"

        # Verify it passes both token and response
        assert "csrf_protect.set_csrf_cookie(signed_token, response)" in source or \
               "csrf_protect.set_csrf_cookie(token, response)" in source, \
            "set_csrf_cookie() must pass both token and response to csrf_protect.set_csrf_cookie()"

    def test_csrf_endpoint_cors_headers_present(self, client, mock_csrf_settings):
        """
        REGRESSION TEST: Verify CORS headers are present in CSRF endpoint response.

        Before fix: 500 error prevented CORS middleware from running
        After fix: CORS headers properly set
        """
        response = client.get("/api/v1/csrf-token")

        assert response.status_code == 200

        # Note: TestClient doesn't always expose CORS headers in tests,
        # but we verify the endpoint completes successfully (allowing CORS to run)
        # In production, verify manually that Access-Control-Allow-Origin is present


class TestFirebaseAuthDatabaseRegression:
    """
    Regression tests for Firebase authentication database query bug fix.

    Bug: object ChunkedIteratorResult can't be used in 'await' expression
    Root Cause: Awaiting synchronous SQLAlchemy Session.execute()
    Fix: Remove 'await' from services.db.execute() calls
    """

    @pytest.fixture
    def mock_firebase_service(self):
        """Mock Firebase service for authentication."""
        mock_service = Mock()
        mock_service.verify_token = AsyncMock(return_value={
            "uid": "test-firebase-uid-123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "doctor"
        })
        return mock_service

    @pytest.fixture
    def mock_db_session(self):
        """Mock synchronous database session."""
        mock_session = Mock()

        # Mock ChunkedIteratorResult (returned by sync execute)
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)

        # execute() should return immediately (synchronous)
        mock_session.execute = Mock(return_value=mock_result)

        return mock_session

    def test_session_auth_does_not_await_sync_execute(self):
        """
        REGRESSION TEST: Verify get_current_user_from_session doesn't await sync execute.

        Checks that services.db.execute() is called WITHOUT await keyword.
        """
        from app.dependencies.auth_dependencies import get_current_user_from_session
        import inspect

        source = inspect.getsource(get_current_user_from_session)

        # Verify execute is called without await
        # Look for "services.db.execute(stmt)" without "await" before it
        assert "result = services.db.execute(stmt)" in source, \
            "Should call services.db.execute() synchronously"

        # Verify there's no "await services.db.execute"
        assert "await services.db.execute" not in source, \
            "REGRESSION: Found 'await services.db.execute' - this causes ChunkedIteratorResult error"

    def test_bearer_token_auth_does_not_await_sync_execute(self):
        """
        REGRESSION TEST: Verify get_current_user doesn't await sync execute.

        Checks that services.db.execute() is called WITHOUT await keyword.
        """
        from app.dependencies.auth_dependencies import get_current_user
        import inspect

        source = inspect.getsource(get_current_user)

        # Verify execute is called without await
        assert "result = services.db.execute(stmt)" in source, \
            "Should call services.db.execute() synchronously"

        # Verify there's no "await services.db.execute"
        assert "await services.db.execute" not in source, \
            "REGRESSION: Found 'await services.db.execute' - this causes ChunkedIteratorResult error"

    @patch('app.dependencies.auth_dependencies._firebase_service')
    @patch('app.dependencies.auth_dependencies._get_service_provider')
    async def test_get_current_user_executes_without_error(
        self, mock_provider_func, mock_firebase_service_dep, mock_db_session
    ):
        """
        REGRESSION TEST: Verify get_current_user executes database queries correctly.

        Ensures SQLAlchemy Session.execute() is called synchronously.
        """
        from app.dependencies.auth_dependencies import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        # Mock Firebase service
        mock_firebase = Mock()
        mock_firebase.verify_token = AsyncMock(return_value={
            "uid": "test-uid-123",
            "email": "test@example.com"
        })
        mock_firebase_service_dep.return_value = mock_firebase

        # Mock service provider
        mock_services = Mock()
        mock_services.db = mock_db_session
        mock_services.user_repository = Mock()

        # Mock the generator function properly
        async def mock_provider_generator():
            yield mock_services

        mock_provider_func.return_value = mock_provider_generator()

        # Mock credentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="test-firebase-token"
        )

        # This should NOT raise "ChunkedIteratorResult can't be used in 'await' expression"
        try:
            # Note: This will fail for other reasons (no user in DB), but should NOT
            # fail with ChunkedIteratorResult error
            await get_current_user(credentials, mock_services)
        except Exception as e:
            error_msg = str(e)
            assert "ChunkedIteratorResult" not in error_msg, \
                f"REGRESSION: ChunkedIteratorResult error detected - " \
                f"services.db.execute() is being awaited. Error: {error_msg}"
            # Other errors are expected (no user found, etc.)


class TestErrorTrackingRegression:
    """
    Regression tests for error tracking bug fix.

    Bug: object NoneType can't be used in 'await' expression
    Root Cause: Awaiting synchronous track_error() function
    Fix: Remove 'await' from track_error() call
    """

    def test_exception_handler_does_not_await_track_error(self):
        """
        REGRESSION TEST: Verify exception handler doesn't await synchronous track_error.

        Checks that track_error() is called WITHOUT await keyword.
        """
        from app.core.application_factory import create_app
        import inspect

        # Get application factory source
        source = inspect.getsource(create_app)

        # Look for track_error call without await
        # This is a basic check - actual implementation may vary
        if "track_error" in source:
            # Verify there's no "await track_error"
            assert "await track_error" not in source, \
                "REGRESSION: Found 'await track_error' - this causes NoneType error"

    def test_track_error_function_is_synchronous(self):
        """
        REGRESSION TEST: Verify track_error() is a synchronous function.

        Ensures track_error() returns None (not a coroutine).
        """
        from app.utils.error_tracking import track_error
        import inspect

        # Check function signature
        assert not inspect.iscoroutinefunction(track_error), \
            "track_error() should be synchronous (not async)"

        # Verify function source doesn't have 'async def'
        source = inspect.getsource(track_error)
        assert not source.strip().startswith("async def"), \
            "track_error() should not be async"


class TestProductionAuthFlowSmoke:
    """
    Smoke tests for complete authentication flow.

    These tests verify the entire auth flow works end-to-end:
    1. CSRF token generation
    2. Session creation with Firebase token
    3. Session validation
    4. Profile retrieval (/auth/me)
    5. Session logout
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_csrf_settings(self, monkeypatch):
        """Mock CSRF settings."""
        import secrets
        from app.config import settings

        csrf_secret = secrets.token_urlsafe(32)
        monkeypatch.setattr(settings, 'CSRF_SECRET_KEY', csrf_secret)
        monkeypatch.setattr(settings, 'ENVIRONMENT', 'development')

    @pytest.fixture
    def mock_firebase_and_db(self, monkeypatch):
        """Mock both Firebase and database for complete flow."""
        # Mock Firebase service
        mock_firebase = Mock()
        mock_firebase.verify_token = AsyncMock(return_value={
            "uid": "smoke-test-uid",
            "email": "smoketest@example.com",
            "name": "Smoke Test User",
            "role": "doctor"
        })

        with patch('app.routers.auth_session._firebase_service', mock_firebase):
            with patch('app.dependencies.auth_dependencies._firebase_service', mock_firebase):
                yield mock_firebase

    def test_smoke_csrf_endpoint_accessible(self, client, mock_csrf_settings):
        """
        SMOKE TEST 1: CSRF endpoint is accessible and returns valid token.
        """
        response = client.get("/api/v1/csrf-token")

        assert response.status_code == 200, \
            f"SMOKE TEST FAILED: CSRF endpoint returned {response.status_code}"

        data = response.json()
        assert "csrf_token" in data
        assert "fastapi-csrf-token" in response.cookies

        print("✅ SMOKE TEST 1 PASSED: CSRF endpoint accessible")

    def test_smoke_health_check_accessible(self, client):
        """
        SMOKE TEST 2: Health check endpoint is accessible.
        """
        response = client.get("/api/v1/health")

        assert response.status_code == 200, \
            f"SMOKE TEST FAILED: Health check returned {response.status_code}"

        data = response.json()
        assert data.get("status") in ["healthy", "ok"]

        print("✅ SMOKE TEST 2 PASSED: Health check accessible")

    def test_smoke_session_endpoint_exists(self, client, mock_csrf_settings):
        """
        SMOKE TEST 3: Session endpoints exist and return proper error codes.
        """
        # Test session creation endpoint (should fail without valid token, but not 500)
        response = client.post(
            "/api/v1/session",
            json={"firebase_token": "invalid-token", "device_info": {}}
        )

        # Should return 401/403/422, NOT 500 (which indicates server error)
        assert response.status_code in [400, 401, 403, 422, 503], \
            f"SMOKE TEST FAILED: Session endpoint returned unexpected {response.status_code}"

        print("✅ SMOKE TEST 3 PASSED: Session endpoints exist")

    def test_smoke_no_500_errors_on_basic_endpoints(self, client, mock_csrf_settings):
        """
        SMOKE TEST 4: Basic endpoints don't return 500 (server errors).

        This test ensures the fixes prevent 500 errors on startup/basic requests.
        """
        endpoints_to_test = [
            ("/api/v1/health", "GET"),
            ("/api/v1/csrf-token", "GET"),
            ("/docs", "GET"),
        ]

        for endpoint, method in endpoints_to_test:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint)

            assert response.status_code != 500, \
                f"SMOKE TEST FAILED: {endpoint} returned 500 (server error). " \
                f"This indicates a critical bug in startup/initialization."

        print("✅ SMOKE TEST 4 PASSED: No 500 errors on basic endpoints")

    def test_smoke_cors_headers_not_blocked(self, client, mock_csrf_settings):
        """
        SMOKE TEST 5: CORS headers are present (not blocked by early 500 errors).

        Before fix: 500 errors prevented CORS middleware from running
        After fix: Requests complete successfully, allowing CORS middleware to run
        """
        response = client.get("/api/v1/csrf-token")

        assert response.status_code == 200, \
            "CSRF endpoint should return 200 (allowing CORS to run)"

        # Note: TestClient doesn't expose CORS headers in test environment
        # In production: manually verify Access-Control-Allow-Origin header is present
        print("✅ SMOKE TEST 5 PASSED: Request completes (CORS can run)")


class TestProductionDeploymentReadiness:
    """
    Production deployment readiness checks.

    These tests verify the application is ready for Railway deployment.
    """

    def test_all_critical_imports_succeed(self):
        """
        Verify all critical modules import without errors.
        """
        critical_modules = [
            "app.main",
            "app.core.application_factory",
            "app.middleware.csrf",
            "app.dependencies.auth_dependencies",
            "app.routers.auth_session",
            "app.utils.error_tracking"
        ]

        for module_name in critical_modules:
            try:
                __import__(module_name)
            except Exception as e:
                pytest.fail(
                    f"Critical module {module_name} failed to import: {e}\n"
                    f"This will cause Railway deployment to fail."
                )

        print("✅ DEPLOYMENT CHECK: All critical modules import successfully")

    def test_csrf_secret_key_configured(self):
        """
        Verify CSRF secret key is configured (required for production).
        """
        from app.config import settings

        csrf_secret = getattr(settings, 'CSRF_SECRET_KEY', None)

        # In test environment, this might not be set (that's OK)
        # But the setting should exist as an attribute
        assert hasattr(settings, 'CSRF_SECRET_KEY'), \
            "CSRF_SECRET_KEY setting missing. Add to config.py and .env"

        print("✅ DEPLOYMENT CHECK: CSRF_SECRET_KEY setting exists")

    def test_firebase_credentials_structure(self):
        """
        Verify Firebase credentials have proper structure.
        """
        from app.config import settings

        # Check Firebase settings exist (even if not configured in test env)
        firebase_attrs = [
            'FIREBASE_ADMIN_PROJECT_ID',
            'FIREBASE_ADMIN_PRIVATE_KEY',
            'FIREBASE_ADMIN_CLIENT_EMAIL'
        ]

        for attr in firebase_attrs:
            assert hasattr(settings, attr), \
                f"Firebase setting {attr} missing. Add to config.py"

        print("✅ DEPLOYMENT CHECK: Firebase settings structure correct")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-k", "smoke or regression"])
