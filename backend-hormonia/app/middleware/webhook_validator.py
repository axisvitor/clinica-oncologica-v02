"""
Webhook Signature Validation Middleware

This middleware enforces HMAC-SHA256 signature validation on all webhook endpoints
to prevent message spoofing and unauthorized webhook calls.

Security Features:
- HMAC-SHA256 signature verification
- Timestamp validation to prevent replay attacks
- Configurable signature header names
- Secure constant-time comparison
- Comprehensive logging and error reporting

Usage:
    from app.middleware.webhook_validator import WebhookValidatorMiddleware

    app.add_middleware(
        WebhookValidatorMiddleware,
        secret_key=settings.WHATSAPP_EVOLUTION_WEBHOOK_SECRET,
        max_timestamp_age=300  # 5 minutes
    )

Configuration:
    Set EVOLUTION_WEBHOOK_SECRET in your environment variables to enable validation.
    Generate a secure secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'

Author: Hormonia Backend Team
Created: 2025-10-09
"""

import hmac
import hashlib
import logging
import time
from typing import Optional, Callable, Awaitable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class WebhookValidatorMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate webhook signatures using HMAC-SHA256.

    This middleware protects webhook endpoints from:
    - Unauthorized webhook calls
    - Message spoofing and tampering
    - Replay attacks (with timestamp validation)

    Security Model:
    1. Webhook sender includes HMAC signature in X-Webhook-Signature header
    2. Signature is computed as: HMAC-SHA256(secret_key, request_body + timestamp)
    3. Middleware recomputes signature and compares using constant-time comparison
    4. Timestamp is validated to prevent replay attacks

    Attributes:
        secret_key: Secret key for HMAC signature generation (from config)
        max_timestamp_age: Maximum age of webhook timestamp in seconds (default: 300)
        signature_header: HTTP header name for signature (default: X-Webhook-Signature)
        timestamp_header: HTTP header name for timestamp (default: X-Webhook-Timestamp)
        webhook_paths: List of paths that require signature validation
        enabled: Whether validation is enabled (requires secret_key)
    """

    def __init__(
        self,
        app: ASGIApp,
        secret_key: Optional[str] = None,
        max_timestamp_age: int = 300,
        signature_header: str = "X-Webhook-Signature",
        timestamp_header: str = "X-Webhook-Timestamp",
        webhook_paths: Optional[list[str]] = None,
    ):
        """
        Initialize webhook validator middleware.

        Args:
            app: ASGI application
            secret_key: Secret key for HMAC validation (if None, validation is disabled)
            max_timestamp_age: Maximum age of timestamp in seconds (default: 300 = 5 minutes)
            signature_header: Header name for signature (default: X-Webhook-Signature)
            timestamp_header: Header name for timestamp (default: X-Webhook-Timestamp)
            webhook_paths: List of URL paths to validate (default: ["/webhooks/"])
        """
        super().__init__(app)
        self.secret_key = secret_key
        self.max_timestamp_age = max_timestamp_age
        self.signature_header = signature_header.lower()
        self.timestamp_header = timestamp_header.lower()
        self.webhook_paths = webhook_paths or ["/webhooks/"]

        # Get environment from settings
        from app.config import settings
        environment = getattr(settings, 'APP_ENVIRONMENT', 'production')
        is_production = environment.lower() in ('production', 'prod')

        if not secret_key:
            if is_production:
                # FAIL-CLOSED in production - webhook validation is mandatory
                raise ValueError(
                    "CRITICAL: EVOLUTION_WEBHOOK_SECRET must be set in production. "
                    "Webhook validation cannot be disabled in production environment."
                )
            else:
                logger.warning(
                    "Webhook signature validation DISABLED in %s environment. "
                    "This is acceptable for development/testing only.",
                    environment
                )
                self.enabled = False
        else:
            self.enabled = True
            logger.info(
                "Webhook HMAC validation enabled "
                "(max_age=%ds, paths=%s)",
                max_timestamp_age,
                self.webhook_paths
            )

    def _is_webhook_path(self, path: str) -> bool:
        """Check if path requires webhook validation."""
        return any(path.startswith(webhook_path) for webhook_path in self.webhook_paths)

    def _compute_signature(self, body: bytes, timestamp: str) -> str:
        """
        Compute HMAC-SHA256 signature for webhook payload.

        Args:
            body: Raw request body bytes
            timestamp: Webhook timestamp string

        Returns:
            Hex-encoded HMAC signature

        Security:
            Uses HMAC-SHA256 with secret key to prevent tampering.
            Includes timestamp to prevent replay attacks.
        """
        message = body + timestamp.encode("utf-8")
        signature = hmac.new(self.secret_key.encode("utf-8"), message, hashlib.sha256)
        return signature.hexdigest()

    def _validate_timestamp(self, timestamp_str: str) -> bool:
        """
        Validate webhook timestamp to prevent replay attacks.

        Args:
            timestamp_str: Unix timestamp string

        Returns:
            True if timestamp is valid and within max_timestamp_age

        Security:
            Prevents replay attacks by rejecting old webhooks.
            Rejects future timestamps to prevent time manipulation.
        """
        try:
            webhook_timestamp = float(timestamp_str)
            current_timestamp = time.time()

            # Calculate age
            age = current_timestamp - webhook_timestamp

            # Reject future timestamps (allow 60s clock skew)
            if age < -60:
                logger.warning(f"Webhook timestamp is in the future: {age}s")
                return False

            # Reject old timestamps
            if age > self.max_timestamp_age:
                logger.warning(
                    f"Webhook timestamp too old: {age}s > {self.max_timestamp_age}s"
                )
                return False

            return True

        except (ValueError, TypeError) as e:
            logger.error(f"Invalid webhook timestamp format: {timestamp_str} - {e}")
            return False

    def _verify_signature(
        self, provided_signature: str, computed_signature: str
    ) -> bool:
        """
        Verify webhook signature using constant-time comparison.

        Args:
            provided_signature: Signature from request header
            computed_signature: Signature computed from request body

        Returns:
            True if signatures match

        Security:
            Uses hmac.compare_digest for constant-time comparison
            to prevent timing attacks.
        """
        return hmac.compare_digest(provided_signature, computed_signature)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process request and validate webhook signature if applicable.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response from next handler or 401 Unauthorized

        Raises:
            HTTPException: 401 if signature validation fails
        """
        # Skip validation if disabled or not a webhook path
        if not self.enabled or not self._is_webhook_path(request.url.path):
            return await call_next(request)

        # Skip validation for non-POST requests (GET health checks, etc.)
        if request.method != "POST":
            return await call_next(request)

        try:
            # Get signature and timestamp from headers
            headers_dict = {k.lower(): v for k, v in request.headers.items()}
            provided_signature = headers_dict.get(self.signature_header)
            timestamp_str = headers_dict.get(self.timestamp_header)

            # Validate headers exist
            if not provided_signature:
                logger.error(
                    f"Missing webhook signature header: {self.signature_header}"
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": f"Missing required header: {self.signature_header}"
                    },
                )

            if not timestamp_str:
                logger.error(
                    f"Missing webhook timestamp header: {self.timestamp_header}"
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": f"Missing required header: {self.timestamp_header}"
                    },
                )

            # Validate timestamp to prevent replay attacks
            if not self._validate_timestamp(timestamp_str):
                logger.error(f"Invalid or expired webhook timestamp: {timestamp_str}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired webhook timestamp"},
                )

            # Read request body
            body = await request.body()

            # Compute expected signature
            computed_signature = self._compute_signature(body, timestamp_str)

            # Verify signature using constant-time comparison
            if not self._verify_signature(provided_signature, computed_signature):
                logger.error(
                    f"Webhook signature validation failed for path: {request.url.path}"
                )
                return JSONResponse(
                    status_code=401, content={"detail": "Invalid webhook signature"}
                )

            # Signature valid - log success and continue
            logger.info(f"✅ Webhook signature validated for {request.url.path}")

            # Re-create request with body for next handler
            # (body was consumed during validation)
            async def receive():
                return {"type": "http.request", "body": body}

            request._receive = receive

            return await call_next(request)

        except Exception as e:
            logger.error(f"Error in webhook signature validation: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal error during webhook validation"},
            )


def generate_webhook_signature(body: bytes, timestamp: str, secret_key: str) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.

    This is a utility function for webhook senders (e.g., Evolution API)
    to generate the signature that should be sent in the X-Webhook-Signature header.

    Args:
        body: Raw request body bytes
        timestamp: Unix timestamp string
        secret_key: Secret key for HMAC

    Returns:
        Hex-encoded HMAC signature

    Example:
        >>> import time
        >>> body = b'{"event": "message.sent"}'
        >>> timestamp = str(int(time.time()))
        >>> signature = generate_webhook_signature(body, timestamp, "my-secret")
        >>> # Include in headers: {"X-Webhook-Signature": signature}
    """
    message = body + timestamp.encode("utf-8")
    signature = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256)
    return signature.hexdigest()


__all__ = [
    "WebhookValidatorMiddleware",
    "generate_webhook_signature",
]
