"""
Custom exception classes for Hormonia Backend System.
"""
from fastapi import HTTPException, status
from typing import Any, Dict, Optional


class HormoniaException(Exception):
    """Base exception class for Hormonia application."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(HormoniaException):
    """Raised when authentication fails."""
    pass


class AuthorizationError(HormoniaException):
    """Raised when user lacks required permissions."""
    pass


class ValidationError(HormoniaException):
    """Raised when data validation fails."""
    pass


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


# HTTP Exception factories
def create_http_exception(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """Create HTTPException with consistent format."""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": message,
            "details": details or {},
            "status_code": status_code
        }
    )


def authentication_exception(message: str = "Authentication failed") -> HTTPException:
    """Create authentication exception."""
    return create_http_exception(
        status_code=status.HTTP_401_UNAUTHORIZED,
        message=message
    )


def authorization_exception(message: str = "Insufficient permissions") -> HTTPException:
    """Create authorization exception."""
    return create_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        message=message
    )


def not_found_exception(message: str = "Resource not found") -> HTTPException:
    """Create not found exception."""
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message=message
    )


def validation_exception(
    message: str = "Validation failed",
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """Create validation exception."""
    return create_http_exception(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message=message,
        details=details
    )


def conflict_exception(message: str = "Conflict occurred") -> HTTPException:
    """Create conflict exception."""
    return create_http_exception(
        status_code=status.HTTP_409_CONFLICT,
        message=message
    )


def internal_server_exception(message: str = "Internal server error") -> HTTPException:
    """Create internal server exception."""
    return create_http_exception(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=message
    )


# Flow-specific exceptions
class FlowStateNotFoundError(NotFoundError):
    """Raised when a flow state is not found."""
    pass


class FlowOperationError(HormoniaException):
    """Raised when a flow operation fails."""
    pass


class FlowValidationError(ValidationError):
    """Raised when flow validation fails."""
    pass


class FlowStateConflictError(ConflictError):
    """Raised when flow state conflicts occur."""
    pass


class PatientNotFoundError(NotFoundError):
    """Raised when a patient is not found."""
    pass


class PatientAccessDeniedError(AuthorizationError):
    """Raised when user lacks access to a patient."""
    pass


# Flow-specific HTTP exception factories
def flow_not_found_exception(patient_id: str) -> HTTPException:
    """Create flow not found exception."""
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message="Flow state not found",
        details={"patient_id": patient_id}
    )


def patient_not_found_exception(patient_id: str) -> HTTPException:
    """Create patient not found exception."""
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message="Patient not found",
        details={"patient_id": patient_id}
    )


def flow_operation_exception(operation: str, reason: str) -> HTTPException:
    """Create flow operation exception."""
    return create_http_exception(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=f"Flow operation failed: {operation}",
        details={"operation": operation, "reason": reason}
    )


def patient_access_denied_exception(patient_id: str) -> HTTPException:
    """Create patient access denied exception."""
    return create_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        message="Access denied to patient",
        details={"patient_id": patient_id}
    )