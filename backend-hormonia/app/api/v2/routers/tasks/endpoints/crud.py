"""
Tasks CRUD Endpoints - Basic task operations.

Endpoints:
- GET / - List tasks with filtering and pagination
- GET /{task_id} - Get a specific task by ID
- POST / - Create a new background task
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request

from app.core.database.async_engine import get_async_db
from app.models.user import UserRole
from app.schemas.v2.tasks import (
    TaskV2Response,
    TaskV2List,
    TaskV2Create,
    TaskStatus,
    TaskType,
    TaskPriority,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.task_queue import (
    task_queue as celery_app,
    update_task as update_stored_task,
)
from app.api.v2.routers import tasks as tasks_module
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import (
    _get_current_user_simple,
    _extract_user_role,
    _get_task_or_404,
    _get_task_with_celery_data,
    _serialize_task,
)
from ..registry import hydrate_registry_from_store
from ..utils import (
    CACHE_TTL_ACTIVE_TASKS,
    CACHE_TTL_TASK_HISTORY,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=TaskV2List)
@limiter.limit("60/minute")
async def list_tasks(
    request: Request,
    pagination: Dict = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    task_type: Optional[TaskType] = Query(None, description="Filter by task type"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Filter tasks from date"),
    end_date: Optional[datetime] = Query(None, description="Filter tasks to date"),
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> TaskV2List:
    """
    List background tasks with advanced filtering and pagination.

    Features:
    - Cursor-based pagination for efficient access
    - Multi-dimensional filtering (status, type, priority, user, date range)
    - Field selection for bandwidth optimization
    - Redis caching with 2-minute TTL
    - RBAC: Admins see all, users see own tasks

    Rate limit: 60 requests/minute
    """
    try:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]

        # Build cache key
        cache_key_parts = [
            "tasks:list",
            f"user:{current_user.get('id')}",
            f"status:{status.value if status else 'all'}",
            f"type:{task_type.value if task_type else 'all'}",
            f"priority:{priority.value if priority else 'all'}",
        ]
        cache_key = ":".join(cache_key_parts)

        # Try cache
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for tasks list: {cache_key}")
            return TaskV2List(**cached_data)

        role = _extract_user_role(current_user)
        current_user_id = UUID(current_user.get("id"))

        # Merge persisted task metadata (Dragonfly/Redis) to avoid process-local
        # blind spots from in-memory registry only.
        hydrate_registry_from_store()

        raw_tasks = []
        for celery_task_id, task_data in tasks_module.task_registry.items():
            raw_tasks.append(_get_task_with_celery_data(celery_task_id, task_data))

        tasks = []
        for task_data in raw_tasks:
            task_user_id = task_data.get("user_id")
            if role != UserRole.ADMIN:
                if not task_user_id or UUID(task_user_id) != current_user_id:
                    continue

            if status:
                task_status = task_data.get("status")
                if hasattr(task_status, "value"):
                    task_status = task_status.value
                if task_status and str(task_status) != status.value:
                    continue

            if task_type:
                if task_data.get("task_type") != task_type.value:
                    continue

            if priority:
                if task_data.get("priority") != priority.value:
                    continue

            if user_id:
                if not task_user_id or UUID(task_user_id) != user_id:
                    continue

            if start_date:
                task_created = task_data.get("created_at")
                if isinstance(task_created, str):
                    try:
                        task_created = datetime.fromisoformat(task_created)
                    except ValueError:
                        task_created = None
                if isinstance(task_created, datetime) and task_created < start_date:
                    continue

            if end_date:
                task_created = task_data.get("created_at")
                if isinstance(task_created, str):
                    try:
                        task_created = datetime.fromisoformat(task_created)
                    except ValueError:
                        task_created = None
                if isinstance(task_created, datetime) and task_created > end_date:
                    continue

            tasks.append(task_data)

        # Sort by created_at
        def _sort_key(item: Dict[str, Any]) -> datetime:
            created = item.get("created_at")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    created = None
            return created if isinstance(created, datetime) else datetime.min

        tasks.sort(key=_sort_key, reverse=True)

        # Apply pagination
        start_index = 0
        if cursor_data and "id" in cursor_data:
            # Find the index of the cursor task
            cursor_id = cursor_data["id"]
            for i, task in enumerate(tasks):
                if task.get("id") == cursor_id:
                    start_index = i + 1
                    break

        page_tasks = tasks[start_index : start_index + limit + 1]
        has_more = len(page_tasks) > limit
        if has_more:
            page_tasks = page_tasks[:limit]

        # Create next cursor
        next_cursor = None
        if has_more and page_tasks:
            next_cursor = create_cursor(page_tasks[-1].get("id", 0))

        # Serialize results
        data = [_serialize_task(task, fields) for task in page_tasks]

        result = TaskV2List(
            data=data, next_cursor=next_cursor, has_more=has_more, total=len(tasks)
        )

        # Cache the result
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_ACTIVE_TASKS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tasks: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tasks",
        )


@router.get("/{task_id}", response_model=TaskV2Response)
@limiter.limit("60/minute")
async def get_task(
    task_id: str,
    request: Request,
    fields: Optional[List[str]] = Depends(get_field_selection),
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get a specific task by ID with real-time progress tracking.

    Features:
    - Real-time status from Celery
    - Progress tracking with ETA
    - Field selection for bandwidth optimization
    - Redis caching with 2-minute TTL
    - RBAC: User must own task or be admin

    Rate limit: 60 requests/minute
    """
    try:
        # Try cache first
        cache_key = f"task:{task_id}:fields:{','.join(fields) if fields else 'all'}"
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for task: {cache_key}")
            return cached_data

        celery_task_id, task_data = _get_task_or_404(task_id)

        # Check RBAC
        role = _extract_user_role(current_user)
        if role != UserRole.ADMIN:
            task_user_id = task_data.get("user_id")
            current_user_id = current_user.get("id")
            if not task_user_id or task_user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this task",
                )

        # Get fresh data from Celery
        merged_data = _get_task_with_celery_data(celery_task_id, task_data)

        # Serialize
        data = _serialize_task(merged_data, fields)

        # Cache the result (short TTL for active tasks)
        cache_ttl = CACHE_TTL_ACTIVE_TASKS
        status_value = merged_data.get("status")
        if hasattr(status_value, "value"):
            status_value = status_value.value
        if status_value in [
            TaskStatus.SUCCESS.value,
            TaskStatus.FAILURE.value,
            TaskStatus.CANCELLED.value,
        ]:
            cache_ttl = CACHE_TTL_TASK_HISTORY

        await redis_cache.set(cache_key, data, ttl=cache_ttl)

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task",
        )


