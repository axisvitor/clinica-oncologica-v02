"""
Flow Templates API v2
Flow template and flow kind management with version control.
Provides endpoints for creating, updating, and managing flow templates and their kinds.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc, or_, case

from app.database import get_db
from app.models.flow import FlowKind, FlowTemplateVersion
from app.schemas.v2.templates import (
    # Flow Template Schemas
    FlowTemplateV2Response,
    FlowTemplateV2List,
    FlowTemplateV2Create,
    FlowTemplateV2Update,
    FlowTemplateV2Duplicate,
    # Flow Kind Schemas
    FlowKindV2Response,
    FlowKindV2List,
    FlowKindV2Create,
)
from app.dependencies.auth_dependencies import get_redis_cache
from .dependencies import apply_field_selection
from app.utils.rate_limiter import limiter

# Import shared helpers and constants from templates_shared module
from .templates_shared import (
    _get_current_user_simple,
    _extract_user_context,
    _check_write_permission,
    _get_cache_key,
    _get_cached_result,
    _set_cached_result,
    _invalidate_template_cache,
    _serialize_flow_template,
    _serialize_flow_kind,
    CACHE_TTL_ACTIVE_TEMPLATES,
    CACHE_TTL_METADATA,
    RATE_LIMIT_READ,
    RATE_LIMIT_WRITE,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== Flow Template Endpoints ====================

@router.get(
    "/flows",
    response_model=FlowTemplateV2List,
    summary="List flow templates",
    description="List flow templates with cursor pagination, field selection, and eager loading"
)
@limiter.limit(RATE_LIMIT_READ)
async def list_flow_templates(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_draft: Optional[bool] = Query(None, description="Filter by draft status"),
    kind_key: Optional[str] = Query(None, description="Filter by flow kind"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    include: Optional[str] = Query(None, description="Eager load relationships (kind)"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    List flow templates with advanced filtering and pagination.

    - **cursor**: Pagination cursor from previous response
    - **limit**: Number of items per page (1-100)
    - **is_active**: Filter by active templates only
    - **is_draft**: Filter by draft templates only
    - **kind_key**: Filter by specific flow kind
    - **fields**: Select specific fields to return
    - **include**: Include related data (kind)
    """
    try:
        # Check cache
        cache_key = _get_cache_key("flow_list", cursor=cursor, limit=limit,
                                   is_active=is_active, is_draft=is_draft, kind_key=kind_key)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Build query with eager loading
        query = db.query(FlowTemplateVersion)

        if include and "kind" in include:
            query = query.options(joinedload(FlowTemplateVersion.kind))
        else:
            query = query.join(FlowKind)

        # Apply filters
        if is_active is not None:
            query = query.filter(FlowTemplateVersion.is_active == is_active)
        if is_draft is not None:
            query = query.filter(FlowTemplateVersion.is_draft == is_draft)
        if kind_key:
            query = query.filter(FlowKind.kind_key == kind_key)

        # Apply cursor pagination
        if cursor:
            try:
                cursor_data = json.loads(cursor)
                cursor_id = UUID(cursor_data["id"])
                cursor_created = datetime.fromisoformat(cursor_data["created_at"])
                query = query.filter(
                    or_(
                        FlowTemplateVersion.created_at < cursor_created,
                        and_(
                            FlowTemplateVersion.created_at == cursor_created,
                            FlowTemplateVersion.id < cursor_id
                        )
                    )
                )
            except (ValueError, KeyError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid cursor format: {str(e)}"
                )

        # Order and limit
        query = query.order_by(desc(FlowTemplateVersion.created_at), desc(FlowTemplateVersion.id))
        templates = query.limit(limit + 1).all()

        # Check if there are more items
        has_more = len(templates) > limit
        if has_more:
            templates = templates[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and templates:
            last_item = templates[-1]
            next_cursor = json.dumps({
                "id": str(last_item.id),
                "created_at": last_item.created_at.isoformat()
            })

        # Serialize templates
        data = [_serialize_flow_template(t) for t in templates]

        # Apply field selection
        if fields:
            field_set = set(fields.split(","))
            data = [apply_field_selection(item, field_set) for item in data]

        result = {
            "data": data,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None  # Optional: could add count query
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing flow templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list flow templates"
        )


@router.get(
    "/flows/{template_id}",
    response_model=FlowTemplateV2Response,
    summary="Get flow template",
    description="Get specific flow template by ID with optional eager loading"
)
@limiter.limit(RATE_LIMIT_READ)
async def get_flow_template(
    request: Request,
    template_id: UUID,
    include: Optional[str] = Query(None, description="Eager load relationships (kind)"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """Get specific flow template by ID."""
    try:
        # Check cache
        cache_key = _get_cache_key("flow_detail", template_id=str(template_id), include=include)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Build query with eager loading
        query = db.query(FlowTemplateVersion).filter(FlowTemplateVersion.id == template_id)

        if include and "kind" in include:
            query = query.options(joinedload(FlowTemplateVersion.kind))
        else:
            query = query.join(FlowKind)

        template = query.first()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow template not found"
            )

        result = _serialize_flow_template(template)

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flow template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get flow template"
        )


@router.post(
    "/flows",
    response_model=FlowTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create flow template",
    description="Create a new flow template version"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def create_flow_template(
    request: Request,
    template: FlowTemplateV2Create,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Create a new flow template version.

    Creates a new template version for an existing flow kind or creates a new flow kind.
    Only administrators and doctors can create templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Get or create flow kind
        flow_kind = None
        if template.flow_kind_id:
            flow_kind = db.query(FlowKind).filter(FlowKind.id == template.flow_kind_id).first()
            if not flow_kind:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Flow kind not found"
                )
        elif template.kind_key:
            # Try to find existing flow kind
            flow_kind = db.query(FlowKind).filter(FlowKind.kind_key == template.kind_key).first()

            if not flow_kind:
                # Create new flow kind
                flow_kind = FlowKind(
                    kind_key=template.kind_key,
                    display_name=template.display_name or template.kind_key,
                    description=template.description,
                    is_active=True
                )
                db.add(flow_kind)
                db.flush()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either flow_kind_id or kind_key must be provided"
            )

        # Check if version already exists
        existing = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.kind_id == flow_kind.id,
            FlowTemplateVersion.version_number == template.version_number
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version {template.version_number} already exists for this flow kind"
            )

        # Create template version
        template_version = FlowTemplateVersion(
            kind_id=flow_kind.id,
            version_number=template.version_number,
            template_name=template.template_name or template.display_name,
            description=template.description,
            messages=template.steps,
            template_metadata=template.metadata or {},
            is_active=template.is_active if template.is_active is not None else False,
            is_draft=template.is_draft if template.is_draft is not None else True,
            published_at=None if template.is_draft else datetime.utcnow(),
            created_by=user_uuid
        )

        db.add(template_version)
        db.commit()
        db.refresh(template_version)

        # Invalidate cache
        await _invalidate_template_cache("flow")

        logger.info(f"Created flow template: {flow_kind.kind_key} v{template.version_number} by user {user_uuid}")

        # Reload with kind relationship
        template_version = db.query(FlowTemplateVersion).options(
            joinedload(FlowTemplateVersion.kind)
        ).filter(FlowTemplateVersion.id == template_version.id).first()

        return _serialize_flow_template(template_version)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating flow template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create flow template: {str(e)}"
        )


