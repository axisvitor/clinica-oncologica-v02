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

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        field: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            details: Additional context information (dict)
            code: Machine-readable error code (optional)
            field: Field that caused the error (optional)
            **kwargs: Additional context fields
        """
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
        code: Optional[str] = None,
        field: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize API exception.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (default: 500)
            error_code: Machine-readable error code (e.g., "VALIDATION_ERROR")
            details: Additional error details
            code: Optional machine-readable error code
            field: Optional field name
            **kwargs: Additional context fields
        """
        super().__init__(
            message, 
            details=details, 
            code=code or error_code, 
            field=field, 
            **kwargs
        )
        self.status_code = status_code
        self.error_code = code or error_code

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


class BusinessRuleError(APIException):
    """
    Business rule violation (400 Bad Request).

    Use when operation violates business logic rules.

    Reference: LOW-017 - Inconsistent Error Handling

    Example:
        raise BusinessRuleError(
            "Patient already exists",
            field="cpf",
            code="duplicate_cpf"
        )
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize business rule error.

        Args:
            message: Human-readable error message
            field: Field that caused the error (optional)
            code: Machine-readable error code (optional)
            details: Additional error context
        """
        error_details = details or {}
        if field:
            error_details["field"] = field
        if code:
            error_details["code"] = code

        super().__init__(message, 400, code or "BUSINESS_RULE_VIOLATION", error_details)
        self.field = field
        self.code = code


class ValidationError(APIException):
    """
    Validation error (422 Unprocessable Entity).

    Use when input data fails validation rules.

    Reference: LOW-017 - Inconsistent Error Handling

    Examples:
        # Single field error
        raise ValidationError("Invalid CPF format", {"cpf": "123.456.789-00"})

        # Multiple field errors
        raise ValidationError("Input validation failed", {
            "cpf": "Invalid CPF format",
            "birth_date": "Patient must be at least 18 years old"
        })
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        errors: Optional[Dict[str, str]] = None,
        field: Optional[str] = None,
        code: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize validation error.

        Args:
            message: Human-readable error message
            details: Additional error details
            errors: Dict of field-level errors (field -> error message)
            field: Field that caused the error (optional)
            code: Machine-readable error code (optional)
            **kwargs: Additional context fields
        """
        error_details = details or {}
        if errors:
            error_details["errors"] = errors
        if field:
            error_details["field"] = field
        if code:
            error_details["code"] = code
        error_details.update(kwargs)

        super().__init__(message, 422, code or "VALIDATION_ERROR", error_details)
        self.errors = errors
        self.field = field
        self.code = code or "VALIDATION_ERROR"


class NotFoundError(APIException):
    """
    Resource not found (404 Not Found).

    Use when a requested resource doesn't exist.

    Reference: LOW-017 - Inconsistent Error Handling

    Examples:
        raise NotFoundError("Patient", patient_id)
        raise NotFoundError("Quiz Session", session_id)
    """

    def __init__(self, resource: str, identifier: Any):
        """
        Initialize not found error.

        Args:
            resource: Resource type (e.g., "Patient", "Quiz Session")
            identifier: Resource identifier (ID, UUID, etc.)
        """
        message = f"{resource} not found"
        details = {"resource": resource, "identifier": str(identifier)}
        super().__init__(message, 404, "NOT_FOUND", details)
        self.resource = resource
        self.identifier = identifier


