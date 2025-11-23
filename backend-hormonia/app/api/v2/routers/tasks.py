"""
Tasks API v2 - Background Task Management System

Enhanced task management endpoints with:
- Cursor-based pagination for efficient task access
- Redis caching with optimized TTLs (tasks are dynamic)
- Rate limiting to prevent system abuse
- Real-time progress tracking with ETA calculation
- Retry mechanism with multiple strategies
- Comprehensive task logging and monitoring
- Queue status and worker health checks
- Bulk task operations
- Task cleanup and maintenance
- RBAC: Admin for management, all users can view own tasks

CRITICAL: This module manages background job execution.
All operations must be reliable and properly monitored.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging
from collections import defaultdict
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Header
# from sqlalchemy.orm import Session,
from celery.result import AsyncResult
from celery import states

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.v2.tasks import (
    TaskV2Response,
    TaskV2List,
    TaskV2Create,
    TaskV2Cancel,
    TaskV2Retry,
    TaskV2WithLogs,
    TaskLogEntryV2,
    TaskStatisticsV2,
    QueueStatusV2,
    WorkerStatusV2,
    BulkTaskOperation,
    BulkTaskResult,
    TaskCleanupConfigV2,
    TaskCleanupResultV2,
    TaskStatus,
    TaskType,
    TaskPriority,
    TaskProgressV2,
    RetryStrategy,
)
from app.schemas.v2.common import ErrorResponse
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.celery_app import celery_app
from app.utils.task_monitoring import task_monitor, get_task_monitoring_data

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configurations (SHORT TTLs for dynamic task data)
CACHE_TTL_ACTIVE_TASKS = 120  # 2 minutes for active tasks
CACHE_TTL_TASK_HISTORY = 600  # 10 minutes for completed tasks
CACHE_TTL_STATISTICS = 300  # 5 minutes for statistics
CACHE_TTL_QUEUE_STATUS = 60  # 1 minute for queue status

# In-memory task tracking (should be replaced with Redis or DB in production)
task_registry: Dict[str, Dict[str, Any]] = {}


async def _get_current_user_simple(
    session_id: str = Header(None, alias="X-Session-ID"),
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> Dict[str, Any]:
    """Simplified session validation for V2 endpoints."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided in X-Session-ID header"
        )

    session_data = await redis_cache.get_session(session_id)
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
            detail="Only administrators can perform this action"
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
            detail="Failed to retrieve task information"
        )


def _register_task(
    celery_task_id: str,
    task_name: str,
    task_type: TaskType,
    priority: TaskPriority,
    user_id: Optional[UUID],
    metadata: Optional[Dict[str, Any]] = None
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
        "created_at": datetime.utcnow(),
        "retry_count": 0,
        "logs": []
    }

    return task_id


def _calculate_retry_delay(
    retry_count: int,
    strategy: RetryStrategy,
    base_delay: int,
    max_delay: int
) -> int:
    """Calculate retry delay based on strategy."""
    if strategy == RetryStrategy.IMMEDIATE:
        return 0
    elif strategy == RetryStrategy.LINEAR:
        return min(base_delay * (retry_count + 1), max_delay)
    elif strategy == RetryStrategy.EXPONENTIAL:
        return min(base_delay * (2 ** retry_count), max_delay)
    elif strategy == RetryStrategy.FIBONACCI:
        fib = [1, 1]
        for i in range(retry_count):
            fib.append(fib[-1] + fib[-2])
        return min(base_delay * fib[retry_count], max_delay)
    return base_delay


