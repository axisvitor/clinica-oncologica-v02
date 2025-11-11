"""
Template Version Management API
Provides version control operations for flow templates including:
- Version listing and history tracking
- Version comparison and diff generation
- Version rollback capabilities
- Draft publication workflow
"""

from typing import Dict, Any
from datetime import datetime
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc

from app.database import get_db
from app.models.flow import FlowTemplateVersion
from app.dependencies.auth_dependencies import get_redis_cache
from app.schemas.v2.templates import (
    FlowTemplateV2Response,
    TemplateVersionV2List,
    TemplateVersionCompareResponse,
    TemplateVersionRollbackRequest,
)
from app.utils.rate_limiter import limiter

# TODO: Import shared helpers and constants from templates_shared module once created:
# from .templates_shared import (
#     _get_current_user_simple,
#     _get_cache_key,
#     _get_cached_result,
#     _set_cached_result,
#     _check_write_permission,
#     _extract_user_context,
#     _serialize_flow_template,
#     _compare_templates,
#     _invalidate_template_cache,
#     CACHE_TTL_VERSIONS,
#     RATE_LIMIT_READ,
#     RATE_LIMIT_WRITE,
# )

# Temporary imports until templates_shared is created
from fastapi import Cookie, Header
from app.models.user import UserRole

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limits (requests per minute)
RATE_LIMIT_READ = "60/minute"
RATE_LIMIT_WRITE = "20/minute"

# Cache TTL configuration (in seconds)
CACHE_TTL_VERSIONS = 3600  # 1 hour


# ==================== Temporary Helper Functions ====================
# NOTE: These should be moved to templates_shared.py and imported from there

async def _get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> Dict[str, Any]:
    """Simplified session validation for template operations."""
    final_session_id = session_cookie_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID required"
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


def _extract_user_context(current_user: Dict[str, Any]) -> tuple[UserRole, UUID | None]:
    """Extract role and user UUID from current_user dict."""
    from typing import Optional, Tuple
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
    import json
    import hashlib
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()
    return f"templates:v2:{prefix}:{param_hash}"


async def _get_cached_result(cache_key: str):
    """Get cached result from Redis."""
    import json
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
    import json
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


async def _invalidate_template_cache(template_type: str, template_id: UUID | None = None):
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


def _compare_templates(old_data: Dict, new_data: Dict) -> Dict[str, Any]:
    """Compare two template versions and generate diff."""
    import json
    from difflib import unified_diff

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
