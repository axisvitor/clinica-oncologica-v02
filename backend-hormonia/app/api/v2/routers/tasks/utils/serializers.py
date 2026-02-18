"""
Task Serialization Utilities

Functions for serializing task data to API response format.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.api.v2.dependencies import apply_field_selection
from app.schemas.v2.tasks import TaskStatus
from app.utils.timezone import now_sao_paulo


def _serialize_task(
    task_data: Dict[str, Any], fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Serialize task data to response format.

    Converts internal task data structure to API response format,
    handling datetime serialization and status enum conversion.

    Args:
        task_data: Raw task data dictionary
        fields: Optional list of fields to include (for field selection)

    Returns:
        Serialized task dictionary ready for API response
    """
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
        "created_at": task_data.get("created_at", now_sao_paulo()).isoformat()
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
