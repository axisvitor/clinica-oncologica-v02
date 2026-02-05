"""
Error Handler Utilities - Standard error handling patterns for the application.

This module provides standardized error handling utilities that integrate with
the comprehensive exception hierarchy in app.core.exceptions.

Usage:
    from app.utils.error_handlers import handle_service_error, handle_validation_error
    from app.core.exceptions import ValidationError

    try:
        # Your service logic
        result = service.do_something()
    except ValidationError as e:
        raise handle_validation_error(e)
    except Exception as e:
        raise handle_service_error(e, "do_something operation")

Author: Error Handling Standardization Team
Date: 2025-01-22
Version: 1.0.0
Reference: LOW-017 - Inconsistent Error Handling
"""

import logging
from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, status

from app.core.exceptions import (
    # Base exceptions
    APIException,
    HormoniaException,
    # HTTP exceptions
    ValidationError,
    NotFoundError,
    ExternalServiceError,
    DatabaseError,
    AIProcessingError,
    # Flow exceptions
    FlowException,
    FlowStateNotFoundError,
    FlowValidationError,
    FlowStateConflictError,
)

logger = logging.getLogger(__name__)


# =========================================================================
# ERROR HANDLER FUNCTIONS
# =========================================================================


def handle_api_exception(exc: APIException) -> HTTPException:
    """
    Convert APIException to FastAPI HTTPException.

    Args:
        exc: The APIException to convert

    Returns:
        HTTPException with proper status code and details

    Example:
        try:
            raise ValidationError("Invalid input", {"field": "email"})
        except APIException as e:
            raise handle_api_exception(e)
    """
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


def handle_validation_error(
    exc: Union[ValidationError, Exception],
    context: Optional[str] = None,
) -> HTTPException:
    """
    Handle validation errors with consistent formatting.

    Args:
        exc: ValidationError or generic Exception
        context: Optional context information for logging

    Returns:
        HTTPException with 422 status code

    Example:
        try:
            validate_email(email)
        except ValidationError as e:
            raise handle_validation_error(e, "email validation")
    """
    if isinstance(exc, ValidationError):
        logger.warning(f"Validation error{f' in {context}' if context else ''}: {exc.message}")
        return handle_api_exception(exc)

    # Convert generic exception to ValidationError
    logger.warning(f"Validation error{f' in {context}' if context else ''}: {exc}")
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "VALIDATION_ERROR",
            "message": str(exc),
            "details": {},
        },
    )


def handle_not_found_error(
    exc: Union[NotFoundError, Exception],
    resource: Optional[str] = None,
    identifier: Optional[Any] = None,
) -> HTTPException:
    """
    Handle not found errors with consistent formatting.

    Args:
        exc: NotFoundError or generic Exception
        resource: Resource type (e.g., "Patient")
        identifier: Resource identifier

    Returns:
        HTTPException with 404 status code

    Example:
        try:
            patient = get_patient(patient_id)
            if not patient:
                raise NotFoundError("Patient", patient_id)
        except NotFoundError as e:
            raise handle_not_found_error(e)
    """
    if isinstance(exc, NotFoundError):
        logger.info(f"Resource not found: {exc.resource} ({exc.identifier})")
        return handle_api_exception(exc)

    # Convert generic exception to NotFoundError
    resource_str = resource or "Resource"
    identifier_str = identifier or "unknown"
    logger.info(f"Resource not found: {resource_str} ({identifier_str})")

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "NOT_FOUND",
            "message": f"{resource_str} not found",
            "details": {"resource": resource_str, "identifier": str(identifier_str)},
        },
    )


def handle_service_error(
    exc: Exception,
    context: str,
    log_traceback: bool = True,
) -> HTTPException:
    """
    Handle generic service errors with proper logging and formatting.

    This is the catch-all error handler for unexpected errors.

    Args:
        exc: The exception that occurred
        context: Description of the operation that failed
        log_traceback: Whether to log full traceback

    Returns:
        HTTPException with appropriate status code

    Example:
        try:
            result = complex_operation()
        except ValidationError:
            raise  # Let specific handlers catch it
        except Exception as e:
            raise handle_service_error(e, "complex_operation")
    """
    # Handle known exception types
    if isinstance(exc, APIException):
        return handle_api_exception(exc)

    # Handle database errors
    if isinstance(exc, DatabaseError):
        logger.error(f"Database error in {context}: {exc}", exc_info=log_traceback)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "DATABASE_ERROR",
                "message": f"Database error during {context}",
                "details": exc.details if hasattr(exc, "details") else {},
            },
        )

    # Handle external service errors
    if isinstance(exc, ExternalServiceError):
        logger.error(f"External service error in {context}: {exc}", exc_info=log_traceback)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "EXTERNAL_SERVICE_ERROR",
                "message": f"External service error during {context}",
                "details": exc.details if hasattr(exc, "details") else {},
            },
        )

    # Handle AI processing errors
    if isinstance(exc, AIProcessingError):
        logger.error(f"AI processing error in {context}: {exc}", exc_info=log_traceback)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "AI_PROCESSING_ERROR",
                "message": f"AI processing failed during {context}",
                "details": exc.details if hasattr(exc, "details") else {},
            },
        )

    # Handle Hormonia exceptions
    if isinstance(exc, HormoniaException):
        logger.error(f"Application error in {context}: {exc}", exc_info=log_traceback)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    # Handle unknown errors
    logger.error(f"Unexpected error in {context}: {exc}", exc_info=log_traceback)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error": "INTERNAL_ERROR",
            "message": f"Internal error during {context}",
            "details": {},
        },
    )


