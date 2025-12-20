"""
Tasks Router Dependencies - Shared dependencies for task endpoints.
"""

from typing import Dict, Any
from datetime import datetime, timezone
from uuid import UUID, uuid4
import logging

from fastapi import Depends, HTTPException, status, Header
from celery.result import AsyncResult
from celery import states

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.v2.tasks import TaskStatus
from app.dependencies.auth_dependencies import get_redis_cache

logger = logging.getLogger(__name__)

# In-memory task tracking (should be replaced with Redis or DB in production)
task_registry: Dict[str, Dict[str, Any]] = {}


async def _get_current_user_simple(
    session_id: str = Header(None, alias="X-Session-ID"),
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
) -> Dict[str, Any]:
    """Simplified session validation for V2 endpoints."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided in X-Session-ID header",
        )

    session_data = await redis_cache.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_active": user.is_active,
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    return user_data


def _extract_user_role(current_user: Dict[str, Any]) -> UserRole:
    """Extract UserRole enum from user data."""
    role_str = current_user.get("role", "").lower()
    try:
        return UserRole(role_str)
    except ValueError:
        # FIXED: Invalid role - default to DOCTOR instead of removed PATIENT role
        # Only ADMIN and DOCTOR roles exist in the system
        return UserRole.DOCTOR


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
    status_mapping = {
        states.PENDING: TaskStatus.PENDING,
        states.STARTED: TaskStatus.RUNNING,
        states.SUCCESS: TaskStatus.SUCCESS,
        states.FAILURE: TaskStatus.FAILURE,
        states.RETRY: TaskStatus.RETRY,
        states.REVOKED: TaskStatus.CANCELLED,
    }
    return status_mapping.get(celery_status, TaskStatus.PENDING)


def _get_task_from_celery(task_id: str) -> Dict[str, Any]:
    """Get task information from Celery."""
    from app.celery_app import celery_app

    try:
        result = AsyncResult(task_id, app=celery_app)

        task_data = {
            "celery_task_id": task_id,
            "status": _celery_status_to_task_status(result.status),
            "result": None,
            "error": None,
            "traceback": None,
        }

        if result.ready():
            if result.successful():
                task_data["result"] = result.result
            elif result.failed():
                task_data["error"] = str(result.info)
                task_data["traceback"] = result.traceback

        # Get task info from registry if available
        if task_id in task_registry:
            registry_data = task_registry[task_id]
            task_data.update(registry_data)

        return task_data

    except Exception as e:
        logger.error(f"Error getting task {task_id} from Celery: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task information",
        )


def _register_task(
    celery_task_id: str,
    task_name: str,
    task_type,
    priority,
    user_id: UUID,
    metadata: Dict[str, Any] = None,
) -> str:
    """Register a task in the task registry."""
    task_id = str(uuid4())

    task_registry[celery_task_id] = {
        "id": task_id,
        "task_name": task_name,
        "task_type": task_type.value,
        "priority": priority.value,
        "user_id": str(user_id) if user_id else None,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc),
        "retry_count": 0,
        "logs": [],
    }

    return task_id


def _serialize_task(task_data: Dict[str, Any], fields: list = None) -> Dict[str, Any]:
    """Serialize task data to response format."""
    from app.api.v2.dependencies import apply_field_selection

    serialized = {
        "id": task_data.get("id", "unknown"),
        "celery_task_id": task_data.get("celery_task_id", ""),
        "task_name": task_data.get("task_name", "Unknown Task"),
        "task_type": task_data.get("task_type", "custom"),
        "status": task_data.get("status", TaskStatus.PENDING).value
        if hasattr(task_data.get("status"), "value")
        else task_data.get("status", "PENDING"),
        "priority": task_data.get("priority", "medium"),
        "description": task_data.get("description"),
        "metadata": task_data.get("metadata", {}),
        "progress": task_data.get("progress"),
        "result": task_data.get("result"),
        "error": task_data.get("error"),
        "traceback": task_data.get("traceback"),
        "retry_count": task_data.get("retry_count", 0),
        "retry_config": task_data.get("retry_config"),
        "worker_name": task_data.get("worker_name"),
        "queue_name": task_data.get("queue_name", "celery"),
        "created_at": task_data.get("created_at", datetime.now(timezone.utc)).isoformat()
        if isinstance(task_data.get("created_at"), datetime)
        else task_data.get("created_at"),
        "started_at": task_data.get("started_at").isoformat()
        if isinstance(task_data.get("started_at"), datetime)
        else task_data.get("started_at"),
        "completed_at": task_data.get("completed_at").isoformat()
        if isinstance(task_data.get("completed_at"), datetime)
        else task_data.get("completed_at"),
        "scheduled_at": task_data.get("scheduled_at").isoformat()
        if isinstance(task_data.get("scheduled_at"), datetime)
        else task_data.get("scheduled_at"),
        "timeout_seconds": task_data.get("timeout_seconds"),
        "user_id": task_data.get("user_id"),
        "runtime_seconds": task_data.get("runtime_seconds"),
    }

    return apply_field_selection(serialized, fields) if fields else serialized
