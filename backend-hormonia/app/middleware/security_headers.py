"""
Security Headers Middleware.

Implements OWASP security headers to protect against common web vulnerabilities.
"""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.

    Implements OWASP recommended security headers:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filter
    - Strict-Transport-Security: Enforces HTTPS
    - Content-Security-Policy: Controls resource loading
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    """

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        enable_csp: bool = True,
        csp_policy: str = "default-src 'self'",
        enable_frame_options: bool = True,
        frame_options: str = "DENY"
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.enable_csp = enable_csp
        self.csp_policy = csp_policy
        self.enable_frame_options = enable_frame_options
        self.frame_options = frame_options

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # X-Content-Type-Options: Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options: Prevent clickjacking
        if self.enable_frame_options:
            response.headers["X-Frame-Options"] = self.frame_options

        # X-XSS-Protection: Enable XSS filter (legacy, CSP is preferred)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Strict-Transport-Security: Enforce HTTPS
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = f"max-age={self.hsts_max_age}; includeSubDomains"

        # Content-Security-Policy: Control resource loading
        if self.enable_csp:
            response.headers["Content-Security-Policy"] = self.csp_policy

        # Referrer-Policy: Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: Control browser features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Remove server header to avoid information disclosure
        if "server" in response.headers:
            del response.headers["server"]

        # Add custom header for security versioning
        response.headers["X-Security-Headers-Version"] = "1.0"

        return response


class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add rate limit information headers.

    Provides transparency about rate limiting to clients.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add rate limit headers to response."""
        response = await call_next(request)

        # Add rate limit headers if available from rate limiter
        if hasattr(request.state, "rate_limit_info"):
            limit_info = request.state.rate_limit_info

            response.headers["X-RateLimit-Limit"] = str(limit_info.get("limit", ""))
            response.headers["X-RateLimit-Remaining"] = str(limit_info.get("remaining", ""))
            response.headers["X-RateLimit-Reset"] = str(limit_info.get("reset", ""))

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add unique request ID for tracing.

    Adds X-Request-ID header for request tracing and correlation.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to response."""
        import uuid

        # Generate or use existing request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Store in request state for access in endpoints
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add to response
        response.headers["X-Request-ID"] = request_id

        return response


def setup_security_middleware(app: ASGIApp, config: dict = None) -> None:
    """
    Setup all security middleware.

    Args:
        app: FastAPI application
        config: Configuration dictionary for middleware
    """
    config = config or {}

    # Request ID middleware (first to ensure all requests have ID)
    app.add_middleware(RequestIDMiddleware)

    # Security headers middleware
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=config.get("enable_hsts", True),
        hsts_max_age=config.get("hsts_max_age", 31536000),
        enable_csp=config.get("enable_csp", True),
        csp_policy=config.get("csp_policy", "default-src 'self'"),
        enable_frame_options=config.get("enable_frame_options", True),
        frame_options=config.get("frame_options", "DENY")
    )

    # Rate limit headers middleware
    app.add_middleware(RateLimitHeadersMiddleware)

    logger.info("Security middleware configured successfully")