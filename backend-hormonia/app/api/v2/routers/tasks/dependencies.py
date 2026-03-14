"""
Tasks Router Dependencies - Shared dependencies for task endpoints.
"""

from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
import logging

from fastapi import Depends, HTTPException, status, Cookie

from app.core.database.async_engine import get_async_db
from app.models.user import UserRole
from app.schemas.v2.tasks import TaskStatus, TaskType, TaskPriority
from app.dependencies.auth_dependencies import get_redis_cache
from app.api.v2.auth_session_shared import resolve_session_id, get_user_data_from_session
from app.utils.auth_helpers import extract_user_role as _extract_user_role
from sqlalchemy.ext.asyncio import AsyncSession

from .registry import (
    get_task_by_celery_id as _registry_get_task_by_celery_id,
    get_task_by_id as _registry_get_task_by_id,
    task_registry,
)
from .utils.celery_integration import (
    _celery_status_to_task_status as _celery_status_to_task_status_impl,
    _get_task_from_celery as _get_task_from_celery_impl,
    _register_task as _register_task_impl,
)
from .utils.serializers import _serialize_task as _serialize_task_impl

logger = logging.getLogger(__name__)


async def _get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
) -> Dict[str, Any]:
    """Simplified session validation for V2 task endpoints using the canonical session cookie."""
    final_session_id = resolve_session_id(session_cookie_id=session_cookie_id)

    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session cookie required",
        )

    return await get_user_data_from_session(
        session_id=final_session_id,
        db=db,
        redis_cache=redis_cache,
    )


def _check_admin_role(current_user: Dict[str, Any]) -> None:
    """Ensure user is an admin."""
    role = _extract_user_role(current_user)
    if role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action",
        )


def _celery_status_to_task_status(celery_status: str) -> TaskStatus:
    """Convert Celery task state to TaskStatus enum."""
    return _celery_status_to_task_status_impl(celery_status)


def _get_task_from_celery(task_id: str) -> Dict[str, Any]:
    """Get task information from Celery."""
    return _get_task_from_celery_impl(task_id, task_registry)


def _register_task(
    celery_task_id: str,
    task_name: str,
    task_type: TaskType,
    priority: TaskPriority,
    user_id: Optional[UUID],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Register a task in the task registry."""
    task_id = _register_task_impl(
        celery_task_id=celery_task_id,
        task_name=task_name,
        task_type=task_type,
        priority=priority,
        user_id=user_id,
        task_registry=task_registry,
        metadata=metadata,
    )
    # Preserve existing response shape used by endpoints that serialize registry-only data.
    if celery_task_id in task_registry:
        task_registry[celery_task_id]["celery_task_id"] = celery_task_id
    return task_id


def _serialize_task(
    task_data: Dict[str, Any], fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Serialize task data to response format."""
    return _serialize_task_impl(task_data, fields)


def _find_task_in_registry(
    task_id: str,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Find task by public task ID."""
    task_data = _registry_get_task_by_id(task_id)
    if task_data:
        celery_task_id = task_data.get("celery_task_id")
        if celery_task_id:
            return celery_task_id, task_data
    return None, None


def _get_task_or_404(task_id: str) -> Tuple[str, Dict[str, Any]]:
    """Get task registry entry by task ID or raise 404."""
    celery_task_id, task_data = _find_task_in_registry(task_id)
    if not celery_task_id or task_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return celery_task_id, task_data


def _get_task_with_celery_data(
    celery_task_id: str, task_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Merge registry data with live Celery state for a task."""
    base_task_data = (
        task_data
        if task_data is not None
        else (_registry_get_task_by_celery_id(celery_task_id) or {})
    )
    celery_data = _get_task_from_celery(celery_task_id)
    return {**base_task_data, **celery_data}
