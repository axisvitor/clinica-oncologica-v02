"""
Celery tasks for Webhook Dead Letter Queue (DLQ) processing.

Implements MEDIUM-005: Celery tasks for DLQ processing with exponential backoff.

Tasks:
- process_webhook_dlq: Process DLQ events every minute
- cleanup_old_dlq_events: Clean up aged events daily
- monitor_dlq_health: Monitor DLQ metrics every 5 minutes
"""

import logging
from typing import Any, Dict

from celery import shared_task
from datetime import datetime, timedelta

from app.db.base import get_db
from app.utils.async_helpers import run_async
from app.services.webhook_dlq import get_webhook_dlq
from app.config.settings.tasks import (
    get_task_config,
    QUIZ_DLQ_BATCH_SIZE,
)

logger = logging.getLogger(__name__)


@shared_task(
    name="webhooks.process_dlq",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def process_webhook_dlq(self, batch_size: int = QUIZ_DLQ_BATCH_SIZE) -> Dict[str, Any]:
    """
    Process webhook Dead Letter Queue with exponential backoff.

    Runs every minute to process failed webhook events that are ready for retry.

    Schedule: Every 1 minute (defined in celery beat schedule)

    Args:
        batch_size: Maximum events to process per run (default: 50)

    Returns:
        Dictionary with processing statistics
    """
    start_time = datetime.utcnow()

    try:
        logger.info(f"Starting DLQ processing (batch_size={batch_size})")

        # Get database session
        db = next(get_db())

        try:
            # Get DLQ service
            dlq_service = get_webhook_dlq(db)

            # Process DLQ using run_async for efficient event loop reuse
            processed_count = run_async(dlq_service.process_dlq(batch_size=batch_size))

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = {
                "success": True,
                "processed_count": processed_count,
                "batch_size": batch_size,
                "execution_time_ms": int(execution_time),
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(
                f"DLQ processing complete: {processed_count} events processed in {execution_time}ms"
            )

            return result

        finally:
            db.close()

    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.error(f"DLQ processing failed: {e}", exc_info=True)

        # Return error result
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "execution_time_ms": int(execution_time),
            "timestamp": datetime.utcnow().isoformat()
        }


@shared_task(
    name="webhooks.cleanup_old_dlq_events",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def cleanup_old_dlq_events(self, days_old: int = 7) -> Dict[str, Any]:
    """
    Clean up DLQ events older than specified days.

    Runs daily to prevent DLQ from growing indefinitely.
    Events are auto-expired via Redis TTL, but this provides additional cleanup.

    Schedule: Daily at 03:00 UTC

    Args:
        days_old: Remove events older than this many days (default: 7)

    Returns:
        Dictionary with cleanup statistics
    """
    start_time = datetime.utcnow()

    try:
        logger.info(f"Starting DLQ cleanup (days_old={days_old})")

        # Get database session
        db = next(get_db())

        try:
            # Get DLQ service
            dlq_service = get_webhook_dlq(db)

            # Async cleanup using run_async for efficient event loop reuse
            async def _run_cleanup():
                # Get Redis client
                from app.core.redis_unified import get_async_redis
                redis_client = await get_async_redis()

                # Get all DLQ keys
                pattern = f"{dlq_service.DLQ_KEY_PREFIX}:*"
                dlq_keys = await redis_client.keys(pattern)

                cleaned = 0
                cutoff = datetime.utcnow() - timedelta(days=days_old)

                for dlq_key in dlq_keys:
                    # Get all events in queue
                    events = await redis_client.lrange(dlq_key, 0, -1)

                    for event_json in events:
                        try:
                            import json
                            event = json.loads(event_json)

                            # Check if event is too old
                            event_timestamp = datetime.fromisoformat(event["timestamp"])

                            if event_timestamp < cutoff:
                                # Remove old event
                                await redis_client.lrem(dlq_key, 1, event_json)
                                cleaned += 1

                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(f"Invalid event in DLQ, removing: {e}")
                            await redis_client.lrem(dlq_key, 1, event_json)
                            cleaned += 1
                return cleaned, cutoff

            cleaned_count, cutoff_date = run_async(_run_cleanup())

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = {
                "success": True,
                "cleaned_count": cleaned_count,
                "days_old": days_old,
                "cutoff_date": cutoff_date.isoformat(),
                "execution_time_ms": int(execution_time),
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(
                f"DLQ cleanup complete: {cleaned_count} old events removed in {execution_time}ms"
            )

            return result

        finally:
            db.close()

    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.error(f"DLQ cleanup failed: {e}", exc_info=True)

        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "execution_time_ms": int(execution_time),
            "timestamp": datetime.utcnow().isoformat()
        }


@shared_task(
    name="webhooks.monitor_dlq_health",
    bind=True,
)
def monitor_dlq_health(self) -> Dict[str, Any]:
    """
    Monitor DLQ health and trigger alerts if needed.

    Checks:
    - Queue size (alert if > 1000)
    - Processing rate
    - Dead letter rate
    - Retry exhaustion rate

    Schedule: Every 5 minutes

    Returns:
        Dictionary with health metrics
    """
    start_time = datetime.utcnow()

    try:
        logger.info("Starting DLQ health monitoring")

        # Get database session
        db = next(get_db())

        try:
            # Get DLQ service
            dlq_service = get_webhook_dlq(db)

            # Async stats logic
            async def _run_stats():
                return await dlq_service.get_dlq_stats()

            stats = asyncio.run(_run_stats())

            # Check for alerts
            alerts = []

            if stats.get("overflow_alert"):
                alerts.append({
                    "type": "dlq_overflow",
                    "message": f"DLQ size ({stats['total_pending']}) exceeds threshold ({stats['max_dlq_size']})",
                    "severity": "critical"
                })

            # Check dead letter rate
            for event_type, metrics in stats.get("by_event_type", {}).items():
                total_processed = metrics.get("total_processed", 0)
                total_dead_letter = metrics.get("total_dead_letter", 0)

                if total_processed > 0:
                    dead_letter_rate = (total_dead_letter / total_processed) * 100

                    if dead_letter_rate > 10:  # >10% dead letter rate
                        alerts.append({
                            "type": "high_dead_letter_rate",
                            "message": f"High dead letter rate for {event_type}: {dead_letter_rate:.1f}%",
                            "severity": "warning",
                            "event_type": event_type,
                            "dead_letter_rate": dead_letter_rate
                        })

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = {
                "success": True,
                "stats": stats,
                "alerts": alerts,
                "alert_count": len(alerts),
                "execution_time_ms": int(execution_time),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Log alerts
            for alert in alerts:
                if alert["severity"] == "critical":
                    logger.error(f"DLQ ALERT: {alert['message']}", extra=alert)
                else:
                    logger.warning(f"DLQ WARNING: {alert['message']}", extra=alert)

            logger.info(f"DLQ health monitoring complete: {len(alerts)} alerts")

            return result

        finally:
            db.close()

    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.error(f"DLQ health monitoring failed: {e}", exc_info=True)

        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "execution_time_ms": int(execution_time),
            "timestamp": datetime.utcnow().isoformat()
        }


# Export all tasks
__all__ = [
    "process_webhook_dlq",
    "cleanup_old_dlq_events",
    "monitor_dlq_health",
]