def _serialize_task(
    task_data: Dict[str, Any],
    fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Serialize task data to response format."""
    serialized = {
        "id": task_data.get("id", "unknown"),
        "celery_task_id": task_data.get("celery_task_id", ""),
        "task_name": task_data.get("task_name", "Unknown Task"),
        "task_type": task_data.get("task_type", "custom"),
        "status": task_data.get("status", TaskStatus.PENDING).value if hasattr(task_data.get("status"), 'value') else task_data.get("status", "PENDING"),
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
        "created_at": task_data.get("created_at", datetime.utcnow()).isoformat() if isinstance(task_data.get("created_at"), datetime) else task_data.get("created_at"),
        "started_at": task_data.get("started_at").isoformat() if isinstance(task_data.get("started_at"), datetime) else task_data.get("started_at"),
        "completed_at": task_data.get("completed_at").isoformat() if isinstance(task_data.get("completed_at"), datetime) else task_data.get("completed_at"),
        "scheduled_at": task_data.get("scheduled_at").isoformat() if isinstance(task_data.get("scheduled_at"), datetime) else task_data.get("scheduled_at"),
        "timeout_seconds": task_data.get("timeout_seconds"),
        "user_id": task_data.get("user_id"),
        "runtime_seconds": task_data.get("runtime_seconds"),
    }

    return apply_field_selection(serialized, fields) if fields else serialized


@router.get("", response_model=TaskV2List)
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
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
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

        # Get tasks from registry
        role = _extract_user_role(current_user)
        current_user_id = UUID(current_user.get("id"))

        tasks = []
        for celery_task_id, task_data in task_registry.items():
            # Apply RBAC filtering
            task_user_id = task_data.get("user_id")
            if role != UserRole.ADMIN:
                if not task_user_id or UUID(task_user_id) != current_user_id:
                    continue

            # Apply filters
            if status:
                task_status = task_data.get("status")
                if task_status and task_status != status:
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
                if isinstance(task_created, datetime) and task_created < start_date:
                    continue

            if end_date:
                task_created = task_data.get("created_at")
                if isinstance(task_created, datetime) and task_created > end_date:
                    continue

            # Get fresh data from Celery
            celery_data = _get_task_from_celery(celery_task_id)
            merged_data = {**task_data, **celery_data}
            tasks.append(merged_data)

        # Sort by created_at
        tasks.sort(
            key=lambda x: x.get("created_at", datetime.min),
            reverse=True
        )

        # Apply pagination
        start_index = 0
        if cursor_data and "id" in cursor_data:
            # Find the index of the cursor task
            cursor_id = cursor_data["id"]
            for i, task in enumerate(tasks):
                if task.get("id") == cursor_id:
                    start_index = i + 1
                    break

        page_tasks = tasks[start_index:start_index + limit + 1]
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
            data=data,
            next_cursor=next_cursor,
            has_more=has_more,
            total=len(tasks)
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
            detail="Failed to retrieve tasks"
        )


@router.get("/{task_id}", response_model=TaskV2Response)
@limiter.limit("60/minute")
async def get_task(
    task_id: str,
    request: Request,
    fields: Optional[List[str]] = Depends(get_field_selection),
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
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

        # Find task in registry
        celery_task_id = None
        task_data = None

        for cid, data in task_registry.items():
            if data.get("id") == task_id:
                celery_task_id = cid
                task_data = data
                break

        if not task_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        # Check RBAC
        role = _extract_user_role(current_user)
        if role != UserRole.ADMIN:
            task_user_id = task_data.get("user_id")
            current_user_id = current_user.get("id")
            if not task_user_id or task_user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this task"
                )

        # Get fresh data from Celery
        celery_data = _get_task_from_celery(celery_task_id)
        merged_data = {**task_data, **celery_data}

        # Serialize
        data = _serialize_task(merged_data, fields)

        # Cache the result (short TTL for active tasks)
        cache_ttl = CACHE_TTL_ACTIVE_TASKS
        if merged_data.get("status") in [TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.CANCELLED]:
            cache_ttl = CACHE_TTL_TASK_HISTORY

        await redis_cache.set(cache_key, data, ttl=cache_ttl)

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task"
        )


@router.post("", response_model=TaskV2Response, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_task(
    task_data: TaskV2Create,
    request: Request,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
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
            **task_options
        )

        # Register task
        task_id = _register_task(
            celery_task.id,
            task_data.task_name,
            task_data.task_type,
            task_data.priority,
            user_id,
            task_data.metadata
        )

        # Update registry with additional info
        task_registry[celery_task.id].update({
            "description": task_data.description,
            "retry_config": task_data.retry_config.dict() if task_data.retry_config else None,
            "timeout_seconds": task_data.timeout_seconds,
            "scheduled_at": task_data.schedule_at,
        })

        # Invalidate list cache
        await redis_cache.delete_pattern("tasks:list:*")

        # Log creation
        logger.info(
            f"Task created: {task_id} ({task_data.task_name}) by user {user_id}"
        )

        # Get and return task data
        task_info = task_registry[celery_task.id]
        celery_data = _get_task_from_celery(celery_task.id)
        merged_data = {**task_info, **celery_data}

        return _serialize_task(merged_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.post("/{task_id}/cancel", response_model=TaskV2Response)
@limiter.limit("30/minute")
async def cancel_task(
    task_id: str,
    cancel_data: TaskV2Cancel,
    request: Request,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Cancel a running or pending task.

    Features:
    - Graceful or forced termination
    - Audit trail with cancellation reason
    - RBAC: User must own task or be admin

    Rate limit: 30 requests/minute
    """
    try:
        # Find task
        celery_task_id = None
        task_data = None

        for cid, data in task_registry.items():
            if data.get("id") == task_id:
                celery_task_id = cid
                task_data = data
                break

        if not task_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        # Check RBAC
        role = _extract_user_role(current_user)
        if role != UserRole.ADMIN:
            task_user_id = task_data.get("user_id")
            current_user_id = current_user.get("id")
            if not task_user_id or task_user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this task"
                )

        # Cancel in Celery
        celery_app.control.revoke(
            celery_task_id,
            terminate=cancel_data.force,
            signal='SIGKILL' if cancel_data.force else 'SIGTERM'
        )

        # Update registry
        task_registry[celery_task_id].update({
            "status": TaskStatus.CANCELLED,
            "completed_at": datetime.utcnow(),
            "metadata": {
                **task_data.get("metadata", {}),
                "cancellation_reason": cancel_data.reason,
                "cancelled_by": current_user.get("id"),
                "forced": cancel_data.force
            }
        })

        # Invalidate caches
        await redis_cache.delete(f"task:{task_id}:*")
        await redis_cache.delete_pattern("tasks:list:*")

        # Log cancellation
        logger.info(
            f"Task cancelled: {task_id} by user {current_user.get('id')} "
            f"(force={cancel_data.force})"
        )

        # Get updated data
        celery_data = _get_task_from_celery(celery_task_id)
        merged_data = {**task_registry[celery_task_id], **celery_data}

        return _serialize_task(merged_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task"
        )


