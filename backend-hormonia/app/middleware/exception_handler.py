"""
Global Exception Handler Middleware for FastAPI.

This middleware provides consistent error response formatting across all endpoints,
ensuring that all exceptions are properly caught and returned in a standard format.

Reference: LOW-017 - Inconsistent Error Handling

Features:
- Catches all application exceptions (APIException hierarchy)
- Handles Pydantic validation errors
- Handles SQLAlchemy database errors
- Handles generic Python exceptions with appropriate status codes
- Provides detailed error responses in development mode
- Logs all exceptions for debugging

Usage:
    from fastapi import FastAPI
    from app.middleware.exception_handler import setup_exception_handlers

    app = FastAPI()
    setup_exception_handlers(app)
"""

from typing import Dict, Any
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import (
    APIException,
    HormoniaException,
)

logger = logging.getLogger(__name__)


# =========================================================================
# EXCEPTION RESPONSE FORMATTERS
# =========================================================================


def format_error_response(
    error_code: str, message: str, status_code: int, details: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Format a standardized error response.

    Args:
        error_code: Machine-readable error code (e.g., "VALIDATION_ERROR")
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details

    Returns:
        Standardized error response dictionary
    """
    response = {"error": error_code, "message": message, "status_code": status_code}

    if details:
        response["details"] = details

    return response


def format_validation_error_response(errors: list) -> Dict[str, Any]:
    """
    Format Pydantic validation errors into standard format.

    Args:
        errors: List of Pydantic validation errors

    Returns:
        Formatted error response
    """
    formatted_errors = {}

    for error in errors:
        # Get field path (e.g., ["body", "birth_date"] -> "birth_date")
        field_path = ".".join(str(loc) for loc in error["loc"] if loc != "body")

        # Get error message
        error_msg = error["msg"]

        # Store in dict
        formatted_errors[field_path] = error_msg

    return format_error_response(
        error_code="VALIDATION_ERROR",
        message="Input validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": formatted_errors},
    )


# =========================================================================
# EXCEPTION HANDLERS
# =========================================================================


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    Handle all APIException instances (ValidationError, NotFoundError, etc.).

    Args:
        request: FastAPI request object
        exc: APIException instance

    Returns:
        JSONResponse with standardized error format
    """
    logger.warning(
        f"API Exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def hormonia_exception_handler(
    request: Request, exc: HormoniaException
) -> JSONResponse:
    """
    Handle generic HormoniaException (non-API exceptions).

    Args:
        request: FastAPI request object
        exc: HormoniaException instance

    Returns:
        JSONResponse with 500 Internal Server Error
    """
    logger.error(
        f"Hormonia Exception: {exc.message}",
        extra={
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(
            error_code="INTERNAL_ERROR",
            message=exc.message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=exc.details,
        ),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic RequestValidationError (422 Unprocessable Entity).

    Args:
        request: FastAPI request object
        exc: RequestValidationError instance

    Returns:
        JSONResponse with formatted validation errors
    """
    logger.warning(
        f"Validation Error: {len(exc.errors())} validation errors",
        extra={
            "errors": exc.errors(),
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=format_validation_error_response(exc.errors()),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTPException.

    Args:
        request: FastAPI request object
        exc: HTTPException instance

    Returns:
        JSONResponse with standardized error format
    """
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
        },
    )

    # Determine error code from status code
    error_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }

    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            error_code=error_code, message=str(exc.detail), status_code=exc.status_code
        ),
    )


async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """
    Handle SQLAlchemy IntegrityError (duplicate keys, constraint violations).

    Args:
        request: FastAPI request object
        exc: IntegrityError instance

    Returns:
        JSONResponse with 409 Conflict
    """
    logger.warning(
        f"Database Integrity Error: {str(exc)}",
        extra={"path": request.url.path, "method": request.method},
        exc_info=True,
    )

    # Parse common constraint violations
    error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)

    # Check for unique constraint violations
    if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
        # Extract field name if possible
        field = None
        if "uq_patient_cpf_doctor" in error_msg:
            field = "cpf"
        elif "uq_patient_email_doctor" in error_msg:
            field = "email"
        elif "uq_patient_phone_doctor" in error_msg:
            field = "phone"

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=format_error_response(
                error_code="DUPLICATE_RESOURCE",
                message="Resource already exists",
                status_code=status.HTTP_409_CONFLICT,
                details={"field": field} if field else None,
            ),
        )

    # Generic integrity error
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=format_error_response(
            error_code="INTEGRITY_ERROR",
            message="Database integrity constraint violated",
            status_code=status.HTTP_400_BAD_REQUEST,
        ),
    )


async def sqlalchemy_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handle generic SQLAlchemy errors.

    Args:
        request: FastAPI request object
        exc: SQLAlchemyError instance

    Returns:
        JSONResponse with 500 Internal Server Error
    """
    logger.error(
        f"Database Error: {str(exc)}",
        extra={"path": request.url.path, "method": request.method},
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(
            error_code="DATABASE_ERROR",
            message="An error occurred while accessing the database",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all unhandled exceptions (catch-all).

    Args:
        request: FastAPI request object
        exc: Exception instance

    Returns:
        JSONResponse with 500 Internal Server Error
    """
    logger.error(
        f"Unhandled Exception: {type(exc).__name__} - {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    )


# =========================================================================
# SETUP FUNCTION
# =========================================================================


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.

    This function should be called during application startup.

    Args:
        app: FastAPI application instance

    Example:
        from fastapi import FastAPI
        from app.middleware.exception_handler import setup_exception_handlers

        app = FastAPI()
        setup_exception_handlers(app)
    """
    # Application-specific exceptions (highest priority)
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(HormoniaException, hormonia_exception_handler)

    # FastAPI built-in exceptions
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Database exceptions
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)

    # Catch-all for unexpected exceptions (lowest priority)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Exception handlers registered successfully")


__all__ = [
    "setup_exception_handlers",
    "format_error_response",
    "format_validation_error_response",
]
