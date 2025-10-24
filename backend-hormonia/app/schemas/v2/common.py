"""
Common schemas for API v2
Shared models for pagination, field selection, and eager loading.
"""

from typing import Generic, TypeVar, Optional, List, Any, Dict, Set
from pydantic import BaseModel, Field, validator
from datetime import datetime
import base64
import json

T = TypeVar("T")


class CursorEncoder:
    """Encode/decode pagination cursors."""
    
    @staticmethod
    def encode(last_id: int, last_created_at: datetime) -> str:
        """
        Encode cursor from last item.
        
        Args:
            last_id: ID of the last item
            last_created_at: Created timestamp of the last item
            
        Returns:
            Base64-encoded cursor string
        """
        payload = {"id": last_id, "created_at": last_created_at.isoformat()}
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    
    @staticmethod
    def decode(cursor: str) -> Dict[str, Any]:
        """
        Decode cursor to filter params.
        
        Args:
            cursor: Base64-encoded cursor string
            
        Returns:
            Dictionary with cursor data
            
        Raises:
            ValueError: If cursor is invalid
        """
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            return payload
        except Exception as e:
            raise ValueError(f"Invalid cursor format: {str(e)}")


class FieldSelector:
    """Handle field selection for responses."""
    
    @staticmethod
    def parse_fields(fields_str: Optional[str]) -> Optional[Set[str]]:
        """
        Parse comma-separated fields string.
        
        Args:
            fields_str: Comma-separated field names
            
        Returns:
            Set of field names or None for all fields
        """
        if not fields_str:
            return None
        return set(f.strip() for f in fields_str.split(',') if f.strip())
    
    @staticmethod
    def filter_dict(data: Dict[str, Any], fields: Optional[Set[str]]) -> Dict[str, Any]:
        """
        Filter dictionary to include only specified fields.
        
        Args:
            data: Full response data
            fields: Set of fields to include (None = all fields)
            
        Returns:
            Filtered dictionary
        """
        if not fields:
            return data
        return {k: v for k, v in data.items() if k in fields}
    
    @staticmethod
    def validate_fields(fields: Set[str], allowed: Set[str]) -> None:
        """
        Validate that requested fields are allowed.
        
        Args:
            fields: Requested fields
            allowed: Allowed fields
            
        Raises:
            ValueError: If any requested field is not allowed
        """
        invalid = fields - allowed
        if invalid:
            raise ValueError(f"Invalid fields: {', '.join(invalid)}")


class PaginationParams(BaseModel):
    """Cursor-based pagination parameters"""
    
    cursor: Optional[str] = Field(None, description="Cursor for next page")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    
    class Config:
        json_schema_extra = {
            "example": {
                "cursor": "eyJpZCI6MTIzfQ==",
                "limit": 20
            }
        }


class CursorPaginatedResponse(BaseModel, Generic[T]):
    """Generic cursor-paginated response"""
    
    data: List[T]
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(description="Whether more items exist")
    total: Optional[int] = Field(None, description="Total count (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "next_cursor": "eyJpZCI6MTQzfQ==",
                "has_more": True,
                "total": 150
            }
        }


class FieldSelection(BaseModel):
    """Field selection for sparse fieldsets"""
    
    fields: Optional[List[str]] = Field(None, description="Fields to include")
    
    @validator("fields")
    def validate_fields(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("fields cannot be empty list")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "fields": ["id", "name", "email"]
            }
        }


class EagerLoadParams(BaseModel):
    """Eager loading parameters for relationships"""
    
    include: Optional[List[str]] = Field(None, description="Relations to include")
    
    @validator("include")
    def validate_include(cls, v):
        allowed = {"doctor", "quizzes", "templates", "analytics"}
        if v is not None:
            invalid = set(v) - allowed
            if invalid:
                raise ValueError(f"Invalid relations: {invalid}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "include": ["doctor", "quizzes"]
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    
    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable message")
    details: Optional[Any] = Field(None, description="Additional details")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid field selection",
                "details": {"fields": ["invalid_field"]},
                "request_id": "req_123abc"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    
    status: str = Field(description="Service status")
    version: str = Field(description="API version")
    timestamp: str = Field(description="Current timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "2.0.0",
                "timestamp": "2025-01-17T15:00:00Z"
            }
        }
