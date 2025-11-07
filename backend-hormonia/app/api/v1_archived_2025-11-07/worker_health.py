"""
Worker Health Check Endpoint

Provides health status for Celery workers, beat scheduler, and background tasks.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.celery_app import celery_app
from app.models.message import Message, MessageStatus
from app.models.flow import PatientFlowState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/worker", tags=["worker-health"])


@router.get("/health", response_model=Dict[str, Any])
async def get_worker_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get comprehensive health status of background workers and tasks.
    
    Returns:
        Dictionary containing:
        - worker_status: Celery worker status
        - beat_status: Celery beat scheduler status
        - queue_status: Message queue status
        - flow_status: Flow processing status
        - overall_healthy: Overall health indicator
    """
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "overall_healthy": True,
        "worker_status": {},
        "beat_status": {},
        "queue_status": {},
        "flow_status": {},
        "issues": []
    }
    
    try:
        # Check Celery workers
        inspect = celery_app.control.inspect()
        
        # Active workers
        active_workers = inspect.active()
        if active_workers:
            health_status["worker_status"] = {
                "status": "healthy",
                "active_workers": len(active_workers),
                "worker_names": list(active_workers.keys()),
                "active_tasks": sum(len(tasks) for tasks in active_workers.values())
            }
        else:
            health_status["worker_status"] = {
                "status": "unhealthy",
                "active_workers": 0,
                "error": "No active workers found"
            }
            health_status["overall_healthy"] = False
            health_status["issues"].append("No Celery workers are running")
        
        # Check scheduled tasks (beat)
        scheduled = inspect.scheduled()
        if scheduled is not None:
            health_status["beat_status"] = {
                "status": "healthy",
                "scheduled_tasks": sum(len(tasks) for tasks in scheduled.values()) if scheduled else 0
            }
        else:
            health_status["beat_status"] = {
                "status": "warning",
                "scheduled_tasks": 0,
                "message": "Beat scheduler status unknown"
            }
            health_status["issues"].append("Celery beat scheduler status could not be determined")
        
        # Check message queue status
        pending_messages = db.query(Message).filter(
            Message.status.in_([MessageStatus.PENDING, MessageStatus.SCHEDULED])
        ).count()
        
        failed_messages_24h = db.query(Message).filter(
            Message.status == MessageStatus.FAILED,
            Message.updated_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        health_status["queue_status"] = {
            "status": "healthy" if failed_messages_24h < 10 else "warning",
            "pending_messages": pending_messages,
            "failed_messages_24h": failed_messages_24h
        }
        
        if failed_messages_24h >= 10:
            health_status["issues"].append(f"{failed_messages_24h} messages failed in last 24 hours")
        
        # Check flow processing status
        active_flows = db.query(PatientFlowState).filter(
            PatientFlowState.completed_at.is_(None)
        ).count()
        
        stale_flows = db.query(PatientFlowState).filter(
            PatientFlowState.completed_at.is_(None),
            PatientFlowState.next_scheduled_at < datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        health_status["flow_status"] = {
            "status": "healthy" if stale_flows < 5 else "warning",
            "active_flows": active_flows,
            "stale_flows": stale_flows
        }
        
        if stale_flows >= 5:
            health_status["issues"].append(f"{stale_flows} flows have not been processed in 24+ hours")
        
        # Check Redis connection
        try:
            from app.core.redis_unified import get_sync_redis
            redis_client = get_sync_redis()
            redis_client.ping()
            health_status["redis_status"] = {"status": "healthy"}
        except Exception as e:
            health_status["redis_status"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["overall_healthy"] = False
            health_status["issues"].append(f"Redis connection failed: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error checking worker health: {e}", exc_info=True)
        health_status["overall_healthy"] = False
        health_status["error"] = str(e)
        health_status["issues"].append(f"Health check failed: {str(e)}")
    
    return health_status


@router.get("/tasks/active", response_model=Dict[str, Any])
async def get_active_tasks() -> Dict[str, Any]:
    """
    Get list of currently active Celery tasks.
    
    Returns:
        Dictionary containing active tasks by worker
    """
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        
        if not active:
            return {
                "status": "no_workers",
                "message": "No active workers found",
                "active_tasks": {}
            }
        
        # Format active tasks
        formatted_tasks = {}
        for worker, tasks in active.items():
            formatted_tasks[worker] = [
                {
                    "id": task["id"],
                    "name": task["name"],
                    "args": task.get("args", []),
                    "kwargs": task.get("kwargs", {}),
                    "time_start": task.get("time_start")
                }
                for task in tasks
            ]
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "total_workers": len(active),
            "total_tasks": sum(len(tasks) for tasks in active.values()),
            "active_tasks": formatted_tasks
        }
        
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/scheduled", response_model=Dict[str, Any])
async def get_scheduled_tasks() -> Dict[str, Any]:
    """
    Get list of scheduled Celery tasks (from beat).
    
    Returns:
        Dictionary containing scheduled tasks
    """
    try:
        inspect = celery_app.control.inspect()
        scheduled = inspect.scheduled()
        
        if scheduled is None:
            return {
                "status": "unknown",
                "message": "Could not retrieve scheduled tasks",
                "scheduled_tasks": {}
            }
        
        # Format scheduled tasks
        formatted_tasks = {}
        for worker, tasks in scheduled.items():
            formatted_tasks[worker] = [
                {
                    "id": task["request"]["id"],
                    "name": task["request"]["name"],
                    "eta": task["eta"],
                    "priority": task.get("priority", 0)
                }
                for task in tasks
            ]
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "total_scheduled": sum(len(tasks) for tasks in scheduled.values()),
            "scheduled_tasks": formatted_tasks
        }
        
    except Exception as e:
        logger.error(f"Error getting scheduled tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=Dict[str, Any])
async def get_worker_stats() -> Dict[str, Any]:
    """
    Get Celery worker statistics.
    
    Returns:
        Dictionary containing worker statistics
    """
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            return {
                "status": "no_workers",
                "message": "No active workers found",
                "stats": {}
            }
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "worker_stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting worker stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

