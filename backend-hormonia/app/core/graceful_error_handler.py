"""
Graceful Error Handler for comprehensive error management.

This module provides graceful error handling with specific handlers for
database, WebSocket, and API errors, along with proper HTTP status codes
and user-friendly error responses.
"""

import logging
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    DatabaseError,
    DisconnectionError,
)
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidState,
)
from pydantic import ValidationError

from app.core.error_handler import CriticalErrorHandler


logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(str, Enum):
    """Error categories for classification."""

    DATABASE = "DATABASE"
    WEBSOCKET = "WEBSOCKET"
    API = "API"
    VALIDATION = "VALIDATION"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    SYSTEM = "SYSTEM"


class ErrorResponse:
    """Standardized error response structure."""

    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[str] = None,
        status_code: int = 500,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details
        self.status_code = status_code
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.suggestions = suggestions or []
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert error response to dictionary."""
        response = {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "category": self.category.value,
                "severity": self.severity.value,
                "timestamp": self.timestamp,
            }
        }

        if self.details:
            response["error"]["details"] = self.details

        if self.suggestions:
            response["error"]["suggestions"] = self.suggestions

        if self.context:
            response["error"]["context"] = self.context

        return response

    def to_json_response(self) -> JSONResponse:
        """Convert to FastAPI JSONResponse."""
        return JSONResponse(status_code=self.status_code, content=self.to_dict())


class GracefulErrorHandler(CriticalErrorHandler):
    """
    Enhanced error handler with graceful degradation and specific error type handling.

    Extends the base CriticalErrorHandler with:
    - Database-specific error handling
    - WebSocket error management
    - API error standardization
    - Graceful degradation strategies
    """

    def __init__(self, max_errors_per_hour: int = 50, enable_tracking: bool = True):
        super().__init__(max_errors_per_hour, enable_tracking)
        self.logger = logging.getLogger(__name__)

    async def handle_database_error(
        self,
        error: Exception,
        operation: str,
        table_name: Optional[str] = None,
        query_context: Optional[Dict[str, Any]] = None,
    ) -> ErrorResponse:
        """
        Handle database-specific errors with appropriate responses.

        Args:
            error: The database error
            operation: The database operation that failed
            table_name: Name of the affected table
            query_context: Additional query context

        Returns:
            ErrorResponse with appropriate status code and message
        """
        context = {
            "operation": operation,
            "table_name": table_name,
            "error_type": type(error).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if query_context:
            context.update(query_context)

        # Handle specific database error types
        if isinstance(error, IntegrityError):
            error_response = ErrorResponse(
                error_code="DB_INTEGRITY_ERROR",
                message="Data integrity constraint violation",
                details="The operation violates database constraints",
                status_code=status.HTTP_400_BAD_REQUEST,
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.WARNING,
                context=context,
                suggestions=[
                    "Check for duplicate values in unique fields",
                    "Ensure foreign key references exist",
                    "Validate required fields are provided",
                ],
            )
        elif isinstance(error, OperationalError):
            error_response = ErrorResponse(
                error_code="DB_OPERATIONAL_ERROR",
                message="Database operation failed",
                details="The database operation could not be completed",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.ERROR,
                context=context,
                suggestions=[
                    "Check database connection",
                    "Verify database server is running",
                    "Try the operation again in a few moments",
                ],
            )
        elif isinstance(error, DisconnectionError):
            error_response = ErrorResponse(
                error_code="DB_CONNECTION_LOST",
                message="Database connection lost",
                details="Connection to the database was unexpectedly closed",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.CRITICAL,
                context=context,
                suggestions=[
                    "The system will attempt to reconnect automatically",
                    "Please try your request again in a few moments",
                ],
            )
        elif isinstance(error, DatabaseError):
            error_response = ErrorResponse(
                error_code="DB_GENERAL_ERROR",
                message="Database error occurred",
                details="A database error prevented the operation from completing",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.ERROR,
                context=context,
                suggestions=[
                    "Please try the operation again",
                    "Contact support if the problem persists",
                ],
            )
        else:
            error_response = ErrorResponse(
                error_code="DB_UNKNOWN_ERROR",
                message="Unknown database error",
                details="An unexpected database error occurred",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.ERROR,
                context=context,
                suggestions=[
                    "Please try the operation again",
                    "Contact support if the problem persists",
                ],
            )

        # Log the error
        await self._log_and_track_error(
            error_type=f"DATABASE_{error_response.error_code}",
            error_message=str(error),
            context=context,
            severity=error_response.severity.value,
            stack_trace=traceback.format_exc(),
        )

        return error_response

    async def handle_websocket_error(
        self,
        error: Exception,
        connection_id: Optional[str] = None,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> ErrorResponse:
        """
        Handle WebSocket-specific errors.

        Args:
            error: The WebSocket error
            connection_id: ID of the WebSocket connection
            user_id: ID of the user associated with the connection
            operation: The WebSocket operation that failed

        Returns:
            ErrorResponse with appropriate handling
        """
        context = {
            "connection_id": connection_id,
            "user_id": user_id,
            "operation": operation,
            "error_type": type(error).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Handle specific WebSocket error types
        if isinstance(error, (ConnectionClosed, ConnectionClosedError)):
            error_response = ErrorResponse(
                error_code="WS_CONNECTION_CLOSED",
                message="WebSocket connection closed",
                details="The WebSocket connection was closed unexpectedly",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                category=ErrorCategory.WEBSOCKET,
                severity=ErrorSeverity.WARNING,
                context=context,
                suggestions=[
                    "The client will attempt to reconnect automatically",
                    "Check your network connection",
                ],
            )
        elif isinstance(error, ConnectionClosedOK):
            error_response = ErrorResponse(
                error_code="WS_CONNECTION_CLOSED_OK",
                message="WebSocket connection closed normally",
                details="The WebSocket connection was closed by the client",
                status_code=status.HTTP_200_OK,
                category=ErrorCategory.WEBSOCKET,
                severity=ErrorSeverity.INFO,
                context=context,
                suggestions=[],
            )
        elif isinstance(error, InvalidState):
            error_response = ErrorResponse(
                error_code="WS_INVALID_STATE",
                message="WebSocket in invalid state",
                details="The WebSocket connection is in an invalid state for this operation",
                status_code=status.HTTP_400_BAD_REQUEST,
                category=ErrorCategory.WEBSOCKET,
                severity=ErrorSeverity.WARNING,
                context=context,
                suggestions=[
                    "Ensure the WebSocket connection is properly established",
                    "Try reconnecting to the WebSocket",
                ],
            )
        else:
            error_response = ErrorResponse(
                error_code="WS_UNKNOWN_ERROR",
                message="WebSocket error occurred",
                details="An unexpected WebSocket error occurred",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.WEBSOCKET,
                severity=ErrorSeverity.ERROR,
                context=context,
                suggestions=[
                    "Try reconnecting to the WebSocket",
                    "Check your network connection",
                ],
            )

        # Log the error (with lower severity for normal closures)
        if not isinstance(error, ConnectionClosedOK):
            await self._log_and_track_error(
                error_type=f"WEBSOCKET_{error_response.error_code}",
                error_message=str(error),
                context=context,
                severity=error_response.severity.value,
                stack_trace=traceback.format_exc(),
            )

        return error_response

    async def handle_api_error(
        self,
        error: Exception,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> ErrorResponse:
        """
        Handle API-specific errors with proper HTTP status codes.

        Args:
            error: The API error
            endpoint: The API endpoint that failed
            method: HTTP method used
            user_id: ID of the user making the request
            request_data: Request data (sanitized)

        Returns:
            ErrorResponse with appropriate status code
        """
        context = {
            "endpoint": endpoint,
            "method": method,
            "user_id": user_id,
            "error_type": type(error).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if request_data:
            # Sanitize sensitive data
            sanitized_data = self._sanitize_request_data(request_data)
            context["request_data"] = sanitized_data

        # Handle specific API error types
        if isinstance(error, ValidationError):
            error_response = ErrorResponse(
                error_code="API_VALIDATION_ERROR",
                message="Request validation failed",
                details=str(error),
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.WARNING,
                context=context,
                suggestions=[
                    "Check the request format and required fields",
                    "Ensure all data types are correct",
                ],
            )
        elif isinstance(error, PermissionError):
            error_response = ErrorResponse(
                error_code="API_PERMISSION_DENIED",
                message="Permission denied",
                details="You don't have permission to perform this operation",
                status_code=status.HTTP_403_FORBIDDEN,
                category=ErrorCategory.AUTHORIZATION,
                severity=ErrorSeverity.WARNING,
                context=context,
                suggestions=[
                    "Check your user permissions",
                    "Contact an administrator if you believe this is an error",
                ],
            )
        elif isinstance(error, ValueError):
            error_response = ErrorResponse(
                error_code="API_VALUE_ERROR",
                message="Invalid value provided",
                details=str(error),
                status_code=status.HTTP_400_BAD_REQUEST,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.WARNING,
                context=context,
                suggestions=[
                    "Check the provided values are in the correct format",
                    "Ensure all required parameters are provided",
                ],
            )
        elif isinstance(error, KeyError):
            error_response = ErrorResponse(
                error_code="API_MISSING_PARAMETER",
                message="Required parameter missing",
                details=f"Missing required parameter: {str(error)}",
                status_code=status.HTTP_400_BAD_REQUEST,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.WARNING,
                context=context,
                suggestions=[
                    "Check that all required parameters are provided",
                    "Review the API documentation for required fields",
                ],
            )
        elif isinstance(error, TimeoutError):
            error_response = ErrorResponse(
                error_code="API_TIMEOUT",
                message="Request timeout",
                details="The request took too long to process",
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                category=ErrorCategory.API,
                severity=ErrorSeverity.ERROR,
                context=context,
                suggestions=[
                    "Try the request again",
                    "Consider reducing the scope of your request",
                ],
            )
        else:
            error_response = ErrorResponse(
                error_code="API_INTERNAL_ERROR",
                message="Internal server error",
                details="An unexpected error occurred while processing your request",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.API,
                severity=ErrorSeverity.ERROR,
                context=context,
                suggestions=[
                    "Please try your request again",
                    "Contact support if the problem persists",
                ],
            )

        # Log the error
        await self._log_and_track_error(
            error_type=f"API_{error_response.error_code}",
            error_message=str(error),
            context=context,
            severity=error_response.severity.value,
            stack_trace=traceback.format_exc(),
        )

        return error_response

    async def handle_graceful_degradation(
        self,
        primary_error: Exception,
        fallback_data: Optional[Any] = None,
        operation: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle graceful degradation when primary functionality fails.

        Args:
            primary_error: The primary error that occurred
            fallback_data: Fallback data to return
            operation: Description of the operation
            context: Additional context

        Returns:
            Response with fallback data and warning
        """
        error_context = {
            "operation": operation,
            "primary_error": str(primary_error),
            "fallback_used": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if context:
            error_context.update(context)

        # Log the degradation
        await self._log_and_track_error(
            error_type="GRACEFUL_DEGRADATION",
            error_message=f"Graceful degradation for {operation}: {str(primary_error)}",
            context=error_context,
            severity=ErrorSeverity.WARNING.value,
        )

        return {
            "data": fallback_data,
            "warning": {
                "message": "Service is running in degraded mode",
                "details": "Some features may be limited due to a temporary issue",
                "operation": operation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def _sanitize_request_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize request data to remove sensitive information.

        Args:
            data: Request data to sanitize

        Returns:
            Sanitized data dictionary
        """
        sensitive_fields = {
            "password",
            "token",
            "secret",
            "key",
            "auth",
            "credential",
            "private",
            "confidential",
            "ssn",
            "social_security",
        }

        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_fields):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_request_data(value)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                sanitized[key] = [self._sanitize_request_data(item) for item in value]
            else:
                sanitized[key] = value

        return sanitized

    async def _log_and_track_error(
        self,
        error_type: str,
        error_message: str,
        context: Dict[str, Any],
        severity: str = "ERROR",
        stack_trace: Optional[str] = None,
    ) -> None:
        """
        Log and track error with rate limiting.

        Args:
            error_type: Type of error
            error_message: Error message
            context: Error context
            severity: Error severity
            stack_trace: Stack trace if available
        """
        error_key = self._create_error_key(error_type, error_message)

        if self._should_log_error(error_key):
            # Log the error
            log_level = getattr(logging, severity, logging.ERROR)
            self.logger.log(
                log_level,
                f"{error_type}: {error_message}",
                extra={
                    "error_type": error_type,
                    "context": context,
                    "stack_trace": stack_trace,
                },
            )

            # Track in database
            await self._track_error_in_db(
                error_type=error_type,
                error_message=error_message,
                context=context,
                stack_trace=stack_trace,
                severity=severity,
            )

    async def create_http_exception_from_error_response(
        self, error_response: ErrorResponse
    ) -> HTTPException:
        """
        Convert ErrorResponse to HTTPException.

        Args:
            error_response: The error response to convert

        Returns:
            HTTPException with appropriate status code and detail
        """
        return HTTPException(
            status_code=error_response.status_code, detail=error_response.to_dict()
        )


# Global graceful error handler instance
graceful_error_handler = GracefulErrorHandler()


# Convenience functions for common error handling patterns
async def handle_db_error(
    error: Exception, operation: str, table_name: str = None
) -> ErrorResponse:
    """Convenience function for database errors."""
    return await graceful_error_handler.handle_database_error(
        error, operation, table_name
    )


async def handle_ws_error(
    error: Exception, connection_id: str = None, user_id: str = None
) -> ErrorResponse:
    """Convenience function for WebSocket errors."""
    return await graceful_error_handler.handle_websocket_error(
        error, connection_id, user_id
    )


async def handle_api_error(
    error: Exception, endpoint: str, method: str, user_id: str = None
) -> ErrorResponse:
    """Convenience function for API errors."""
    return await graceful_error_handler.handle_api_error(
        error, endpoint, method, user_id
    )


async def graceful_degradation(
    error: Exception, fallback_data: Any = None, operation: str = "unknown"
) -> Dict[str, Any]:
    """Convenience function for graceful degradation."""
    return await graceful_error_handler.handle_graceful_degradation(
        error, fallback_data, operation
    )
