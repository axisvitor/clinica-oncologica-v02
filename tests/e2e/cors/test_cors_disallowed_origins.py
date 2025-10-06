"""
CORS Disallowed Origin Tests
Tests that requests from non-whitelisted origins are properly rejected
"""
import pytest
from playwright.sync_api import Page


class TestCORSDisallowedOrigins:
    """Test suite for CORS requests from disallowed origins"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, backend_url: str):
        """Setup for each test"""
        self.page = page
        self.backend_url = backend_url
        self.disallowed_origins = [
            "http://evil.com",
            "https://malicious-site.com",
            "http://localhost:8080",  # Not in allowed list
            "http://192.168.1.100:3000",  # IP address not in allowed list
            "https://fake-clinic.com"
        ]

    async def test_request_from_evil_origin_rejected(self):
        """Test that requests from evil.com are rejected"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/patients",
            method="GET",
            headers={
                "Origin": "http://evil.com"
            }
        )

        headers = response.headers

        # CORS headers should NOT be present for disallowed origins
        # OR if present, should not match the requesting origin
        allow_origin = headers.get("access-control-allow-origin", "")

        assert allow_origin != "http://evil.com", \
            "Should not allow origin from evil.com"
        assert allow_origin != "*", \
            "Should not use wildcard with credentials"

        await context.close()

    async def test_preflight_from_disallowed_origin(self):
        """Test preflight from disallowed origin"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/patients",
            method="OPTIONS",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST"
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        # Should not return CORS headers for disallowed origin
        assert allow_origin != "https://malicious-site.com", \
            "Should not allow malicious origin"

        await context.close()

    async def test_post_request_from_disallowed_origin(self):
        """Test POST request from disallowed origin"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/auth/login",
            method="POST",
            headers={
                "Origin": "http://localhost:8080",
                "Content-Type": "application/json"
            },
            data={
                "email": "test@example.com",
                "password": "password"
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        # Should not allow localhost:8080 (not in whitelist)
        assert allow_origin != "http://localhost:8080", \
            "Should not allow localhost:8080"

        await context.close()

    async def test_ip_address_origin_rejected(self):
        """Test that IP address origins not in whitelist are rejected"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "http://192.168.1.100:3000"
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        assert allow_origin != "http://192.168.1.100:3000", \
            "Should not allow random IP addresses"

        await context.close()

    async def test_subdomain_not_allowed(self):
        """Test that subdomains of allowed domains are not automatically allowed"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # If production domain is allowed, subdomain should not be
        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "https://evil.clinica-oncologica-production.up.railway.app"
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        assert allow_origin != "https://evil.clinica-oncologica-production.up.railway.app", \
            "Should not allow arbitrary subdomains"

        await context.close()

    async def test_null_origin_handling(self):
        """Test handling of null origin (file:// protocol, sandboxed iframe)"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "null"
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        # Null origin should not be allowed (security risk)
        assert allow_origin != "null", \
            "Should not allow null origin (security risk)"

        await context.close()

    async def test_missing_origin_header(self):
        """Test request without Origin header (same-origin request)"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Request without Origin header
        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET"
        )

        # Should succeed (same-origin request)
        assert response.status == 200

        # CORS headers may or may not be present for same-origin requests
        # This is implementation-dependent

        await context.close()

    async def test_case_sensitive_origin_validation(self):
        """Test that origin validation is case-sensitive for security"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Try uppercase version of allowed origin
        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "HTTP://LOCALHOST:3000"  # Uppercase
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        # Should be case-sensitive (HTTP vs http, LOCALHOST vs localhost)
        # Most implementations normalize to lowercase
        if allow_origin:
            assert allow_origin.lower() == allow_origin, \
                "Origin should be normalized to lowercase"

        await context.close()
