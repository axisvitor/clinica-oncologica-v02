"""
Core exceptions for Hormonia Backend - Unified Exception Hierarchy.

This module provides a comprehensive, standardized exception system for the entire application.
All custom exceptions should inherit from these base classes to ensure consistent error handling.

Architecture:
- HormoniaException: Root of all application exceptions
- APIException: Base for HTTP-related exceptions with status codes
- Domain-specific exceptions: Specialized exceptions for each domain

Usage:
    from app.core.exceptions import NotFoundError, ValidationError

    raise NotFoundError("Patient", patient_id)
    raise ValidationError("Invalid CPF format", {"cpf": cpf})
"""

from typing import Optional, Dict, Any


# =========================================================================
# BASE EXCEPTION HIERARCHY
# =========================================================================


class HormoniaException(Exception):
    """
    Root exception for all Hormonia application errors.

    All custom exceptions should inherit from this class directly or indirectly.
    This allows catching all application-specific errors with a single except clause.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            details: Additional context information (dict)
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation of the exception."""
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class APIException(HormoniaException):
    """
    Base exception for HTTP API errors with status codes.

    Use this for exceptions that should be translated to HTTP responses.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize API exception.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (default: 500)
            error_code: Machine-readable error code (e.g., "VALIDATION_ERROR")
            details: Additional error details
        """
        super().__init__(message, details)
        self.status_code = status_code
        self.error_code = error_code

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code,
        }


# =========================================================================
# HTTP EXCEPTIONS (4xx/5xx)
# =========================================================================


class ValidationError(APIException):
    """
    Validation error (422 Unprocessable Entity).

    Use when input data fails validation rules.

    Example:
        raise ValidationError("Invalid CPF format", {"cpf": "123.456.789-00"})
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 422, "VALIDATION_ERROR", details)


class NotFoundError(APIException):
    """
    Resource not found (404 Not Found).

    Use when a requested resource doesn't exist.

    Example:
        raise NotFoundError("Patient", patient_id)
    """

    def __init__(self, resource: str, identifier: str):
        message = f"{resource} not found"
        details = {"resource": resource, "identifier": str(identifier)}
        super().__init__(message, 404, "NOT_FOUND", details)


class ConflictError(APIException):
    """
    Resource conflict (409 Conflict).

    Use when operation conflicts with current state (e.g., duplicate creation).

    Example:
        raise ConflictError("Patient with this CPF already exists", {"cpf": cpf})
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 409, "CONFLICT", details)


class UnauthorizedError(APIException):
    """
    Authentication required (401 Unauthorized).

    Use when user is not authenticated.

    Example:
        raise UnauthorizedError("Invalid or expired token")
    """

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, 401, "UNAUTHORIZED")


class ForbiddenError(APIException):
    """
    Insufficient permissions (403 Forbidden).

    Use when user is authenticated but lacks required permissions.

    Example:
        raise ForbiddenError("Only admins can delete patients")
    """

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, 403, "FORBIDDEN")


class BadRequestError(APIException):
    """
    Bad request (400 Bad Request).

    Use for malformed requests or invalid parameters.

    Example:
        raise BadRequestError("Invalid date format", {"date": "2025-13-40"})
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 400, "BAD_REQUEST", details)


class RateLimitError(APIException):
    """
    Rate limit exceeded (429 Too Many Requests).

    Use when user exceeds allowed request rate.

    Example:
        raise RateLimitError("Too many login attempts", retry_after=60)
    """

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None
    ):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, 429, "RATE_LIMIT_EXCEEDED", details)


class ServiceUnavailableError(APIException):
    """
    Service unavailable (503 Service Unavailable).

    Use when service is temporarily down or overloaded.

    Example:
        raise ServiceUnavailableError("Database connection failed")
    """

    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, 503, "SERVICE_UNAVAILABLE")


# =========================================================================
# DOMAIN-SPECIFIC EXCEPTIONS
# =========================================================================


class AuthenticationError(UnauthorizedError):
    """Authentication failure (more specific than UnauthorizedError)."""

    pass


class AuthorizationError(ForbiddenError):
    """Authorization failure (more specific than ForbiddenError)."""

    pass


class ExternalServiceError(APIException):
    """
    External service integration error (503 Service Unavailable).

    Use when external APIs (WhatsApp, Firebase, Gemini, etc.) fail.

    Example:
        raise ExternalServiceError("WhatsApp", "Connection timeout")
    """

    def __init__(self, service_name: str, error_message: str):
        message = f"{service_name} service error: {error_message}"
        details = {"service": service_name, "error": error_message}
        super().__init__(message, 503, "EXTERNAL_SERVICE_ERROR", details)


class DatabaseError(HormoniaException):
    """
    Database operation error.

    Use for database-level errors (not business logic errors).

    Example:
        raise DatabaseError("Connection pool exhausted", {"pool_size": 10})
    """

    pass


class ProcessingError(HormoniaException):
    """
    Generic processing error.

    Use for errors during data processing pipelines.

    Example:
        raise ProcessingError("Failed to parse quiz response", {"response_id": id})
    """

    pass


# =========================================================================
# FLOW-SPECIFIC EXCEPTIONS
# =========================================================================


class FlowException(HormoniaException):
    """
    Base exception for flow-related errors.

    All flow exceptions should inherit from this.
    """

    def __init__(
        self,
        message: str,
        patient_id: Optional[str] = None,
        flow_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize flow exception.

        Args:
            message: Error message
            patient_id: Patient ID (if applicable)
            flow_type: Flow type (e.g., "ONBOARDING", "QUIZ")
            details: Additional context
        """
        flow_details = details or {}
        if patient_id:
            flow_details["patient_id"] = patient_id
        if flow_type:
            flow_details["flow_type"] = flow_type

        super().__init__(message, flow_details)
        self.patient_id = patient_id
        self.flow_type = flow_type


