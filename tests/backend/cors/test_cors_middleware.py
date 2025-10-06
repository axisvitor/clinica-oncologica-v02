"""
Backend Unit Tests for CORS Middleware
Tests the FastAPI CORS middleware configuration directly
"""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


class TestCORSMiddleware:
    """Unit tests for CORS middleware configuration"""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app with CORS middleware"""
        app = FastAPI()

        # Configure CORS exactly as in production
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",
                "http://localhost:5173",
                "https://clinica-oncologica-production.up.railway.app"
            ],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["*"],
            max_age=600
        )

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}

        @app.post("/api/test")
        async def test_post():
            return {"message": "posted"}

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    def test_preflight_allowed_origin(self, client):
        """Test preflight request from allowed origin"""
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"
            }
        )

        assert response.status_code in [200, 204]
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "POST" in response.headers["access-control-allow-methods"]

    def test_actual_request_allowed_origin(self, client):
        """Test actual GET request from allowed origin"""
        response = client.get(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000"
            }
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_post_request_allowed_origin(self, client):
        """Test POST request from allowed origin"""
        response = client.post(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Content-Type": "application/json"
            },
            json={"data": "test"}
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_request_from_vite_dev_server(self, client):
        """Test request from Vite dev server (port 5173)"""
        response = client.get(
            "/api/test",
            headers={
                "Origin": "http://localhost:5173"
            }
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_request_from_production_origin(self, client):
        """Test request from production Railway app"""
        production_origin = "https://clinica-oncologica-production.up.railway.app"
        response = client.get(
            "/api/test",
            headers={
                "Origin": production_origin
            }
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == production_origin

    def test_disallowed_origin_no_cors_headers(self, client):
        """Test that disallowed origin does not get CORS headers"""
        response = client.get(
            "/api/test",
            headers={
                "Origin": "http://evil.com"
            }
        )

        # FastAPI CORS middleware returns 400 for disallowed origins
        # or does not include the origin in allow-origin header
        if response.status_code == 200:
            # If request succeeds, CORS headers should not match evil origin
            allow_origin = response.headers.get("access-control-allow-origin", "")
            assert allow_origin != "http://evil.com"

    def test_credentials_true_no_wildcard_origin(self, client):
        """Test that wildcard origin is not used with credentials:true"""
        response = client.get(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000"
            }
        )

        allow_origin = response.headers.get("access-control-allow-origin", "")
        allow_credentials = response.headers.get("access-control-allow-credentials", "")

        # Critical: Cannot have both * origin and credentials:true
        assert not (allow_origin == "*" and allow_credentials == "true"), \
            "CRITICAL: Cannot use wildcard origin with credentials:true"

    def test_vary_header_includes_origin(self, client):
        """Test that Vary header includes Origin for proper caching"""
        response = client.get(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000"
            }
        )

        vary = response.headers.get("vary", "").lower()
        assert "origin" in vary, "Vary header should include Origin"

    def test_expose_headers_configuration(self, client):
        """Test that expose headers are configured"""
        response = client.get(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000"
            }
        )

        # With expose_headers=["*"], should expose headers
        expose_headers = response.headers.get("access-control-expose-headers", "")
        assert expose_headers, "Should have expose headers configured"

    def test_max_age_configuration(self, client):
        """Test that max age is configured for preflight caching"""
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )

        max_age = response.headers.get("access-control-max-age", "")
        assert max_age, "Max age should be set"
        assert int(max_age) == 600, "Max age should be 600 seconds"

    def test_all_http_methods_allowed(self, client):
        """Test that all required HTTP methods are allowed"""
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "DELETE"
            }
        )

        allow_methods = response.headers.get("access-control-allow-methods", "").upper()

        required_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        for method in required_methods:
            assert method in allow_methods, f"{method} should be in allowed methods"

    def test_custom_headers_allowed(self, client):
        """Test that custom headers are allowed"""
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,x-custom-header"
            }
        )

        allow_headers = response.headers.get("access-control-allow-headers", "").lower()

        # With allow_headers=["*"], should allow any headers
        assert allow_headers == "*" or "authorization" in allow_headers

    def test_cors_headers_on_error_response(self, client):
        """Test that CORS headers are present on error responses"""
        response = client.get(
            "/api/nonexistent",
            headers={
                "Origin": "http://localhost:3000"
            }
        )

        assert response.status_code == 404

        # CORS headers should still be present on 404
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