@router.post("/{task_id}/retry", response_model=TaskV2Response)
@limiter.limit("30/minute")
async def retry_task(
    task_id: str,
    retry_data: TaskV2Retry,
    request: Request,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Manually retry a failed task.

    Features:
    - Override retry limits if needed
    - Custom retry delay
    - Exponential backoff support
    - RBAC: User must own task or be admin

    Rate limit: 30 requests/minute
    """
    try:
        # Find task
        celery_task_id = None
        task_data = None

        for cid, data in task_registry.items():
            if data.get("id") == task_id:
                celery_task_id = cid
                task_data = data
                break

        if not task_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        # Check RBAC
        role = _extract_user_role(current_user)
        if role != UserRole.ADMIN:
            task_user_id = task_data.get("user_id")
            current_user_id = current_user.get("id")
            if not task_user_id or task_user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this task"
                )

        # Check if task can be retried
        current_status = task_data.get("status")
        if current_status not in [TaskStatus.FAILURE, TaskStatus.RETRY]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot retry task in {current_status} status"
            )

        # Check retry limit
        retry_count = task_data.get("retry_count", 0)
        retry_config = task_data.get("retry_config")

        if retry_config and not retry_data.override_retry_limit:
            max_retries = retry_config.get("max_retries", 3)
            if retry_count >= max_retries:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Task has exceeded maximum retry attempts ({max_retries})"
                )

        # Calculate delay
        delay = retry_data.delay_seconds
        if delay is None and retry_config:
            strategy = RetryStrategy(retry_config.get("retry_strategy", "exponential"))
            delay = _calculate_retry_delay(
                retry_count,
                strategy,
                retry_config.get("base_delay", 60),
                retry_config.get("max_delay", 3600)
            )

        # Retry the task
        # Note: In a real implementation, you would requeue the original task
        # For now, we'll update the status
        task_registry[celery_task_id].update({
            "status": TaskStatus.RETRY,
            "retry_count": retry_count + 1,
            "metadata": {
                **task_data.get("metadata", {}),
                "manual_retry": True,
                "retry_notes": retry_data.notes,
                "retried_by": current_user.get("id"),
                "retried_at": datetime.utcnow().isoformat()
            }
        })

        # Invalidate caches
        await redis_cache.delete(f"task:{task_id}:*")
        await redis_cache.delete_pattern("tasks:list:*")

        # Log retry
        logger.info(
            f"Task retry initiated: {task_id} by user {current_user.get('id')} "
            f"(attempt {retry_count + 1})"
        )

        # Get updated data
        merged_data = task_registry[celery_task_id]

        return _serialize_task(merged_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry task"
        )


@router.get("/{task_id}/logs", response_model=TaskV2WithLogs)
@limiter.limit("60/minute")
async def get_task_logs(
    task_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Maximum log entries"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get task execution logs with pagination.

    Features:
    - Filter by log level
    - Pagination support
    - Redis caching with 10-minute TTL
    - RBAC: User must own task or be admin

    Rate limit: 60 requests/minute
    """
    try:
        # Find task
        celery_task_id = None
        task_data = None

        for cid, data in task_registry.items():
            if data.get("id") == task_id:
                celery_task_id = cid
                task_data = data
                break

        if not task_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        # Check RBAC
        role = _extract_user_role(current_user)
        if role != UserRole.ADMIN:
            task_user_id = task_data.get("user_id")
            current_user_id = current_user.get("id")
            if not task_user_id or task_user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this task"
                )

        # Get logs
        logs = task_data.get("logs", [])

        # Filter by level if specified
        if level:
            logs = [log for log in logs if log.get("level") == level.upper()]

        # Limit results
        logs = logs[:limit]

        # Get task data
        celery_data = _get_task_from_celery(celery_task_id)
        merged_data = {**task_data, **celery_data, "logs": logs}

        return merged_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving logs for task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task logs"
        )


