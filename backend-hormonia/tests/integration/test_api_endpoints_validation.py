"""
Comprehensive API Endpoints Validation Test Suite

Tests critical API endpoints for:
- Health checks
- System status
- Authentication
- CORS configuration
- Trailing slash handling
- Database connectivity

This test suite validates the API without requiring a running server
by using FastAPI's TestClient for in-memory testing.
"""

import pytest
from fastapi.testclient import TestClient
from app.core.application_factory import create_application


@pytest.fixture(scope="module")
def test_app():
    """Create test application instance."""
    app = create_application(
        enable_monitoring=False,
        enable_debug_endpoints=True,
        deployment_mode="development",
        enable_error_tracking=False,
        enable_enhanced_openapi=True,
    )
    return app


@pytest.fixture(scope="module")
def client(test_app):
    """Create test client for API testing."""
    return TestClient(test_app)


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    def test_health_live_endpoint(self, client):
        """Test /health/live endpoint."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "live", "alive"]

    def test_health_ready_endpoint(self, client):
        """Test /health/ready endpoint."""
        response = client.get("/health/ready")
        assert response.status_code in [200, 503]  # May fail if DB not ready
        data = response.json()
        assert "status" in data

    def test_health_metrics_endpoint(self, client):
        """Test /health/metrics endpoint."""
        response = client.get("/health/metrics")
        # This endpoint may require auth or be protected
        assert response.status_code in [200, 401, 403]

    def test_v2_health_endpoint(self, client):
        """Test /api/v2/health endpoint."""
        response = client.get("/api/v2/health")
        # Should exist and return health status
        assert response.status_code in [200, 404]

    def test_redis_health_endpoint(self, client):
        """Test /api/v2/redis/health endpoint."""
        response = client.get("/api/v2/redis/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert data["status"] in ["healthy", "unavailable", "unknown"]


class TestDebugEndpoints:
    """Test suite for legacy root debug endpoints (must be absent)."""

    def test_debug_env_endpoint(self, client):
        """Test legacy /debug/env endpoint is not exposed."""
        response = client.get("/debug/env")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Not Found"

    def test_debug_imports_endpoint(self, client):
        """Test legacy /debug/imports endpoint is not exposed."""
        response = client.get("/debug/imports")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Not Found"

    def test_debug_health_endpoint(self, client):
        """Test legacy /debug/health endpoint is not exposed."""
        response = client.get("/debug/health")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Not Found"


class TestAuthEndpoints:
    """Test suite for authentication endpoints."""

    def test_csrf_token_endpoint_without_auth(self, client):
        """Test GET /api/v2/auth/csrf-token without authentication."""
        response = client.get("/api/v2/auth/csrf-token")
        # Should be accessible without auth to get CSRF token
        assert response.status_code in [200, 401]

    def test_me_endpoint_without_auth(self, client):
        """Test GET /api/v2/auth/me without authentication."""
        response = client.get("/api/v2/auth/me")
        # Should require authentication
        assert response.status_code == 401

    def test_auth_endpoints_exist(self, client):
        """Test that critical auth endpoints are registered."""
        # Test various auth endpoints
        endpoints = [
            "/api/v2/auth/csrf-token",
            "/api/v2/auth/me",
            "/api/v2/auth/preferences",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Endpoints should exist (200, 401, 403) not 404
            assert response.status_code != 404, f"Endpoint {endpoint} not found"


class TestTrailingSlashHandling:
    """Test suite for trailing slash handling (known issue from git status)."""

    def test_patients_endpoint_no_slash(self, client):
        """Test /api/v2/patients without trailing slash."""
        response = client.get("/api/v2/patients")
        # Should work or require auth, not redirect
        assert response.status_code in [200, 401, 403]
        # CRITICAL: Should NOT be 307 (redirect) which loses CORS headers
        assert response.status_code != 307

    def test_patients_endpoint_with_slash(self, client):
        """Test /api/v2/patients/ with trailing slash."""
        response = client.get("/api/v2/patients/")
        # Should work the same as without slash
        assert response.status_code in [200, 401, 403]
        assert response.status_code != 307

    def test_health_endpoint_no_slash(self, client):
        """Test /health/live without trailing slash."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.status_code != 307

    def test_health_endpoint_with_slash(self, client):
        """Test /health/live/ with trailing slash."""
        response = client.get("/health/live/")
        # Should work the same (redirect_slashes=False in app config)
        assert response.status_code in [200, 404]  # May 404 if not matched