@router.put(
    "/flows/{template_id}",
    response_model=FlowTemplateV2Response,
    summary="Update flow template",
    description="Update an existing flow template"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def update_flow_template(
    request: Request,
    template_id: UUID,
    updates: FlowTemplateV2Update,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Update flow template.

    Note: For versioned templates, consider creating a new version instead of updating.
    Only administrators and doctors can update templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        template = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == template_id
        ).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow template not found"
            )

        # Apply updates
        if updates.template_name is not None:
            template.template_name = updates.template_name
        if updates.description is not None:
            template.description = updates.description
        if updates.steps is not None:
            template.messages = updates.steps
        if updates.metadata is not None:
            template.template_metadata = updates.metadata
        if updates.is_active is not None:
            template.is_active = updates.is_active
        if updates.is_draft is not None:
            # If changing from draft to published, set published_at
            if template.is_draft and not updates.is_draft:
                template.published_at = datetime.utcnow()
            template.is_draft = updates.is_draft

        template.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(template)

        # Invalidate cache
        await _invalidate_template_cache("flow", template_id)

        logger.info(f"Updated flow template: {template_id} by user {user_uuid}")

        # Reload with kind relationship
        template = db.query(FlowTemplateVersion).options(
            joinedload(FlowTemplateVersion.kind)
        ).filter(FlowTemplateVersion.id == template_id).first()

        return _serialize_flow_template(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating flow template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update flow template: {str(e)}"
        )


