"""
Enhanced Error Handling Middleware
Provides comprehensive error handling, logging, and recovery for production
"""

import logging
import traceback
import time
from typing import Dict, Any, Union
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import (
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from datetime import datetime, timezone
import psutil
import os

logger = logging.getLogger(__name__)


class EnhancedErrorHandler(BaseHTTPMiddleware):
    """
    Enhanced error handling middleware for production Railway deployment.

    Features:
    - Structured error logging with context
    - Error categorization and severity assessment
    - Performance impact monitoring
    - System resource monitoring during errors
    - Client-safe error responses
    - Error rate limiting and circuit breaker patterns
    """

    def __init__(self, app, enable_detailed_errors: bool = False):
        super().__init__(app)
        self.enable_detailed_errors = enable_detailed_errors
        self.error_counts: Dict[str, int] = {}
        self.error_rate_window = 300  # 5 minutes
        self.max_error_rate = 50  # errors per window
        self.circuit_breaker_active = False

    async def dispatch(self, request: Request, call_next):
        """
        Enhanced error handling with comprehensive logging and monitoring.
        """
        start_time = time.time()
        request_id = getattr(request.state, "request_id", f"req_{int(time.time())}")

        try:
            # Check circuit breaker
            if self._should_circuit_break():
                return self._circuit_breaker_response()

            # Process request
            response = await call_next(request)

            # Log successful requests with performance metrics
            if response.status_code >= 400:
                self._log_http_error(
                    request, response, time.time() - start_time, request_id
                )

            return response

        except HTTPException as http_exc:
            # Handle FastAPI HTTP exceptions
            return await self._handle_http_exception(
                request, http_exc, start_time, request_id
            )

        except Exception as exc:
            # Handle unexpected exceptions
            return await self._handle_unexpected_exception(
                request, exc, start_time, request_id
            )

    async def _handle_http_exception(
        self, request: Request, exc: HTTPException, start_time: float, request_id: str
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions with enhanced logging."""

        error_context = self._build_error_context(request, exc, start_time, request_id)

        # Log based on severity
        if exc.status_code >= 500:
            logger.error(f"HTTP {exc.status_code} Error", extra=error_context)
            self._increment_error_count("http_5xx")
        elif exc.status_code >= 400:
            logger.warning(f"HTTP {exc.status_code} Client Error", extra=error_context)
            self._increment_error_count("http_4xx")

        # Create client-safe response
        response_data = {
            "detail": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
        }

        # Add debug info if enabled
        if self.enable_detailed_errors and exc.status_code >= 500:
            response_data["debug_info"] = {
                "path": str(request.url.path),
                "method": request.method,
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
            }

        return JSONResponse(
            status_code=exc.status_code,
            content=response_data,
            headers={"X-Request-ID": request_id},
        )

    async def _handle_unexpected_exception(
        self, request: Request, exc: Exception, start_time: float, request_id: str
    ) -> JSONResponse:
        """Handle unexpected exceptions with comprehensive error tracking."""

        error_context = self._build_error_context(request, exc, start_time, request_id)
        error_context["exception_type"] = type(exc).__name__
        error_context["traceback"] = traceback.format_exc()

        # Categorize error
        error_category = self._categorize_error(exc)
        error_context["error_category"] = error_category

        # Get system state during error
        system_state = self._get_system_state()
        error_context["system_state"] = system_state

        # Log with full context
        logger.error(
            f"Unexpected {error_category} Error: {str(exc)}", extra=error_context
        )
        self._increment_error_count(error_category)

        # Determine response based on error type
        status_code = self._determine_status_code(exc, error_category)

        # Create client-safe error response
        response_data = {
            "detail": "Internal server error"
            if not self.enable_detailed_errors
            else str(exc),
            "status_code": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "error_category": error_category,
        }

        # Add debug information for development
        if self.enable_detailed_errors:
            response_data["debug_info"] = {
                "exception_type": type(exc).__name__,
                "path": str(request.url.path),
                "method": request.method,
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
                "system_state": system_state,
            }

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={"X-Request-ID": request_id, "X-Error-Category": error_category},
        )

    # SECURITY: Headers that should never be logged (contain sensitive data)
    _SENSITIVE_HEADERS = {
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
        "x-csrf-token",
        "x-xsrf-token",
        "set-cookie",
        "proxy-authorization",
    }

    def _filter_sensitive_headers(self, headers: dict) -> dict:
        """Filter sensitive headers before logging to prevent credential leakage."""
        return {
            k: "[REDACTED]" if k.lower() in self._SENSITIVE_HEADERS else v
            for k, v in headers.items()
        }

    def _build_error_context(
        self,
        request: Request,
        exc: Union[Exception, HTTPException],
        start_time: float,
        request_id: str,
    ) -> Dict[str, Any]:
        """Build comprehensive error context for logging.

        SECURITY: Sensitive headers are filtered to prevent credential leakage in logs.
        """
        # SECURITY FIX: Filter sensitive headers before logging
        filtered_headers = self._filter_sensitive_headers(dict(request.headers))

        return {
            "request_id": request_id,
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "headers": filtered_headers,  # SECURITY: Use filtered headers
            "client_ip": getattr(request.client, "host", "unknown"),
            "user_agent": request.headers.get("user-agent", "unknown"),
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "exception_message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _categorize_error(self, exc: Exception) -> str:
        """Categorize error for better handling and monitoring."""

        type(exc).__name__
        exc_message = str(exc).lower()

        # Database errors
        if any(
            db_term in exc_message
            for db_term in ["database", "connection", "psycopg", "sqlalchemy"]
        ):
            return "database"

        # Network/HTTP errors
        if any(
            net_term in exc_message
            for net_term in ["timeout", "connection", "network", "unreachable"]
        ):
            return "network"

        # Authentication/Authorization errors
        if any(
            auth_term in exc_message
            for auth_term in [
                "unauthorized",
                "forbidden",
                "authentication",
                "permission",
            ]
        ):
            return "authentication"

        # Validation errors
        if any(
            val_term in exc_message
            for val_term in ["validation", "invalid", "required", "format"]
        ):
            return "validation"

        # Resource errors
        if any(
            res_term in exc_message
            for res_term in ["not found", "does not exist", "missing"]
        ):
            return "resource"

        # External service errors
        if any(
            ext_term in exc_message
            for ext_term in ["firebase", "redis", "external", "api"]
        ):
            return "external_service"

        # Memory/Performance errors
        if any(
            perf_term in exc_message
            for perf_term in ["memory", "timeout", "too large", "limit"]
        ):
            return "performance"

        return "unknown"

    def _determine_status_code(self, exc: Exception, category: str) -> int:
        """Determine appropriate HTTP status code based on error type."""

        status_mapping = {
            "database": HTTP_503_SERVICE_UNAVAILABLE,
            "network": HTTP_503_SERVICE_UNAVAILABLE,
            "external_service": HTTP_503_SERVICE_UNAVAILABLE,
            "authentication": 401,
            "validation": 422,
            "resource": 404,
            "performance": HTTP_503_SERVICE_UNAVAILABLE,
            "unknown": HTTP_500_INTERNAL_SERVER_ERROR,
        }

        return status_mapping.get(category, HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_system_state(self) -> Dict[str, Any]:
        """Get current system state for error context."""

        try:
            return {
                "cpu_percent": round(psutil.cpu_percent(interval=0.1), 2),
                "memory_percent": round(psutil.virtual_memory().percent, 2),
                "memory_available_mb": round(
                    psutil.virtual_memory().available / 1024 / 1024, 2
                ),
                "disk_usage_percent": round(psutil.disk_usage("/").percent, 2),
                "process_count": len(psutil.pids()),
                "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
            }
        except Exception:
            return {"error": "Could not retrieve system state"}

    def _increment_error_count(self, error_type: str):
        """Track error counts for rate limiting and monitoring."""

        current_time = int(time.time())
        window_key = f"{error_type}_{current_time // self.error_rate_window}"

        self.error_counts[window_key] = self.error_counts.get(window_key, 0) + 1

        # Clean old windows
        cutoff_time = current_time - self.error_rate_window
        keys_to_remove = [
            key
            for key in self.error_counts.keys()
            if int(key.split("_")[-1]) * self.error_rate_window < cutoff_time
        ]
        for key in keys_to_remove:
            del self.error_counts[key]

    def _should_circuit_break(self) -> bool:
        """Determine if circuit breaker should activate."""

        current_time = int(time.time())
        current_window = current_time // self.error_rate_window

        # Count recent errors
        recent_errors = sum(
            count
            for key, count in self.error_counts.items()
            if int(key.split("_")[-1])
            >= current_window - 1  # Current and previous window
        )

        return recent_errors > self.max_error_rate

    def _circuit_breaker_response(self) -> JSONResponse:
        """Return circuit breaker response."""

        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Service temporarily unavailable due to high error rate",
                "status_code": HTTP_503_SERVICE_UNAVAILABLE,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "retry_after": 60,
            },
            headers={"Retry-After": "60"},
        )

    def _log_http_error(
        self, request: Request, response: Response, duration: float, request_id: str
    ):
        """Log HTTP errors with context."""

        context = {
            "request_id": request_id,
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "response_time_ms": round(duration * 1000, 2),
            "client_ip": getattr(request.client, "host", "unknown"),
            "user_agent": request.headers.get("user-agent", "unknown"),
        }

        if response.status_code >= 500:
            logger.error(f"HTTP {response.status_code} Error", extra=context)
        elif response.status_code >= 400:
            logger.warning(f"HTTP {response.status_code} Client Error", extra=context)

    def get_error_metrics(self) -> Dict[str, Any]:
        """Get current error metrics for monitoring."""

        return {
            "error_counts": self.error_counts.copy(),
            "circuit_breaker_active": self.circuit_breaker_active,
            "error_rate_threshold": self.max_error_rate,
            "window_seconds": self.error_rate_window,
        }