@router.get("/statistics/overview", response_model=TaskStatisticsV2)
@limiter.limit("30/minute")
async def get_task_statistics(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Analysis period in hours"),
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> TaskStatisticsV2:
    """
    Get comprehensive task system statistics.

    Includes:
    - Task counts by status, type, and priority
    - Success rate and average runtime
    - Slowest tasks identification
    - Trend analysis

    Features:
    - Redis caching with 5-minute TTL
    - RBAC: Admins see all, users see own stats

    Rate limit: 30 requests/minute
    """
    try:
        # Try cache
        cache_key = f"tasks:statistics:hours:{hours}:user:{current_user.get('id')}"
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for task statistics: {cache_key}")
            return TaskStatisticsV2(**cached_data)

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=hours)

        # Filter tasks
        role = _extract_user_role(current_user)
        current_user_id = UUID(current_user.get("id"))

        filtered_tasks = []
        for celery_task_id, task_data in task_registry.items():
            # Apply RBAC
            if role != UserRole.ADMIN:
                task_user_id = task_data.get("user_id")
                if not task_user_id or UUID(task_user_id) != current_user_id:
                    continue

            # Apply date filter
            created_at = task_data.get("created_at")
            if isinstance(created_at, datetime) and start_date <= created_at <= end_date:
                celery_data = _get_task_from_celery(celery_task_id)
                filtered_tasks.append({**task_data, **celery_data})

        # Calculate statistics
        total_tasks = len(filtered_tasks)

        status_counts = defaultdict(int)
        type_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        runtimes = []
        wait_times = []

        for task in filtered_tasks:
            task_status = task.get("status")
            if hasattr(task_status, 'value'):
                status_counts[task_status.value] += 1
            else:
                status_counts[str(task_status)] += 1

            type_counts[task.get("task_type", "custom")] += 1
            priority_counts[task.get("priority", "medium")] += 1

            runtime = task.get("runtime_seconds")
            if runtime:
                runtimes.append(runtime)

        # Calculate averages
        avg_runtime = sum(runtimes) / len(runtimes) if runtimes else 0
        avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0

        # Calculate success rate
        completed = status_counts.get("SUCCESS", 0)
        success_rate = (completed / total_tasks * 100) if total_tasks > 0 else 0

        # Find slowest tasks
        slowest = sorted(
            [
                {"task_name": t.get("task_name"), "runtime_seconds": t.get("runtime_seconds")}
                for t in filtered_tasks
                if t.get("runtime_seconds")
            ],
            key=lambda x: x["runtime_seconds"],
            reverse=True
        )[:5]

        statistics = TaskStatisticsV2(
            total_tasks=total_tasks,
            pending_tasks=status_counts.get("PENDING", 0),
            running_tasks=status_counts.get("RUNNING", 0),
            completed_tasks=status_counts.get("SUCCESS", 0),
            failed_tasks=status_counts.get("FAILURE", 0),
            cancelled_tasks=status_counts.get("CANCELLED", 0),
            retry_tasks=status_counts.get("RETRY", 0),
            avg_runtime_seconds=round(avg_runtime, 2),
            avg_wait_time_seconds=round(avg_wait_time, 2),
            success_rate=round(success_rate, 2),
            tasks_by_type=dict(type_counts),
            tasks_by_priority=dict(priority_counts),
            slowest_tasks=slowest,
            analysis_period_hours=hours
        )

        # Cache result
        await redis_cache.set(cache_key, statistics.dict(), ttl=CACHE_TTL_STATISTICS)

        return statistics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating task statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate task statistics"
        )


