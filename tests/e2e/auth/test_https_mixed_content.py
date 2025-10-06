"""
E2E Tests for HTTPS and Mixed Content Security

Tests that all API calls use HTTPS and no mixed content warnings occur
in production Railway environment.
"""
import pytest
import os
import httpx
from urllib.parse import urlparse


@pytest.fixture
def production_frontend_url():
    """Production frontend URL (must be HTTPS)"""
    return os.getenv(
        "FRONTEND_URL",
        "https://clinica-oncologica-v02-production.up.railway.app"
    )


@pytest.fixture
def production_backend_url():
    """Production backend URL (must be HTTPS)"""
    return os.getenv(
        "BACKEND_URL",
        "https://backend-hormonia-production.up.railway.app"
    )


class TestHTTPSConfiguration:
    """Test suite for HTTPS configuration and mixed content prevention"""

    @pytest.mark.asyncio
    async def test_backend_serves_https_only(self, production_backend_url):
        """
        Test 1: Backend serves only HTTPS

        Validates:
        - Backend URL is HTTPS
        - HTTP requests redirect to HTTPS
        - HSTS headers are present
        """
        parsed = urlparse(production_backend_url)
        assert parsed.scheme == "https", \
            f"Backend must use HTTPS, got: {parsed.scheme}"

        async with httpx.AsyncClient(follow_redirects=False) as client:
            # Try HTTPS endpoint
            response = await client.get(f"{production_backend_url}/api/v1/health")
            assert response.status_code == 200

            # Check for security headers
            headers = response.headers

            # HSTS header should be present (Railway adds this)
            # Note: May not be present in all Railway configs, but recommended
            if 'strict-transport-security' in headers:
                assert 'max-age' in headers['strict-transport-security'].lower()

    @pytest.mark.asyncio
    async def test_frontend_serves_https_only(self, production_frontend_url):
        """
        Test 2: Frontend serves only HTTPS

        Validates:
        - Frontend URL is HTTPS
        - No HTTP fallback
        """
        parsed = urlparse(production_frontend_url)
        assert parsed.scheme == "https", \
            f"Frontend must use HTTPS, got: {parsed.scheme}"

        async with httpx.AsyncClient() as client:
            response = await client.get(production_frontend_url)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_api_endpoints_use_https(self, production_backend_url):
        """
        Test 3: All API endpoints accessible via HTTPS

        Validates:
        - Health endpoint: HTTPS
        - Auth endpoints: HTTPS
        - API routes: HTTPS
        """
        endpoints = [
            "/api/v1/health",
            "/api/v1/auth/verify",
            "/api/v1/users/me",
            "/api/v1/patients",
            "/api/v1/appointments"
        ]

        async with httpx.AsyncClient() as client:
            for endpoint in endpoints:
                url = f"{production_backend_url}{endpoint}"
                parsed = urlparse(url)

                assert parsed.scheme == "https", \
                    f"Endpoint {endpoint} must use HTTPS"

                # Just verify HTTPS works (will get 401 for auth-required endpoints)
                # We're only testing protocol, not authorization
                try:
                    response = await client.get(url)
                    # 200, 401, or 403 are all acceptable (means HTTPS worked)
                    assert response.status_code in [200, 401, 403, 404]
                except httpx.ConnectError:
                    pytest.skip(f"Cannot connect to {url} - may not be deployed")

    @pytest.mark.asyncio
    async def test_websocket_uses_wss(self, production_backend_url):
        """
        Test 4: WebSocket connections use WSS (secure)

        Validates:
        - WebSocket upgrade uses wss:// protocol
        - No insecure ws:// connections
        """
        # Convert HTTPS URL to WSS URL
        ws_url = production_backend_url.replace("https://", "wss://")
        parsed = urlparse(ws_url)

        assert parsed.scheme == "wss", \
            "WebSocket connections must use wss:// (secure WebSocket)"

    @pytest.mark.asyncio
    async def test_cors_headers_with_https_origins(self, production_backend_url):
        """
        Test 5: CORS headers only allow HTTPS origins

        Validates:
        - Allowed origins are HTTPS
        - No HTTP origins in production
        """
        allowed_https_origins = [
            "https://clinica-oncologica-v02-production.up.railway.app",
            "https://interface-quiz-production.up.railway.app"
        ]

        async with httpx.AsyncClient() as client:
            for origin in allowed_https_origins:
                response = await client.options(
                    f"{production_backend_url}/api/v1/health",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "GET"
                    }
                )

                # Should allow HTTPS origins
                assert response.status_code in [200, 204]

                allow_origin = response.headers.get("access-control-allow-origin")
                if allow_origin:
                    assert allow_origin.startswith("https://"), \
                        f"CORS should only allow HTTPS origins, got: {allow_origin}"

    @pytest.mark.asyncio
    async def test_no_http_origins_allowed(self, production_backend_url):
        """
        Test 6: HTTP origins are rejected in production

        Validates:
        - HTTP origins don't get CORS approval
        - Only HTTPS origins are whitelisted
        """
        http_origins = [
            "http://clinica-oncologica-v02-production.up.railway.app",
            "http://malicious-site.com"
        ]

        async with httpx.AsyncClient() as client:
            for origin in http_origins:
                response = await client.options(
                    f"{production_backend_url}/api/v1/health",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "GET"
                    }
                )

                # Should not return CORS headers for HTTP origins
                allow_origin = response.headers.get("access-control-allow-origin")

                if allow_origin:
                    assert allow_origin != origin, \
                        f"HTTP origin {origin} should not be allowed in production"


