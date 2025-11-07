"""
Templates API v2
Unified template management with version control and rollback capabilities.
Combines flow templates, quiz templates, and version management in a single cohesive API.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from uuid import UUID
import json
import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc, or_, case
from difflib import unified_diff

from app.database import get_db
from app.models.flow import FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate
from app.models.user import User, UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.schemas.v2.templates import (
    # Flow Template Schemas
    FlowTemplateV2Response,
    FlowTemplateV2List,
    FlowTemplateV2Create,
    FlowTemplateV2Update,
    FlowTemplateV2Duplicate,

    # Quiz Template Schemas
    QuizTemplateV2Response,
    QuizTemplateV2List,
    QuizTemplateV2Create,
    QuizTemplateV2Update,
    QuizTemplateV2Duplicate,

    # Flow Kind Schemas
    FlowKindV2Response,
    FlowKindV2List,
    FlowKindV2Create,
    FlowKindV2Update,

    # Version Management Schemas
    TemplateVersionV2Response,
    TemplateVersionV2List,
    TemplateVersionV2Create,
    TemplateVersionCompareResponse,
    TemplateVersionHistoryResponse,
    TemplateVersionRollbackRequest,

    # Template Preview & Validation
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateValidationResponse,

    # Search & Filter
    TemplateSearchResponse,
    TemplateSearchFilters,

    # Import/Export
    TemplateExportResponse,
    TemplateImportRequest,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
    apply_field_selection,
)
from app.utils.rate_limiter import limiter
from fastapi import Cookie, Header

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configuration (in seconds)
CACHE_TTL_ACTIVE_TEMPLATES = 1800  # 30 minutes
CACHE_TTL_VERSIONS = 3600  # 1 hour
CACHE_TTL_METADATA = 900  # 15 minutes

# Rate limits (requests per minute)
RATE_LIMIT_READ = "60/minute"
RATE_LIMIT_WRITE = "20/minute"
RATE_LIMIT_SEARCH = "30/minute"


# ==================== Helper Functions ====================

async def _get_current_user_simple(
    session_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> Dict[str, Any]:
    """Simplified session validation for template operations."""
    final_session_id = session_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided"
        )

    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user_data


def _extract_user_context(current_user: Dict[str, Any]) -> Tuple[UserRole, Optional[UUID]]:
    """Extract role and user UUID from current_user dict."""
    role_value = current_user.get("role", "doctor")
    user_id = current_user.get("id")

    if isinstance(role_value, UserRole):
        role = role_value
    elif isinstance(role_value, str):
        role_lower = role_value.lower()
        if role_lower == "admin":
            role = UserRole.ADMIN
        else:
            role = UserRole.DOCTOR
    else:
        role = UserRole.DOCTOR

    user_uuid = UUID(str(user_id)) if user_id else None
    return role, user_uuid


def _is_admin_or_doctor(current_user: Dict[str, Any]) -> bool:
    """Check if user has admin or doctor role."""
    role, _ = _extract_user_context(current_user)
    return role in [UserRole.ADMIN, UserRole.DOCTOR]


def _check_write_permission(current_user: Dict[str, Any]) -> None:
    """Ensure user has write permissions (admin or doctor)."""
    if not _is_admin_or_doctor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and doctors can create/modify templates"
        )


def _get_cache_key(prefix: str, **params) -> str:
    """Generate cache key from prefix and parameters."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()
    return f"templates:v2:{prefix}:{param_hash}"


async def _get_cached_result(cache_key: str):
    """Get cached result from Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        return None
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


async def _set_cached_result(cache_key: str, data: dict, ttl: int):
    """Set cached result in Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


