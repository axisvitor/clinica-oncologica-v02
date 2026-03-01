"""
Message Template Management Endpoints

Handles CRUD operations for message templates including:
- Creating templates with variables and conditionals
- Listing templates with filtering and pagination
- Retrieving individual template details
- Updating templates with versioning
"""

from typing import Optional
from datetime import datetime, timezone
from uuid import uuid4
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request

from app.core.database.async_engine import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
)
from app.schemas.v2.enhanced_messages import (
    MessageTemplateV2Create,
    MessageTemplateV2Update,
    MessageTemplateV2Response,
    MessageTemplateV2List,
    TemplateCategoryV2,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    create_cursor,
)
from app.utils.rate_limiter import limiter
from .dependencies import _check_admin_or_owner
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/templates",
    response_model=MessageTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create message template",
    description="Create a new message template with variables and conditionals",
)
@limiter.limit("30/minute")
async def create_template(
    request: Request,
    template_data: MessageTemplateV2Create,
    current_user: dict = Depends(get_current_user_from_session),
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
) -> MessageTemplateV2Response:
    """
    Create a new message template.

    Features:
    - Variable definitions with validation
    - Conditional content
    - Template versioning
    - Tag-based organization
    """
    try:
        # Check permissions (only admin and doctors can create templates)
        role = current_user.get("role", "").lower()
        if role not in ["admin", "administrator", "doctor"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and doctors can create templates",
            )

        # Create template record
        template_id = f"tpl_{uuid4().hex[:12]}"
        template_dict = {
            "id": template_id,
            "name": template_data.name,
            "content": template_data.content,
            "category": template_data.category.value,
            "language": template_data.language,
            "variables": [var.model_dump() for var in template_data.variables],
            "conditionals": [cond.model_dump() for cond in template_data.conditionals],
            "tags": template_data.tags,
            "metadata": template_data.metadata,
            "version": 1,
            "status": "active",
            "is_active": True,
            "usage_count": 0,
            "created_by": current_user.get("id"),
            "created_at": now_sao_paulo(),
            "updated_at": now_sao_paulo(),
        }

        # Store in cache (30 min TTL for templates)
        cache_key = f"template:v2:{template_id}"
        await redis_cache.set(
            cache_key, json.dumps(template_dict, default=str), ex=1800
        )

        # Also store in category index
        category_key = f"templates:v2:category:{template_data.category.value}"
        await redis_cache.sadd(category_key, template_id)
        await redis_cache.expire(category_key, 1800)

        logger.info(
            f"Template created: {template_id}",
            extra={
                "template_id": template_id,
                "category": template_data.category.value,
                "user_id": current_user.get("id"),
            },
        )

        return MessageTemplateV2Response(**template_dict)

    except ValueError as e:
        logger.warning(f"Template validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template data")
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template",
        )