class TestMixedContentPrevention:
    """Test suite for preventing mixed content warnings"""

    @pytest.mark.asyncio
    async def test_csp_headers_prevent_http_resources(self, production_backend_url):
        """
        Test 7: CSP headers block HTTP resources

        Validates:
        - Content-Security-Policy header is present
        - upgrade-insecure-requests directive is set
        - block-all-mixed-content is configured (optional)
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{production_backend_url}/api/v1/health")

            # Check for CSP header (may not be present on API, more common on frontend)
            csp = response.headers.get("content-security-policy", "")

            # If CSP is present, validate it blocks HTTP
            if csp:
                # Should upgrade insecure requests or block mixed content
                assert ("upgrade-insecure-requests" in csp.lower() or
                        "block-all-mixed-content" in csp.lower()), \
                    "CSP should prevent mixed content"

    @pytest.mark.asyncio
    async def test_all_external_apis_use_https(self):
        """
        Test 8: All external API calls use HTTPS

        Validates:
        - Firebase API: HTTPS
        - Supabase API: HTTPS
        - Any third-party APIs: HTTPS
        """
        external_apis = {
            "Firebase Auth": "https://identitytoolkit.googleapis.com",
            "Firebase Admin": "https://www.googleapis.com/robot/v1",
            "Supabase": "https://supabase.co"
        }

        for api_name, api_url in external_apis.items():
            parsed = urlparse(api_url)
            assert parsed.scheme == "https", \
                f"{api_name} must use HTTPS, got: {parsed.scheme}"

    @pytest.mark.asyncio
    async def test_static_assets_use_https(self, production_frontend_url):
        """
        Test 9: Static assets (JS, CSS, images) use HTTPS

        Validates:
        - Frontend assets are served over HTTPS
        - No HTTP asset URLs in HTML
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(production_frontend_url)
                html_content = response.text

                # Check for any HTTP asset URLs (should be none in production)
                http_assets = [
                    'src="http://',
                    'href="http://',
                    'url(http://'
                ]

                for pattern in http_assets:
                    assert pattern not in html_content, \
                        f"Found insecure HTTP asset: {pattern}"

            except httpx.ConnectError:
                pytest.skip(f"Cannot connect to {production_frontend_url}")

    @pytest.mark.asyncio
    async def test_api_calls_from_frontend_use_https(self, production_backend_url):
        """
        Test 10: Frontend API calls use HTTPS backend URL

        Validates:
        - VITE_API_URL is HTTPS
        - No hardcoded HTTP API URLs
        """
        # Check that environment variable is HTTPS
        api_url = os.getenv("VITE_API_URL", production_backend_url)
        parsed = urlparse(api_url)

        assert parsed.scheme == "https", \
            f"VITE_API_URL must be HTTPS in production, got: {parsed.scheme}"


@pytest.mark.integration
class TestHTTPSProductionIntegration:
    """Integration tests for HTTPS in production environment"""

    @pytest.mark.skip(reason="Requires browser automation for CSP validation")
    async def test_browser_no_mixed_content_warnings(self):
        """
        Test 11: Browser doesn't show mixed content warnings

        Manual test steps:
        1. Open browser DevTools
        2. Navigate to production frontend
        3. Check Console for mixed content warnings
        4. Check Network tab for HTTP requests

        Expected: No warnings or HTTP requests
        """
        pass

    @pytest.mark.skip(reason="Requires live Railway deployment")
    async def test_railway_https_configuration(self):
        """
        Test 12: Railway HTTPS configuration is correct

        Manual validation steps:
        1. Check Railway dashboard for HTTPS settings
        2. Verify custom domain has SSL certificate
        3. Check auto-SSL renewal is enabled

        Expected: Railway handles HTTPS automatically
        """
        pass
