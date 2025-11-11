"""
Templates Shared Utilities
Shared helper functions and constants for template management operations.
Provides common functionality for authentication, caching, serialization, and validation.
"""

from typing import Optional, Dict, Any, Tuple
from uuid import UUID
import json
import hashlib
import logging
from difflib import unified_diff

from fastapi import Cookie, Header, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.flow import FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate
from app.models.user import User, UserRole
from app.dependencies.auth_dependencies import get_redis_cache

# Initialize logger
logger = logging.getLogger(__name__)

# ==================== Constants ====================

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