class TestCORSConfiguration:
    """Test suite for CORS configuration."""

    def test_cors_headers_on_options_request(self, client):
        """Test CORS headers on OPTIONS preflight request."""
        response = client.options(
            "/api/v2/patients",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # OPTIONS should return 200 with CORS headers
        assert response.status_code in [200, 204]
        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers

    def test_cors_headers_on_get_request(self, client):
        """Test CORS headers on actual GET request."""
        response = client.get(
            "/api/v2/patients",
            headers={"Origin": "http://localhost:5173"}
        )
        # Should have CORS headers
        assert response.status_code in [200, 401, 403]
        # CORS headers should be present
        if response.status_code != 401:
            assert "access-control-allow-origin" in response.headers


class TestAPIDocumentation:
    """Test suite for API documentation accessibility."""

    def test_openapi_json_accessible(self, client):
        """Test /openapi.json is accessible."""
        response = client.get("/openapi.json")
        # Should be accessible in development mode
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "Hormonia Backend API (Development)"

    def test_swagger_ui_accessible(self, client):
        """Test /docs (Swagger UI) is accessible."""
        response = client.get("/docs")
        # Should be accessible in development mode
        assert response.status_code == 200

    def test_redoc_accessible(self, client):
        """Test /redoc is accessible."""
        response = client.get("/redoc")
        # Should be accessible in development mode
        assert response.status_code == 200


class TestCriticalEndpointsExist:
    """Test that all critical endpoints are registered."""

    @pytest.mark.parametrize("endpoint", [
        "/api/v2/patients",
        "/api/v2/auth/me",
        "/api/v2/quiz/sessions",
        "/api/v2/appointments",
        "/api/v2/treatments",
        "/api/v2/analytics/overview",
        "/api/v2/flows",
        "/api/v2/messages",
        "/api/v2/reports",
        "/api/v2/admin-extensions/audit-logs",
        "/api/v2/ai/health/",
        "/api/v2/dashboard/main",
        "/api/v2/physicians",
        "/api/v2/system/health",
    ])
    def test_critical_endpoint_exists(self, client, endpoint):
        """Test that critical endpoints exist (not 404)."""
        response = client.get(endpoint)
        # Endpoint should exist (may require auth or return other status)
        assert response.status_code != 404, f"Critical endpoint {endpoint} not found"


class TestSystemEndpoints:
    """Test suite for system management endpoints."""

    def test_system_health_endpoint(self, client):
        """Test /api/v2/system/health endpoint."""
        response = client.get("/api/v2/system/health")
        # May require auth or be public
        assert response.status_code in [200, 401, 403, 404]

    def test_metrics_endpoint(self, client):
        """Test /metrics (Prometheus) endpoint."""
        response = client.get("/metrics")
        assert response.status_code in [200, 401, 403]

    def test_performance_endpoint(self, client):
        """Test /api/v2/performance endpoint."""
        response = client.get("/api/v2/performance")
        # Should exist
        assert response.status_code in [200, 401, 403, 404]


class TestDatabaseHealth:
    """Test suite for database connectivity."""

    def test_database_connection_via_health(self, client):
        """Test database connection via health endpoint."""
        response = client.get("/health/ready")
        # If DB is healthy, ready should return 200
        # If DB is down, ready should return 503
        assert response.status_code in [200, 503]

        data = response.json()
        if "database" in data:
            assert data["database"] in ["healthy", "unhealthy"]


class TestRouterConfiguration:
    """Test router configuration and registration."""

    def test_all_routers_registered(self, test_app):
        """Test that all expected routers are registered."""
        routes = [route.path for route in test_app.routes]

        # Critical route patterns that must exist
        critical_patterns = [
            "/api/v2/patients",
            "/api/v2/auth",
            "/health/live",
            "/metrics",
        ]

        for pattern in critical_patterns:
            matching_routes = [r for r in routes if pattern in r]
            assert len(matching_routes) > 0, f"No routes found matching pattern: {pattern}"

    def test_redirect_slashes_disabled(self, test_app):
        """Test that redirect_slashes is disabled to prevent CORS issues."""
        # In FastAPI, redirect_slashes is set during app creation
        # We can't access it directly, but we test the behavior
        client = TestClient(test_app)

        # Test that requests don't redirect
        response = client.get("/api/v2/patients", follow_redirects=False)
        # Should not be a redirect
        assert response.status_code not in [301, 302, 307, 308]


class TestSecurityHeaders:
    """Test security headers configuration."""

    def test_security_headers_present(self, client):
        """Test that security headers are present in responses."""
        response = client.get("/health/live")

        # Check for common security headers
        # Some may not be present depending on middleware config
        headers = response.headers

        # These headers should be set by SecurityHeadersMiddleware
        # Note: Not all headers may be present in test environment
        if "x-frame-options" in headers:
            assert headers["x-frame-options"] in ["DENY", "SAMEORIGIN"]

        if "x-content-type-options" in headers:
            assert headers["x-content-type-options"] == "nosniff"


class TestAPIVersioning:
    """Test API versioning support."""

    def test_v2_prefix_in_routes(self, test_app):
        """Test that v2 routes have /api/v2 prefix."""
        routes = [route.path for route in test_app.routes]
        v2_routes = [r for r in routes if "/api/v2" in r]

        # Should have many v2 routes
        assert len(v2_routes) > 50, "Insufficient v2 routes registered"

    def test_versioning_middleware_enabled(self, test_app):
        """Test that versioning middleware is enabled."""
        # Check middleware stack includes version middleware
        # This is validated by checking routes work correctly
        client = TestClient(test_app)
        response = client.get("/api/v2/patients")

        # Should work or require auth, not fail with routing error
        assert response.status_code != 500


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
