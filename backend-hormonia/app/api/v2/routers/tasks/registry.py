"""
Task Registry Management

Provides the in-memory task registry and management functions.

NOTE: In production, this should be replaced with Redis or database-backed storage.
This is a temporary solution for tracking task metadata alongside Celery.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID

# In-memory task tracking (should be replaced with Redis or DB in production)
task_registry: Dict[str, Dict[str, Any]] = {}


def get_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get task data by task ID.

    Args:
        task_id: Task ID to look up

    Returns:
        Task data dictionary if found, None otherwise
    """
    for celery_task_id, task_data in task_registry.items():
        if task_data.get("id") == task_id:
            return {**task_data, "celery_task_id": celery_task_id}
    return None


def get_task_by_celery_id(celery_task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get task data by Celery task ID.

    Args:
        celery_task_id: Celery task ID to look up

    Returns:
        Task data dictionary if found, None otherwise
    """
    return task_registry.get(celery_task_id)


def update_task(celery_task_id: str, updates: Dict[str, Any]) -> None:
    """
    Update task data in registry.

    Args:
        celery_task_id: Celery task ID
        updates: Dictionary of fields to update
    """
    if celery_task_id in task_registry:
        task_registry[celery_task_id].update(updates)


def delete_task(celery_task_id: str) -> bool:
    """
    Delete task from registry.

    Args:
        celery_task_id: Celery task ID to delete

    Returns:
        True if task was deleted, False if not found
    """
    if celery_task_id in task_registry:
        del task_registry[celery_task_id]
        return True
    return False


def list_tasks(
    user_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    task_type_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    List tasks with optional filters.

    Args:
        user_id: Filter by user ID
        status_filter: Filter by status
        task_type_filter: Filter by task type
        priority_filter: Filter by priority
        start_date: Filter tasks created after this date
        end_date: Filter tasks created before this date

    Returns:
        List of task data dictionaries
    """
    tasks = []

    for celery_task_id, task_data in task_registry.items():
        # Apply filters
        if user_id and task_data.get("user_id") != str(user_id):
            continue

        if status_filter and task_data.get("status") != status_filter:
            continue

        if task_type_filter and task_data.get("task_type") != task_type_filter:
            continue

        if priority_filter and task_data.get("priority") != priority_filter:
            continue

        if start_date:
            created_at = task_data.get("created_at")
            if isinstance(created_at, datetime) and created_at < start_date:
                continue

        if end_date:
            created_at = task_data.get("created_at")
            if isinstance(created_at, datetime) and created_at > end_date:
                continue

        tasks.append({**task_data, "celery_task_id": celery_task_id})

    return tasks


def get_task_count() -> int:
    """
    Get total number of tasks in registry.

    Returns:
        Number of tasks
    """
    return len(task_registry)


def clear_registry() -> int:
    """
    Clear all tasks from registry.

    Returns:
        Number of tasks cleared
    """
    count = len(task_registry)
    task_registry.clear()
    return count
