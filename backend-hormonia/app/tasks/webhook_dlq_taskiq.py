"""
Taskiq webhook DLQ tasks — async-native replacements for Celery webhook_dlq tasks (M009-S04).

3 tasks migrated from Celery to Taskiq:
  1. process_webhook_dlq    — interval 60s (process failed webhook events)
  2. cleanup_old_dlq_events — cron 0 6 * * * (daily 03:00 BRT → 06:00 UTC)
  3. monitor_dlq_health     — interval 300s (monitor DLQ metrics)

Key translation patterns from Celery → Taskiq:
  - Celery's sync bridge removed → `await service.method()` directly
  - `_retry_or_raise` helper dropped: SmartRetryMiddleware handles retries
  - `self` (bind=True) removed: SmartRetryMiddleware handles retries externally
  - Structured logging via log_task_start/success/error from taskiq_base

Schedule labels (all 3 tasks are periodic):
  - process_webhook_dlq:    interval 60s
  - cleanup_old_dlq_events: cron 0 6 * * * (BRT 03:00 → UTC 06:00)
  - monitor_dlq_health:     interval 300s
"""

import json
import logging
from datetime import timedelta
from typing import Any, Dict

from app.database import get_scoped_session
from app.taskiq_broker import broker
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.config.settings.tasks import (
    QUIZ_DLQ_BATCH_SIZE,
    WEBHOOK_DLQ_PROCESSING_TIMEOUT,
)
from app.services.webhook_dlq import get_webhook_dlq
from app.utils.timezone import now_sao_paulo, to_sao_paulo

logger = logging.getLogger("app.tasks.webhook_dlq_taskiq")


