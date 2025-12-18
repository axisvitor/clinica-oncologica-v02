"""
Celery Integration Utilities

Functions for interacting with Celery task system:
- Status conversion between Celery and TaskStatus enum
- Task information retrieval from Celery
- Task registration in the task registry
"""

from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID, uuid4
import logging

from celery.result import AsyncResult
from celery import states
from fastapi import HTTPException, status

from app.schemas.v2.tasks import TaskStatus, TaskType, TaskPriority
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _celery_status_to_task_status(celery_status: str) -> TaskStatus:
    """
    Convert Celery task state to TaskStatus enum.

    Args:
        celery_status: Celery task state string

    Returns:
        TaskStatus enum value
    """
    status_mapping = {
        states.PENDING: TaskStatus.PENDING,
        states.STARTED: TaskStatus.RUNNING,
        states.SUCCESS: TaskStatus.SUCCESS,
        states.FAILURE: TaskStatus.FAILURE,
        states.RETRY: TaskStatus.RETRY,
        states.REVOKED: TaskStatus.CANCELLED,
    }
    return status_mapping.get(celery_status, TaskStatus.PENDING)


def _get_task_from_celery(
    task_id: str, task_registry: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Get task information from Celery.

    Args:
        task_id: Celery task ID
        task_registry: Task registry dictionary

    Returns:
        Dictionary containing task information

    Raises:
        HTTPException: If task retrieval fails
    """
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
    task_type: TaskType,
    priority: TaskPriority,
    user_id: Optional[UUID],
    task_registry: Dict[str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Register a task in the task registry.

    Args:
        celery_task_id: Celery task ID
        task_name: Human-readable task name
        task_type: Type of task
        priority: Task priority level
        user_id: ID of user who created the task
        task_registry: Task registry dictionary to update
        metadata: Optional metadata dictionary

    Returns:
        Generated task ID
    """
    task_id = str(uuid4())

    task_registry[celery_task_id] = {
        "id": task_id,
        "task_name": task_name,
        "task_type": task_type.value,
        "priority": priority.value,
        "user_id": str(user_id) if user_id else None,
        "metadata": metadata or {},
        "created_at": datetime.utcnow(),
        "retry_count": 0,
        "logs": [],
    }

    return task_id
