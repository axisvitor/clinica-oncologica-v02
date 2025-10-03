"""
Pagination utilities for API responses.
Provides standardized pagination functionality with efficient database queries.
"""
from typing import Optional, List, Dict, Any, TypeVar, Generic
from math import ceil
from sqlalchemy.orm import Query, Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from uuid import UUID

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.size


class SortParams(BaseModel):
    """Standard sorting parameters."""
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        size: int
    ) -> "PaginatedResponse[T]":
        """Create paginated response with calculated fields."""
        pages = ceil(total / size) if size > 0 else 0

        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1
        )


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    current_page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next_page: bool
    has_previous_page: bool
    next_page: Optional[int]
    previous_page: Optional[int]


def paginate_query(
    query: Query,
    page: int = 1,
    size: int = 20,
    max_size: int = 100
) -> tuple[List[Any], PaginationMeta]:
    """
    Paginate a SQLAlchemy query with metadata.

    Args:
        query: SQLAlchemy query to paginate
        page: Page number (1-based)
        size: Items per page
        max_size: Maximum allowed page size

    Returns:
        Tuple of (items, pagination_meta)
    """
    # Validate parameters
    page = max(1, page)
    size = min(max(1, size), max_size)

    # Calculate offset
    offset = (page - 1) * size

    # Get total count
    total_items = query.count()

    # Get paginated items
    items = query.offset(offset).limit(size).all()

    # Calculate pagination metadata
    total_pages = ceil(total_items / size) if size > 0 else 0
    has_next_page = page < total_pages
    has_previous_page = page > 1
    next_page = page + 1 if has_next_page else None
    previous_page = page - 1 if has_previous_page else None

    meta = PaginationMeta(
        current_page=page,
        per_page=size,
        total_items=total_items,
        total_pages=total_pages,
        has_next_page=has_next_page,
        has_previous_page=has_previous_page,
        next_page=next_page,
        previous_page=previous_page
    )

    return items, meta


async def paginate_async_query(
    db: Session,
    base_query: Query,
    page: int = 1,
    size: int = 20,
    max_size: int = 100
) -> tuple[List[Any], PaginationMeta]:
    """
    Paginate a query asynchronously.

    Args:
        db: Database session
        base_query: Base SQLAlchemy query
        page: Page number (1-based)
        size: Items per page
        max_size: Maximum allowed page size

    Returns:
        Tuple of (items, pagination_meta)
    """
    return paginate_query(base_query, page, size, max_size)


