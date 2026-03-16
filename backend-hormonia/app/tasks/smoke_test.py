"""
Smoke test tasks for Taskiq broker verification (M009/S01).

These tasks exist to prove the Taskiq infrastructure works:
- Basic task dispatch + execution + result
- Retry middleware (deliberately failing task)
- Scheduled task (cron-based periodic)

Remove or repurpose after M009 migration is complete.
"""

import asyncio
import logging
from datetime import datetime

from app.taskiq_broker import broker

logger = logging.getLogger(__name__)


@broker.task
async def smoke_test_echo(message: str = "hello") -> dict:
    """
    Simple echo task — proves dispatch → worker → result pipeline.
    """
    logger.info(f"smoke_test_echo received: {message}")
    return {
        "status": "ok",
        "message": message,
        "executed_at": datetime.utcnow().isoformat(),
        "worker": "taskiq",
    }


_fail_counter: dict[str, int] = {}


@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=2,
)
async def smoke_test_retry(task_id: str = "default") -> dict:
    """
    Deliberately fails twice, then succeeds on third attempt.
    Proves SmartRetryMiddleware works with exponential backoff.
    """
    _fail_counter.setdefault(task_id, 0)
    _fail_counter[task_id] += 1
    attempt = _fail_counter[task_id]

    logger.info(f"smoke_test_retry attempt {attempt} for {task_id}")

    if attempt < 3:
        raise RuntimeError(f"Deliberate failure on attempt {attempt} (will retry)")

    # Reset for next test run
    result_attempt = attempt
    _fail_counter.pop(task_id, None)

    return {
        "status": "ok",
        "succeeded_on_attempt": result_attempt,
        "task_id": task_id,
    }


@broker.task(
    schedule=[{"cron": "* * * * *", "args": []}],
)
async def smoke_test_scheduled() -> dict:
    """
    Fires every minute via LabelScheduleSource.
    Proves the scheduler reads task labels and dispatches.
    """
    logger.info("smoke_test_scheduled fired")
    return {
        "status": "ok",
        "fired_at": datetime.utcnow().isoformat(),
        "type": "scheduled",
    }