# ===========================================================================
# 1. process_webhook_dlq — periodic (interval 60s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 60}}],
)
async def process_webhook_dlq(batch_size: int = QUIZ_DLQ_BATCH_SIZE) -> Dict[str, Any]:
    """Process webhook Dead Letter Queue with exponential backoff.

    Runs every minute to process failed webhook events that are ready for retry.
    Calls the async DLQ service directly (no sync bridge).

    Args:
        batch_size: Maximum events to process per run.

    Returns:
        Dict with processing statistics.
    """
    start_time = log_task_start("process_webhook_dlq", batch_size=batch_size)
    wall_clock_start = now_sao_paulo()

    try:
        with get_scoped_session() as db:
            dlq_service = get_webhook_dlq(db)

            # Async-native: call directly with await (Celery used sync bridge)
            processed_count = await dlq_service.process_dlq(batch_size=batch_size)

            execution_time_ms = int(
                (now_sao_paulo() - wall_clock_start).total_seconds() * 1000
            )

            log_task_success(
                "process_webhook_dlq",
                start_time,
                processed_count=processed_count,
                execution_time_ms=execution_time_ms,
            )
            return {
                "success": True,
                "processed_count": processed_count,
                "batch_size": batch_size,
                "execution_time_ms": execution_time_ms,
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("process_webhook_dlq", exc, start_time, batch_size=batch_size)
        raise


# ===========================================================================
# 2. cleanup_old_dlq_events — periodic (cron daily 06:00 UTC = 03:00 BRT)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=300,
    schedule=[{"cron": "0 6 * * *"}],
)
async def cleanup_old_dlq_events(days_old: int = 7) -> Dict[str, Any]:
    """Clean up DLQ events older than specified days.

    Runs daily at 03:00 BRT (06:00 UTC) to prevent DLQ from growing
    indefinitely. Uses async Redis SCAN to stream keys without blocking.

    Args:
        days_old: Remove events older than this many days.

    Returns:
        Dict with cleanup statistics.
    """
    start_time = log_task_start("cleanup_old_dlq_events", days_old=days_old)
    wall_clock_start = now_sao_paulo()

    try:
        with get_scoped_session() as db:
            dlq_service = get_webhook_dlq(db)

            from app.core.redis_manager import get_async_redis_client as get_async_redis
            from datetime import datetime

            redis_client = await get_async_redis()

            pattern = f"{dlq_service.DLQ_KEY_PREFIX}:*"
            cleaned = 0
            cutoff = now_sao_paulo() - timedelta(days=days_old)

            async for dlq_key in redis_client.scan_iter(match=pattern):
                events = await redis_client.lrange(dlq_key, 0, -1)
                events_to_remove = []

                for event_json in events:
                    try:
                        event = json.loads(event_json)
                        event_timestamp = datetime.fromisoformat(event["timestamp"])
                        event_timestamp = to_sao_paulo(event_timestamp)

                        if event_timestamp < cutoff:
                            cleaned += 1
                            events_to_remove.append(event_json)
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning("Invalid event in DLQ, removing: %s", e)
                        cleaned += 1
                        events_to_remove.append(event_json)

                for event_json in events_to_remove:
                    await redis_client.lrem(dlq_key, 1, event_json)

            execution_time_ms = int(
                (now_sao_paulo() - wall_clock_start).total_seconds() * 1000
            )

            log_task_success(
                "cleanup_old_dlq_events",
                start_time,
                cleaned_count=cleaned,
                days_old=days_old,
            )
            return {
                "success": True,
                "cleaned_count": cleaned,
                "days_old": days_old,
                "cutoff_date": cutoff.isoformat(),
                "execution_time_ms": execution_time_ms,
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("cleanup_old_dlq_events", exc, start_time, days_old=days_old)
        raise


# ===========================================================================
# 3. monitor_dlq_health — periodic (interval 300s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 300}}],
)
async def monitor_dlq_health() -> Dict[str, Any]:
    """Monitor DLQ health and trigger alerts if needed.

    Checks queue size, processing rate, dead letter rate, and
    retry exhaustion rate. Critical alerts are logged as errors.

    Returns:
        Dict with health metrics and any triggered alerts.
    """
    start_time = log_task_start("monitor_dlq_health")
    wall_clock_start = now_sao_paulo()

    try:
        with get_scoped_session() as db:
            dlq_service = get_webhook_dlq(db)

            # Async-native: call directly with await (Celery used sync bridge)
            stats = await dlq_service.get_dlq_stats()

            # Check for alerts
            alerts = []

            if stats.get("overflow_alert"):
                alerts.append(
                    {
                        "type": "dlq_overflow",
                        "message": (
                            f"DLQ size ({stats['total_pending']}) exceeds "
                            f"threshold ({stats['max_dlq_size']})"
                        ),
                        "severity": "critical",
                    }
                )

            for event_type, metrics in stats.get("by_event_type", {}).items():
                total_processed = metrics.get("total_processed", 0)
                total_dead_letter = metrics.get("total_dead_letter", 0)

                if total_processed > 0:
                    dead_letter_rate = (total_dead_letter / total_processed) * 100

                    if dead_letter_rate > 10:
                        alerts.append(
                            {
                                "type": "high_dead_letter_rate",
                                "message": (
                                    f"High dead letter rate for {event_type}: "
                                    f"{dead_letter_rate:.1f}%"
                                ),
                                "severity": "warning",
                                "event_type": event_type,
                                "dead_letter_rate": dead_letter_rate,
                            }
                        )

            # Log alerts
            for alert in alerts:
                if alert["severity"] == "critical":
                    logger.error("DLQ ALERT: %s", alert["message"], extra=alert)
                else:
                    logger.warning("DLQ WARNING: %s", alert["message"], extra=alert)

            execution_time_ms = int(
                (now_sao_paulo() - wall_clock_start).total_seconds() * 1000
            )

            log_task_success(
                "monitor_dlq_health",
                start_time,
                alert_count=len(alerts),
                execution_time_ms=execution_time_ms,
            )
            return {
                "success": True,
                "stats": stats,
                "alerts": alerts,
                "alert_count": len(alerts),
                "execution_time_ms": execution_time_ms,
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("monitor_dlq_health", exc, start_time)
        raise


__all__ = [
    "process_webhook_dlq",
    "cleanup_old_dlq_events",
    "monitor_dlq_health",
]