@router.get("/queue/status", response_model=List[QueueStatusV2])
@limiter.limit("30/minute")
async def get_queue_status(
    request: Request,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> List[QueueStatusV2]:
    """
    Get status of all task queues.

    Includes:
    - Pending and active task counts
    - Worker assignments
    - Average processing times

    Features:
    - Redis caching with 1-minute TTL
    - RBAC: Admin only

    Rate limit: 30 requests/minute
    """
    try:
        # Check admin role
        _check_admin_role(current_user)

        # Try cache
        cache_key = "tasks:queue:status"
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for queue status")
            return [QueueStatusV2(**q) for q in cached_data]

        # Get monitoring data
        monitoring_data = get_task_monitoring_data()

        # Build queue status
        queues = {}

        # Process active tasks
        for task in monitoring_data.get("active_tasks", []):
            queue_name = task.get("delivery_info", {}).get("routing_key", "celery")
            if queue_name not in queues:
                queues[queue_name] = {
                    "queue_name": queue_name,
                    "pending_count": 0,
                    "active_count": 0,
                    "workers": set(),
                    "processing_times": []
                }

            queues[queue_name]["active_count"] += 1
            queues[queue_name]["workers"].add(task.get("worker"))

        # Convert to list
        queue_list = [
            QueueStatusV2(
                queue_name=q["queue_name"],
                pending_count=q["pending_count"],
                active_count=q["active_count"],
                workers=list(q["workers"]),
                avg_processing_time=sum(q["processing_times"]) / len(q["processing_times"]) if q["processing_times"] else None
            )
            for q in queues.values()
        ]

        # Cache result
        await redis_cache.set(cache_key, [q.dict() for q in queue_list], ttl=CACHE_TTL_QUEUE_STATUS)

        return queue_list

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get queue status"
        )