async def _invalidate_template_cache(template_type: str, template_id: Optional[UUID] = None):
    """Invalidate template-related cache entries."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return

        # Invalidate list caches
        pattern = f"templates:v2:{template_type}:*"
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
            logger.debug(f"Invalidated {len(keys)} cache entries for {template_type}")

        # Invalidate specific template cache if ID provided
        if template_id:
            key = f"templates:v2:{template_type}:{template_id}"
            await redis_client.delete(key)
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")


def _serialize_flow_template(template: FlowTemplateVersion) -> Dict[str, Any]:
    """Serialize FlowTemplateVersion to API-friendly dict."""
    return {
        "id": str(template.id),
        "flow_kind_id": str(template.kind_id),
        "kind_key": template.kind.kind_key if template.kind else None,
        "display_name": template.kind.display_name if template.kind else None,
        "version_number": template.version_number,
        "template_name": template.template_name,
        "description": template.description,
        "steps": template.messages,
        "metadata": template.template_metadata or {},
        "is_active": template.is_active,
        "is_draft": template.is_draft,
        "published_at": template.published_at.isoformat() if template.published_at else None,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        "created_by": str(template.created_by) if template.created_by else None,
    }


def _serialize_quiz_template(template: QuizTemplate) -> Dict[str, Any]:
    """Serialize QuizTemplate to API-friendly dict."""
    return {
        "id": str(template.id),
        "name": template.name,
        "version": template.version,
        "description": template.description,
        "questions": template.questions,
        "category": template.category,
        "tags": template.tags or [],
        "passing_score": template.passing_score,
        "time_limit_minutes": template.time_limit_minutes,
        "randomize_questions": template.randomize_questions,
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def _serialize_flow_kind(kind: FlowKind, version_stats: Optional[Dict] = None) -> Dict[str, Any]:
    """Serialize FlowKind to API-friendly dict with optional version statistics."""
    result = {
        "id": str(kind.id),
        "kind_key": kind.kind_key,
        "display_name": kind.display_name,
        "description": kind.description,
        "is_active": kind.is_active,
        "created_at": kind.created_at.isoformat() if kind.created_at else None,
        "updated_at": kind.updated_at.isoformat() if kind.updated_at else None,
    }

    if version_stats:
        result.update({
            "total_versions": version_stats.get("total", 0),
            "published_versions": version_stats.get("published", 0),
            "draft_versions": version_stats.get("draft", 0),
            "active_version": version_stats.get("active_version"),
        })

    return result


def _compare_templates(old_data: Dict, new_data: Dict) -> Dict[str, Any]:
    """Compare two template versions and generate diff."""
    old_json = json.dumps(old_data, indent=2, sort_keys=True)
    new_json = json.dumps(new_data, indent=2, sort_keys=True)

    diff_lines = list(unified_diff(
        old_json.splitlines(keepends=True),
        new_json.splitlines(keepends=True),
        fromfile="old_version",
        tofile="new_version",
        lineterm=""
    ))

    changes = []
    for line in diff_lines:
        if line.startswith('+') and not line.startswith('+++'):
            changes.append({"type": "added", "content": line[1:].strip()})
        elif line.startswith('-') and not line.startswith('---'):
            changes.append({"type": "removed", "content": line[1:].strip()})

    return {
        "diff": "".join(diff_lines),
        "changes": changes,
        "total_changes": len(changes),
    }


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


# ==================== Quiz Template Endpoints ====================

@router.get(
    "/quiz",
    response_model=QuizTemplateV2List,
    summary="List quiz templates",
    description="List quiz templates with cursor pagination and filtering"
)
@limiter.limit(RATE_LIMIT_READ)
async def list_quiz_templates(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """List quiz templates with advanced filtering and pagination."""
    try:
        # Check cache
        cache_key = _get_cache_key("quiz_list", cursor=cursor, limit=limit,
                                   is_active=is_active, category=category)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Build query
        query = db.query(QuizTemplate)

        # Apply filters
        if is_active is not None:
            query = query.filter(QuizTemplate.is_active == is_active)
        if category:
            query = query.filter(QuizTemplate.category == category)

        # Apply cursor pagination
        if cursor:
            try:
                cursor_data = json.loads(cursor)
                cursor_id = UUID(cursor_data["id"])
                cursor_created = datetime.fromisoformat(cursor_data["created_at"])
                query = query.filter(
                    or_(
                        QuizTemplate.created_at < cursor_created,
                        and_(
                            QuizTemplate.created_at == cursor_created,
                            QuizTemplate.id < cursor_id
                        )
                    )
                )
            except (ValueError, KeyError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid cursor format: {str(e)}"
                )

        # Order and limit
        query = query.order_by(desc(QuizTemplate.created_at), desc(QuizTemplate.id))
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
        data = [_serialize_quiz_template(t) for t in templates]

        # Apply field selection
        if fields:
            field_set = set(fields.split(","))
            data = [apply_field_selection(item, field_set) for item in data]

        result = {
            "data": data,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing quiz templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list quiz templates"
        )


@router.get(
    "/quiz/{quiz_id}",
    response_model=QuizTemplateV2Response,
    summary="Get quiz template",
    description="Get specific quiz template by ID"
)
@limiter.limit(RATE_LIMIT_READ)
async def get_quiz_template(
    request: Request,
    quiz_id: UUID,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """Get specific quiz template by ID."""
    try:
        # Check cache
        cache_key = _get_cache_key("quiz_detail", quiz_id=str(quiz_id))
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        template = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz template not found"
            )

        result = _serialize_quiz_template(template)

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_ACTIVE_TEMPLATES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quiz template"
        )


@router.post(
    "/quiz",
    response_model=QuizTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Create quiz template",
    description="Create a new quiz template"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def create_quiz_template(
    request: Request,
    quiz: QuizTemplateV2Create,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Create a new quiz template.

    Only administrators and doctors can create quiz templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Check if quiz with same name and version already exists
        existing = db.query(QuizTemplate).filter(
            QuizTemplate.name == quiz.name,
            QuizTemplate.version == quiz.version
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Quiz template '{quiz.name}' version '{quiz.version}' already exists"
            )

        # Create quiz template
        quiz_template = QuizTemplate(
            name=quiz.name,
            version=quiz.version,
            description=quiz.description,
            questions=quiz.questions,
            category=quiz.category,
            tags=quiz.tags or [],
            passing_score=quiz.passing_score,
            time_limit_minutes=quiz.time_limit_minutes,
            randomize_questions=quiz.randomize_questions,
            is_active=quiz.is_active if quiz.is_active is not None else True
        )

        db.add(quiz_template)
        db.commit()
        db.refresh(quiz_template)

        # Invalidate cache
        await _invalidate_template_cache("quiz")

        logger.info(f"Created quiz template: {quiz.name} v{quiz.version} by user {user_uuid}")

        return _serialize_quiz_template(quiz_template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating quiz template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create quiz template: {str(e)}"
        )


@router.put(
    "/quiz/{quiz_id}",
    response_model=QuizTemplateV2Response,
    summary="Update quiz template",
    description="Update an existing quiz template"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def update_quiz_template(
    request: Request,
    quiz_id: UUID,
    updates: QuizTemplateV2Update,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Update quiz template.

    Only administrators and doctors can update quiz templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        quiz = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz template not found"
            )

        # Apply updates
        if updates.name is not None:
            quiz.name = updates.name
        if updates.version is not None:
            quiz.version = updates.version
        if updates.description is not None:
            quiz.description = updates.description
        if updates.questions is not None:
            quiz.questions = updates.questions
        if updates.category is not None:
            quiz.category = updates.category
        if updates.tags is not None:
            quiz.tags = updates.tags
        if updates.passing_score is not None:
            quiz.passing_score = updates.passing_score
        if updates.time_limit_minutes is not None:
            quiz.time_limit_minutes = updates.time_limit_minutes
        if updates.randomize_questions is not None:
            quiz.randomize_questions = updates.randomize_questions
        if updates.is_active is not None:
            quiz.is_active = updates.is_active

        quiz.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(quiz)

        # Invalidate cache
        await _invalidate_template_cache("quiz", quiz_id)

        logger.info(f"Updated quiz template: {quiz_id} by user {user_uuid}")

        return _serialize_quiz_template(quiz)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating quiz template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update quiz template: {str(e)}"
        )


@router.delete(
    "/quiz/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete quiz template",
    description="Delete quiz template (soft or hard delete)"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def delete_quiz_template(
    request: Request,
    quiz_id: UUID,
    soft_delete: bool = Query(True, description="Soft delete (deactivate) vs hard delete"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Delete quiz template (soft or hard delete).

    - **soft_delete=true**: Sets is_active = False (recommended)
    - **soft_delete=false**: Permanently removes from database (use with caution)

    Only administrators and doctors can delete quiz templates.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        quiz = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz template not found"
            )

        if soft_delete:
            # Soft delete: deactivate
            quiz.is_active = False
            quiz.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Soft deleted quiz template: {quiz_id} by user {user_uuid}")
        else:
            # Hard delete: remove from database
            db.delete(quiz)
            db.commit()
            logger.warning(f"Hard deleted quiz template: {quiz_id} by user {user_uuid}")

        # Invalidate cache
        await _invalidate_template_cache("quiz", quiz_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting quiz template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete quiz template"
        )


@router.post(
    "/quiz/{quiz_id}/duplicate",
    response_model=QuizTemplateV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate quiz template",
    description="Create a copy of an existing quiz template"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def duplicate_quiz_template(
    request: Request,
    quiz_id: UUID,
    duplicate_data: QuizTemplateV2Duplicate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Duplicate an existing quiz template.

    Creates a new version based on an existing template.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Get source template
        source = db.query(QuizTemplate).filter(QuizTemplate.id == quiz_id).first()

        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source quiz template not found"
            )

        # Check if new version already exists
        existing = db.query(QuizTemplate).filter(
            QuizTemplate.name == (duplicate_data.new_name or source.name),
            QuizTemplate.version == duplicate_data.new_version
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Quiz '{duplicate_data.new_name or source.name}' version '{duplicate_data.new_version}' already exists"
            )

        # Create duplicate
        new_quiz = QuizTemplate(
            name=duplicate_data.new_name or source.name,
            version=duplicate_data.new_version,
            description=duplicate_data.description or source.description,
            questions=source.questions.copy() if isinstance(source.questions, list) else source.questions,
            category=source.category,
            tags=source.tags.copy() if source.tags else [],
            passing_score=source.passing_score,
            time_limit_minutes=source.time_limit_minutes,
            randomize_questions=source.randomize_questions,
            is_active=False  # New duplicates are inactive by default
        )

        db.add(new_quiz)
        db.commit()
        db.refresh(new_quiz)

        # Invalidate cache
        await _invalidate_template_cache("quiz")

        logger.info(f"Duplicated quiz template: {quiz_id} -> {new_quiz.id} by user {user_uuid}")

        return _serialize_quiz_template(new_quiz)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating quiz template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to duplicate quiz template: {str(e)}"
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


# ==================== Version Management Endpoints ====================

@router.get(
    "/flows/{template_id}/versions",
    response_model=TemplateVersionV2List,
    summary="List template versions",
    description="List all versions for a specific flow template"
)
@limiter.limit(RATE_LIMIT_READ)
async def list_template_versions(
    request: Request,
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    List all versions for a specific flow template.

    Returns version history with metadata, timestamps, and status information.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("template_versions", template_id=str(template_id))
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Get the template to find its kind
        template = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == template_id
        ).first()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )

        # Get all versions for this kind
        versions = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.kind_id == template.kind_id
        ).order_by(desc(FlowTemplateVersion.version_number)).all()

        data = [_serialize_flow_template(v) for v in versions]

        result = {
            "data": data,
            "kind_key": template.kind.kind_key if template.kind else None,
            "total": len(data)
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_VERSIONS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing template versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list template versions"
        )


@router.post(
    "/flows/{template_id}/versions/compare",
    response_model=TemplateVersionCompareResponse,
    summary="Compare template versions",
    description="Compare two template versions and show differences"
)
@limiter.limit(RATE_LIMIT_READ)
async def compare_template_versions(
    request: Request,
    template_id: UUID,
    compare_with_id: UUID = Query(..., description="Version ID to compare with"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple)
):
    """
    Compare two template versions and generate a diff.

    Shows structural differences between versions to help understand what changed.
    """
    try:
        # Get both templates
        template1 = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == template_id
        ).first()
        template2 = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == compare_with_id
        ).first()

        if not template1 or not template2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both templates not found"
            )

        # Compare templates
        diff_result = _compare_templates(
            _serialize_flow_template(template1),
            _serialize_flow_template(template2)
        )

        return {
            "version1": _serialize_flow_template(template1),
            "version2": _serialize_flow_template(template2),
            "diff": diff_result["diff"],
            "changes": diff_result["changes"],
            "total_changes": diff_result["total_changes"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing template versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare template versions"
        )


@router.post(
    "/flows/{template_id}/rollback",
    response_model=FlowTemplateV2Response,
    summary="Rollback to template version",
    description="Rollback to a previous template version"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def rollback_template_version(
    request: Request,
    template_id: UUID,
    rollback_data: TemplateVersionRollbackRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Rollback to a previous template version.

    Creates a new version based on a previous version's configuration.
    This maintains version history while reverting to known-good state.
    """
    try:
        # Check write permission
        _check_write_permission(current_user)
        role, user_uuid = _extract_user_context(current_user)

        # Get source version to rollback to
        source_version = db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.id == template_id
        ).first()

        if not source_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source version not found"
            )

        # Get latest version number for this kind
        latest = db.query(func.max(FlowTemplateVersion.version_number)).filter(
            FlowTemplateVersion.kind_id == source_version.kind_id
        ).scalar()

        new_version_number = (latest or 0) + 1

        # Create rollback version
        rollback_version = FlowTemplateVersion(
            kind_id=source_version.kind_id,
            version_number=new_version_number,
            template_name=f"{source_version.template_name} (Rollback)",
            description=rollback_data.reason or f"Rollback to version {source_version.version_number}",
            messages=source_version.messages,
            template_metadata=source_version.template_metadata.copy() if source_version.template_metadata else {},
            is_active=rollback_data.set_as_active if rollback_data.set_as_active is not None else False,
            is_draft=False,  # Rollbacks are published by default
            published_at=datetime.utcnow(),
            created_by=user_uuid
        )

        db.add(rollback_version)

        # If set_as_active, deactivate other versions
        if rollback_data.set_as_active:
            db.query(FlowTemplateVersion).filter(
                FlowTemplateVersion.kind_id == source_version.kind_id,
                FlowTemplateVersion.id != rollback_version.id
            ).update({"is_active": False})

        db.commit()
        db.refresh(rollback_version)

        # Invalidate cache
        await _invalidate_template_cache("flow")

        logger.info(f"Rolled back to template version: {template_id} -> {rollback_version.id} by user {user_uuid}")

        # Reload with kind relationship
        rollback_version = db.query(FlowTemplateVersion).options(
            joinedload(FlowTemplateVersion.kind)
        ).filter(FlowTemplateVersion.id == rollback_version.id).first()

        return _serialize_flow_template(rollback_version)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rolling back template version: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback template version: {str(e)}"
        )