class FlowStateNotFoundError(FlowException):
    """Flow state not found for patient."""

    pass


class FlowValidationError(FlowException):
    """Flow validation failed."""

    pass


class FlowStateConflictError(FlowException):
    """Flow state conflict (e.g., invalid transition)."""

    pass


class FlowOperationError(FlowException):
    """Flow operation failed."""

    pass


# =========================================================================
# PATIENT-SPECIFIC EXCEPTIONS
# =========================================================================


class PatientNotFoundError(NotFoundError):
    """
    Patient not found.

    Example:
        raise PatientNotFoundError(patient_id)
    """

    def __init__(self, patient_id: str):
        super().__init__("Patient", patient_id)


class PatientAccessDeniedError(ForbiddenError):
    """
    Access denied to patient data.

    Example:
        raise PatientAccessDeniedError(patient_id, user_id)
    """

    def __init__(self, patient_id: str, user_id: Optional[str] = None):
        message = f"Access denied to patient {patient_id}"
        self.patient_id = patient_id
        self.user_id = user_id
        super().__init__(message)


# =========================================================================
# AI/RESPONSE PROCESSING EXCEPTIONS
# =========================================================================


class AIProcessingError(ProcessingError):
    """
    AI service processing error.

    Use for errors during AI operations (Gemini, OpenAI, etc.).

    Example:
        raise AIProcessingError("Failed to generate response", {"prompt_length": 1000})
    """

    pass


class ResponseValidationError(ValidationError):
    """
    Response validation error.

    Use when AI or user response doesn't match expected format.
    """

    pass


class ResponseProcessingError(ProcessingError):
    """
    Response processing error.

    Use for errors during response processing pipeline.
    """

    pass


# =========================================================================
# MESSAGE/COMMUNICATION EXCEPTIONS
# =========================================================================


class MessageSendError(ExternalServiceError):
    """
    Message sending error.

    Example:
        raise MessageSendError("WhatsApp", "Invalid phone number")
    """

    def __init__(
        self, service_name: str, error_message: str, message_id: Optional[str] = None
    ):
        super().__init__(service_name, error_message)
        if message_id:
            self.details["message_id"] = message_id


class MessageNotFoundError(NotFoundError):
    """Message not found."""

    def __init__(self, message_id: str):
        super().__init__("Message", message_id)


# =========================================================================
# QUIZ-SPECIFIC EXCEPTIONS
# =========================================================================


class QuizNotFoundError(NotFoundError):
    """Quiz template or session not found."""

    def __init__(self, quiz_id: str, quiz_type: str = "Quiz"):
        super().__init__(quiz_type, quiz_id)


class QuizValidationError(ValidationError):
    """Quiz validation error."""

    pass


class QuizSessionExpiredError(ConflictError):
    """Quiz session expired."""

    def __init__(self, session_id: str):
        super().__init__("Quiz session has expired", {"session_id": session_id})


# =========================================================================
# CACHE EXCEPTIONS
# =========================================================================


class CacheError(HormoniaException):
    """
    Cache operation error.

    Use for errors during cache operations (Redis, memory, etc.).
    """

    pass


class CacheKeyNotFoundError(CacheError):
    """Cache key not found (not critical, usually handled gracefully)."""

    pass


# =========================================================================
# EXPORT ALL EXCEPTIONS
# =========================================================================

__all__ = [
    # Base
    "HormoniaException",
    "APIException",
    # HTTP Exceptions
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "UnauthorizedError",
    "ForbiddenError",
    "BadRequestError",
    "RateLimitError",
    "ServiceUnavailableError",
    # Domain Exceptions
    "AuthenticationError",
    "AuthorizationError",
    "ExternalServiceError",
    "DatabaseError",
    "ProcessingError",
    # Flow Exceptions
    "FlowException",
    "FlowStateNotFoundError",
    "FlowValidationError",
    "FlowStateConflictError",
    "FlowOperationError",
    # Patient Exceptions
    "PatientNotFoundError",
    "PatientAccessDeniedError",
    # AI/Response Exceptions
    "AIProcessingError",
    "ResponseValidationError",
    "ResponseProcessingError",
    # Message Exceptions
    "MessageSendError",
    "MessageNotFoundError",
    # Quiz Exceptions
    "QuizNotFoundError",
    "QuizValidationError",
    "QuizSessionExpiredError",
    # Cache Exceptions
    "CacheError",
    "CacheKeyNotFoundError",
]
