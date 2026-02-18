"""
Security Headers Middleware

This middleware adds essential security headers to all HTTP responses to protect
against common web vulnerabilities including:
- Clickjacking attacks (X-Frame-Options)
- MIME-type sniffing (X-Content-Type-Options)
- Man-in-the-middle attacks (Strict-Transport-Security)
- XSS attacks (X-XSS-Protection, Content-Security-Policy)
- Information leakage (Referrer-Policy)
"""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.

    This middleware implements OWASP recommended security headers to protect
    against common web vulnerabilities in production environments.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        frame_options: str = "DENY",
        content_type_options: str = "nosniff",
        xss_protection: str = "1; mode=block",
        referrer_policy: str = "strict-origin-when-cross-origin",
        csp_policy: str | None = None,
        permissions_policy: str | None = None,
    ):
        """
        Initialize the security headers middleware.

        Args:
            app: The ASGI application
            enable_hsts: Whether to enable HSTS header (only for HTTPS)
            hsts_max_age: HSTS max-age in seconds (default: 1 year)
            hsts_include_subdomains: Include subdomains in HSTS
            hsts_preload: Enable HSTS preload
            frame_options: X-Frame-Options value (DENY, SAMEORIGIN, or ALLOW-FROM)
            content_type_options: X-Content-Type-Options value
            xss_protection: X-XSS-Protection value
            referrer_policy: Referrer-Policy value
            csp_policy: Content-Security-Policy directives
            permissions_policy: Permissions-Policy directives
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.frame_options = frame_options
        self.content_type_options = content_type_options
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy
        self.csp_policy = csp_policy
        self.permissions_policy = permissions_policy

    def _build_hsts_header(self) -> str:
        """Build the Strict-Transport-Security header value."""
        hsts_parts = [f"max-age={self.hsts_max_age}"]

        if self.hsts_include_subdomains:
            hsts_parts.append("includeSubDomains")

        if self.hsts_preload:
            hsts_parts.append("preload")

        return "; ".join(hsts_parts)

    def _get_default_csp(self, nonce: str = None) -> str:
        """
        Get default Content-Security-Policy with CSP Level 3 nonce support.

        This CSP is designed for a typical FastAPI + React application:
        - Uses nonces instead of unsafe-inline/unsafe-eval (CSP Level 3)
        - strict-dynamic for modern browser compatibility
        - Allows same-origin resources by default
        - Prevents loading resources from arbitrary origins

        Args:
            nonce: Optional cryptographic nonce for this request

        Returns:
            CSP policy string with nonce if provided
        """
        if nonce:
            return (
                f"default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}' 'strict-dynamic' https://www.gstatic.com https://identitytoolkit.googleapis.com; "
                f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com; "
                f"img-src 'self' data: https:; "
                f"font-src 'self' data: https://fonts.gstatic.com; "
                # SECURITY: Using specific Railway domains instead of wildcards
                # Update these if your Railway app domain changes
                f"connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com wss://backend-hormonia-production.up.railway.app https://backend-hormonia-production.up.railway.app wss://frontend-clinica-production.up.railway.app https://frontend-clinica-production.up.railway.app https://clinica-api-217549452180.us-central1.run.app; "
                f"object-src 'none'; "
                f"base-uri 'self'; "
                f"form-action 'self'; "
                f"frame-ancestors 'none'; "
                f"block-all-mixed-content; "
                f"upgrade-insecure-requests"
            )
        else:
            # Fallback without nonce (less secure, for backwards compatibility)
            # SECURITY: Using specific Railway domains instead of wildcards
            return (
                "default-src 'self'; "
                "script-src 'self' https://www.gstatic.com https://identitytoolkit.googleapis.com; "
                "style-src 'self' https://fonts.googleapis.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com "
                "wss://backend-hormonia-production.up.railway.app https://backend-hormonia-production.up.railway.app "
                "wss://frontend-clinica-production.up.railway.app https://frontend-clinica-production.up.railway.app https://clinica-api-217549452180.us-central1.run.app; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'"
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and add security headers to the response.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            The response with security headers added
        """
        response = await call_next(request)

        # X-Frame-Options: Prevents clickjacking attacks
        response.headers["X-Frame-Options"] = self.frame_options

        # X-Content-Type-Options: Prevents MIME-type sniffing
        response.headers["X-Content-Type-Options"] = self.content_type_options

        # X-XSS-Protection: Legacy XSS protection (for older browsers)
        response.headers["X-XSS-Protection"] = self.xss_protection

        # Referrer-Policy: Controls referrer information
        response.headers["Referrer-Policy"] = self.referrer_policy

        # Strict-Transport-Security: Forces HTTPS connections
        # Only set if HSTS is enabled and the request is over HTTPS
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = self._build_hsts_header()

        # Content-Security-Policy: Prevents XSS and injection attacks.
        # A nonce may be set upstream in request.state by CSP-aware handlers.
        nonce = getattr(request.state, "csp_nonce", None)
        csp = self.csp_policy if self.csp_policy else self._get_default_csp(nonce)

        # Respect an existing CSP header when one was already set upstream.
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = csp

        # Permissions-Policy: Controls browser features
        if self.permissions_policy:
            response.headers["Permissions-Policy"] = self.permissions_policy

        return response


def create_production_security_middleware(
    app: ASGIApp,
    *,
    custom_csp: str | None = None,
) -> SecurityHeadersMiddleware:
    """
    Create a security headers middleware with production-ready defaults.

    This factory function creates middleware configured with security headers
    appropriate for a production medical application handling sensitive data.

    Args:
        app: The ASGI application
        custom_csp: Optional custom Content-Security-Policy

    Returns:
        Configured SecurityHeadersMiddleware instance
    """
    return SecurityHeadersMiddleware(
        app,
        enable_hsts=True,
        hsts_max_age=31536000,  # 1 year
        hsts_include_subdomains=True,
        hsts_preload=False,  # Only enable after testing
        frame_options="DENY",
        content_type_options="nosniff",
        xss_protection="1; mode=block",
        referrer_policy="strict-origin-when-cross-origin",
        csp_policy=custom_csp,
        permissions_policy=(
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        ),
    )
