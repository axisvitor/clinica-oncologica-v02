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
    """Handle FastAPI/Pydantic validation errors."""
    # Sanitize errors to ensure they are JSON serializable
    # Pydantic v2 often includes raw exception objects in ctx['error']
    errors = exc.errors()
    for error in errors:
        if "ctx" in error and isinstance(error["ctx"], dict):
            for key, value in error["ctx"].items():
                if isinstance(value, Exception):
                    error["ctx"][key] = str(value)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Input validation failed",
            "details": {"errors": errors},
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
