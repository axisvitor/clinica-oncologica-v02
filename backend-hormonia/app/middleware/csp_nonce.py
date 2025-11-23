"""
CSP Nonce Middleware - Content Security Policy Level 3 Implementation

This middleware implements CSP Level 3 with cryptographic nonces to eliminate
CVSS 7.5 vulnerability by replacing unsafe-inline and unsafe-eval directives.

Features:
- Cryptographically secure nonce generation (16+ bytes)
- Nonce rotation per request
- strict-dynamic for backwards compatibility
- Report-URI for CSP violation monitoring
"""

import secrets
import hashlib
from typing import Callable, Optional
from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.datastructures import MutableHeaders

from app.utils.logging import get_logger

logger = get_logger(__name__)


class CSPNonceMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates cryptographic nonces for CSP Level 3.

    This middleware:
    1. Generates a unique nonce for each request (16+ bytes, base64url-encoded)
    2. Adds the nonce to request state for template injection
    3. Sets Content-Security-Policy header with nonce directives
    4. Uses strict-dynamic for forward compatibility
    5. Monitors and logs CSP violations
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        nonce_length: int = 16,
        enable_report_uri: bool = True,
        report_uri: Optional[str] = "/api/v2/csp-report",
        enable_upgrade_insecure: bool = True,
        allowed_script_domains: Optional[list[str]] = None,
        allowed_style_domains: Optional[list[str]] = None,
        allowed_connect_domains: Optional[list[str]] = None,
    ):
        """
        Initialize CSP nonce middleware.

        Args:
            app: The ASGI application
            nonce_length: Length of nonce in bytes (minimum 16)
            enable_report_uri: Enable CSP violation reporting
            report_uri: Endpoint for CSP violation reports
            enable_upgrade_insecure: Force upgrade of insecure requests
            allowed_script_domains: Whitelist of allowed script sources
            allowed_style_domains: Whitelist of allowed style sources
            allowed_connect_domains: Whitelist of allowed connect sources
        """
        super().__init__(app)

        if nonce_length < 16:
            raise ValueError("Nonce length must be at least 16 bytes for security")

        self.nonce_length = nonce_length
        self.enable_report_uri = enable_report_uri
        self.report_uri = report_uri
        self.enable_upgrade_insecure = enable_upgrade_insecure

        # Default allowed domains
        self.allowed_script_domains = allowed_script_domains or [
            "'self'",
            "https://www.gstatic.com",  # Firebase/Google services
            "https://identitytoolkit.googleapis.com",
            "https://securetoken.googleapis.com"
        ]

        self.allowed_style_domains = allowed_style_domains or [
            "'self'",
            "https://fonts.googleapis.com"
        ]

        self.allowed_connect_domains = allowed_connect_domains or [
            "'self'",
            "https://identitytoolkit.googleapis.com",
            "https://securetoken.googleapis.com",
            "wss://*.railway.app",
            "https://*.railway.app"
        ]

    def _generate_nonce(self) -> str:
        """
        Generate cryptographically secure nonce.

        Uses secrets.token_urlsafe for cryptographic randomness.
        Minimum 16 bytes ensures 128+ bits of entropy.

        Returns:
            Base64url-encoded nonce string (safe for URLs and HTML)
        """
        nonce = secrets.token_urlsafe(self.nonce_length)

        # Log nonce generation for security audit
        logger.debug(
            f"Generated CSP nonce",
            extra={
                "event_type": "csp_nonce_generated",
                "nonce_length": len(nonce),
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )

        return nonce

    def _build_csp_policy(self, nonce: str) -> str:
        """
        Build Content-Security-Policy header value with nonce.

        CSP Level 3 with strict-dynamic:
        - Nonces for inline scripts/styles
        - strict-dynamic allows dynamically added scripts
        - Fallback to domain whitelist for older browsers

        Args:
            nonce: The cryptographic nonce for this request

        Returns:
            Complete CSP policy string
        """
        # Build script-src directive with nonce and strict-dynamic
        script_src = [
            f"'nonce-{nonce}'",
            "'strict-dynamic'"
        ] + self.allowed_script_domains

        # Build style-src directive with nonce
        style_src = [
            f"'nonce-{nonce}'"
        ] + self.allowed_style_domains

        # Build complete CSP policy
        csp_directives = [
            f"default-src 'self'",
            f"script-src {' '.join(script_src)}",
            f"style-src {' '.join(style_src)}",
            f"img-src 'self' data: https:",
            f"font-src 'self' data: https://fonts.gstatic.com",
            f"connect-src {' '.join(self.allowed_connect_domains)}",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "block-all-mixed-content"
        ]

        # Add upgrade-insecure-requests if enabled
        if self.enable_upgrade_insecure:
            csp_directives.append("upgrade-insecure-requests")

        # Add report-uri if enabled
        if self.enable_report_uri and self.report_uri:
            csp_directives.append(f"report-uri {self.report_uri}")

        policy = "; ".join(csp_directives)

        logger.debug(
            f"Built CSP policy",
            extra={
                "event_type": "csp_policy_built",
                "policy_length": len(policy),
                "nonce_present": f"nonce-{nonce}" in policy,
                "strict_dynamic": "'strict-dynamic'" in policy
            }
        )

        return policy

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process request and inject CSP nonce.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response with CSP header and nonce
        """
        # Generate nonce for this request
        nonce = self._generate_nonce()

        # Store nonce in request state for template access
        request.state.csp_nonce = nonce

        # Also store in a meta tag value for client-side access
        request.state.csp_nonce_meta = nonce

        # Process request
        response = await call_next(request)

        # Build and set CSP header
        csp_policy = self._build_csp_policy(nonce)
        response.headers["Content-Security-Policy"] = csp_policy

        # Also set report-only header for monitoring (optional)
        # This allows testing without breaking functionality
        # response.headers["Content-Security-Policy-Report-Only"] = csp_policy

        # Add nonce to response headers for debugging (dev only)
        if request.app.state.debug:
            response.headers["X-CSP-Nonce"] = nonce

        logger.info(
            f"CSP nonce applied",
            extra={
                "event_type": "csp_applied",
                "path": request.url.path,
                "method": request.method,
                "nonce_length": len(nonce),
                "policy_length": len(csp_policy)
            }
        )

        return response


class CSPReportHandler:
    """
    Handler for CSP violation reports.

    Receives and processes CSP violation reports from browsers
    to monitor security issues and potential attacks.
    """

    def __init__(self):
        self.violations = []
        self.max_violations = 1000  # Keep last 1000 violations

    async def handle_report(self, request: Request) -> dict:
        """
        Process CSP violation report.

        Args:
            request: Request containing CSP violation report

        Returns:
            Acknowledgment response
        """
        try:
            report = await request.json()

            # Extract violation details
            csp_report = report.get("csp-report", {})

            violation = {
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "document_uri": csp_report.get("document-uri"),
                "violated_directive": csp_report.get("violated-directive"),
                "effective_directive": csp_report.get("effective-directive"),
                "original_policy": csp_report.get("original-policy"),
                "blocked_uri": csp_report.get("blocked-uri"),
                "status_code": csp_report.get("status-code"),
                "source_file": csp_report.get("source-file"),
                "line_number": csp_report.get("line-number"),
                "column_number": csp_report.get("column-number")
            }

            # Store violation
            self.violations.append(violation)

            # Keep only recent violations
            if len(self.violations) > self.max_violations:
                self.violations = self.violations[-self.max_violations:]

            # Log violation
            logger.warning(
                f"CSP violation: {violation['violated_directive']}",
                extra={
                    "event_type": "csp_violation",
                    **violation
                }
            )

            # Alert on suspicious patterns
            if self._is_suspicious(violation):
                logger.error(
                    f"Suspicious CSP violation detected",
                    extra={
                        "event_type": "csp_suspicious_violation",
                        "severity": "HIGH",
                        **violation
                    }
                )

            return {"status": "accepted", "violation_id": len(self.violations)}

        except Exception as e:
            logger.error(
                f"Failed to process CSP report: {str(e)}",
                exc_info=True
            )
            return {"status": "error", "message": str(e)}

    def _is_suspicious(self, violation: dict) -> bool:
        """
        Check if violation indicates potential attack.

        Args:
            violation: CSP violation details

        Returns:
            True if violation appears suspicious
        """
        suspicious_patterns = [
            "eval",
            "inline",
            "data:",
            "javascript:",
            "vbscript:",
            "blob:",
            "filesystem:"
        ]

        blocked_uri = violation.get("blocked_uri", "").lower()
        violated_directive = violation.get("violated_directive", "").lower()

        return any(
            pattern in blocked_uri or pattern in violated_directive
            for pattern in suspicious_patterns
        )

    def get_violations(
        self,
        limit: int = 100,
        severity: Optional[str] = None
    ) -> list[dict]:
        """
        Get recent CSP violations.

        Args:
            limit: Maximum number of violations to return
            severity: Filter by severity (optional)

        Returns:
            List of violation records
        """
        violations = self.violations[-limit:]

        if severity:
            violations = [
                v for v in violations
                if self._is_suspicious(v) == (severity == "HIGH")
            ]

        return violations


# Global CSP report handler instance
csp_report_handler = CSPReportHandler()


def create_csp_middleware(
    app: ASGIApp,
    **kwargs
) -> CSPNonceMiddleware:
    """
    Create CSP nonce middleware with production-ready defaults.

    Args:
        app: The ASGI application
        **kwargs: Additional middleware configuration

    Returns:
        Configured CSPNonceMiddleware instance
    """
    return CSPNonceMiddleware(
        app,
        nonce_length=16,  # 128-bit security
        enable_report_uri=True,
        enable_upgrade_insecure=True,
        **kwargs
    )
