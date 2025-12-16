"""
CSRF Protection Middleware for FastAPI

This middleware provides comprehensive CSRF protection for the FastAPI backend.
It validates CSRF tokens on state-changing requests (POST, PUT, DELETE, PATCH)
and exempts safe methods (GET, HEAD, OPTIONS).

Features:
- Secure token generation using secrets module and HMAC-SHA256
- Token validation with expiration checking
- Configurable exempted routes
- Compatible with existing Firebase authentication
- Production-ready with proper logging and error handling

Security Implementation:
- Uses HMAC-SHA256 for token signing
- Tokens include timestamp for expiration validation
- Constant-time comparison to prevent timing attacks
- Tokens transmitted via X-CSRF-Token header
- No cookie dependency for better cross-domain support
"""

import hmac
import hashlib
import secrets
import time
import logging
from typing import Callable, List, Optional, Set
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


logger = logging.getLogger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection Middleware for FastAPI.

    This middleware validates CSRF tokens on state-changing HTTP methods
    (POST, PUT, DELETE, PATCH) to prevent Cross-Site Request Forgery attacks.

    Safe methods (GET, HEAD, OPTIONS) are exempted from CSRF validation as they
    should not have side effects per HTTP specifications.

    Token Format:
        The CSRF token is a base64-encoded string containing:
        - timestamp: Token generation time
        - random_data: 32 bytes of random data
        - signature: HMAC-SHA256 signature of timestamp:random_data

    Usage:
        app.add_middleware(
            CSRFMiddleware,
            secret_key=settings.SECURITY_CSRF_SECRET_KEY,
            token_expiry=3600,
            exempt_paths=["/api/v2/auth/csrf-token", "/health", "/docs"]
        )
    """

    # HTTP methods that require CSRF protection
    PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    # HTTP methods that are safe (no side effects)
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    def __init__(
        self,
        app: ASGIApp,
        secret_key: str,
        token_expiry: int = 3600,
        exempt_paths: Optional[List[str]] = None,
        header_name: str = "X-CSRF-Token",
    ):
        """
        Initialize CSRF middleware.

        Args:
            app: The ASGI application
            secret_key: Secret key for HMAC signing (should be from settings)
            token_expiry: Token expiration time in seconds (default: 1 hour)
            exempt_paths: List of path prefixes to exempt from CSRF protection
            header_name: Name of the header containing CSRF token
        """
        super().__init__(app)

        if not secret_key:
            raise ValueError("CSRF_SECRET_KEY is required for CSRF protection")

        self.secret_key = secret_key.encode('utf-8')
        self.token_expiry = token_expiry
        self.header_name = header_name

        # Convert exempt paths to a set for O(1) lookup
        self.exempt_paths: Set[str] = set(exempt_paths or [])

        # Add default exempted paths
        self.exempt_paths.update([
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/v2/auth/csrf-token",
        ])

        logger.info(
            f"CSRF middleware initialized with {len(self.exempt_paths)} exempt paths",
            extra={"exempt_paths": list(self.exempt_paths)}
        )

    def _is_path_exempt(self, path: str) -> bool:
        """
        Check if a path is exempt from CSRF protection.

        Args:
            path: Request path

        Returns:
            bool: True if path is exempt, False otherwise
        """
        # Check exact matches first
        if path in self.exempt_paths:
            return True

        # Check prefix matches
        for exempt_path in self.exempt_paths:
            if path.startswith(exempt_path):
                return True

        return False

    def _generate_token(self) -> str:
        """
        Generate a new CSRF token.

        Token format: base64(timestamp:random_data:hmac_signature)

        Returns:
            str: Base64-encoded CSRF token
        """
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)  # 64 character hex string (32 bytes)

        # Create payload
        payload = f"{timestamp}:{random_data}"

        # Create HMAC signature
        signature = hmac.new(
            self.secret_key,
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Combine payload and signature
        token = f"{payload}:{signature}"

        # Base64 encode for safe transport
        import base64
        encoded = base64.urlsafe_b64encode(token.encode('utf-8')).decode('utf-8')
        return encoded.rstrip('=')

    def _validate_token(self, token: str) -> bool:
        """
        Validate a CSRF token.

        Checks:
        1. Token format is correct
        2. Token has not expired
        3. HMAC signature is valid

        Args:
            token: CSRF token to validate

        Returns:
            bool: True if token is valid, False otherwise
        """
        try:
            # Base64 decode
            import base64
            padding = '=' * (-len(token) % 4)
            decoded = base64.urlsafe_b64decode((token + padding).encode('utf-8')).decode('utf-8')

            # Split components
            parts = decoded.split(':')
            if len(parts) != 3:
                logger.warning("CSRF token has invalid format (expected 3 parts)")
                return False

            timestamp_str, random_data, provided_signature = parts

            # Check expiration
            timestamp = int(timestamp_str)
            current_time = int(time.time())

            if current_time - timestamp > self.token_expiry:
                logger.warning(
                    f"CSRF token has expired (age: {current_time - timestamp}s, max: {self.token_expiry}s)"
                )
                return False

            # Recreate payload and verify signature
            payload = f"{timestamp_str}:{random_data}"
            expected_signature = hmac.new(
                self.secret_key,
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # Constant-time comparison to prevent timing attacks
            if not hmac.compare_digest(expected_signature, provided_signature):
                logger.warning("CSRF token signature is invalid")
                return False

            logger.debug("CSRF token validation successful")
            return True

        except Exception as e:
            logger.warning(f"CSRF token validation error: {type(e).__name__}: {e}")
            return False

    def _get_token_from_request(self, request: Request) -> Optional[str]:
        """
        Extract CSRF token from request headers.

        Supports multiple header name variations:
        - X-CSRF-Token (primary)
        - X-CSRFToken (alternative)
        - X-XSRF-Token (Angular convention)

        Args:
            request: FastAPI request object

        Returns:
            Optional[str]: CSRF token if found, None otherwise
        """
        # Check primary header
        token = request.headers.get(self.header_name)
        if token:
            return token

        # Check alternative header names
        for header in ["X-CSRFToken", "X-XSRF-Token"]:
            token = request.headers.get(header)
            if token:
                return token

        return None

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process the request and validate CSRF token if required.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response: The response from the route handler or error response
        """
        # Skip CSRF validation for safe methods
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        # Skip CSRF validation for exempt paths
        if self._is_path_exempt(request.url.path):
            logger.debug(f"Path {request.url.path} is exempt from CSRF protection")
            return await call_next(request)

        # For protected methods, validate CSRF token
        if request.method in self.PROTECTED_METHODS:
            token = self._get_token_from_request(request)

            if not token:
                logger.warning(
                    f"CSRF token missing for {request.method} {request.url.path}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "client_ip": request.client.host if request.client else "unknown",
                        "user_agent": request.headers.get("user-agent", "unknown")
                    }
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "csrf_token_missing",
                        "message": "CSRF token is required for this request. Please include X-CSRF-Token header.",
                        "timestamp": time.time()
                    }
                )

            if not self._validate_token(token):
                logger.warning(
                    f"CSRF token validation failed for {request.method} {request.url.path}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "client_ip": request.client.host if request.client else "unknown",
                        "user_agent": request.headers.get("user-agent", "unknown"),
                        "token_present": bool(token)
                    }
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "csrf_token_invalid",
                        "message": "CSRF token validation failed. Please refresh and try again.",
                        "timestamp": time.time()
                    }
                )

            logger.debug(f"CSRF validation successful for {request.method} {request.url.path}")

        # Continue to the next middleware or route handler
        return await call_next(request)


def create_csrf_middleware(
    app: ASGIApp,
    secret_key: str,
    token_expiry: int = 3600,
    exempt_paths: Optional[List[str]] = None,
) -> CSRFMiddleware:
    """
    Factory function to create CSRF middleware with configuration.

    This is a convenience function for creating the middleware with
    common configuration options.

    Args:
        app: The ASGI application
        secret_key: Secret key for HMAC signing
        token_expiry: Token expiration time in seconds (default: 1 hour)
        exempt_paths: List of path prefixes to exempt from CSRF protection

    Returns:
        CSRFMiddleware: Configured CSRF middleware instance

    Example:
        middleware = create_csrf_middleware(
            app,
            secret_key=settings.SECURITY_CSRF_SECRET_KEY,
            token_expiry=3600,
            exempt_paths=["/webhooks/", "/api/public/"]
        )
    """
    return CSRFMiddleware(
        app,
        secret_key=secret_key,
        token_expiry=token_expiry,
        exempt_paths=exempt_paths,
    )