class ConflictError(APIException):
    """
    Resource conflict (409 Conflict).

    Use when operation conflicts with current state (e.g., duplicate creation).

    Example:
        raise ConflictError("Patient with this CPF already exists", {"cpf": cpf})
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
    ):
        conflict_details = details or {}
        detail_code = code or conflict_details.get("code")
        super().__init__(message, 409, "CONFLICT", conflict_details)
        # Preserve domain-specific conflict details (for example,
        # duplicate_patient) without changing the top-level HTTP error class.
        if detail_code:
            self.code = detail_code
            self.details["code"] = detail_code
            self.error_code = "CONFLICT"


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
    External service integration error with compatibility constructors.

    Supports legacy call signatures:
    - (service_name, error_message)
    - (message, service, status_code)
    - (message, service_name=..., error_code=..., is_recoverable=..., retry_after=...)
    - (message)
    """

    def __init__(
        self,
        *args: Any,
        service_name: Optional[str] = None,
        error_message: Optional[str] = None,
        service: Optional[str] = None,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        is_recoverable: bool = True,
        retry_after: Optional[int] = None,
        patient_id: Optional[Any] = None,
        flow_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        parsed_service = service_name or service
        parsed_status_code = status_code if status_code is not None else 503
        parsed_error_code = error_code or "EXTERNAL_SERVICE_ERROR"
        parsed_message: Optional[str] = None
        legacy_service_error_pair = False
        status_code_explicit = status_code is not None

        if args:
            if len(args) == 1:
                parsed_message = str(args[0])
            elif len(args) == 2:
                if (
                    service_name is None
                    and service is None
                    and error_message is None
                    and status_code is None
                ):
                    # Legacy core signature: (service_name, error_message)
                    legacy_service_error_pair = True
                    parsed_service = str(args[0])
                    parsed_message = str(args[1])
                else:
                    # Legacy external_service signature: (message, service)
                    parsed_message = str(args[0])
                    parsed_service = parsed_service or str(args[1])
            else:
                # Legacy external_service signature: (message, service, status_code)
                parsed_message = str(args[0])
                parsed_service = parsed_service or str(args[1])
                if status_code is None:
                    try:
                        parsed_status_code = int(args[2])
                        status_code_explicit = True
                    except (TypeError, ValueError):
                        parsed_status_code = 503
        elif error_message is not None:
            parsed_message = error_message

        if parsed_message is None:
            parsed_message = "External service integration failed"

        if legacy_service_error_pair and parsed_service:
            public_message = f"{parsed_service} service error: {parsed_message}"
            underlying_error = parsed_message
        else:
            public_message = parsed_message
            underlying_error = parsed_message

        exception_details: Dict[str, Any] = {}
        if details:
            exception_details.update(details)
        if context:
            exception_details.update(context)
        if parsed_service:
            exception_details.setdefault("service", parsed_service)
            exception_details.setdefault("service_name", parsed_service)
        if retry_after is not None:
            exception_details["retry_after"] = retry_after
        if patient_id is not None:
            exception_details.setdefault("patient_id", str(patient_id))
        if flow_type:
            exception_details.setdefault("flow_type", flow_type)
        if underlying_error:
            exception_details.setdefault("error", underlying_error)
        if status_code is not None:
            exception_details.setdefault("status_code", parsed_status_code)

        super().__init__(
            public_message,
            status_code=parsed_status_code,
            error_code=parsed_error_code,
            details=exception_details or None,
        )
        self.service_name = parsed_service
        self.service = parsed_service
        self.is_recoverable = is_recoverable
        self.retry_after = retry_after
        self.patient_id = patient_id
        self.flow_type = flow_type
        self.context = self.details
        self.external_error_code = error_code
        self._status_code_explicit = status_code_explicit

    def __str__(self) -> str:
        parts = [self.message]
        if self.service_name:
            parts.insert(0, f"[{self.service_name}]")
        if self._status_code_explicit and self.status_code:
            parts.append(f"(Status: {self.status_code})")
        return " ".join(parts)


class DatabaseError(HormoniaException):
    """
    Database operation error.

    Use for database-level errors (not business logic errors).

    Example:
        raise DatabaseError("Connection pool exhausted", {"pool_size": 10})
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        table: Optional[str] = None,
        patient_id: Optional[Any] = None,
        is_recoverable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details.copy() if details else {}
        if operation:
            error_details.setdefault("operation", operation)
        if table:
            error_details.setdefault("table", table)
        if patient_id is not None:
            error_details.setdefault("patient_id", str(patient_id))

        super().__init__(message, error_details or None)
        self.operation = operation or "unknown"
        self.table = table
        self.patient_id = patient_id
        self.is_recoverable = is_recoverable


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
        patient_id: Optional[Any] = None,
        flow_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        field: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize flow exception.

        Args:
            message: Error message
            patient_id: Patient ID (if applicable)
            flow_type: Flow type (e.g., "ONBOARDING", "QUIZ")
            details: Additional context
        """
        flow_details: Dict[str, Any] = {}
        if details:
            flow_details.update(details)
        if context:
            flow_details.update(context)
        if patient_id is not None:
            flow_details["patient_id"] = patient_id
        if flow_type:
            flow_details["flow_type"] = flow_type

        super().__init__(
            message,
            details=flow_details or None,
            code=code,
            field=field,
            **kwargs,
        )
        self.patient_id = patient_id
        self.flow_type = flow_type
        self.context = self.details


class FlowStateNotFoundError(FlowException):
    """Flow state not found for patient."""

    pass


class FlowValidationError(FlowException):
    """Flow validation failed."""

    def __init__(
        self,
        message: str,
        validation_errors: Optional[Dict[str, str]] = None,
        patient_id: Optional[Any] = None,
        flow_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        merged_context = context.copy() if context else {}
        if validation_errors is not None:
            merged_context["validation_errors"] = validation_errors

        super().__init__(
            message,
            patient_id=patient_id,
            flow_type=flow_type,
            context=merged_context or None,
        )
        self.validation_errors = validation_errors or {}


class FlowStateConflictError(FlowException):
    """Flow state conflict (e.g., invalid transition)."""

    pass


class FlowOperationError(FlowException):
    """Flow operation failed."""

    pass


class MessageDeliveryError(FlowException):
    """Exception raised when message delivery fails."""

    def __init__(
        self,
        message: str,
        patient_id: Any,
        message_id: Optional[Any] = None,
        retry_count: int = 0,
        last_error: Optional[str] = None,
    ):
        context = {"message_id": message_id, "retry_count": retry_count}
        if last_error is not None:
            context["last_error"] = last_error
        super().__init__(message, patient_id=patient_id, context=context)
        self.message_id = message_id
        self.retry_count = retry_count
        self.last_error = last_error


class FlowStateCorruptionError(FlowException):
    """Exception raised when flow state data is corrupted or invalid."""

    def __init__(
        self,
        message: str,
        patient_id: Any,
        flow_state_data: Optional[Dict[str, Any]] = None,
        corruption_type: str = "unknown",
    ):
        context = {
            "flow_state_data": flow_state_data,
            "corruption_type": corruption_type,
        }
        super().__init__(message, patient_id=patient_id, context=context)
        self.flow_state_data = flow_state_data
        self.corruption_type = corruption_type


class FlowProcessingError(FlowException):
    """Exception raised during flow processing operations."""

    def __init__(
        self,
        message: str,
        patient_id: Any,
        flow_type: str,
        current_day: Optional[int] = None,
        operation: Optional[str] = None,
    ):
        context: Dict[str, Any] = {}
        if current_day is not None:
            context["current_day"] = current_day
        if operation is not None:
            context["operation"] = operation
        super().__init__(
            message,
            patient_id=patient_id,
            flow_type=flow_type,
            context=context or None,
        )
        self.current_day = current_day
        self.operation = operation


class TemplateLoadError(FlowException):
    """Exception raised when flow templates cannot be loaded."""

    def __init__(
        self,
        message: str,
        template_path: str,
        flow_type: Optional[str] = None,
    ):
        super().__init__(
            message,
            flow_type=flow_type,
            context={"template_path": template_path},
        )
        self.template_path = template_path


class AIServiceError(ExternalServiceError):
    """Exception raised when AI services fail."""

    def __init__(
        self,
        message: str,
        ai_service: str,
        prompt: Optional[str] = None,
        error_code: Optional[str] = None,
        is_recoverable: bool = True,
    ):
        context = {"prompt": prompt} if prompt is not None else None
        super().__init__(
            message,
            service_name=ai_service,
            error_code=error_code,
            is_recoverable=is_recoverable,
            context=context,
        )
        self.ai_service = ai_service
        self.prompt = prompt


class FeatureNotAvailableError(AIServiceError):
    """Raised when a required AI feature (LangGraph graph) returns no usable output.

    This exception replaces silent None fallbacks. It signals to the caller
    that the feature failed explicitly, enabling Sentry capture and retry logic.

    Never shown to patients -- used for backend/ops visibility only.
    """

    def __init__(
        self,
        message: str,
        graph_name: str,
        operation: Optional[str] = None,
    ):
        super().__init__(
            message,
            ai_service=f"langgraph:{graph_name}",
            error_code="FEATURE_NOT_AVAILABLE",
            is_recoverable=True,
        )
        self.graph_name = graph_name
        self.operation = operation


class RedisConnectionError(ExternalServiceError):
    """Exception raised when Redis connection fails."""

    def __init__(self, message: str, operation: str, key: Optional[str] = None):
        context = {"operation": operation}
        if key is not None:
            context["key"] = key
        super().__init__(
            message,
            service_name="redis",
            is_recoverable=True,
            context=context,
        )
        self.operation = operation
        self.key = key


class ConcurrencyError(FlowException):
    """Exception raised when concurrent flow operations conflict."""

    def __init__(self, message: str, patient_id: Any, conflicting_operation: str):
        super().__init__(
            message,
            patient_id=patient_id,
            context={"conflicting_operation": conflicting_operation},
        )
        self.conflicting_operation = conflicting_operation


class APITimeoutError(ExternalServiceError):
    """Exception raised when an API call times out."""

    def __init__(self, message: str = "API request timed out", service: Optional[str] = None):
        super().__init__(message, service=service, status_code=408)


class APIRateLimitError(ExternalServiceError):
    """Exception raised when API rate limit is exceeded."""

    def __init__(self, message: str = "API rate limit exceeded", service: Optional[str] = None):
        super().__init__(message, service=service, status_code=429)


class APIAuthenticationError(ExternalServiceError):
    """Exception raised for API authentication failures."""

    def __init__(self, message: str = "API authentication failed", service: Optional[str] = None):
        super().__init__(message, service=service, status_code=401)


class APIResponseError(ExternalServiceError):
    """Exception raised for invalid API responses."""

    def __init__(
        self,
        message: str = "Invalid API response",
        service: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        super().__init__(message, service=service, status_code=status_code)


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

    Use for errors during AI operations (Gemini, etc.).

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
    "BusinessRuleError",
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
    "APITimeoutError",
    "APIRateLimitError",
    "APIAuthenticationError",
    "APIResponseError",
    "DatabaseError",
    "ProcessingError",
    # Flow Exceptions
    "FlowException",
    "FlowStateNotFoundError",
    "FlowValidationError",
    "FlowStateConflictError",
    "FlowOperationError",
    "MessageDeliveryError",
    "FlowStateCorruptionError",
    "FlowProcessingError",
    "TemplateLoadError",
    "AIServiceError",
    "RedisConnectionError",
    "ConcurrencyError",
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