def create_cursor_pagination(
    items: List[Any],
    cursor_field: str = "id",
    limit: int = 20,
    cursor: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create cursor-based pagination for efficient large dataset pagination.

    Args:
        items: List of items to paginate
        cursor_field: Field to use as cursor
        limit: Number of items per page
        cursor: Current cursor position

    Returns:
        Dictionary with paginated data and cursors
    """
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        if hasattr(last_item, cursor_field):
            next_cursor = str(getattr(last_item, cursor_field))

    return {
        "items": items,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "cursor_field": cursor_field
    }


class SearchParams(BaseModel):
    """Search parameters for filtering."""
    q: Optional[str] = Field(None, description="Search query")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Additional filters")


class ListParams(PaginationParams, SortParams, SearchParams):
    """Combined parameters for list endpoints."""
    pass


def apply_search_filters(
    query: Query,
    search_params: SearchParams,
    searchable_fields: List[str]
) -> Query:
    """
    Apply search filters to query.

    Args:
        query: SQLAlchemy query
        search_params: Search parameters
        searchable_fields: List of fields to search in

    Returns:
        Filtered query
    """
    if search_params.q and searchable_fields:
        # Create OR conditions for all searchable fields
        from sqlalchemy import or_
        search_conditions = []

        for field in searchable_fields:
            # Assume model has the field as attribute
            try:
                model_class = query.column_descriptions[0]['type']
                if hasattr(model_class, field):
                    attr = getattr(model_class, field)
                    if hasattr(attr.type, 'python_type') and attr.type.python_type == str:
                        search_conditions.append(attr.ilike(f"%{search_params.q}%"))
            except (IndexError, AttributeError):
                continue

        if search_conditions:
            query = query.filter(or_(*search_conditions))

    # Apply additional filters
    for field, value in search_params.filters.items():
        if value is not None:
            try:
                model_class = query.column_descriptions[0]['type']
                if hasattr(model_class, field):
                    attr = getattr(model_class, field)
                    query = query.filter(attr == value)
            except (IndexError, AttributeError):
                continue

    return query


def apply_sorting(
    query: Query,
    sort_params: SortParams,
    allowed_sort_fields: List[str]
) -> Query:
    """
    Apply sorting to query.

    Args:
        query: SQLAlchemy query
        sort_params: Sort parameters
        allowed_sort_fields: List of fields that can be sorted

    Returns:
        Sorted query
    """
    if sort_params.sort_by not in allowed_sort_fields:
        return query

    try:
        model_class = query.column_descriptions[0]['type']
        if hasattr(model_class, sort_params.sort_by):
            attr = getattr(model_class, sort_params.sort_by)
            if sort_params.sort_order.lower() == "desc":
                query = query.order_by(attr.desc())
            else:
                query = query.order_by(attr.asc())
    except (IndexError, AttributeError):
        pass

    return query


class PaginationHelper:
    """Helper class for common pagination operations."""

    @staticmethod
    def get_pagination_links(
        base_url: str,
        page: int,
        total_pages: int,
        size: int
    ) -> Dict[str, Optional[str]]:
        """Generate pagination links."""
        links = {
            "first": f"{base_url}?page=1&size={size}",
            "last": f"{base_url}?page={total_pages}&size={size}",
            "next": None,
            "prev": None
        }

        if page < total_pages:
            links["next"] = f"{base_url}?page={page + 1}&size={size}"

        if page > 1:
            links["prev"] = f"{base_url}?page={page - 1}&size={size}"

        return links

    @staticmethod
    def validate_pagination_params(
        page: Optional[int],
        size: Optional[int],
        default_size: int = 20,
        max_size: int = 100
    ) -> tuple[int, int]:
        """Validate and normalize pagination parameters."""
        if page is None or page < 1:
            page = 1

        if size is None or size < 1:
            size = default_size
        elif size > max_size:
            size = max_size

        return page, size


# Convenience functions for common pagination patterns

def paginate_patients(
    db: Session,
    page: int = 1,
    size: int = 20,
    search: Optional[str] = None,
    doctor_id: Optional[UUID] = None,
    flow_state: Optional[str] = None
):
    """Paginate patients with common filters."""
    from app.models.patient import Patient, FlowState

    query = db.query(Patient)

    # Apply filters
    if search:
        query = query.filter(Patient.name.ilike(f"%{search}%"))

    if doctor_id:
        query = query.filter(Patient.doctor_id == doctor_id)

    if flow_state is not None:
        try:
            state_enum = FlowState(flow_state)
            query = query.filter(Patient.flow_state == state_enum)
        except ValueError:
            # Invalid flow_state value, ignore filter
            pass

    # Default sorting
    query = query.order_by(Patient.created_at.desc())

    return paginate_query(query, page, size)


def paginate_messages(
    db: Session,
    patient_id: UUID,
    page: int = 1,
    size: int = 20,
    direction: Optional[str] = None
):
    """Paginate messages for a patient."""
    from app.models.message import Message

    query = db.query(Message).filter(Message.patient_id == patient_id)

    if direction:
        query = query.filter(Message.direction == direction)

    query = query.order_by(Message.created_at.desc())

    return paginate_query(query, page, size)


def paginate_alerts(
    db: Session,
    page: int = 1,
    size: int = 20,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    patient_id: Optional[UUID] = None
):
    """Paginate alerts with filters."""
    from app.models.alert import Alert

    query = db.query(Alert)

    if severity:
        query = query.filter(Alert.severity == severity)

    if status:
        query = query.filter(Alert.status == status)

    if patient_id:
        query = query.filter(Alert.patient_id == patient_id)

    query = query.order_by(Alert.created_at.desc())

    return paginate_query(query, page, size)