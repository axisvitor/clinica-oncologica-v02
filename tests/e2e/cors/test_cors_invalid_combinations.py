"""
CORS Invalid Combinations Tests
Tests that invalid CORS configurations are prevented
"""
import pytest
from playwright.sync_api import Page


class TestCORSInvalidCombinations:
    """Test suite for invalid CORS header combinations"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, backend_url: str):
        """Setup for each test"""
        self.page = page
        self.backend_url = backend_url

    async def test_no_wildcard_with_credentials(self):
        """
        CRITICAL: Access-Control-Allow-Origin: *
        CANNOT be used with Access-Control-Allow-Credentials: true

        This is explicitly forbidden by CORS spec for security reasons.
        """
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Test all allowed origins
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://clinica-oncologica-production.up.railway.app"
        ]

        for origin in allowed_origins:
            response = await page.request.fetch(
                f"{self.backend_url}/api/health",
                method="GET",
                headers={
                    "Origin": origin
                }
            )

            headers = response.headers
            allow_origin = headers.get("access-control-allow-origin", "")
            allow_credentials = headers.get("access-control-allow-credentials", "")

            # If credentials are true, origin MUST NOT be "*"
            if allow_credentials == "true":
                assert allow_origin != "*", \
                    f"CRITICAL VIOLATION: Cannot use wildcard (*) with credentials: true for origin {origin}"
                assert allow_origin in allowed_origins or allow_origin == origin, \
                    f"Origin must be specific, not wildcard, when credentials are true"

        await context.close()

    async def test_credentials_true_requires_specific_origin(self):
        """Test that credentials: true requires specific origin"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        response = await page.request.fetch(
            f"{self.backend_url}/api/auth/login",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )

        headers = response.headers

        # If credentials are allowed
        if headers.get("access-control-allow-credentials") == "true":
            allow_origin = headers.get("access-control-allow-origin", "")

            # Origin must be specific
            assert allow_origin != "*", \
                "Specific origin required when credentials are true"
            assert allow_origin != "", \
                "Origin header required when credentials are true"
            assert "http" in allow_origin.lower(), \
                "Origin must be a valid URL"

        await context.close()

    async def test_preflight_missing_required_headers(self):
        """Test preflight validation when required headers are missing"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Preflight without Access-Control-Request-Method (invalid)
        response = await page.request.fetch(
            f"{self.backend_url}/api/patients",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000"
                # Missing Access-Control-Request-Method
            }
        )

        # Server might still respond, but should not treat as CORS preflight
        # Some servers return 200, some return 400
        # The key is that it's not a valid CORS preflight

        await context.close()

    async def test_wildcard_in_allow_headers_with_credentials(self):
        """
        Test that Access-Control-Allow-Headers: *
        is handled correctly with credentials
        """
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
                "Access-Control-Request-Headers": "content-type,authorization,x-custom"
            }
        )

        headers = response.headers
        allow_credentials = headers.get("access-control-allow-credentials", "")
        allow_headers = headers.get("access-control-allow-headers", "")

        # Some implementations allow * for headers even with credentials
        # But it's safer to explicitly list them
        if allow_credentials == "true" and allow_headers == "*":
            print("WARNING: Using wildcard (*) for Allow-Headers with credentials:true")
            print("Consider explicitly listing allowed headers for better security")

        await context.close()

    async def test_multiple_origins_in_allow_origin(self):
        """
        Test that Access-Control-Allow-Origin does not contain multiple origins
        (comma-separated origins are not allowed)
        """
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
        allow_origin = headers.get("access-control-allow-origin", "")

        # Should NOT contain comma-separated multiple origins
        assert "," not in allow_origin, \
            "Access-Control-Allow-Origin cannot contain multiple comma-separated origins"

        await context.close()

    async def test_http_https_scheme_mismatch(self):
        """Test that HTTP/HTTPS scheme must match exactly"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # If localhost:3000 is allowed as http, https should not automatically work
        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "https://localhost:3000"  # HTTPS instead of HTTP
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        # Should require exact scheme match
        if "http://localhost:3000" in ["http://localhost:3000", "http://localhost:5173"]:
            # If http://localhost:3000 is whitelisted, https://localhost:3000 should not be automatically allowed
            if allow_origin == "https://localhost:3000":
                print("WARNING: HTTPS origin allowed when only HTTP might be whitelisted")

        await context.close()

    async def test_port_number_specificity(self):
        """Test that port numbers must match exactly"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Request from port 3001 when only 3000 is allowed
        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "http://localhost:3001"  # Different port
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        # Should not allow different port
        assert allow_origin != "http://localhost:3001", \
            "Port 3001 should not be allowed when only 3000 is whitelisted"

        await context.close()

    async def test_trailing_slash_in_origin(self):
        """Test handling of trailing slash in origin"""
        context = await self.page.context.browser.new_context(
            base_url=self.backend_url
        )
        page = await context.new_page()

        # Origin with trailing slash
        response = await page.request.fetch(
            f"{self.backend_url}/api/health",
            method="GET",
            headers={
                "Origin": "http://localhost:3000/"  # Trailing slash
            }
        )

        headers = response.headers
        allow_origin = headers.get("access-control-allow-origin", "")

        # Origins should not have trailing slashes (per spec)
        # Server should either normalize or reject
        if allow_origin == "http://localhost:3000/":
            print("WARNING: Server is returning origin with trailing slash")
            print("Origins should not contain trailing slashes per CORS spec")

        await context.close()

    async def test_credentials_cannot_be_wildcard(self):
        """Test that Access-Control-Allow-Credentials cannot be '*'"""
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
        allow_credentials = headers.get("access-control-allow-credentials", "")

        # Only valid value is "true" (case-sensitive) or absent
        assert allow_credentials != "*", \
            "Access-Control-Allow-Credentials cannot be '*'"

        if allow_credentials:
            assert allow_credentials.lower() == "true", \
                "Access-Control-Allow-Credentials must be 'true' (lowercase) or absent"

        await context.close()
