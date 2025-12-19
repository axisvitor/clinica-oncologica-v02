"""
Exceptions package for the application.

This package consolidates base exception classes and specialized exceptions
into a single namespace `app.exceptions` to avoid circular imports.

Design:
- Base exceptions (HormoniaException, ValidationError, etc.) are defined here
- ProcessingError is introduced as a generic base for processing-related errors
- Specialized exceptions live in submodules (flow_exceptions, response_processing)
- Submodules import base classes from this package (relative import) to avoid cycles
- We import specialized exceptions at the end, after base classes are defined
"""

from fastapi import HTTPException, status
from typing import Any, Dict, Optional


# -------------------------
# Base exception hierarchy
# -------------------------
class HormoniaException(Exception):
    """Base exception class for the application."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        field: Optional[str] = None,
        **kwargs
    ):
        self.message = message
        self.details = details or {}
        self.details.update(kwargs)
        self.code = code or self.details.get("code")
        self.field = field or self.details.get("field")

        if self.code:
            self.details["code"] = self.code
        if self.field:
            self.details["field"] = self.field

        super().__init__(self.message)


class AuthenticationError(HormoniaException):
    """Raised when authentication fails."""

    pass


class AuthorizationError(HormoniaException):
    """Raised when user lacks required permissions."""

    pass


class ValidationError(HormoniaException):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        field: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, details=details, code=code, field=field, **kwargs)


class NotFoundError(HormoniaException):
    """Raised when a requested resource is not found."""

    pass


class ConflictError(HormoniaException):
    """Raised when a business rule conflict occurs."""

    pass


class ExternalServiceError(HormoniaException):
    """Raised when external service integration fails."""

    pass


class DatabaseError(HormoniaException):
    """Raised when database operations fail."""

    pass


class ProcessingError(HormoniaException):
    """Generic base for processing pipeline errors (parsing, AI, state)."""

    pass


class ServiceError(HormoniaException):
    """Raised when a service operation fails."""

    pass


# -------------------------
# HTTP Exception factories
# -------------------------


def create_http_exception(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create HTTPException with consistent format."""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": message,
            "details": details or {},
            "status_code": status_code,
        },
    )


def authentication_exception(message: str = "Authentication failed") -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_401_UNAUTHORIZED, message=message
    )


def authorization_exception(message: str = "Insufficient permissions") -> HTTPException:
    return create_http_exception(status_code=status.HTTP_403_FORBIDDEN, message=message)


def not_found_exception(message: str = "Resource not found") -> HTTPException:
    return create_http_exception(status_code=status.HTTP_404_NOT_FOUND, message=message)


def validation_exception(
    message: str = "Validation failed", details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message=message,
        details=details,
    )


def conflict_exception(message: str = "Conflict occurred") -> HTTPException:
    return create_http_exception(status_code=status.HTTP_409_CONFLICT, message=message)


def internal_server_exception(message: str = "Internal server error") -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=message
    )


# -------------------------
# Flow-specific convenience
# -------------------------
class FlowStateNotFoundError(NotFoundError):
    pass


class FlowOperationError(HormoniaException):
    pass


class FlowValidationError(ValidationError):
    pass


class FlowStateConflictError(ConflictError):
    pass


class ConcurrentModificationError(ConflictError):
    """
    Raised when optimistic locking detects a concurrent modification.

    This occurs when another process/request modified the resource
    between when it was read and when the update was attempted.
    The caller should retry the operation.
    """

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        expected_version: int,
        actual_version: int,
    ):
        message = (
            f"Concurrent modification detected for {resource_type} {resource_id}. "
            f"Expected version {expected_version}, found {actual_version}. "
            "Please retry the operation."
        )
        super().__init__(
            message,
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "expected_version": expected_version,
                "actual_version": actual_version,
                "retry_recommended": True,
            },
        )


class PatientNotFoundError(NotFoundError):
    pass


class PatientAccessDeniedError(AuthorizationError):
    pass


def flow_not_found_exception(patient_id: str) -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message="Flow state not found",
        details={"patient_id": patient_id},
    )


def patient_not_found_exception(patient_id: str) -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message="Patient not found",
        details={"patient_id": patient_id},
    )


def flow_operation_exception(operation: str, reason: str) -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=f"Flow operation failed: {operation}",
        details={"operation": operation, "reason": reason},
    )


def patient_access_denied_exception(patient_id: str) -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        message="Access denied to patient",
        details={"patient_id": patient_id},
    )


# -------------------------
# Import specialized exceptions last to avoid cycles
# -------------------------
try:
    from .response_processing import (
        ResponseValidationError,
        ResponseProcessingError,
        AIProcessingError,
        FlowStateError,
    )
except Exception:
    # During early import phases in some tools/tests, these may be unavailable
    ResponseValidationError = None  # type: ignore
    ResponseProcessingError = None  # type: ignore
    AIProcessingError = None  # type: ignore
    FlowStateError = None  # type: ignore

__all__ = [
    # Base
    "HormoniaException",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "ExternalServiceError",
    "DatabaseError",
    "ProcessingError",
    "ServiceError",
    # HTTP helpers
    "create_http_exception",
    "authentication_exception",
    "authorization_exception",
    "not_found_exception",
    "validation_exception",
    "conflict_exception",
    "internal_server_exception",
    # Flow convenience
    "FlowStateNotFoundError",
    "FlowOperationError",
    "FlowValidationError",
    "FlowStateConflictError",
    "ConcurrentModificationError",
    "PatientNotFoundError",
    "PatientAccessDeniedError",
    "flow_not_found_exception",
    "patient_not_found_exception",
    "flow_operation_exception",
    "patient_access_denied_exception",
    # Specialized (may be None during early import)
    "ResponseValidationError",
    "ResponseProcessingError",
    "AIProcessingError",
    "FlowStateError",
]
