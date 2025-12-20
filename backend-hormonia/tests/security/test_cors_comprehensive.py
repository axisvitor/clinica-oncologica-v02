"""
CORS Comprehensive Test Suite

Tests all aspects of CORS configuration and middleware:
- Origin validation (allowed/blocked)
- Preflight request handling
- Credentials handling
- Method restrictions
- Header validation
- Production vs development mode
- Security edge cases
- Attack scenarios

Target Coverage: >90%

Created by: Tester Agent (Hive Mind)
Coordination: Memory-based swarm coordination
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.security
@pytest.mark.unit
class TestCORSOriginValidation:
    """Test CORS origin validation and security."""

    @patch("app.core.cors.settings")
    def test_allowed_origin_accepted(self, mock_settings):
        """Test that configured origins are allowed."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = [
            "http://localhost:3000",
            "https://app.hormonia.io",
        ]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        # Test localhost origin
        response = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert response.headers.get("access-control-allow-credentials") == "true"

    @patch("app.core.cors.settings")
    def test_blocked_origin_rejected(self, mock_settings):
        """Test that non-configured origins are blocked."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://app.hormonia.io"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        # Malicious origin should not get CORS header
        response = client.get(
            "/api/test",
            headers={"Origin": "https://evil.com"},
        )

        # Request succeeds but no CORS header returned
        assert response.status_code == 200
        # Browser will block access because Access-Control-Allow-Origin doesn't match
        assert response.headers.get("access-control-allow-origin") != "https://evil.com"

    @patch("app.core.cors.settings")
    def test_wildcard_blocked_in_production(self, mock_settings):
        """Test that wildcard origin is blocked in production."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["*", "https://app.hormonia.io"]

        from app.core.cors import get_allowed_origins

        origins = get_allowed_origins()

        # Wildcard should be removed in production
        assert "*" not in origins
        assert "https://app.hormonia.io" in origins

    @patch("app.core.cors.settings")
    def test_wildcard_allowed_in_development(self, mock_settings):
        """Test that wildcard can be used in development (not recommended)."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["*"]

        from app.core.cors import get_allowed_origins

        origins = get_allowed_origins()

        # Wildcard allowed in development
        assert "*" in origins


@pytest.mark.security
@pytest.mark.integration
class TestCORSPreflightRequests:
    """Test CORS preflight (OPTIONS) request handling."""

    @patch("app.core.cors.settings")
    def test_preflight_request_successful(self, mock_settings):
        """Test successful preflight request."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:3000"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        # Preflight OPTIONS request
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-CSRF-Token",
            },
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers
        assert "access-control-max-age" in response.headers

    @patch("app.core.cors.settings")
    def test_preflight_caching(self, mock_settings):
        """Test that preflight responses include max-age for caching."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:3000"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should include cache time (3600 seconds = 1 hour)
        max_age = response.headers.get("access-control-max-age")
        assert max_age is not None
        assert int(max_age) >= 3600


@pytest.mark.security
@pytest.mark.unit
class TestCORSMethodValidation:
    """Test CORS allowed methods validation."""

    @patch("app.core.cors.settings")
    def test_allowed_methods_configured(self, mock_settings):
        """Test that only configured methods are allowed."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:3000"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        allowed_methods = response.headers.get("access-control-allow-methods", "")

        # Standard REST methods should be allowed
        assert "GET" in allowed_methods
        assert "POST" in allowed_methods
        assert "PUT" in allowed_methods
        assert "DELETE" in allowed_methods
        assert "PATCH" in allowed_methods
        assert "OPTIONS" in allowed_methods


@pytest.mark.security
@pytest.mark.unit
class TestCORSHeaderValidation:
    """Test CORS header validation and security."""

    @patch("app.core.cors.settings")
    def test_csrf_headers_allowed(self, mock_settings):
        """Test that CSRF headers are in allowed list."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:3000"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-CSRF-Token",
            },
        )

        allowed_headers = response.headers.get("access-control-allow-headers", "")

        # CSRF headers must be allowed
        assert "X-CSRF-Token" in allowed_headers or "x-csrf-token" in allowed_headers.lower()

    @patch("app.core.cors.settings")
    def test_exposed_headers_include_csrf(self, mock_settings):
        """Test that CSRF token is exposed to JavaScript."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:3000"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        response = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:3000"},
        )

        # X-CSRF-Token should be in exposed headers
        exposed = response.headers.get("access-control-expose-headers", "")
        assert "X-CSRF-Token" in exposed or "x-csrf-token" in exposed.lower()


@pytest.mark.security
@pytest.mark.unit
class TestCORSCredentialsHandling:
    """Test CORS credentials handling security."""

    @patch("app.core.cors.settings")
    def test_credentials_enabled(self, mock_settings):
        """Test that credentials are enabled for session management."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:3000"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        response = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:3000"},
        )

        # Must be true for cookies/sessions
        assert response.headers.get("access-control-allow-credentials") == "true"

    @patch("app.core.cors.settings")
    def test_no_wildcard_with_credentials(self, mock_settings):
        """CRITICAL: Test that wildcard origin is never used with credentials in production."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["*"]

        from app.core.cors import get_allowed_origins

        origins = get_allowed_origins()

        # SECURITY: Wildcard with credentials is a critical vulnerability
        # Browser will reject this configuration
        assert "*" not in origins


