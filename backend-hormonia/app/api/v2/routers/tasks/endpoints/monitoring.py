"""
Tasks Monitoring Endpoints - Task monitoring and analytics.

Endpoints:
- GET /{task_id}/logs - Get task execution logs
- GET /statistics/overview - Get comprehensive task system statistics
- GET /queue/status - Get status of all task queues
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from collections import defaultdict
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request

from app.database import get_db
from app.models.user import UserRole
from app.schemas.v2.tasks import (
    TaskV2WithLogs,
    TaskStatisticsV2,
    QueueStatusV2,
    TaskStatus,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.utils.task_monitoring import get_task_monitoring_data

from ..dependencies import (
    _get_current_user_simple,
    _extract_user_role,
    _check_admin_role,
    _get_task_from_celery,
    task_registry,
)
from ..utils import (
    CACHE_TTL_STATISTICS,
    CACHE_TTL_QUEUE_STATUS,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
