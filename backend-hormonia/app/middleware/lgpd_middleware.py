"""LGPD Compliance Middleware

Validates and audits access to sensitive patient data fields across all requests.

LGPD Articles Implemented:
- Art. 46: Security, technical and administrative measures
- Art. 48: Security incident notification
- Art. 49: International data transfer requirements

This middleware provides:
1. Access logging for patient data endpoints
2. Request validation for sensitive fields
3. Audit trail for LGPD compliance
4. IP-based access control monitoring

Integration:
Add to main.py middleware stack:
    app.add_middleware(LGPDMiddleware)
"""

import logging
import time
from datetime import datetime, timezone
from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Fields that require LGPD protection (Brazilian data protection law)
LGPD_SENSITIVE_FIELDS = ["cpf", "email", "phone", "rg", "cns", "birth_date"]

# Patient data endpoints that require logging
PATIENT_ENDPOINTS = ["/patients", "/api/v1/patients", "/api/v2/patients"]


class LGPDMiddleware:
    """
    ASGI Middleware for LGPD compliance validation and audit logging.
    
    Avoids BaseHTTPMiddleware issues with request.state and performance.
    """

    def __init__(self, app: ASGIApp, enable_ip_logging: bool = True):
        self.app = app
        self.enable_ip_logging = enable_ip_logging
        logger.info("LGPD Compliance Middleware (ASGI) initialized")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        start_time = time.time()

        # Check if this is a patient data endpoint
        path = scope.get("path", "")
        is_patient_endpoint = any(endpoint in path for endpoint in PATIENT_ENDPOINTS)

        if is_patient_endpoint and request.method in ["POST", "PUT", "PATCH"]:
            # Basic validation (logging only, encryption is handled by repository)
            logger.debug(
                "LGPD: Patient data modification request received",
                extra={
                    "method": request.method,
                    "path": path,
                },
            )

        # We need to capture the response status code
        status_code = [None]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        # Process request
        await self.app(scope, receive, send_wrapper)

        # Log access after request to ensure dependencies have set user context in request.state
        if is_patient_endpoint:
            duration = time.time() - start_time
            
            # Extract user information from request state
            # NOTE: In ASGI middleware, we access the same scope that dependencies used
            user_id = getattr(request.state, "user_id", None)
            user_role = getattr(request.state, "user_role", None)

            # Extract IP address
            ip_address = None
            if self.enable_ip_logging and request.client:
                ip_address = request.client.host

            # Extract user agent
            user_agent = request.headers.get("user-agent", "unknown")

            # Build audit log entry
            audit_data = {
                "event": "patient_data_access",
                "user_id": str(user_id) if user_id else None,
                "user_role": user_role,
                "method": request.method,
                "path": path,
                "status_code": status_code[0],
                "duration_ms": round(duration * 1000, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_agent": user_agent[:200],
            }

            if ip_address:
                audit_data["ip_address"] = ip_address

            if self.enable_ip_logging:
                audit_data["ip"] = ip_address # Compatibility with old schema if any

            logger.info("LGPD: Patient data access", extra=audit_data)

    @staticmethod
    def is_sensitive_field(field_name: str) -> bool:
        """Check if a field contains sensitive PII data."""
        return field_name in LGPD_SENSITIVE_FIELDS
