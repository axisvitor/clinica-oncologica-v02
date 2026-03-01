"""
Common schemas used across the application.
"""

from typing import Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field
from app.utils.timezone import now_sao_paulo_naive


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(
        100, ge=1, le=200, description="Maximum number of items to return"
    )


class PaginatedResponse(BaseModel):
    """Base paginated response format."""

    total: int = Field(..., description="Total number of items")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")
    has_next: bool = Field(..., description="Whether there are more items")
    has_previous: bool = Field(..., description="Whether there are previous items")

    @classmethod
    def create(cls, items: list, total: int, skip: int, limit: int):
        """Create paginated response with calculated pagination info."""
        return cls(
            total=total,
            skip=skip,
            limit=limit,
            has_next=skip + len(items) < total,
            has_previous=skip > 0,
        )


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human readable error message")
    details: Optional[dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Error timestamp"
    )


class ValidationErrorResponse(BaseModel):
    """Validation error response format."""

    error: str = Field("validation_error", description="Error code")
    message: str = Field(..., description="Human readable error message")
    field_errors: dict[str, list[str]] = Field(
        ..., description="Field-specific validation errors"
    )
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Error timestamp"
    )


class NotFoundErrorResponse(BaseModel):
    """Not found error response format."""

    error: str = Field("not_found", description="Error code")
    message: str = Field(..., description="Human readable error message")
    resource_type: str = Field(..., description="Type of resource not found")
    resource_id: Optional[str] = Field(None, description="ID of resource not found")
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Error timestamp"
    )


class UnauthorizedErrorResponse(BaseModel):
    """Unauthorized error response format."""

    error: str = Field("unauthorized", description="Error code")
    message: str = Field(
        "Authentication required", description="Human readable error message"
    )
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Error timestamp"
    )


class ForbiddenErrorResponse(BaseModel):
    """Forbidden error response format."""

    error: str = Field("forbidden", description="Error code")
    message: str = Field(
        "Insufficient permissions", description="Human readable error message"
    )
    required_permissions: Optional[list[str]] = Field(
        None, description="Required permissions"
    )
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Error timestamp"
    )


class ConflictErrorResponse(BaseModel):
    """Conflict error response format."""

    error: str = Field("conflict", description="Error code")
    message: str = Field(..., description="Human readable error message")
    conflicting_resource: Optional[str] = Field(
        None, description="Conflicting resource identifier"
    )
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Error timestamp"
    )


class RateLimitErrorResponse(BaseModel):
    """Rate limit error response format."""

    error: str = Field("rate_limit_exceeded", description="Error code")
    message: str = Field(
        "Rate limit exceeded", description="Human readable error message"
    )
    retry_after: int = Field(..., description="Seconds to wait before retrying")
    limit: int = Field(..., description="Rate limit threshold")
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Error timestamp"
    )


class ServiceUnavailableErrorResponse(BaseModel):
    """Service unavailable error response format."""

    error: str = Field("service_unavailable", description="Error code")
    message: str = Field(
        "Service temporarily unavailable", description="Human readable error message"
    )
    retry_after: Optional[int] = Field(
        None, description="Seconds to wait before retrying"
    )
    maintenance_mode: bool = Field(
        False, description="Whether service is in maintenance mode"
    )
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Error timestamp"
    )


class SuccessResponse(BaseModel):
    """Standard success response format."""

    status: str = Field("success", description="Response status")
    message: str = Field(..., description="Success message")
    data: Optional[dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Response timestamp"
    )


class HealthCheckResponse(BaseModel):
    """Health check response format."""

    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(
        default_factory=now_sao_paulo_naive, description="Check timestamp"
    )
    version: Optional[str] = Field(None, description="Application version")
    dependencies: Optional[dict[str, str]] = Field(
        None, description="Dependency status"
    )


__all__ = [
    "PaginationParams",
    "PaginatedResponse",
    "ErrorResponse",
    "ValidationErrorResponse",
    "NotFoundErrorResponse",
    "UnauthorizedErrorResponse",
    "ForbiddenErrorResponse",
    "ConflictErrorResponse",
    "RateLimitErrorResponse",
    "ServiceUnavailableErrorResponse",
    "SuccessResponse",
    "HealthCheckResponse",
]