@pytest.mark.security
@pytest.mark.unit
class TestCORSProductionSecurity:
    """Test production-specific CORS security requirements."""

    @patch("app.core.cors.settings")
    def test_no_localhost_in_production(self, mock_settings):
        """Test that production doesn't allow localhost origins."""
        mock_settings.APP_ENVIRONMENT = "production"
        # Simulate production config without localhost
        mock_settings.get_cors_origins.return_value = ["https://app.hormonia.io"]

        from app.core.cors import get_allowed_origins

        origins = get_allowed_origins()

        # No localhost should be present
        assert not any("localhost" in origin for origin in origins)
        assert not any("127.0.0.1" in origin for origin in origins)

    @patch("app.core.cors.settings")
    def test_production_requires_https(self, mock_settings):
        """Test that production origins should use HTTPS."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = [
            "https://app.hormonia.io",
            "https://quiz.hormonia.io",
        ]

        from app.core.cors import get_allowed_origins

        origins = get_allowed_origins()

        # All production origins should use HTTPS
        for origin in origins:
            if not origin.startswith("http://localhost"):
                assert origin.startswith("https://"), f"Origin {origin} should use HTTPS"


@pytest.mark.security
@pytest.mark.integration
class TestCORSAttackScenarios:
    """Test CORS against common attack scenarios."""

    @patch("app.core.cors.settings")
    def test_subdomain_bypass_prevention(self, mock_settings):
        """Test that attackers cannot bypass using subdomains."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://app.hormonia.io"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        # Attacker tries evil.app.hormonia.io
        response = client.get(
            "/api/test",
            headers={"Origin": "https://evil.app.hormonia.io"},
        )

        # Should not get CORS header
        assert response.headers.get("access-control-allow-origin") != "https://evil.app.hormonia.io"

    @patch("app.core.cors.settings")
    def test_null_origin_handling(self, mock_settings):
        """Test handling of null origin (sandboxed iframes)."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://app.hormonia.io"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        # Null origin from sandboxed iframe
        response = client.get(
            "/api/test",
            headers={"Origin": "null"},
        )

        # Should not allow null origin
        assert response.headers.get("access-control-allow-origin") != "null"

    @patch("app.core.cors.settings")
    def test_case_sensitivity_bypass_prevention(self, mock_settings):
        """Test that case variations don't bypass origin validation."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://app.hormonia.io"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.get("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        # Try uppercase variation
        response = client.get(
            "/api/test",
            headers={"Origin": "https://APP.HORMONIA.IO"},
        )

        # Should not match (origins are case-sensitive)
        allowed_origin = response.headers.get("access-control-allow-origin")
        assert allowed_origin != "https://APP.HORMONIA.IO"


@pytest.mark.security
@pytest.mark.unit
class TestCORSEnvironmentConfiguration:
    """Test environment-specific CORS configuration."""

    @patch("app.core.cors.settings")
    def test_development_fallback_origins(self, mock_settings):
        """Test that development has localhost fallbacks."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = []  # Empty config

        from app.core.cors import get_allowed_origins

        origins = get_allowed_origins()

        # Should have localhost fallbacks
        assert len(origins) > 0
        assert any("localhost" in origin for origin in origins)

    @patch("app.core.cors.settings")
    def test_production_no_fallback_origins(self, mock_settings):
        """Test that production doesn't add fallback origins."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = []  # Empty config

        from app.core.cors import get_allowed_origins

        origins = get_allowed_origins()

        # Production should have no fallbacks (explicit config required)
        assert len(origins) == 0

    @patch("app.core.cors.settings")
    def test_is_production_detection(self, mock_settings):
        """Test production environment detection."""
        from app.core.cors import is_production

        mock_settings.APP_ENVIRONMENT = "production"
        assert is_production() is True

        mock_settings.APP_ENVIRONMENT = "PRODUCTION"
        assert is_production() is True

        mock_settings.APP_ENVIRONMENT = "prod"
        assert is_production() is True

        mock_settings.APP_ENVIRONMENT = "development"
        assert is_production() is False


@pytest.mark.security
@pytest.mark.performance
class TestCORSPerformance:
    """Test CORS performance characteristics."""

    @patch("app.core.cors.settings")
    def test_preflight_caching_reduces_load(self, mock_settings):
        """Test that preflight responses can be cached."""
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = ["https://app.hormonia.io"]

        from app.core.cors import configure_cors

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        response = client.options(
            "/api/test",
            headers={
                "Origin": "https://app.hormonia.io",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Max-age should be set for caching (1 hour = 3600s)
        max_age = int(response.headers.get("access-control-max-age", "0"))
        assert max_age == 3600

    @patch("app.core.cors.settings")
    def test_origin_validation_efficient(self, mock_settings):
        """Test that origin validation is efficient with many origins."""
        # Create 100 origins
        origins = [f"https://app{i}.hormonia.io" for i in range(100)]
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.get_cors_origins.return_value = origins

        from app.core.cors import get_allowed_origins
        import time

        start = time.time()
        result = get_allowed_origins()
        duration = time.time() - start

        # Should be very fast (< 10ms)
        assert duration < 0.01
        assert len(result) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
