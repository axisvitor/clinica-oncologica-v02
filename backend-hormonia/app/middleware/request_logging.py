"""
Request logging middleware module.

This middleware provides structured request/response logging with
correlation IDs and performance metrics.
"""

import time
import uuid
import json
from typing import Callable, Dict, Any

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging import get_logger, log_security_event, log_performance_metric

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware for structured request/response logging"""

    def __init__(
        self, app, log_request_body: bool = False, log_response_body: bool = False
    ):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID and correlation ID
        request_id = str(uuid.uuid4())
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

        # Store in request state
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        # Extract request information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")

        # Create contextual logger
        request_logger = logger.with_context(
            request_id=request_id, correlation_id=correlation_id, client_ip=client_ip
        )

        # Log request start
        start_time = time.time()
        request_data = await self._extract_request_data(request)

        request_logger.info(
            "HTTP request started",
            extra={
                "event_type": "http_request_start",
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": self._filter_headers(dict(request.headers)),
                "client_ip": client_ip,
                "user_agent": user_agent,
                "content_type": request.headers.get("Content-Type"),
                "content_length": request.headers.get("Content-Length"),
                "request_body": request_data.get("body")
                if self.log_request_body
                else None,
            },
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Extract response data
            response_data = (
                await self._extract_response_data(response)
                if self.log_response_body
                else {}
            )

            # Log successful response
            request_logger.info(
                "HTTP request completed",
                extra={
                    "event_type": "http_request_complete",
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time * 1000, 2),
                    "response_headers": self._filter_headers(dict(response.headers)),
                    "response_size": response.headers.get("Content-Length"),
                    "response_body": response_data.get("body")
                    if self.log_response_body
                    else None,
                },
            )

            # Log performance metric
            log_performance_metric(
                "http_request_duration",
                round(process_time * 1000, 2),
                "ms",
                {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": str(response.status_code),
                },
                request_logger.logger,
            )

            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))

            return response

        except Exception as e:
            # Calculate processing time for errors
            process_time = time.time() - start_time

            # Log error with full context
            request_logger.error(
                "HTTP request failed",
                extra={
                    "event_type": "http_request_error",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "process_time_ms": round(process_time * 1000, 2),
                    "request_data": request_data,
                },
                exc_info=True,
            )

            # Log security event for certain error types
            if isinstance(e, HTTPException):
                if e.status_code in [401, 403, 429]:
                    log_security_event(
                        "authentication_failure"
                        if e.status_code == 401
                        else "authorization_failure"
                        if e.status_code == 403
                        else "rate_limit_exceeded",
                        f"HTTP {e.status_code}: {e.detail}",
                        ip_address=client_ip,
                        user_agent=user_agent,
                        severity="WARNING",
                        logger=request_logger.logger,
                    )

            raise

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address considering proxy headers."""
        # Check for forwarded headers (common in load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _filter_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Filter sensitive headers from logging."""
        sensitive_headers = {
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
            "x-access-token",
            "x-refresh-token",
        }

        filtered = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                filtered[key] = "[REDACTED]"
            else:
                filtered[key] = value

        return filtered

    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """Extract request data for logging."""
        data = {}

        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Read body without consuming it
                body = await request.body()
                if body:
                    content_type = request.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        try:
                            data["body"] = json.loads(body.decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            data["body"] = "[INVALID_JSON]"
                    else:
                        data["body"] = f"[BINARY_DATA:{len(body)}_bytes]"
            except Exception:
                data["body"] = "[ERROR_READING_BODY]"

        return data

    async def _extract_response_data(self, response: Response) -> Dict[str, Any]:
        """Extract response data for logging."""
        data = {}

        if self.log_response_body:
            try:
                # This is complex for streaming responses, so we'll skip for now
                # In production, you might want to implement response body capture
                data["body"] = "[RESPONSE_BODY_LOGGING_NOT_IMPLEMENTED]"
            except Exception:
                data["body"] = "[ERROR_READING_RESPONSE]"

        return data


__all__ = ["LoggingMiddleware"]
