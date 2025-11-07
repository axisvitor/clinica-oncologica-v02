"""
Messages API v2 - Template Management
Handles message template operations: list, get, create, update, and delete templates.

5 endpoints:
- GET "/templates" - List message templates
- GET "/templates/{template_id}" - Get a specific message template
- POST "/templates" - Create a new message template
- PUT "/templates/{template_id}" - Update a message template
- DELETE "/templates/{template_id}" - Delete a message template

Note: Templates feature is not yet fully implemented in the database.
These are stub endpoints that return "not implemented" responses.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.v2.messages import (
    MessageTemplateV2Response,
    MessageTemplateV2List,
)
from ..dependencies import get_pagination_params
from app.dependencies.auth_dependencies import get_current_user_from_session

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Template Operations (5 endpoints)
# ============================================================================

@router.get(
    "/templates",
    response_model=MessageTemplateV2List,
    summary="List message templates",
    description="Get list of message templates (feature not yet implemented)"
)
async def list_templates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
):
    """List message templates (stub implementation)."""
    # Templates are not yet implemented in the database
    # Return empty list for now
    return {
        "data": [],
        "next_cursor": None,
        "has_more": False,
        "total": 0,
    }


@router.get(
    "/templates/{template_id}",
    response_model=MessageTemplateV2Response,
    summary="Get message template",
    description="Get a specific message template (feature not yet implemented)"
)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Get a message template (stub implementation)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Message templates feature not yet implemented"
    )


@router.post(
    "/templates",
    response_model=MessageTemplateV2Response,
    summary="Create message template",
    description="Create a new message template (feature not yet implemented)"
)
async def create_template(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Create a message template (stub implementation)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Message templates feature not yet implemented"
    )


@router.put(
    "/templates/{template_id}",
    response_model=MessageTemplateV2Response,
    summary="Update message template",
    description="Update a message template (feature not yet implemented)"
)
async def update_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Update a message template (stub implementation)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Message templates feature not yet implemented"
    )


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete message template",
    description="Delete a message template (feature not yet implemented)"
)
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Delete a message template (stub implementation)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Message templates feature not yet implemented"
    )
