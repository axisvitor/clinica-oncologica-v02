"""
Task management and monitoring endpoints.
"""
from typing import Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.utils.task_monitoring import get_task_monitoring_data, task_monitor
from app.tasks.messaging import (
    send_bulk_messages,
    process_scheduled_messages,
    retry_failed_messages,
    cleanup_old_messages,
    generate_message_analytics
)
from app.schemas.common import SuccessResponse


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/status", response_model=None)
async def get_task_status(
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Get current task system status and monitoring data.
    
    Requires authentication.
    """
    try:
        monitoring_data = get_task_monitoring_data()
        return {
            "success": True,
            "data": monitoring_data
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(exc)}"
        )


@router.get("/active", response_model=None)
async def get_active_tasks(
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Get currently active tasks.
    
    Requires authentication.
    """
    try:
        active_tasks = task_monitor.get_active_tasks()
        return {
            "success": True,
            "active_tasks": active_tasks,
            "count": len(active_tasks)
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active tasks: {str(exc)}"
        )


@router.get("/scheduled", response_model=None)
async def get_scheduled_tasks(
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Get scheduled tasks.
    
    Requires authentication.
    """
    try:
        scheduled_tasks = task_monitor.get_scheduled_tasks()
        return {
            "success": True,
            "scheduled_tasks": scheduled_tasks,
            "count": len(scheduled_tasks)
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scheduled tasks: {str(exc)}"
        )


@router.get("/workers", response_model=None)
async def get_worker_stats(
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Get Celery worker statistics.
    
    Requires authentication.
    """
    try:
        worker_stats = task_monitor.get_worker_stats()
        return {
            "success": True,
            "workers": worker_stats,
            "worker_count": len(worker_stats)
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get worker stats: {str(exc)}"
        )


@router.post("/messaging/process-scheduled", response_model=SuccessResponse)
async def trigger_process_scheduled_messages(
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: User = Depends(get_current_user)
) -> SuccessResponse:
    """
    Manually trigger processing of scheduled messages.
    
    Args:
        limit: Maximum number of messages to process
        
    Requires authentication.
    """
    try:
        # Trigger the task asynchronously
        task = process_scheduled_messages.delay(limit=limit)
        
        return SuccessResponse(
            message=f"Scheduled message processing triggered with limit {limit}",
            data={
                "task_id": task.id,
                "limit": limit,
                "triggered_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger scheduled message processing: {str(exc)}"
        )


@router.post("/messaging/retry-failed", response_model=SuccessResponse)
async def trigger_retry_failed_messages(
    limit: int = Query(default=50, ge=1, le=500),
    max_retries: int = Query(default=3, ge=1, le=10),
    current_user: User = Depends(get_current_user)
) -> SuccessResponse:
    """
    Manually trigger retry of failed messages.
    
    Args:
        limit: Maximum number of messages to retry
        max_retries: Maximum retry attempts per message
        
    Requires authentication.
    """
    try:
        # Trigger the task asynchronously
        task = retry_failed_messages.delay(limit=limit, max_retries=max_retries)
        
        return SuccessResponse(
            message=f"Failed message retry triggered with limit {limit}",
            data={
                "task_id": task.id,
                "limit": limit,
                "max_retries": max_retries,
                "triggered_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger message retry: {str(exc)}"
        )


@router.post("/messaging/bulk-send", response_model=SuccessResponse)
async def trigger_bulk_message_send(
    message_data: List[dict[str, Any]],
    current_user: User = Depends(get_current_user)
) -> SuccessResponse:
    """
    Send multiple messages in bulk.
    
    Args:
        message_data: List of message data dictionaries
        
    Requires authentication.
    """
    try:
        if not message_data:
            raise HTTPException(
                status_code=400,
                detail="Message data list cannot be empty"
            )
        
        if len(message_data) > 1000:
            raise HTTPException(
                status_code=400,
                detail="Cannot send more than 1000 messages in a single bulk operation"
            )
        
        # Trigger the task asynchronously
        task = send_bulk_messages.delay(message_data)
        
        return SuccessResponse(
            message=f"Bulk message sending triggered for {len(message_data)} messages",
            data={
                "task_id": task.id,
                "message_count": len(message_data),
                "triggered_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger bulk message sending: {str(exc)}"
        )


@router.post("/messaging/cleanup", response_model=SuccessResponse)
async def trigger_message_cleanup(
    days_old: int = Query(default=90, ge=30, le=365),
    current_user: User = Depends(get_current_user)
) -> SuccessResponse:
    """
    Manually trigger cleanup of old messages.
    
    Args:
        days_old: Number of days after which messages should be cleaned up
        
    Requires authentication.
    """
    try:
        # Trigger the task asynchronously
        task = cleanup_old_messages.delay(days_old=days_old)
        
        return SuccessResponse(
            message=f"Message cleanup triggered for messages older than {days_old} days",
            data={
                "task_id": task.id,
                "days_old": days_old,
                "triggered_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger message cleanup: {str(exc)}"
        )


@router.post("/messaging/analytics", response_model=SuccessResponse)
async def trigger_message_analytics(
    patient_id: Optional[str] = Query(default=None),
    days_back: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user)
) -> SuccessResponse:
    """
    Generate message analytics.
    
    Args:
        patient_id: Optional patient ID to filter analytics
        days_back: Number of days to look back for analytics
        
    Requires authentication.
    """
    try:
        # Trigger the task asynchronously
        task = generate_message_analytics.delay(
            patient_id=patient_id,
            days_back=days_back
        )
        
        return SuccessResponse(
            message=f"Message analytics generation triggered for {days_back} days",
            data={
                "task_id": task.id,
                "patient_id": patient_id,
                "days_back": days_back,
                "triggered_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger message analytics: {str(exc)}"
        )


@router.get("/result/{task_id}", response_model=None)
async def get_task_result(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Get the result of a specific task.
    
    Args:
        task_id: The ID of the task to check
        
    Requires authentication.
    """
    try:
        from app.celery_app import celery_app
        
        # Get task result
        result = celery_app.AsyncResult(task_id)
        
        response_data = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "failed": result.failed() if result.ready() else None,
        }
        
        if result.ready():
            if result.successful():
                response_data["result"] = result.result
            elif result.failed():
                response_data["error"] = str(result.info)
                response_data["traceback"] = result.traceback
        
        return {
            "success": True,
            "data": response_data
        }
        
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task result: {str(exc)}"
        )