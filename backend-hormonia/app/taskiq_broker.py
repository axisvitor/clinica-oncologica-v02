"""
Taskiq broker configuration for Hormonia Backend System.

Async-native task queue replacing Celery (M009).
Uses Dragonfly (Redis-compatible) as broker and result backend.

IMPORTANT: taskiq_fastapi.init() is called AFTER broker creation but
BEFORE any task definitions that use TaskiqDepends. This module must
be imported before task modules.
"""

import logging
import os
from typing import Optional

import taskiq_fastapi
from taskiq import TaskiqScheduler
from taskiq.middlewares import SmartRetryMiddleware
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker, ListRedisScheduleSource, RedisAsyncResultBackend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Broker URL — Dragonfly on port 6380 (non-standard, see decision #63)
# Reads from env directly to avoid importing heavy app.config.settings
# (which requires ALL env vars including WuzAPI tokens).
# Falls back to the Celery broker URL, then to localhost:6380.
# ---------------------------------------------------------------------------
_broker_url = (
    os.environ.get("TASKIQ_BROKER_URL")
    or os.environ.get("CELERY_BROKER_URL")
    or os.environ.get("REDIS_URL")
    or "redis://localhost:6380/0"
)

# ---------------------------------------------------------------------------
# Result backend — stores task results in Dragonfly with 1h TTL
# ---------------------------------------------------------------------------
result_backend = RedisAsyncResultBackend(
    redis_url=_broker_url,
    result_ex_time=3600,  # 1 hour
)

# ---------------------------------------------------------------------------
# Broker — ListQueueBroker for simple FIFO dispatch (no ack overhead)
#
# Decision #74: Taskiq replaces Celery as async-native task queue.
# ListQueueBroker chosen over RedisStreamBroker for simplicity —
# tasks already have their own retry logic and we don't need
# consumer groups or stream acknowledgement.
# ---------------------------------------------------------------------------
broker = ListQueueBroker(
    url=_broker_url,
    queue_name="hormonia",
).with_result_backend(result_backend).with_middlewares(
    SmartRetryMiddleware(
        default_retry_count=3,
        default_delay=60,
        use_jitter=True,
        use_delay_exponent=True,
        max_delay_exponent=600,  # cap at 10 minutes (matches Celery retry_backoff_max)
    ),
)

# ---------------------------------------------------------------------------
# FastAPI integration — allows TaskiqDepends to resolve FastAPI dependencies
# inside tasks. Must be called AFTER broker creation, BEFORE task definitions.
# The app path string is resolved lazily when the worker starts.
# ---------------------------------------------------------------------------
taskiq_fastapi.init(broker, "app.main:app")

# ---------------------------------------------------------------------------
# Scheduler — combines two schedule sources:
#   - LabelScheduleSource: reads cron/interval from @broker.task() labels (static, periodic)
#   - ListRedisScheduleSource: stores one-shot delayed dispatch in Redis (dynamic, ETA)
#
# LabelScheduleSource does NOT support add_schedule() — it raises NotImplementedError.
# ListRedisScheduleSource is required for the .apply_async(eta=datetime) replacement
# pattern used by task_scheduler.py, retry_handler.py, and send_bulk_messages.
# ---------------------------------------------------------------------------
schedule_source = LabelScheduleSource(broker)
dynamic_schedule_source = ListRedisScheduleSource(url=_broker_url)
scheduler = TaskiqScheduler(broker, sources=[schedule_source, dynamic_schedule_source])


def get_broker_status() -> dict:
    """
    Return broker connection status for health checks.

    This replaces the Celery `control.inspect()` pattern used in
    health/core.py and health/service_health.py.
    """
    try:
        return {
            "taskiq": {
                "status": "configured",
                "broker_type": "ListQueueBroker",
                "broker_url": _broker_url.split("@")[-1] if "@" in _broker_url else _broker_url,
                "queue_name": "hormonia",
                "result_backend": "RedisAsyncResultBackend",
                "retry_middleware": "SmartRetryMiddleware",
                "scheduler_sources": ["LabelScheduleSource", "ListRedisScheduleSource"],
            }
        }
    except Exception as e:
        logger.error(f"Failed to get broker status: {e}")
        return {"taskiq": {"status": "error", "error": str(e)}}


async def check_broker_health() -> dict:
    """
    Async health check — pings Dragonfly via the broker's Redis connection.
    """
    try:
        # Use the result backend's Redis connection for a quick ping
        from redis.asyncio import Redis

        client = Redis.from_url(_broker_url, decode_responses=True)
        try:
            pong = await client.ping()
            return {
                "taskiq_broker": "healthy" if pong else "unhealthy",
                "dragonfly_reachable": bool(pong),
            }
        finally:
            await client.aclose()
    except Exception as e:
        logger.error(f"Taskiq broker health check failed: {e}")
        return {
            "taskiq_broker": "unhealthy",
            "dragonfly_reachable": False,
            "error": str(e),
        }