@router.post(
    "/flows/{template_id}/publish",
    response_model=FlowTemplateV2Response,
    summary="Publish template version",
    description="Publish a draft template version"
)
@limiter.limit(RATE_LIMIT_WRITE)
async def publish_template_version(
    request: Request,
    template_id: UUID,
    set_as_active: bool = Query(False, description="Set this version as active"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Publish a draft template version.

    Moves a template from draft to published state, optionally setting it as the active version.
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
                detail="Template not found"
            )

        if not template.is_draft:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template is already published"
            )

        # Publish template
        template.is_draft = False
        template.published_at = datetime.utcnow()

        if set_as_active:
            # Deactivate other versions
            db.query(FlowTemplateVersion).filter(
                FlowTemplateVersion.kind_id == template.kind_id,
                FlowTemplateVersion.id != template.id
            ).update({"is_active": False})
            template.is_active = True

        template.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(template)

        # Invalidate cache
        await _invalidate_template_cache("flow", template_id)

        logger.info(f"Published template: {template_id} by user {user_uuid}")

        # Reload with kind relationship
        template = db.query(FlowTemplateVersion).options(
            joinedload(FlowTemplateVersion.kind)
        ).filter(FlowTemplateVersion.id == template_id).first()

        return _serialize_flow_template(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing template: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish template"
        )


