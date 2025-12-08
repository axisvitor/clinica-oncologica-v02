"""
Messages API v2 - Template Management
Handles message template operations: list, get, create, update, and delete templates.

5 endpoints:
- GET "/templates" - List message templates
- GET "/templates/{template_id}" - Get a specific message template
- POST "/templates" - Create a new message template
- PUT "/templates/{template_id}" - Update a message template
- DELETE "/templates/{template_id}" - Delete a message template
"""

import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.template import MessageTemplate
from app.repositories.template import TemplateRepository
from app.schemas.v2.messages import (
    MessageTemplateV2Response,
    MessageTemplateV2List,
    MessageTemplateV2Create,
    MessageTemplateV2Update,
)
from ..dependencies import get_pagination_params, create_cursor
from app.dependencies.auth_dependencies import get_current_user_from_session

router = APIRouter()
logger = logging.getLogger(__name__)


def _template_to_response(template: MessageTemplate) -> dict:
    """Convert a MessageTemplate model to API response format."""
    return {
        "id": str(template.id),
        "name": template.name,
        "content": template.content,
        "variables": template.variables or [],
        "category": template.message_type or "text",  # Map message_type to category
        "language": "pt_BR",  # Default language (not in model)
        "is_active": template.is_active,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


# ============================================================================
# Template Operations (5 endpoints)
# ============================================================================

@router.get(
    "/templates",
    response_model=MessageTemplateV2List,
    summary="List message templates",
    description="Get paginated list of message templates with optional filtering."
)
async def list_templates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """
    List message templates with cursor pagination.

    Features:
    - Cursor-based pagination
    - Filter by active status
    - Filter by category (message_type)
    """
    try:
        cursor_data = pagination.get("cursor_data")
        limit = pagination.get("limit", 20)

        # Build query
        query = db.query(MessageTemplate)

        # Apply filters
        if is_active is not None:
            query = query.filter(MessageTemplate.is_active == is_active)

        if category:
            query = query.filter(MessageTemplate.message_type == category)

        # Apply cursor
        if cursor_data and cursor_data.get("id"):
            query = query.filter(MessageTemplate.id > cursor_data["id"])

        # Order and fetch
        query = query.order_by(MessageTemplate.name)
        templates = query.limit(limit + 1).all()

        # Check for more results
        has_more = len(templates) > limit
        if has_more:
            templates = templates[:limit]

        # Get total count (without pagination)
        total_query = db.query(MessageTemplate)
        if is_active is not None:
            total_query = total_query.filter(MessageTemplate.is_active == is_active)
        if category:
            total_query = total_query.filter(MessageTemplate.message_type == category)
        total = total_query.count()

        # Create next cursor
        next_cursor = create_cursor(str(templates[-1].id)) if has_more and templates else None

        # Convert to response format
        data = [_template_to_response(t) for t in templates]

        return {
            "data": data,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": total,
        }

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing message templates"
        )


@router.get(
    "/templates/{template_id}",
    response_model=MessageTemplateV2Response,
    summary="Get message template",
    description="Get a specific message template by ID."
)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Get a message template by ID."""
    try:
        # Validate UUID format
        try:
            template_uuid = UUID(template_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid template ID format"
            )

        repo = TemplateRepository(db)
        template = repo.get(template_uuid)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message template not found"
            )

        return _template_to_response(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving message template"
        )


@router.post(
    "/templates",
    response_model=MessageTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create message template",
    description="Create a new message template."
)
async def create_template(
    template_data: MessageTemplateV2Create,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Create a new message template.

    Features:
    - Validates unique template name
    - Stores variables for placeholder substitution
    - Supports different categories (text, image, document)
    """
    try:
        repo = TemplateRepository(db)

        # Check if name already exists
        existing = repo.get_by_name(template_data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template with name '{template_data.name}' already exists"
            )

        # Create template
        template = MessageTemplate(
            name=template_data.name,
            content=template_data.content,
            variables=template_data.variables,
            message_type=template_data.category,  # Map category to message_type
            is_active=True,
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        logger.info(f"Created message template: {template.name} (ID: {template.id})")

        return _template_to_response(template)

    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template name must be unique"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating message template"
        )


@router.put(
    "/templates/{template_id}",
    response_model=MessageTemplateV2Response,
    summary="Update message template",
    description="Update an existing message template."
)
async def update_template(
    template_id: str,
    template_data: MessageTemplateV2Update,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Update a message template.

    Features:
    - Partial updates (only provided fields are updated)
    - Validates unique name if name is being changed
    """
    try:
        # Validate UUID format
        try:
            template_uuid = UUID(template_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid template ID format"
            )

        repo = TemplateRepository(db)
        template = repo.get(template_uuid)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message template not found"
            )

        # Check name uniqueness if name is being changed
        if template_data.name and template_data.name != template.name:
            existing = repo.get_by_name(template_data.name)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Template with name '{template_data.name}' already exists"
                )

        # Build update dict with non-None values
        update_dict = {}
        if template_data.name is not None:
            update_dict["name"] = template_data.name
        if template_data.content is not None:
            update_dict["content"] = template_data.content
        if template_data.variables is not None:
            update_dict["variables"] = template_data.variables
        if template_data.category is not None:
            update_dict["message_type"] = template_data.category  # Map to model field
        if template_data.is_active is not None:
            update_dict["is_active"] = template_data.is_active

        # Apply updates
        if update_dict:
            for key, value in update_dict.items():
                setattr(template, key, value)
            db.commit()
            db.refresh(template)

        logger.info(f"Updated message template: {template.name} (ID: {template.id})")

        return _template_to_response(template)

    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template name must be unique"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating message template"
        )


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete message template",
    description="Delete a message template."
)
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    hard_delete: bool = Query(False, description="Permanently delete instead of soft delete"),
):
    """
    Delete a message template.

    Features:
    - Soft delete by default (sets is_active=False)
    - Hard delete option for permanent removal
    """
    try:
        # Validate UUID format
        try:
            template_uuid = UUID(template_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid template ID format"
            )

        repo = TemplateRepository(db)
        template = repo.get(template_uuid)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message template not found"
            )

        if hard_delete:
            # Permanent deletion
            db.delete(template)
            logger.info(f"Hard deleted message template: {template.name} (ID: {template.id})")
        else:
            # Soft delete (deactivate)
            template.is_active = False
            logger.info(f"Soft deleted message template: {template.name} (ID: {template.id})")

        db.commit()

        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting message template"
        )
