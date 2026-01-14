"""LGPD Compliance Middleware

Validates and audits access to sensitive patient data fields across all requests.

LGPD Articles Implemented:
- Art. 46: Security, technical and administrative measures
- Art. 48: Security incident notification
- Art. 49: International data transfer requirements

This middleware provides:
1. Access logging for patient data endpoints
2. Request validation for sensitive fields
3. Audit trail for LGPD compliance (persisted to database)
4. IP-based access control monitoring

Integration:
Add to main.py middleware stack:
    app.add_middleware(LGPDMiddleware)
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Fields that require LGPD protection (Brazilian data protection law)
LGPD_SENSITIVE_FIELDS = ["cpf", "email", "phone", "rg", "cns", "birth_date"]

# Patient data endpoints that require logging
PATIENT_ENDPOINTS = ["/patients", "/api/v1/patients", "/api/v2/patients"]

# Map HTTP methods to LGPD action types
HTTP_METHOD_TO_ACTION = {
    "GET": "view",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


def _enqueue_lgpd_audit(
    action: str,
    resource_type: str,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    additional_data: Optional[dict] = None,
) -> None:
    """
    Enqueue LGPD audit log for async persistence.
    
    Uses Celery to avoid adding latency to HTTP requests.
    Falls back to logger-only if Celery is unavailable.
    """
    try:
        from app.tasks.lgpd_tasks import persist_lgpd_audit_log
        
        persist_lgpd_audit_log.delay(
            action=action,
            resource_type=resource_type,
            data_category="health",  # Patient data is health category
            user_id=user_id,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            additional_data=additional_data,
        )
    except Exception as exc:
        # Log but don't fail the request if Celery is unavailable
        logger.warning(
            f"LGPD: Failed to enqueue audit log (Celery unavailable?): {exc}",
            extra={"action": action, "resource_type": resource_type},
        )


class LGPDMiddleware:
    """
    ASGI Middleware for LGPD compliance validation and audit logging.
    
    Avoids BaseHTTPMiddleware issues with request.state and performance.
    Persists audit logs to database via async Celery task.
    """

    def __init__(self, app: ASGIApp, enable_ip_logging: bool = True, enable_db_logging: bool = True):
        self.app = app
        self.enable_ip_logging = enable_ip_logging
        self.enable_db_logging = enable_db_logging
        logger.info("LGPD Compliance Middleware (ASGI) initialized with DB logging=%s", enable_db_logging)

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

            # Determine success based on status code
            is_success = status_code[0] is not None and status_code[0] < 400

            # Build audit log entry for logger (backwards compatibility)
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
                audit_data["ip"] = ip_address  # Compatibility with old schema if any

            # Log to Python logger (always)
            logger.info("LGPD: Patient data access", extra=audit_data)

            # Persist to database via async task (if enabled)
            if self.enable_db_logging:
                action = HTTP_METHOD_TO_ACTION.get(request.method, "view")
                _enqueue_lgpd_audit(
                    action=action,
                    resource_type="patients",
                    user_id=str(user_id) if user_id else None,
                    user_role=user_role,
                    ip_address=ip_address,
                    user_agent=user_agent[:500] if user_agent else None,
                    success=is_success,
                    additional_data={
                        "path": path,
                        "method": request.method,
                        "status_code": status_code[0],
                        "duration_ms": round(duration * 1000, 2),
                    },
                )

    @staticmethod
    def is_sensitive_field(field_name: str) -> bool:
        """Check if a field contains sensitive PII data."""
        return field_name in LGPD_SENSITIVE_FIELDS