# ==================== Template Search & Validation ====================

@router.get(
    "/search",
    response_model=TemplateSearchResponse,
    summary="Search templates",
    description="Full-text search across flow and quiz templates"
)
@limiter.limit(RATE_LIMIT_SEARCH)
async def search_templates(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    template_type: Optional[str] = Query(None, description="Filter by type (flow, quiz)"),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(_get_current_user_simple)
):
    """
    Full-text search across templates.

    Searches in template names, descriptions, and metadata.
    """
    try:
        results = []

        # Search flow templates
        if not template_type or template_type == "flow":
            flow_query = db.query(FlowTemplateVersion).join(FlowKind).filter(
                or_(
                    FlowTemplateVersion.template_name.ilike(f"%{q}%"),
                    FlowTemplateVersion.description.ilike(f"%{q}%"),
                    FlowKind.display_name.ilike(f"%{q}%"),
                    FlowKind.kind_key.ilike(f"%{q}%")
                )
            ).limit(limit)

            for template in flow_query:
                results.append({
                    "type": "flow",
                    "id": str(template.id),
                    "name": template.template_name,
                    "description": template.description,
                    "relevance_score": 1.0  # Could implement proper scoring
                })

        # Search quiz templates
        if not template_type or template_type == "quiz":
            quiz_query = db.query(QuizTemplate).filter(
                or_(
                    QuizTemplate.name.ilike(f"%{q}%"),
                    QuizTemplate.description.ilike(f"%{q}%"),
                    QuizTemplate.category.ilike(f"%{q}%")
                )
            ).limit(limit)

            for quiz in quiz_query:
                results.append({
                    "type": "quiz",
                    "id": str(quiz.id),
                    "name": quiz.name,
                    "description": quiz.description,
                    "relevance_score": 1.0
                })

        return {
            "query": q,
            "results": results[:limit],
            "total": len(results)
        }

    except Exception as e:
        logger.error(f"Error searching templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search templates"
        )


