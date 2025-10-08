"""
Integration tests for CORS Middleware.

Tests Cross-Origin Resource Sharing configuration and behavior.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware.cors import setup_cors_middleware


@pytest.fixture
def app_with_cors():
    """Create FastAPI app with CORS middleware."""
    app = FastAPI()

    # Setup CORS middleware
    setup_cors_middleware(app)

    @app.get("/api/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.post("/api/data")
    async def post_endpoint(data: dict):
        return {"received": data}

    @app.options("/api/test")
    async def options_endpoint():
        return {}

    return app


@pytest.fixture
def client(app_with_cors):
    """Create test client."""
    return TestClient(app_with_cors)


class TestCORSMiddleware:
    """Test CORS middleware functionality."""

    def test_cors_headers_on_simple_request(self, client):
        """Test CORS headers on simple GET request."""
        response = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers

    def test_cors_preflight_request(self, client):
        """Test CORS preflight OPTIONS request."""
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers

    def test_allowed_origins(self, client):
        """Test allowed origins are accepted."""
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",
            "https://clinica-oncologica.vercel.app"
        ]

        for origin in allowed_origins:
            response = client.get(
                "/api/test",
                headers={"Origin": origin}
            )
            assert response.status_code == 200
            assert response.headers.get("Access-Control-Allow-Origin") == origin

    def test_disallowed_origin(self, client):
        """Test disallowed origins are rejected."""
        response = client.get(
            "/api/test",
            headers={"Origin": "http://evil-site.com"}
        )
        assert response.status_code == 200
        # Should not have CORS headers for disallowed origins
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_cors_credentials(self, client):
        """Test CORS credentials support."""
        response = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_cors_allowed_methods(self, client):
        """Test CORS allowed methods."""
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        assert response.status_code == 200
        allowed_methods = response.headers.get("Access-Control-Allow-Methods")
        assert allowed_methods is not None
        methods = allowed_methods.split(", ")
        assert "GET" in methods
        assert "POST" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_cors_allowed_headers(self, client):
        """Test CORS allowed headers."""
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Headers": "Content-Type, Authorization"
            }
        )
        assert response.status_code == 200
        allowed_headers = response.headers.get("Access-Control-Allow-Headers")
        assert allowed_headers is not None
        assert "Content-Type" in allowed_headers
        assert "Authorization" in allowed_headers

    def test_cors_expose_headers(self, client):
        """Test CORS expose headers."""
        response = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        expose_headers = response.headers.get("Access-Control-Expose-Headers")
        if expose_headers:
            assert "X-Request-ID" in expose_headers

    def test_cors_max_age(self, client):
        """Test CORS max age for preflight caching."""
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert response.status_code == 200
        max_age = response.headers.get("Access-Control-Max-Age")
        assert max_age is not None
        assert int(max_age) > 0

    def test_cors_with_post_request(self, client):
        """Test CORS with POST request."""
        response = client.post(
            "/api/data",
            json={"test": "data"},
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers

    def test_cors_wildcard_subdomain(self, client):
        """Test CORS with wildcard subdomain if configured."""
        # This test assumes production URLs are configured
        response = client.get(
            "/api/test",
            headers={"Origin": "https://api.clinica-oncologica.com"}
        )
        # Behavior depends on configuration
        assert response.status_code == 200

    def test_no_origin_header(self, client):
        """Test request without Origin header."""
        response = client.get("/api/test")
        assert response.status_code == 200
        # Should work but no CORS headers
        assert "Access-Control-Allow-Origin" not in response.headers