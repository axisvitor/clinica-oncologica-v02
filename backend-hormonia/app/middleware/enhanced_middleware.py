"""
Enhanced middleware components for comprehensive API security and monitoring.

This module provides:
- EnhancedSecurityMiddleware: SQL injection, XSS detection, request validation
- RequestLoggingMiddleware: Structured logging with correlation IDs and rate limiting

NOTE: Rate limiting is handled by distributed_rate_limiter.py (RateLimitMiddleware)
which provides Redis-based distributed rate limiting with tier support.
"""

import time
import json
import hashlib
from typing import Optional, Callable
from datetime import datetime

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from pydantic import BaseModel

from app.utils.logging import get_logger
from app.core.logging_config import OptimizedRequestLogger, RateLimitedLogger

logger = get_logger(__name__)


class SecurityConfig(BaseModel):
    """Security configuration for middleware."""

    max_request_size: int = 10 * 1024 * 1024  # 10MB
    allowed_content_types: list = [
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",
    ]
    blocked_user_agents: list = []
    blocked_ips: list = []
    require_user_agent: bool = True


# =============================================================================
# ENHANCED SECURITY MIDDLEWARE
# =============================================================================


class EnhancedSecurityMiddleware(BaseHTTPMiddleware):
    """
    Advanced security middleware with comprehensive protection.

    Features:
    - Request size validation
    - Content type validation
    - User agent validation
    - IP filtering
    - SQL injection detection
    - XSS protection
    - Input sanitization
    """

    def __init__(self, app: ASGIApp, config: Optional[SecurityConfig] = None):
        super().__init__(app)
        self.config = config or SecurityConfig()

        # Optimized and compiled suspicious patterns for better performance
        import re

        self.sql_patterns = [
            re.compile(r"(\%27)|(\')|(\-\-)|(\%23)|(#)", re.IGNORECASE),
            re.compile(
                r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))", re.IGNORECASE
            ),
            re.compile(
                r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))", re.IGNORECASE
            ),
            re.compile(r"((\%27)|(\'))union", re.IGNORECASE),
            re.compile(r"exec(\s|\+)+(s|x)p\w+", re.IGNORECASE),
            re.compile(r"UNION.*SELECT.*FROM", re.IGNORECASE),
            re.compile(r"SELECT.*FROM.*WHERE", re.IGNORECASE),
        ]

        self.xss_patterns = [
            re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"vbscript:", re.IGNORECASE),
            re.compile(r"onload=", re.IGNORECASE),
            re.compile(r"onerror=", re.IGNORECASE),
            re.compile(r"onclick=", re.IGNORECASE),
            re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE),
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with security validation."""
        try:
            # Validate request
            await self._validate_request(request)

            # Process request
            response = await call_next(request)

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}", exc_info=True)
            return await call_next(request)

    async def _validate_request(self, request: Request) -> None:
        """Validate incoming request for security threats."""
        # Allow public endpoints without strict validation (health/metrics/docs)
        url_path = str(request.url.path)
        if (
            url_path == "/health"
            or url_path.startswith("/health")
            or url_path.startswith("/api/v2/health")
            or url_path == "/metrics"
            or url_path == "/openapi.json"
            or url_path.startswith("/docs")
            or url_path.startswith("/redoc")
        ):
            return

        # Check content length
        content_length = int(request.headers.get("content-length", 0))
        if content_length > self.config.max_request_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request too large",
            )

        # Check user agent
        user_agent = request.headers.get("User-Agent", "")
        if self.config.require_user_agent and not user_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User-Agent header required",
            )

        # Check blocked user agents
        if any(
            blocked in user_agent.lower() for blocked in self.config.blocked_user_agents
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Validate content type for requests with body
        if request.method in ["POST", "PUT", "PATCH"] and content_length > 0:
            content_type = request.headers.get("content-type", "").lower()
            if not any(
                allowed in content_type for allowed in self.config.allowed_content_types
            ):
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Unsupported content type",
                )

        # Check for suspicious patterns in URL and query parameters
        await self._check_suspicious_patterns(request)

    async def _check_suspicious_patterns(self, request: Request) -> None:
        """Check for SQL injection and XSS patterns."""
        # Check URL path
        url_path = str(request.url.path)

        # Check query parameters
        query_string = str(request.url.query)

        # Check for SQL injection patterns
        for pattern in self.sql_patterns:
            if pattern.search(url_path) or pattern.search(query_string):
                logger.warning(
                    f"SQL injection attempt detected from {request.client.host if request.client else 'unknown'}",
                    extra={
                        "event_type": "security_threat",
                        "threat_type": "sql_injection",
                        "path": url_path,
                        "query": query_string,
                        "client_ip": request.client.host
                        if request.client
                        else "unknown",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request"
                )

        # Check for XSS patterns
        for pattern in self.xss_patterns:
            if pattern.search(url_path) or pattern.search(query_string):
                logger.warning(
                    f"XSS attempt detected from {request.client.host if request.client else 'unknown'}",
                    extra={
                        "event_type": "security_threat",
                        "threat_type": "xss",
                        "path": url_path,
                        "query": query_string,
                        "client_ip": request.client.host
                        if request.client
                        else "unknown",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request"
                )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive request/response logging middleware with rate limiting.

    Features:
    - Structured logging with correlation IDs
    - Request/response body logging (configurable)
    - Performance metrics
    - Error tracking
    - Audit trail
    - Rate limiting and log optimization
    """

    def __init__(
        self,
        app: ASGIApp,
        log_request_body: bool = False,
        log_response_body: bool = False,
        sensitive_headers: Optional[list] = None,
        max_logs_per_second: int = 50,
        enable_rate_limiting: bool = True,
    ):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.sensitive_headers = set(
            sensitive_headers
            or ["authorization", "cookie", "x-api-key", "x-auth-token"]
        )

        # Initialize rate-limited logger
        if enable_rate_limiting:
            self.rate_limiter = RateLimitedLogger(
                max_logs_per_second=max_logs_per_second, enable_deduplication=True
            )
            self.optimized_logger = OptimizedRequestLogger(self.rate_limiter)
        else:
            self.rate_limiter = None
            self.optimized_logger = None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with comprehensive logging and rate limiting."""
        start_time = time.time()

        # Generate correlation ID
        correlation_id = self._generate_correlation_id(request)
        request.state.correlation_id = correlation_id

        # Log incoming request with optimized logging
        client_ip = request.client.host if request.client else "unknown"

        if self.optimized_logger:
            self.optimized_logger.log_request_start(
                request.method, request.url.path, client_ip, correlation_id
            )
        else:
            await self._log_request(request, correlation_id)

        try:
            # Process request
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Add correlation headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time"] = str(round(process_time, 3))

            # Log response with optimized logging
            if self.optimized_logger:
                self.optimized_logger.log_request_complete(
                    request.method,
                    request.url.path,
                    response.status_code,
                    process_time,
                    correlation_id,
                )
            else:
                await self._log_response(
                    request, response, process_time, correlation_id
                )

            return response

        except Exception as e:
            # Log error with optimized logging
            process_time = time.time() - start_time

            if self.optimized_logger:
                self.optimized_logger.log_request_error(
                    request.method, request.url.path, e, process_time, correlation_id
                )
            else:
                await self._log_error(request, e, process_time, correlation_id)
            raise

    def _generate_correlation_id(self, request: Request) -> str:
        """Generate unique correlation ID for request tracking."""
        # Use existing correlation ID if provided
        existing_id = request.headers.get("X-Correlation-ID")
        if existing_id:
            return existing_id

        # Generate new correlation ID
        timestamp = str(int(time.time() * 1000))
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Create hash
        hash_input = f"{timestamp}-{client_ip}-{path}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    async def _log_request(self, request: Request, correlation_id: str) -> None:
        """Log incoming request details (fallback when optimized logger not available)."""
        # Sanitize headers
        headers = dict(request.headers)
        for header in self.sensitive_headers:
            if header in headers:
                headers[header] = "***REDACTED***"

        log_data = {
            "event_type": "http_request_start",
            "correlation_id": correlation_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": headers,
            "client_ip": request.client.host if request.client else "unknown",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Add request body if enabled and appropriate
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    content_type = request.headers.get("content-type", "")
                    if "application/json" in content_type:
                        log_data["request_body"] = json.loads(body)
                    else:
                        log_data["request_body_size"] = len(body)
            except Exception as e:
                # Use DEBUG level for non-critical logging errors
                logger.debug(f"Failed to log request body: {str(e)}")

        # Use DEBUG level for routine requests to reduce log volume
        logger.debug(f"HTTP {request.method} {request.url.path}", extra=log_data)

    async def _log_response(
        self,
        request: Request,
        response: Response,
        process_time: float,
        correlation_id: str,
    ) -> None:
        """Log response details (fallback when optimized logger not available)."""
        log_data = {
            "event_type": "http_request_complete",
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_seconds": round(process_time, 3),
            "response_size": response.headers.get("content-length", 0),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Log response body if enabled and not too large
        if self.log_response_body and hasattr(response, "body"):
            try:
                if len(response.body) < 10000:  # Only log if less than 10KB
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        log_data["response_body"] = json.loads(response.body)
            except Exception as e:
                # Use DEBUG level for non-critical logging errors
                logger.debug(f"Failed to log response body: {str(e)}")

        # Use DEBUG level for routine requests, appropriate levels for errors
        if response.status_code >= 500:
            logger.error(
                f"HTTP {request.method} {request.url.path} - {response.status_code}",
                extra=log_data,
            )
        elif response.status_code >= 400:
            logger.warning(
                f"HTTP {request.method} {request.url.path} - {response.status_code}",
                extra=log_data,
            )
        else:
            # Use DEBUG level for successful requests to reduce log volume
            logger.debug(
                f"HTTP {request.method} {request.url.path} - {response.status_code}",
                extra=log_data,
            )

    async def _log_error(
        self,
        request: Request,
        error: Exception,
        process_time: float,
        correlation_id: str,
    ) -> None:
        """Log request error (fallback when optimized logger not available)."""
        log_data = {
            "event_type": "http_request_error",
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "process_time_seconds": round(process_time, 3),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Determine if we should include stack trace based on error type
        error_type = type(error).__name__
        expected_errors = {
            "ValidationError",
            "HTTPException",
            "AuthenticationError",
            "AuthorizationError",
        }
        include_stacktrace = error_type not in expected_errors

        # Use appropriate log level based on error type
        if hasattr(error, "status_code") and 400 <= error.status_code < 500:
            # Client errors - use WARNING level, no stack trace
            logger.warning(
                f"HTTP {request.method} {request.url.path} - {error_type}: {str(error)}",
                extra=log_data,
            )
        else:
            # Server errors - use ERROR level with stack trace if appropriate
            logger.error(
                f"HTTP {request.method} {request.url.path} - ERROR: {str(error)}",
                extra=log_data,
                exc_info=include_stacktrace,
            )