@router.post("/", response_model=TaskV2Response, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_task(
    task_data: TaskV2Create,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Create and schedule a new background task.

    Features:
    - Immediate or scheduled execution
    - Custom retry configuration
    - Task timeout support
    - Priority queue support
    - RBAC: All authenticated users can create tasks

    Rate limit: 30 requests/minute
    """
    try:
        user_id = UUID(current_user.get("id"))

        # Prepare task options
        task_options = {
            "priority": {"low": 3, "medium": 6, "high": 9, "critical": 10}.get(
                task_data.priority.value, 6
            )
        }

        if task_data.timeout_seconds:
            task_options["time_limit"] = task_data.timeout_seconds

        if task_data.schedule_at:
            task_options["eta"] = task_data.schedule_at

        # Apply the task to Celery
        celery_task = celery_app.send_task(
            task_data.celery_task_name,
            args=task_data.args,
            kwargs=task_data.kwargs,
            **task_options,
        )

        # Register task
        task_id = tasks_module._register_task(
            celery_task.id,
            task_data.task_name,
            task_data.task_type,
            task_data.priority,
            user_id,
            task_data.metadata,
        )

        # Update registry with additional info
        tasks_module.task_registry[celery_task.id].update(
            {
                "description": task_data.description,
                "retry_config": task_data.retry_config.dict()
                if task_data.retry_config
                else None,
                "timeout_seconds": task_data.timeout_seconds,
                "scheduled_at": task_data.schedule_at,
            }
        )
        update_stored_task(
            task_id,
            {
                "description": task_data.description,
                "retry_config": task_data.retry_config.dict()
                if task_data.retry_config
                else None,
                "timeout_seconds": task_data.timeout_seconds,
                "scheduled_at": task_data.schedule_at,
            },
        )

        # Invalidate list cache
        await redis_cache.delete_pattern("tasks:list:*")

        # Log creation
        logger.info(
            f"Task created: {task_id} ({task_data.task_name}) by user {user_id}"
        )

        # Get and return task data
        task_info = tasks_module.task_registry[celery_task.id]
        merged_data = _get_task_with_celery_data(celery_task.id, task_info)

        return _serialize_task(merged_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}",
        )