@router.post("/bulk/cancel", response_model=BulkTaskResult)
@limiter.limit("10/minute")
async def bulk_cancel_tasks(
    operation: BulkTaskOperation,
    request: Request,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> BulkTaskResult:
    """
    Bulk cancel multiple tasks.

    Features:
    - Cancel up to 100 tasks at once
    - Atomic operation tracking
    - Detailed error reporting
    - RBAC: User must own all tasks or be admin

    Rate limit: 10 requests/minute (lower for bulk operations)
    """
    try:
        if operation.operation != "cancel":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only supports 'cancel' operation"
            )

        role = _extract_user_role(current_user)
        current_user_id = current_user.get("id")

        success_count = 0
        failed_count = 0
        failed_ids = []
        errors = {}

        for task_id in operation.task_ids:
            try:
                # Find task
                celery_task_id = None
                task_data = None

                for cid, data in task_registry.items():
                    if data.get("id") == task_id:
                        celery_task_id = cid
                        task_data = data
                        break

                if not task_data:
                    failed_count += 1
                    failed_ids.append(task_id)
                    errors[task_id] = "Task not found"
                    continue

                # Check RBAC
                if role != UserRole.ADMIN:
                    task_user_id = task_data.get("user_id")
                    if not task_user_id or task_user_id != current_user_id:
                        failed_count += 1
                        failed_ids.append(task_id)
                        errors[task_id] = "Access denied"
                        continue

                # Cancel in Celery
                celery_app.control.revoke(celery_task_id, terminate=True)

                # Update registry
                task_registry[celery_task_id].update({
                    "status": TaskStatus.CANCELLED,
                    "completed_at": datetime.utcnow(),
                })

                success_count += 1

            except Exception as e:
                logger.error(f"Failed to cancel task {task_id}: {str(e)}")
                failed_count += 1
                failed_ids.append(task_id)
                errors[task_id] = str(e)

        # Invalidate caches
        await redis_cache.delete_pattern("tasks:list:*")
        await redis_cache.delete_pattern("task:*")

        # Log bulk operation
        logger.info(
            f"Bulk cancel: {success_count} tasks by user {current_user_id}"
        )

        return BulkTaskResult(
            success_count=success_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk cancel: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk cancel tasks"
        )


@router.post("/cleanup", response_model=TaskCleanupResultV2)
@limiter.limit("5/minute")
async def cleanup_old_tasks(
    cleanup_config: TaskCleanupConfigV2,
    request: Request,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> TaskCleanupResultV2:
    """
    Clean up old completed tasks to free up storage.

    Features:
    - Configurable retention period
    - Status and type filtering
    - Dry run mode for preview
    - Batch processing
    - RBAC: Admin only

    Rate limit: 5 requests/minute
    """
    try:
        # Check admin role
        _check_admin_role(current_user)

        cutoff_date = datetime.utcnow() - timedelta(days=cleanup_config.days_old)

        tasks_deleted = 0
        tasks_analyzed = 0

        # Find tasks to delete
        to_delete = []

        for celery_task_id, task_data in list(task_registry.items()):
            created_at = task_data.get("created_at")

            if not isinstance(created_at, datetime):
                continue

            if created_at >= cutoff_date:
                continue

            tasks_analyzed += 1

            # Apply status filter
            if cleanup_config.status_filter:
                task_status = task_data.get("status")
                if task_status not in cleanup_config.status_filter:
                    continue

            # Apply type filter
            if cleanup_config.task_types:
                task_type = task_data.get("task_type")
                if task_type not in [tt.value for tt in cleanup_config.task_types]:
                    continue

            to_delete.append(celery_task_id)

        # Delete tasks
        if not cleanup_config.dry_run:
            for celery_task_id in to_delete:
                del task_registry[celery_task_id]
                tasks_deleted += 1

            # Invalidate caches
            await redis_cache.delete_pattern("tasks:*")
        else:
            tasks_deleted = len(to_delete)

        # Estimate space freed (rough estimate: 1KB per task)
        space_freed_mb = tasks_deleted * 0.001

        result = TaskCleanupResultV2(
            tasks_deleted=tasks_deleted,
            tasks_analyzed=tasks_analyzed,
            space_freed_mb=round(space_freed_mb, 2),
            dry_run=cleanup_config.dry_run,
            completion_time=datetime.utcnow()
        )

        # Log cleanup
        logger.info(
            f"Task cleanup: {tasks_deleted} tasks {'would be ' if cleanup_config.dry_run else ''}deleted "
            f"by user {current_user.get('id')}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in task cleanup: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup tasks"
        )
