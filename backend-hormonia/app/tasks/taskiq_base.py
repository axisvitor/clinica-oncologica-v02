"""
Base patterns for Taskiq tasks (M009).

Provides:
- DB session dependency via TaskiqDepends (AsyncSession)
- Task logging helpers (structured start/success/error logging)
- ETA/delayed dispatch helper (schedule_task_at)
- Retry configuration documentation and patterns

Usage:
    from app.tasks.taskiq_base import DbSession, log_task_start, log_task_success, log_task_error
    from app.taskiq_broker import broker

    @broker.task(retry_on_error=True, max_retries=3, delay=60)
    async def my_task(patient_id: int, db: AsyncSession = DbSession) -> dict:
        log_task_start("my_task", patient_id=patient_id)
        try:
            result = await db.execute(select(Patient).where(Patient.id == patient_id))
            patient = result.scalar_one_or_none()
            log_task_success("my_task", patient_id=patient_id)
            return {"status": "ok", "patient": patient.name}
        except Exception as e:
            log_task_error("my_task", e, patient_id=patient_id)
            raise

Retry Configuration (via SmartRetryMiddleware labels):
    @broker.task(
        retry_on_error=True,   # Enable retry on exception
        max_retries=3,         # Max retry attempts
        delay=60,              # Base delay in seconds (exponential backoff applied)
    )

    The SmartRetryMiddleware (configured in taskiq_broker.py) applies:
    - Exponential backoff: delay * 2^attempt (capped at max_delay_exponent=600s)
    - Jitter: ±random to avoid thundering herd
    - Per-task override via labels in @broker.task() decorator
"""

import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends

logger = logging.getLogger("app.tasks")


# ---------------------------------------------------------------------------
# DB session dependency — resolves to an AsyncSession inside Taskiq worker.
#
# This replaces the Celery pattern of `get_scoped_session()` (sync).
# The session is created fresh per task execution and closed after.
# Uses the same async engine/session factory as FastAPI endpoints.
# ---------------------------------------------------------------------------

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async DB session for Taskiq tasks.

    Yields an AsyncSession that auto-rolls back on exception
    and closes after the task completes. Compatible with
    TaskiqDepends for automatic injection.
    """
    from app.core.database.async_engine import get_async_session_factory

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# TaskiqDepends shorthand — use as default parameter in task signatures.
# Example: async def my_task(db: AsyncSession = DbSession)
DbSession = TaskiqDepends(get_db_session)


# ---------------------------------------------------------------------------
# Task logging helpers — structured logging for task lifecycle events.
# These produce consistent log lines that can be searched/filtered.
# ---------------------------------------------------------------------------

def log_task_start(task_name: str, **context: Any) -> float:
    """
    Log task start. Returns start timestamp for duration calculation.

    Args:
        task_name: Name of the task being executed.
        **context: Key-value pairs for structured log context.

    Returns:
        Start time (time.monotonic) for use with log_task_success.
    """
    extra = {"task_name": task_name, "event": "task_start", **context}
    logger.info(f"Task started: {task_name}", extra=extra)
    return time.monotonic()


def log_task_success(task_name: str, start_time: float = 0.0, **context: Any) -> None:
    """
    Log task success with optional duration.

    Args:
        task_name: Name of the task that completed.
        start_time: Value from log_task_start for duration calculation.
        **context: Key-value pairs for structured log context.
    """
    duration_ms = round((time.monotonic() - start_time) * 1000, 2) if start_time else 0.0
    extra = {
        "task_name": task_name,
        "event": "task_success",
        "duration_ms": duration_ms,
        **context,
    }
    logger.info(f"Task completed: {task_name} ({duration_ms}ms)", extra=extra)


def log_task_error(task_name: str, error: Exception, start_time: float = 0.0, **context: Any) -> None:
    """
    Log task error with exception details and optional duration.

    Args:
        task_name: Name of the task that failed.
        error: The exception that occurred.
        start_time: Value from log_task_start for duration calculation.
        **context: Key-value pairs for structured log context.
    """
    duration_ms = round((time.monotonic() - start_time) * 1000, 2) if start_time else 0.0
    extra = {
        "task_name": task_name,
        "event": "task_error",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "duration_ms": duration_ms,
        **context,
    }
    logger.error(f"Task failed: {task_name} — {type(error).__name__}: {error}", extra=extra)


# ---------------------------------------------------------------------------
# ETA / delayed dispatch helper — replaces Celery's .apply_async(eta=datetime)
# ---------------------------------------------------------------------------

async def schedule_task_at(task: Any, scheduled_time: datetime, *args: Any, **kwargs: Any) -> Any:
    """
    Schedule a Taskiq task to execute at a specific future time.

    Replaces Celery's `task.apply_async(args=(...,), eta=datetime)` pattern.
    Uses `ListRedisScheduleSource` to store a one-shot schedule in Redis/Dragonfly
    that fires at `scheduled_time`.

    Args:
        task: A Taskiq AsyncKicker-compatible task (e.g. `send_scheduled_message`).
        scheduled_time: When the task should execute (datetime, should be UTC).
        *args: Positional arguments passed to the task.
        **kwargs: Keyword arguments passed to the task.

    Returns:
        CreatedSchedule — contains `schedule_id` for tracking/cancellation.

    Example:
        from app.tasks.messaging_taskiq import send_scheduled_message
        from app.tasks.taskiq_base import schedule_task_at

        result = await schedule_task_at(
            send_scheduled_message,
            delivery_time,
            str(message.id),
        )
    """
    # Lazy import to avoid circular dependency:
    # taskiq_broker → (broker used by task modules) → taskiq_base → taskiq_broker
    from app.taskiq_broker import dynamic_schedule_source

    return await task.kicker().schedule_by_time(
        dynamic_schedule_source,
        scheduled_time,
        *args,
        **kwargs,
    )
