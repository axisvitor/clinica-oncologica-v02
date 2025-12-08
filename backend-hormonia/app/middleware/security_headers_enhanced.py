"""Enhanced security headers middleware.

This middleware adds comprehensive security headers to all HTTP responses
to protect against common web vulnerabilities.

Security Headers Implemented:
- X-Frame-Options: Prevent clickjacking
- X-Content-Type-Options: Prevent MIME sniffing
- X-XSS-Protection: Enable XSS filtering (legacy browsers)
- Referrer-Policy: Control referrer information
- Permissions-Policy: Disable unnecessary browser features
- Content-Security-Policy: Comprehensive CSP
- Strict-Transport-Security: Enforce HTTPS (production only)

References:
- OWASP Secure Headers Project
- Mozilla Observatory
- Security Headers (securityheaders.com)
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add comprehensive security headers to all responses.

    This middleware implements security best practices from OWASP
    and Mozilla to protect against various attack vectors.

    Attributes:
        enable_hsts: Whether to enable HSTS (production only)
        csp_nonce_enabled: Whether CSP nonce is enabled
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = False,
        csp_report_uri: str = None
    ):
        """Initialize security headers middleware.

        Args:
            app: FastAPI application instance
            enable_hsts: Enable HSTS header (only for production HTTPS)
            csp_report_uri: URI for CSP violation reports
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.csp_report_uri = csp_report_uri

        logger.info("SecurityHeadersMiddleware initialized")
        if enable_hsts:
            logger.info("HSTS enabled - ensure HTTPS is configured")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Add security headers to response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response with security headers added
        """
        response = await call_next(request)

        # Prevent clickjacking attacks
        # Deny: Never allow framing (most secure)
        # SAMEORIGIN: Allow same-origin framing
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        # Force browser to respect declared content-type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection (legacy browsers)
        # Modern browsers rely on CSP instead
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy - control referrer information leakage
        # strict-origin-when-cross-origin: Send full URL for same-origin,
        # only origin for cross-origin HTTPS, nothing for HTTP
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy - disable unnecessary browser features
        # Prevents unauthorized access to sensitive APIs
        permissions_directives = [
            "geolocation=()",      # No location access
            "microphone=()",       # No microphone access
            "camera=()",           # No camera access
            "payment=()",          # No payment API
            "usb=()",              # No USB access
            "accelerometer=()",    # No accelerometer
            "gyroscope=()",        # No gyroscope
            "magnetometer=()",     # No magnetometer
            "ambient-light-sensor=()",  # No ambient light sensor
            "autoplay=()",         # No autoplay
            "encrypted-media=()",  # No encrypted media
            "picture-in-picture=()",  # No PiP
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions_directives)

        # Content Security Policy (CSP)
        # Comprehensive policy to prevent XSS and data injection
        csp_directives = [
            "default-src 'self'",  # Default: same-origin only

            # Scripts: Allow self + inline (needed for some frameworks)
            # TODO: Use nonce or hash for inline scripts (more secure)
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",

            # Styles: Allow self + inline
            "style-src 'self' 'unsafe-inline'",

            # Images: Allow self, data URIs, and HTTPS
            "img-src 'self' data: https:",

            # Fonts: Allow self and data URIs
            "font-src 'self' data:",

            # AJAX/WebSocket connections
            "connect-src 'self' https://api.evolution.com.br wss://api.evolution.com.br",

            # Media (audio/video)
            "media-src 'self'",

            # Object/embed tags (disabled)
            "object-src 'none'",

            # Frames: Prevent framing
            "frame-ancestors 'none'",

            # Base tag: Prevent base tag injection
            "base-uri 'self'",

            # Forms: Only submit to self
            "form-action 'self'",

            # Upgrade insecure requests (HTTP -> HTTPS)
            "upgrade-insecure-requests",

            # Block all mixed content
            "block-all-mixed-content",
        ]

        # Add CSP reporting endpoint if configured
        if self.csp_report_uri:
            csp_directives.append(f"report-uri {self.csp_report_uri}")

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Strict Transport Security (HSTS)
        # Only enable in production with HTTPS
        # WARNING: Once enabled, browsers will refuse HTTP connections
        if self.enable_hsts:
            # max-age: 1 year (31536000 seconds)
            # includeSubDomains: Apply to all subdomains
            # preload: Submit to HSTS preload list
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Cross-Origin policies (additional hardening)
        # Cross-Origin-Opener-Policy: Isolate browsing context
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # Cross-Origin-Embedder-Policy: Prevent loading cross-origin resources
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        # Cross-Origin-Resource-Policy: Control resource sharing
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # Server header - hide version information
        # Security through obscurity (minor benefit)
        response.headers["Server"] = "Backend-Hormonia"

        return response


class CSPReportMiddleware(BaseHTTPMiddleware):
    """Handle CSP violation reports.

    This middleware logs CSP violations to help identify issues
    with the CSP policy or potential XSS attempts.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Log CSP violations.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response
        """
        if request.url.path == "/api/v2/csp-report":
            try:
                report = await request.json()
                logger.warning(
                    f"CSP Violation Report: {report}",
                    extra={
                        "csp_violation": report,
                        "client_ip": request.client.host
                    }
                )
            except Exception as e:
                logger.error(f"Failed to parse CSP report: {e}")

            # Return 204 No Content
            return Response(status_code=204)

        return await call_next(request)


def get_security_headers_score(headers: dict) -> dict:
    """Calculate security headers score.

    Useful for monitoring and validation.

    Args:
        headers: Response headers dict

    Returns:
        Dict with score and missing headers
    """
    required_headers = {
        "X-Frame-Options": 10,
        "X-Content-Type-Options": 10,
        "Content-Security-Policy": 20,
        "Referrer-Policy": 10,
        "Permissions-Policy": 15,
        "Strict-Transport-Security": 15,
        "X-XSS-Protection": 5,
        "Cross-Origin-Opener-Policy": 5,
        "Cross-Origin-Embedder-Policy": 5,
        "Cross-Origin-Resource-Policy": 5,
    }

    score = 0
    missing = []

    for header, points in required_headers.items():
        if header in headers:
            score += points
        else:
            missing.append(header)

    return {
        "score": score,
        "max_score": 100,
        "percentage": score,
        "grade": _get_grade(score),
        "missing_headers": missing
    }


def _get_grade(score: int) -> str:
    """Convert score to letter grade."""
    if score >= 95:
        return "A+"
    elif score >= 90:
        return "A"
    elif score >= 85:
        return "B+"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"
