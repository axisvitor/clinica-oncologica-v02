
"""
Pagination utilities for standardized responses
"""
from typing import List, TypeVar, Generic
from pydantic import BaseModel
from app.schemas.common import PaginationParams

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated response format."""
    items: List[T]
    total: int
    page: int
    pages: int
    size: int
    has_next: bool
    has_previous: bool
    
    @classmethod
    def create(cls, items: List[T], total: int, pagination: PaginationParams):
        """Create paginated response from items and pagination params."""
        page = (pagination.skip // pagination.limit) + 1 if pagination.limit > 0 else 1
        pages = (total + pagination.limit - 1) // pagination.limit if pagination.limit > 0 else 1
        
        return cls(
            items=items,
            total=total,
            page=page,
            pages=pages,
            size=pagination.limit,
            has_next=page < pages,
            has_previous=page > 1
        )

def convert_pagination_params(pagination: PaginationParams) -> dict:
    """Convert PaginationParams to various formats for compatibility."""
    page = (pagination.skip // pagination.limit) + 1 if pagination.limit > 0 else 1
    
    return {
        # Standard format
        "skip": pagination.skip,
        "limit": pagination.limit,
        
        # Page-based format
        "page": page,
        "size": pagination.limit,
        "per_page": pagination.limit,
        
        # Offset-based format
        "offset": pagination.skip,
        "count": pagination.limit
    }