@router.delete(
    "/flows/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete flow template",
    description="Delete flow template (soft or hard delete)"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def delete_flow_template(
    request: Request,
    template_id: UUID,
    soft_delete: bool = Query(True, description="Soft delete (deactivate) vs hard delete"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Delete flow template (soft or hard delete).

    - **soft_delete=true**: Sets is_active = False (recommended)
    - **soft_delete=false**: Permanently removes from database (use with caution)

    Only administrators and doctors can delete templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        template = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == template_id
        ).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow template not found"
            )

        if soft_delete:
            # Soft delete: deactivate
            template.is_active = False
            template.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Soft deleted flow template: {template_id} by user {user_uuid}")
        else:
            # Hard delete: remove from database
            db.delete(template)
            db.commit()
            logger.warning(f"Hard deleted flow template: {template_id} by user {user_uuid}")

        # Invalidate cache
        await _invalidate_template_cache("flow", template_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting flow template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete flow template"
        )


@router.post(
    "/flows/{template_id}/duplicate",
    response_model=FlowTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate flow template",
    description="Create a copy of an existing flow template with new version"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def duplicate_flow_template(
    request: Request,
    template_id: UUID,
    duplicate_data: FlowTemplateV2Duplicate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Duplicate an existing flow template.

    Creates a new version based on an existing template. Useful for creating variations
    or new versions without starting from scratch.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Get source template
        source = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == template_id
        ).first()

        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source template not found"
            )

        # Check if new version already exists
        existing = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.kind_id == source.kind_id,
            FlowTemplateVersion.version_number == duplicate_data.new_version_number
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version {duplicate_data.new_version_number} already exists"
            )

        # Create duplicate
        new_template = FlowTemplateVersion(
            kind_id=source.kind_id,
            version_number=duplicate_data.new_version_number,
            template_name=duplicate_data.new_template_name or f"{source.template_name} (Copy)",
            description=duplicate_data.description or source.description,
            messages=source.messages,  # Copy steps
            template_metadata=source.template_metadata.copy() if source.template_metadata else {},
            is_active=False,  # New duplicates are inactive by default
            is_draft=True,  # New duplicates are drafts by default
            published_at=None,
            created_by=user_uuid
        )

        db.add(new_template)
        db.commit()
        db.refresh(new_template)

        # Invalidate cache
        await _invalidate_template_cache("flow")

        logger.info(f"Duplicated flow template: {template_id} -> {new_template.id} by user {user_uuid}")

        # Reload with kind relationship
        new_template = db.query(FlowTemplateVersion).options(
            joinedload(FlowTemplateVersion.kind)
        ).filter(FlowTemplateVersion.id == new_template.id).first()

        return _serialize_flow_template(new_template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating flow template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to duplicate flow template: {str(e)}"
        )


# ==================== Flow Kind Endpoints ====================

@router.get(
    "/flow-kinds",
    response_model=FlowKindV2List,
    summary="List flow kinds",
    description="List all flow kinds with version statistics"
)
@limiter.limit(RATE_LIMIT_READ)
async def list_flow_kinds(
    request: Request,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    List all flow kinds (flow types) with version statistics.

    Returns comprehensive information about each flow kind including:
    - Total versions
    - Published versions
    - Draft versions
    - Active version details
    """
    try:
        # Check cache
        cache_key = _get_cache_key("flow_kinds", is_active=is_active)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Build query
        query = db.query(FlowKind)

        if is_active is not None:
            query = query.filter(FlowKind.is_active == is_active)

        flow_kinds = query.all()

        # Get version statistics for each kind
        data = []
        for kind in flow_kinds:
            version_stats = db.query(
                func.count(FlowTemplateVersion.id).label("total"),
                func.sum(case((FlowTemplateVersion.is_draft == False, 1), else_=0)).label("published"),
                func.sum(case((FlowTemplateVersion.is_draft == True, 1), else_=0)).label("draft")
            ).filter(FlowTemplateVersion.kind_id == kind.id).first()

            active_version = db.query(FlowTemplateVersion).filter(
                FlowTemplateVersion.kind_id == kind.id,
                FlowTemplateVersion.is_active == True,
                FlowTemplateVersion.is_draft == False
            ).first()

            stats = {
                "total": version_stats.total or 0,
                "published": version_stats.published or 0,
                "draft": version_stats.draft or 0,
                "active_version": str(active_version.id) if active_version else None
            }

            data.append(_serialize_flow_kind(kind, stats))

        result = {
            "data": data,
            "total": len(data)
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_METADATA)

        return result

    except Exception as e:
        logger.error(f"Error listing flow kinds: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list flow kinds"
        )


@router.post(
    "/flow-kinds",
    response_model=FlowKindV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create flow kind",
    description="Create a new flow kind (flow type)"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def create_flow_kind(
    request: Request,
    kind_data: FlowKindV2Create,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Create a new flow kind.

    Flow kinds are the base types for flow templates. Each kind can have multiple versions.
    Only administrators and doctors can create flow kinds.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Check if kind_key already exists
        existing = db.query(FlowKind).filter(FlowKind.kind_key == kind_data.kind_key).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Flow kind with key '{kind_data.kind_key}' already exists"
            )

        # Create flow kind
        flow_kind = FlowKind(
            kind_key=kind_data.kind_key,
            display_name=kind_data.display_name,
            description=kind_data.description,
            is_active=kind_data.is_active if kind_data.is_active is not None else True
        )

        db.add(flow_kind)
        db.commit()
        db.refresh(flow_kind)

        # Invalidate cache
        await _invalidate_template_cache("flow_kinds")

        logger.info(f"Created flow kind: {kind_data.kind_key} by user {user_uuid}")

        return _serialize_flow_kind(flow_kind)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating flow kind: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create flow kind: {str(e)}"
        )
