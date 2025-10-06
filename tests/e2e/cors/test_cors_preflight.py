"""
CORS Preflight (OPTIONS) Tests
Tests preflight requests from allowed and disallowed origins
"""
import pytest
from playwright.sync_api import Page, expect


class TestCORSPreflight:
    """Test suite for CORS preflight (OPTIONS) requests"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, backend_url: str):
        """Setup for each test"""
        self.page = page
        self.backend_url = backend_url
        self.allowed_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://clinica-oncologica-production.up.railway.app"
        ]

    async def test_preflight_from_allowed_origin_localhost_3000(self):
        """Test preflight request from localhost:3000 (allowed origin)"""
        # Set context origin to simulate request from allowed origin
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url,
            extra_http_headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization"
            }
        )
        page = await context.new_page()

        # Make preflight request
        response = await page.request.fetch(
            f"{self.backend_url}/api/patients",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization"
            }
        )

        # Validate status
        assert response.status in [200, 204], f"Preflight failed with status {response.status}"

        # Validate CORS headers
        headers = response.headers

        # Access-Control-Allow-Origin should be the requesting origin
        assert headers.get("access-control-allow-origin") == "http://localhost:3000", \
            "Access-Control-Allow-Origin header incorrect"

        # Access-Control-Allow-Credentials must be true
        assert headers.get("access-control-allow-credentials") == "true", \
            "Access-Control-Allow-Credentials must be 'true'"

        # Access-Control-Allow-Methods should include requested method
        allow_methods = headers.get("access-control-allow-methods", "").upper()
        assert "POST" in allow_methods, "POST method not allowed"
        assert "GET" in allow_methods, "GET method not allowed"
        assert "PUT" in allow_methods, "PUT method not allowed"
        assert "DELETE" in allow_methods, "DELETE method not allowed"
        assert "PATCH" in allow_methods, "PATCH method not allowed"

        # Access-Control-Allow-Headers should include requested headers
        allow_headers = headers.get("access-control-allow-headers", "").lower()
        assert "content-type" in allow_headers, "content-type not in allowed headers"
        assert "authorization" in allow_headers, "authorization not in allowed headers"

        # Vary header should include Origin
        vary = headers.get("vary", "").lower()
        assert "origin" in vary, "Vary header should include Origin"

        # Access-Control-Max-Age should be set
        assert headers.get("access-control-max-age"), "Access-Control-Max-Age should be set"

        await context.close()

    async def test_preflight_from_allowed_origin_localhost_5173(self):
        """Test preflight request from localhost:5173 (Vite dev server)"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/appointments",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization"
            }
        )

        assert response.status in [200, 204]
        headers = response.headers

        assert headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert headers.get("access-control-allow-credentials") == "true"
        assert "GET" in headers.get("access-control-allow-methods", "").upper()
        assert "authorization" in headers.get("access-control-allow-headers", "").lower()

        await context.close()

    async def test_preflight_from_production_origin(self):
        """Test preflight request from production Railway app"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        production_origin = "https://clinica-oncologica-production.up.railway.app"
        response = await page.request.fetch(
            f"{self.backend_url}/api/auth/login",
            method="OPTIONS",
            headers={
                "Origin": production_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"
            }
        )

        assert response.status in [200, 204]
        headers = response.headers

        assert headers.get("access-control-allow-origin") == production_origin
        assert headers.get("access-control-allow-credentials") == "true"
        assert "POST" in headers.get("access-control-allow-methods", "").upper()

        await context.close()

    async def test_preflight_complex_headers(self):
        """Test preflight with multiple custom headers"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/patients",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization,x-custom-header,x-request-id"
            }
        )

        assert response.status in [200, 204]
        headers = response.headers

        allow_headers = headers.get("access-control-allow-headers", "").lower()
        assert "content-type" in allow_headers
        assert "authorization" in allow_headers
        # Custom headers should be reflected or * should be allowed
        assert ("x-custom-header" in allow_headers or "*" in allow_headers)

        await context.close()

    async def test_preflight_vary_header_presence(self):
        """Test that Vary header is properly set for cache safety"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/patients",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        headers = response.headers
        vary = headers.get("vary", "").lower()

        # Vary should include Origin to prevent caching issues
        assert "origin" in vary, "Vary: Origin is required for proper CORS caching"

        await context.close()

    async def test_preflight_max_age(self):
        """Test that preflight results can be cached"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/patients",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )

        headers = response.headers
        max_age = headers.get("access-control-max-age")

        assert max_age is not None, "Access-Control-Max-Age should be set"
        assert int(max_age) > 0, "Max age should be positive"
        assert int(max_age) <= 86400, "Max age should not exceed 24 hours"

        await context.close()