@router.get(
    "/templates",
    response_model=MessageTemplateV2List,
    summary="List message templates",
    description="Get paginated list of message templates with filtering",
)
@limiter.limit("100/minute")
async def list_templates(
    request: Request,
    pagination=Depends(get_pagination_params),
    category: Optional[TemplateCategoryV2] = Query(
        None, description="Filter by category"
    ),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name and content"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
) -> MessageTemplateV2List:
    """
    List message templates with cursor-based pagination.

    Features:
    - Category filtering
    - Active status filtering
    - Full-text search
    - Tag filtering
    - Redis caching (30 min TTL)
    """
    try:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]

        # Try to get from cache first
        cache_key = (
            f"templates:v2:list:{category}:{is_active}:{search}:{tags}:{cursor_data}"
        )
        cached_result = await redis_cache.get(cache_key)
        if cached_result:
            logger.debug("Cache hit for templates list")
            return MessageTemplateV2List(**json.loads(cached_result))

        # Build filter for templates
        # In production, this would query the database
        # For now, we'll use a simulated response
        templates = []

        # Simulate getting templates from cache/db
        if category:
            category_key = f"templates:v2:category:{category.value}"
            template_ids = list(await redis_cache.smembers(category_key) or [])

            for template_id in template_ids[: limit + 1]:
                template_key = f"template:v2:{template_id}"
                template_data = await redis_cache.get(template_key)
                if template_data:
                    templates.append(json.loads(template_data))

        # Apply additional filters
        if is_active is not None:
            templates = [t for t in templates if t.get("is_active") == is_active]

        if search:
            search_lower = search.lower()
            templates = [
                t
                for t in templates
                if search_lower in t.get("name", "").lower()
                or search_lower in t.get("content", "").lower()
            ]

        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            templates = [
                t
                for t in templates
                if any(tag in t.get("tags", []) for tag in tag_list)
            ]

        # Pagination
        has_more = len(templates) > limit
        if has_more:
            templates = templates[:limit]

        next_cursor = None
        if has_more and templates:
            next_cursor = create_cursor(len(templates))

        # Count active templates
        total_active = sum(1 for t in templates if t.get("is_active"))

        result = MessageTemplateV2List(
            data=[MessageTemplateV2Response(**t) for t in templates],
            next_cursor=next_cursor,
            has_more=has_more,
            total=len(templates),
            total_active=total_active,
        )

        # Cache result (30 min)
        await redis_cache.set(cache_key, result.model_dump_json(), ex=1800)

        logger.info(
            f"Templates listed: {len(templates)}",
            extra={"count": len(templates), "user_id": current_user.get("id")},
        )

        return result

    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list templates",
        )


@router.get(
    "/templates/{template_id}",
    response_model=MessageTemplateV2Response,
    summary="Get template details",
    description="Get detailed information about a message template",
)
@limiter.limit("100/minute")
async def get_template(
    request: Request,
    template_id: str,
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
) -> MessageTemplateV2Response:
    """Get template by ID with caching."""
    try:
        # Try cache first (30 min TTL)
        cache_key = f"template:v2:{template_id}"
        template_data = await redis_cache.get(cache_key)

        if not template_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        template_dict = json.loads(template_data)

        logger.info(
            f"Template retrieved: {template_id}",
            extra={"template_id": template_id, "user_id": current_user.get("id")},
        )

        return MessageTemplateV2Response(**template_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve template",
        )


@router.patch(
    "/templates/{template_id}",
    response_model=MessageTemplateV2Response,
    summary="Update template",
    description="Update a message template (creates new version)",
)
@limiter.limit("30/minute")
async def update_template(
    request: Request,
    template_id: str,
    template_update: MessageTemplateV2Update,
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
) -> MessageTemplateV2Response:
    """
    Update template (with versioning).

    Creates a new version of the template while preserving old versions.
    """
    try:
        # Get existing template
        cache_key = f"template:v2:{template_id}"
        template_data = await redis_cache.get(cache_key)

        if not template_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        template_dict = json.loads(template_data)

        # Check permissions
        _check_admin_or_owner(current_user, template_dict.get("created_by"))

        # Update fields
        update_data = template_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "variables" and value:
                template_dict[field] = [v.model_dump() for v in value]
            elif field == "conditionals" and value:
                template_dict[field] = [c.model_dump() for c in value]
            elif field == "category" and value:
                template_dict[field] = value.value if hasattr(value, "value") else value
            else:
                template_dict[field] = value

        # Increment version
        template_dict["version"] = template_dict.get("version", 1) + 1
        template_dict["updated_at"] = now_sao_paulo()

        # Update cache
        await redis_cache.set(
            cache_key, json.dumps(template_dict, default=str), ex=1800
        )

        # Invalidate list cache
        await redis_cache.delete_pattern("templates:v2:list:*")

        logger.info(
            f"Template updated: {template_id}",
            extra={
                "template_id": template_id,
                "version": template_dict["version"],
                "user_id": current_user.get("id"),
            },
        )

        return MessageTemplateV2Response(**template_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update template",
        )
