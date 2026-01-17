"""
Internal task execution endpoints for Cloud Tasks.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.config import settings
from app.task_queue import (
    CloudTaskRetry,
    TaskAuthError,
    append_task_log,
    get_task as get_stored_task,
    store_task,
    task_queue,
    update_task,
    validate_task_request,
)

router = APIRouter()


class TaskExecutionPayload(BaseModel):
    task_name: str = Field(..., description="Registered task name")
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[str] = None
    retries: int = 0
    scheduled_at: Optional[datetime] = None


@router.post("/execute", include_in_schema=False)
async def execute_task(payload: TaskExecutionPayload, request: Request) -> Dict[str, Any]:
    if settings.TASK_QUEUE_PROVIDER.lower() != "cloud_tasks":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cloud Tasks execution is not enabled",
        )

    try:
        validate_task_request(request.headers)
    except TaskAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    task_id = payload.task_id
    if not task_id:
        header_task_name = request.headers.get("X-CloudTasks-TaskName")
        if header_task_name:
            task_id = header_task_name.split("/")[-1]
    task_id = task_id or str(uuid4())
    if not get_stored_task(task_id):
        store_task(
            {
                "id": task_id,
                "task_name": payload.task_name,
                "args": payload.args,
                "kwargs": payload.kwargs,
                "status": "PENDING",
                "queue_name": "cloud_tasks",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    started_at = datetime.now(timezone.utc)
    try:
        result = await run_in_threadpool(
            task_queue.execute,
            payload.task_name,
            payload.args,
            payload.kwargs,
            task_id,
            payload.retries,
        )
    except CloudTaskRetry as retry_exc:
        countdown = retry_exc.countdown or 0
        update_task(
            task_id,
            {
                "status": "RETRY",
                "retry_count": payload.retries + 1,
                "scheduled_at": (
                    datetime.now(timezone.utc) + timedelta(seconds=countdown)
                ).isoformat(),
            },
        )
        append_task_log(
            task_id,
            {
                "level": "WARNING",
                "message": str(retry_exc.exc or "retry"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        task_queue.enqueue(
            payload.task_name,
            args=payload.args,
            kwargs=payload.kwargs,
            countdown=countdown,
            retries=payload.retries + 1,
            task_id=task_id,
        )
        return {
            "status": "retry_scheduled",
            "task_id": task_id,
            "retry_count": payload.retries + 1,
            "scheduled_at": (
                datetime.now(timezone.utc) + timedelta(seconds=countdown)
            ).isoformat(),
        }
    except Exception as exc:
        runtime = (datetime.now(timezone.utc) - started_at).total_seconds()
        update_task(
            task_id,
            {
                "status": "FAILURE",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "runtime_seconds": round(runtime, 2),
                "error": str(exc),
            },
        )
        append_task_log(
            task_id,
            {
                "level": "ERROR",
                "message": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    runtime = (datetime.now(timezone.utc) - started_at).total_seconds()
    update_task(
        task_id,
        {
            "status": "SUCCESS",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "runtime_seconds": round(runtime, 2),
            "result": result,
        },
    )
    append_task_log(
        task_id,
        {
            "level": "INFO",
            "message": "Task completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"status": "ok", "task_id": task_id, "result": result}
