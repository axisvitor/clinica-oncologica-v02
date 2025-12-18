"""
Tasks Bulk Operations Endpoints - Bulk task operations and maintenance.

Endpoints:
- POST /bulk/cancel - Bulk cancel multiple tasks
- POST /cleanup - Clean up old completed tasks
"""

from typing import Dict
from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.database import get_db
from app.models.user import UserRole
from app.schemas.v2.tasks import (
    BulkTaskOperation,
    BulkTaskResult,
    TaskCleanupConfigV2,
    TaskCleanupResultV2,
    TaskStatus,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.celery_app import celery_app

from ..dependencies import (
    _get_current_user_simple,
    _extract_user_role,
    _check_admin_role,
    task_registry,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/bulk/cancel", response_model=BulkTaskResult)
@limiter.limit("10/minute")
async def bulk_cancel_tasks(
    operation: BulkTaskOperation,
    request: Request,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
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
                detail="This endpoint only supports 'cancel' operation",
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
                task_registry[celery_task_id].update(
                    {
                        "status": TaskStatus.CANCELLED,
                        "completed_at": datetime.utcnow(),
                    }
                )

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
        logger.info(f"Bulk cancel: {success_count} tasks by user {current_user_id}")

        return BulkTaskResult(
            success_count=success_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            errors=errors,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk cancel: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk cancel tasks",
        )


@router.post("/cleanup", response_model=TaskCleanupResultV2)
@limiter.limit("5/minute")
async def cleanup_old_tasks(
    cleanup_config: TaskCleanupConfigV2,
    request: Request,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
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
            completion_time=datetime.utcnow(),
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
            detail="Failed to cleanup tasks",
        )
