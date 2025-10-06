"""
CORS Actual Request Tests
Tests actual GET/POST/PUT/DELETE requests from allowed origins
"""
import pytest
from playwright.sync_api import Page, expect


class TestCORSActualRequests:
    """Test suite for actual CORS requests (not preflight)"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, backend_url: str):
        """Setup for each test"""
        self.page = page
        self.backend_url = backend_url

    async def test_get_request_from_allowed_origin(self):
        """Test GET request from allowed origin includes CORS headers"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Make GET request with Origin header
        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "http://localhost:3000"
            }
        )

        assert response.status == 200

        headers = response.headers

        # Validate CORS headers on actual response
        assert headers.get("access-control-allow-origin") == "http://localhost:3000", \
            "Access-Control-Allow-Origin must match request origin"

        assert headers.get("access-control-allow-credentials") == "true", \
            "Credentials must be allowed"

        # Vary header for cache safety
        vary = headers.get("vary", "").lower()
        assert "origin" in vary

        await context.close()

    async def test_post_request_from_allowed_origin(self):
        """Test POST request from allowed origin with credentials"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Make POST request with credentials
        response = await page.request.fetch(
            f"{self.backend_url}/api/auth/register",
            method="POST",
            headers={
                "Origin": "http://localhost:3000",
                "Content-Type": "application/json"
            },
            data={
                "email": "test@example.com",
                "password": "TestPass123!",
                "nome": "Test User"
            }
        )

        # Response might be 400 if user exists, but CORS headers should still be present
        headers = response.headers

        assert headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert headers.get("access-control-allow-credentials") == "true"

        # Expose headers for JavaScript access
        expose_headers = headers.get("access-control-expose-headers", "").lower()
        assert expose_headers, "Access-Control-Expose-Headers should be set"

        await context.close()

    async def test_put_request_cors_headers(self):
        """Test PUT request includes proper CORS headers"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # First, preflight
        preflight_response = await page.request.fetch(
            f"{self.backend_url}/api/patients/123",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type,authorization"
            }
        )

        assert preflight_response.status in [200, 204]

        # Then actual request
        response = await page.request.fetch(
            f"{self.backend_url}/api/patients/123",
            method="PUT",
            headers={
                "Origin": "http://localhost:3000",
                "Content-Type": "application/json",
                "Authorization": "Bearer fake-token"
            },
            data={"nome": "Updated Name"}
        )

        # Might be 401/404, but CORS headers should be present
        headers = response.headers
        assert headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert headers.get("access-control-allow-credentials") == "true"

        await context.close()

    async def test_delete_request_cors_headers(self):
        """Test DELETE request includes proper CORS headers"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/appointments/123",
            method="DELETE",
            headers={
                "Origin": "http://localhost:3000",
                "Authorization": "Bearer fake-token"
            }
        )

        # Might be 401/404, but CORS headers should be present
        headers = response.headers
        assert headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert headers.get("access-control-allow-credentials") == "true"

        await context.close()

    async def test_expose_headers_for_javascript_access(self):
        """Test that custom headers are exposed for JavaScript access"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "http://localhost:3000"
            }
        )

        headers = response.headers
        expose_headers = headers.get("access-control-expose-headers", "").lower()

        # Should expose custom headers that JavaScript needs access to
        assert expose_headers, "Should expose at least some headers"
        # Common headers to expose
        expected_exposed = ["content-type", "content-length"]
        for header in expected_exposed:
            if header not in expose_headers and "*" not in expose_headers:
                print(f"Warning: {header} not in exposed headers: {expose_headers}")

        await context.close()

    async def test_cors_with_cookies(self):
        """Test CORS with cookies (credentials: true scenario)"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Make request that sets cookies
        response = await page.request.fetch(
            f"{self.backend_url}/api/auth/login",
            method="POST",
            headers={
                "Origin": "http://localhost:3000",
                "Content-Type": "application/json"
            },
            data={
                "email": "test@example.com",
                "password": "password"
            }
        )

        headers = response.headers

        # With credentials: true, origin cannot be "*"
        assert headers.get("access-control-allow-origin") != "*", \
            "Cannot use wildcard origin with credentials"

        assert headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert headers.get("access-control-allow-credentials") == "true"

        await context.close()

    async def test_cors_headers_on_error_responses(self):
        """Test that CORS headers are present even on error responses"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Request to non-existent endpoint
        response = await page.request.fetch(
            f"{self.backend_url}/api/non-existent-endpoint",
            method="GET",
            headers={
                "Origin": "http://localhost:3000"
            }
        )

        # Should be 404, but CORS headers must still be present
        assert response.status == 404

        headers = response.headers
        assert headers.get("access-control-allow-origin") == "http://localhost:3000", \
            "CORS headers must be present on error responses"
        assert headers.get("access-control-allow-credentials") == "true"

        await context.close()

    async def test_cors_multiple_sequential_requests(self):
        """Test CORS headers are consistent across multiple requests"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        origin = "http://localhost:3000"

        # Make multiple requests
        for i in range(3):
            response = await page.request.fetch(
                f"{self.backend_url}/api/health",
                method="GET",
                headers={"Origin": origin}
            )

            headers = response.headers
            assert headers.get("access-control-allow-origin") == origin, \
                f"Request {i+1}: Origin mismatch"
            assert headers.get("access-control-allow-credentials") == "true", \
                f"Request {i+1}: Credentials not allowed"

        await context.close()
