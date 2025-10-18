"""
Dependencies for API v2
Shared dependencies for pagination, field selection, and eager loading.
"""

from typing import Optional, List
from fastapi import Query, HTTPException, status
import base64
import json


def get_pagination_params(
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Extract and validate cursor-based pagination parameters.
    
    Args:
        cursor: Base64-encoded cursor string
        limit: Number of items per page (1-100)
    
    Returns:
        dict: Decoded cursor data and limit
    
    Raises:
        HTTPException: If cursor is invalid
    """
    cursor_data = None
    
    if cursor:
        try:
            decoded = base64.b64decode(cursor).decode("utf-8")
            cursor_data = json.loads(decoded)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cursor format: {str(e)}"
            )
    
    return {
        "cursor_data": cursor_data,
        "limit": limit
    }


def get_field_selection(
    fields: Optional[str] = Query(None, description="Comma-separated fields to include")
):
    """
    Extract and validate field selection parameters.
    
    Args:
        fields: Comma-separated list of field names
    
    Returns:
        Optional[List[str]]: List of fields or None for all fields
    
    Raises:
        HTTPException: If fields parameter is invalid
    """
    if not fields:
        return None
    
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    
    if not field_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fields parameter cannot be empty"
        )
    
    return field_list


def get_eager_load_params(
    include: Optional[str] = Query(None, description="Comma-separated relations to include")
):
    """
    Extract and validate eager loading parameters.
    
    Args:
        include: Comma-separated list of relation names
    
    Returns:
        Optional[List[str]]: List of relations or None
    
    Raises:
        HTTPException: If include parameter contains invalid relations
    """
    if not include:
        return None
    
    relation_list = [r.strip() for r in include.split(",") if r.strip()]
    
    if not relation_list:
        return None
    
    # Validate allowed relations (can be customized per endpoint)
    allowed_relations = {"doctor", "quizzes", "templates", "analytics", "patient"}
    invalid_relations = set(relation_list) - allowed_relations
    
    if invalid_relations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid relations: {', '.join(invalid_relations)}"
        )
    
    return relation_list


def create_cursor(last_id: int) -> str:
    """
    Create a base64-encoded cursor from the last item ID.
    
    Args:
        last_id: ID of the last item in the current page
    
    Returns:
        str: Base64-encoded cursor
    """
    cursor_data = {"id": last_id}
    cursor_json = json.dumps(cursor_data)
    return base64.b64encode(cursor_json.encode("utf-8")).decode("utf-8")


def apply_field_selection(data: dict, fields: Optional[List[str]]) -> dict:
    """
    Apply field selection to response data.
    
    Args:
        data: Full response data
        fields: List of fields to include (None = all fields)
    
    Returns:
        dict: Filtered data with only selected fields
    """
    if not fields:
        return data
    
    return {k: v for k, v in data.items() if k in fields}
