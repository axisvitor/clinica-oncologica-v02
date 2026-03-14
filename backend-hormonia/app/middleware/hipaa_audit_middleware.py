"""
HIPAA Audit Middleware - Phase 3 Sprint 1

This middleware automatically captures and logs all HTTP requests for HIPAA compliance:
- Captures user context (ID, email, role, session)
- Captures network context (IP, user agent, device fingerprint)
- Captures request details (method, endpoint, query params, body hash)
- Detects PHI endpoint access
- Detects data modification operations
- Logs events asynchronously for performance

HIPAA Compliance:
- § 164.312(b) - Audit Controls (comprehensive event logging)
- § 164.308(a)(1)(ii)(D) - Audit Review (provides data for review)

Usage:
    from fastapi import FastAPI
    from app.middleware.hipaa_audit_middleware import HIPAAAuditMiddleware

    app = FastAPI()
    app.add_middleware(HIPAAAuditMiddleware)
"""

import time
import hashlib
from typing import Optional
import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditEventType
from app.services.audit.audit_service import AuditService, AuditEventContext


class HIPAAAuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic HIPAA-compliant audit logging of all HTTP requests.
    """

    # PHI endpoint patterns (regex patterns for detecting PHI access)
    PHI_PATTERNS = {
        "PATIENT": [
            r"/api/v2/patients/[^/]+$",  # Single patient view
            r"/api/v2/patients$",  # Patient list
            r"/api/v2/patients/search",  # Patient search
        ],
        "MEDICATION": [
            r"/api/v2/medications/[^/]+$",
            r"/api/v2/patients/[^/]+/medications",
        ],
        "LAB_RESULT": [
            r"/api/v2/lab-results/[^/]+$",
            r"/api/v2/patients/[^/]+/lab-results",
        ],
        "DIAGNOSIS": [
            r"/api/v2/diagnoses/[^/]+$",
            r"/api/v2/patients/[^/]+/diagnoses",
        ],
        "QUIZ_RESPONSE": [
            r"/api/v2/quiz-responses/[^/]+$",
            r"/api/v2/patients/[^/]+/quiz-responses",
        ],
        "APPOINTMENT": [
            r"/api/v2/appointments/[^/]+$",
            r"/api/v2/patients/[^/]+/appointments",
        ],
    }

    # Endpoints that should NOT be logged (health checks, static assets, etc.)
    EXCLUDED_PATHS = [
        "/health",
        "/docs",
        "/openapi.json",
        "/static",
        "/favicon.ico",
        "/metrics",  # Prometheus metrics
    ]

    # Authentication endpoints
    AUTH_PATTERNS = [
        r"/api/v2/auth/login",
        r"/api/v2/auth/logout",
        r"/api/v2/auth/refresh",
        r"/api/v2/auth/reset-password",
    ]

    def __init__(self, app: ASGIApp):
        """Initialize middleware."""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """
        Process the request and log audit events.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Start timing
        start_time = time.time()

        # Check if path should be excluded
        if self._should_exclude(request.url.path):
            return await call_next(request)

        # Extract context from request
        context = await self._extract_context(request)

        # Process request
        response = await call_next(request)

        # Refresh identity/session context after downstream auth dependencies run.
        self._apply_request_state_identity(request, context)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        context.duration_ms = duration_ms
        context.http_status_code = response.status_code

        # Determine status
        context.status = self._determine_status(response.status_code)

        # Detect event type and category
        event_type, event_category = self._detect_event_type(request, context)

        # Log audit event (async, non-blocking)
        try:
            # Get database session from request state
            if hasattr(request.state, "db"):
                db: AsyncSession = request.state.db
                audit_service = AuditService(db)

                await audit_service.log_event(
                    event_type=event_type,
                    event_category=event_category,
                    context=context,
                )
        except Exception as e:
            # Don't fail the request if audit logging fails
            # Log error for monitoring
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                "HIPAA audit logging failed",
                extra={
                    "error": str(e),
                    "endpoint": context.endpoint
                    if hasattr(context, "endpoint")
                    else None,
                    "http_method": context.http_method
                    if hasattr(context, "http_method")
                    else None,
                    "user_id": context.user_id if hasattr(context, "user_id") else None,
                },
            )

        return response

    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded from audit logging."""
        for excluded in self.EXCLUDED_PATHS:
            if path.startswith(excluded):
                return True
        return False

    async def _extract_context(self, request: Request) -> AuditEventContext:
        """
        Extract audit context from HTTP request.

        Args:
            request: HTTP request

        Returns:
            AuditEventContext with extracted information
        """
        # User context (from request state if an upstream dependency already populated it)
        user_id = getattr(request.state, "user_id", None)
        user_email = getattr(request.state, "user_email", None)
        user_role = getattr(request.state, "user_role", None)

        # Session context
        session_token_hash = None

        # Hash bearer token if present (for non-cookie auth surfaces that still use it)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            session_token_hash = AuditService.hash_session_token(token)

        # Canonical runtime transport is cookie-backed session auth.
        session_id = getattr(request.state, "session_id", None) or request.cookies.get(
            "session_id"
        )

        # Device fingerprint (can be enhanced with client-side fingerprinting)
        device_fingerprint = self._calculate_device_fingerprint(request)

        # Network context
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent")

        # Request context
        http_method = request.method
        endpoint = str(request.url.path)
        query_params = dict(request.query_params) if request.query_params else None

        # Hash request body (if present) - don't store PHI
        request_body_hash = None
        if request.method in ["POST", "PUT", "PATCH"]:
            # Note: Reading body here might interfere with downstream handlers
            # In production, consider using a different approach or middleware ordering
            try:
                body = await request.body()
                if body:
                    request_body_hash = hashlib.sha256(body).hexdigest()
            except (RuntimeError, ConnectionError):
                pass  # Body already consumed by another middleware or connection error

        # Resource context (detect from URL)
        resource_type, resource_id = self._detect_resource(endpoint)

        # Operation context
        operation = self._determine_operation(http_method)

        # Build context
        context = AuditEventContext(
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            session_id=session_id,
            session_token_hash=session_token_hash,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent,
            http_method=http_method,
            endpoint=endpoint,
            query_params=query_params,
            request_body_hash=request_body_hash,
            resource_type=resource_type,
            resource_id=resource_id,
            operation=operation,
            description=f"{http_method} {endpoint}",
        )

        return context

    def _apply_request_state_identity(
        self, request: Request, context: AuditEventContext
    ) -> None:
        """Refresh canonical identity/session fields after downstream auth resolution."""
        for field_name in ("user_id", "user_email", "user_role", "session_id"):
            value = getattr(request.state, field_name, None)
            if value is None:
                continue
            if field_name == "user_id":
                value = AuditEventContext(user_id=value).user_id
            setattr(context, field_name, value)

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP address, handling proxies."""
        # Check for proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get first IP (client IP before proxies)
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client IP
        return request.client.host if request.client else None

    def _calculate_device_fingerprint(self, request: Request) -> Optional[str]:
        """Calculate a basic device fingerprint from request headers."""
        user_agent = request.headers.get("User-Agent", "")
        accept_language = request.headers.get("Accept-Language", "")
        accept_encoding = request.headers.get("Accept-Encoding", "")

        # Create fingerprint from stable headers
        fingerprint_data = f"{user_agent}|{accept_language}|{accept_encoding}"
        return hashlib.md5(fingerprint_data.encode()).hexdigest()

    def _detect_resource(self, endpoint: str) -> tuple[Optional[str], Optional[str]]:
        """
        Detect resource type and ID from endpoint.

        Args:
            endpoint: URL path

        Returns:
            Tuple of (resource_type, resource_id)
        """
        # Check each PHI pattern
        for resource_type, patterns in self.PHI_PATTERNS.items():
            for pattern in patterns:
                match = re.match(pattern, endpoint)
                if match:
                    # Try to extract resource ID (UUID pattern)
                    uuid_pattern = r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
                    id_match = re.search(uuid_pattern, endpoint)
                    resource_id = id_match.group(1) if id_match else None
                    return resource_type, resource_id

        return None, None

    def _determine_operation(self, http_method: str) -> str:
        """Map HTTP method to CRUD operation."""
        mapping = {
            "GET": "READ",
            "POST": "CREATE",
            "PUT": "UPDATE",
            "PATCH": "UPDATE",
            "DELETE": "DELETE",
        }
        return mapping.get(http_method, "UNKNOWN")

    def _determine_status(self, status_code: int) -> str:
        """Determine audit status from HTTP status code."""
        if 200 <= status_code < 300:
            return "SUCCESS"
        elif 400 <= status_code < 500:
            if status_code == 401 or status_code == 403:
                return "BLOCKED"
            return "FAILURE"
        elif 500 <= status_code < 600:
            return "ERROR"
        return "SUCCESS"

    def _detect_event_type(
        self, request: Request, context: AuditEventContext
    ) -> tuple[AuditEventType, str]:
        """
        Detect the appropriate event type and category.

        Args:
            request: HTTP request
            context: Audit event context

        Returns:
            Tuple of (event_type, event_category)
        """
        endpoint = context.endpoint
        operation = context.operation

        # Check for authentication endpoints
        for pattern in self.AUTH_PATTERNS:
            if re.match(pattern, endpoint):
                if "login" in endpoint:
                    event_type = (
                        AuditEventType.LOGIN_SUCCESS
                        if context.status == "SUCCESS"
                        else AuditEventType.LOGIN_FAILURE
                    )
                elif "logout" in endpoint:
                    event_type = AuditEventType.LOGOUT
                elif "refresh" in endpoint:
                    event_type = AuditEventType.TOKEN_REFRESH
                else:
                    event_type = AuditEventType.PASSWORD_RESET_REQUESTED
                return event_type, "AUTHENTICATION"

        # Check for PHI access (default for now, will be enhanced in Sprint 2)
        if context.resource_type:
            if operation == "READ":
                # For now, use generic event types (will add specific PHI events in Sprint 2)
                event_type = (
                    AuditEventType.ACCESS_DENIED
                    if context.status == "BLOCKED"
                    else AuditEventType.SUSPICIOUS_ACTIVITY
                )
                return event_type, "PHI_ACCESS"
            elif operation in ["CREATE", "UPDATE", "DELETE"]:
                # Data modification (will add specific events in Sprint 2)
                event_type = AuditEventType.SUSPICIOUS_ACTIVITY  # Placeholder
                return event_type, "DATA_MODIFICATION"

        # Default to system event
        return AuditEventType.SUSPICIOUS_ACTIVITY, "SYSTEM"