@router.post(
    "/validate",
    response_model=TemplateValidationResponse,
    summary="Validate template",
    description="Validate template structure and content"
)
@limiter.limit(RATE_LIMIT_READ)
async def validate_template(
    request: Request,
    template_data: Dict[str, Any],
    template_type: str = Query(..., description="Template type (flow, quiz)"),
    current_user: Dict = Depends(_get_current_user_simple)
):
    """
    Validate template structure and content.

    Checks for required fields, data types, and business rules.
    """
    try:
        errors = []
        warnings = []

        if template_type == "flow":
            # Validate flow template
            if "steps" not in template_data:
                errors.append("Missing required field: steps")
            elif not isinstance(template_data["steps"], (list, dict)):
                errors.append("Field 'steps' must be array or object")

            if "version_number" not in template_data:
                errors.append("Missing required field: version_number")

            if "template_name" not in template_data:
                warnings.append("Missing recommended field: template_name")

        elif template_type == "quiz":
            # Validate quiz template
            if "questions" not in template_data:
                errors.append("Missing required field: questions")
            elif not isinstance(template_data["questions"], list):
                errors.append("Field 'questions' must be array")
            elif len(template_data["questions"]) == 0:
                errors.append("Quiz must have at least one question")

            if "name" not in template_data:
                errors.append("Missing required field: name")

            if "version" not in template_data:
                errors.append("Missing required field: version")
        else:
            errors.append(f"Invalid template type: {template_type}")

        is_valid = len(errors) == 0

        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }

    except Exception as e:
        logger.error(f"Error validating template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate template"
        )