def handle_flow_error(
    exc: Union[FlowException, Exception],
    context: str,
    patient_id: Optional[str] = None,
) -> HTTPException:
    """
    Handle flow-related errors with specialized logging.

    Args:
        exc: The flow exception
        context: Description of the flow operation
        patient_id: Optional patient identifier for logging

    Returns:
        HTTPException with appropriate status code

    Example:
        try:
            flow_state = get_flow_state(patient_id)
        except FlowStateNotFoundError as e:
            raise handle_flow_error(e, "get_flow_state", patient_id)
    """
    patient_info = f" for patient {patient_id}" if patient_id else ""

    if isinstance(exc, FlowStateNotFoundError):
        logger.info(f"Flow state not found{patient_info} in {context}")
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "FLOW_STATE_NOT_FOUND",
                "message": f"Flow state not found{patient_info}",
                "details": exc.details if hasattr(exc, "details") else {},
            },
        )

    if isinstance(exc, FlowValidationError):
        logger.warning(f"Flow validation error{patient_info} in {context}: {exc}")
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "FLOW_VALIDATION_ERROR",
                "message": str(exc),
                "details": exc.details if hasattr(exc, "details") else {},
            },
        )

    if isinstance(exc, FlowStateConflictError):
        logger.warning(f"Flow state conflict{patient_info} in {context}: {exc}")
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "FLOW_STATE_CONFLICT",
                "message": str(exc),
                "details": exc.details if hasattr(exc, "details") else {},
            },
        )

    if isinstance(exc, FlowException):
        logger.error(f"Flow error{patient_info} in {context}: {exc}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FLOW_ERROR",
                "message": str(exc),
                "details": exc.details if hasattr(exc, "details") else {},
            },
        )

    # Fall back to generic error handler
    return handle_service_error(exc, f"{context}{patient_info}")


def handle_ai_error(
    exc: Union[AIProcessingError, ExternalServiceError, Exception],
    context: str,
    operation: str,
) -> HTTPException:
    """
    Handle AI service errors with specialized logging and fallback handling.

    Args:
        exc: The AI-related exception
        context: Description of the context (e.g., "message humanization")
        operation: Specific operation that failed

    Returns:
        HTTPException with appropriate status code

    Example:
        try:
            response = ai_service.humanize_message(template, context)
        except AIProcessingError as e:
            raise handle_ai_error(e, "message_humanization", "humanize_message")
    """
    if isinstance(exc, AIProcessingError):
        logger.error(f"AI processing error in {context} ({operation}): {exc}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "AI_PROCESSING_ERROR",
                "message": f"AI service failed during {context}",
                "details": {
                    "operation": operation,
                    **(exc.details if hasattr(exc, "details") else {}),
                },
            },
        )

    if isinstance(exc, ExternalServiceError):
        logger.error(f"External AI service error in {context} ({operation}): {exc}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "EXTERNAL_SERVICE_ERROR",
                "message": f"External AI service unavailable during {context}",
                "details": {
                    "operation": operation,
                    **(exc.details if hasattr(exc, "details") else {}),
                },
            },
        )

    # Generic error
    logger.error(f"Unexpected error in AI {context} ({operation}): {exc}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error": "AI_ERROR",
            "message": f"Error during {context}",
            "details": {"operation": operation},
        },
    )


# =========================================================================
# RESPONSE HELPERS
# =========================================================================


def create_error_response(
    error_code: str,
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """
    Create a standardized error response.

    Args:
        error_code: Machine-readable error code (e.g., "VALIDATION_ERROR")
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details

    Returns:
        HTTPException with standardized format

    Example:
        raise create_error_response(
            "INVALID_OPERATION",
            "Cannot delete active template",
            status.HTTP_400_BAD_REQUEST,
            {"template_id": template_id}
        )
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error_code,
            "message": message,
            "details": details or {},
        },
    )


# =========================================================================
# EXPORTS
# =========================================================================

__all__ = [
    "handle_api_exception",
    "handle_validation_error",
    "handle_not_found_error",
    "handle_service_error",
    "handle_flow_error",
    "handle_ai_error",
    "create_error_response",
]
