from datetime import datetime, timezone
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    HormoniaException,
    APIException,
)


async def hormonia_exception_handler(request: Request, exc: HormoniaException):
    """Handle base Hormonia exceptions."""
    return JSONResponse(
        status_code=500,
        content=exc.to_dict(),
    )


async def api_exception_handler(request: Request, exc: APIException):
    """Handle API exceptions with specific status codes."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle FastAPI/Pydantic validation errors with detailed field information.
    Ensures JSON serializability by extracting only necessary fields and
    stringifying any non-serializable objects.
    """
    request_id = getattr(request.state, "request_id", None)

    # Format validation errors into a cleaner structure for frontend consumption
    errors = []
    for error in exc.errors():
        # Build field path (e.g., "body.patient.cpf")
        field_path = ".".join(str(loc) for loc in error["loc"])

        # Extract message and type
        msg = error.get("msg", "Unknown validation error")
        error_type = error.get("type", "value_error")

        # Sanitize context if present (ensure no raw Exception objects)
        details = {}
        if "ctx" in error and isinstance(error["ctx"], dict):
            for key, value in error["ctx"].items():
                details[key] = str(value) if isinstance(value, Exception) else value

        errors.append(
            {
                "field": field_path,
                "message": msg,
                "type": error_type,
                "details": details if details else None,
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Input validation failed",
            "details": {"errors": errors},
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle standard HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code,
        },
    )


def register_exception_handlers(app):
    """Register all exception handlers to the FastAPI app."""
    app.add_exception_handler(HormoniaException, hormonia_exception_handler)
    app.add_exception_handler(APIException, api_exception_handler)

    # Register specific subclasses if needed, though APIException covers them
    # (FastAPI uses isinstance check, so base class handler works)

    # Override default handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
