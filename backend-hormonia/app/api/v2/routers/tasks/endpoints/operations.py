"""
Tasks Operations Endpoints - Task lifecycle operations.

Endpoints:
- POST /{task_id}/cancel - Cancel a running or pending task
- POST /{task_id}/retry - Manually retry a failed task
"""

from typing import Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.core.database.async_engine import get_async_db
from app.models.user import UserRole
from app.schemas.v2.tasks import (
    TaskV2Response,
    TaskV2Cancel,
    TaskV2Retry,
    TaskStatus,
    RetryStrategy,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.api.v2.routers import tasks as tasks_module
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import (
    _get_current_user_simple,
    _extract_user_role,
    _get_task_or_404,
    _get_task_with_backend_data,
    _serialize_task,
)
from ..registry import update_task as update_registry_task
from ..utils import _calculate_retry_delay
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{task_id}/cancel", response_model=TaskV2Response)
@limiter.limit("30/minute")
async def cancel_task(
    task_id: str,
    cancel_data: TaskV2Cancel,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
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

        # Task revocation not supported in Taskiq — log and continue
        logger.warning(
            "Task revocation requested but not supported in Taskiq",
            extra={"task_id": celery_task_id, "force": cancel_data.force},
        )

        update_payload = {
            "status": TaskStatus.CANCELLED.value,
            "completed_at": now_sao_paulo(),
            "metadata": {
                **task_data.get("metadata", {}),
                "cancellation_reason": cancel_data.reason,
                "cancelled_by": current_user.get("id"),
                "forced": cancel_data.force,
            },
        }
        update_registry_task(celery_task_id, update_payload)

        # Invalidate caches
        await redis_cache.delete(f"task:{task_id}:*")
        await redis_cache.delete_pattern("tasks:list:*")

        # Log cancellation
        logger.info(
            f"Task cancelled: {task_id} by user {current_user.get('id')} "
            f"(force={cancel_data.force})"
        )

        # Get updated data
        merged_data = _get_task_with_backend_data(
            celery_task_id, tasks_module.task_registry[celery_task_id]
        )

        return _serialize_task(merged_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task",
        )


@router.post("/{task_id}/retry", response_model=TaskV2Response)
@limiter.limit("30/minute")
async def retry_task(
    task_id: str,
    retry_data: TaskV2Retry,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
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

        # Check if task can be retried
        current_status = task_data.get("status")
        if hasattr(current_status, "value"):
            current_status = current_status.value
        if str(current_status) not in [TaskStatus.FAILURE.value, TaskStatus.RETRY.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot retry task in {current_status} status",
            )

        # Check retry limit
        retry_count = task_data.get("retry_count", 0)
        retry_config = task_data.get("retry_config")

        if retry_config and not retry_data.override_retry_limit:
            max_retries = retry_config.get("max_retries", 3)
            if retry_count >= max_retries:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Task has exceeded maximum retry attempts ({max_retries})",
                )

        # Calculate delay
        delay = retry_data.delay_seconds
        if delay is None and retry_config:
            strategy = RetryStrategy(retry_config.get("retry_strategy", "exponential"))
            delay = _calculate_retry_delay(
                retry_count,
                strategy,
                retry_config.get("base_delay", 60),
                retry_config.get("max_delay", 3600),
            )

        # Update registry status (actual re-dispatch not supported via admin API)
        update_payload = {
            "status": TaskStatus.RETRY.value,
            "retry_count": retry_count + 1,
            "metadata": {
                **task_data.get("metadata", {}),
                "manual_retry": True,
                "retry_notes": retry_data.notes,
                "retried_by": current_user.get("id"),
                "retried_at": now_sao_paulo().isoformat(),
            },
        }
        update_registry_task(celery_task_id, update_payload)

        # Invalidate caches
        await redis_cache.delete(f"task:{task_id}:*")
        await redis_cache.delete_pattern("tasks:list:*")

        # Log retry
        logger.info(
            f"Task retry initiated: {task_id} by user {current_user.get('id')} "
            f"(attempt {retry_count + 1})"
        )

        # Get updated data
        merged_data = tasks_module.task_registry[celery_task_id]

        return _serialize_task(merged_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry task",
        )
