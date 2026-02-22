"""
Base classes and helpers for flow tasks.

This module provides the base FlowTaskBase class for all flow-related Celery tasks,
as well as helper functions like send_critical_alert_sync.
"""

import logging
from typing import Any
from asgiref.sync import async_to_sync
from celery import Task
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


def send_critical_alert_sync(task_name: str, error: str, context: dict = None):
    """
    Helper to send critical alerts synchronously from Celery tasks.
    Uses AlertManager to process the alert.

    Args:
        task_name: Name of the failing task
        error: Error message or description
        context: Optional context dictionary with additional information

    Note:
        Uses async_to_sync from asgiref to run the async alert processing from
        a synchronous Celery task context without manual event loop management.
    """
    try:
        from app.services.alerts import (
            get_alert_manager,
            AlertRuleType,
            AlertSeverity,
            Alert,
        )

        # Create alert object
        alert = Alert(
            severity=AlertSeverity.CRITICAL,
            rule_type=AlertRuleType.CUSTOM,
            message=f"Critical failure in task {task_name}: {error}",
            context=context or {},
            timestamp=now_sao_paulo(),
        )

        # Get manager and process using async_to_sync (no loop detection boilerplate)
        manager = get_alert_manager()
        async_to_sync(manager.process_alert)(alert)

    except Exception as e:
        logger.error(f"Failed to send critical alert for {task_name}: {e}")


class FlowTaskBase(Task):
    """
    Base class for flow tasks with Redis tracking.

    This class provides common functionality for all flow-related Celery tasks,
    including automatic result storage in Redis and standardized error handling.
    """

    def on_success(self, retval, task_id, args, kwargs):
        """
        Called when task succeeds.

        Args:
            retval: Return value from task execution
            task_id: Unique task identifier
            args: Task positional arguments
            kwargs: Task keyword arguments
        """
        logger.info(f"Flow task {task_id} completed successfully: {retval}")
        # Store success in Redis for monitoring
        self._store_task_result(task_id, "success", retval)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task fails.

        Args:
            exc: Exception that caused the failure
            task_id: Unique task identifier
            args: Task positional arguments
            kwargs: Task keyword arguments
            einfo: Exception info object
        """
        logger.error(f"Flow task {task_id} failed: {exc}")
        # Store failure in Redis for monitoring
        self._store_task_result(
            task_id, "failure", {"error": str(exc), "traceback": str(einfo)}
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task is retried.

        Args:
            exc: Exception that triggered the retry
            task_id: Unique task identifier
            args: Task positional arguments
            kwargs: Task keyword arguments
            einfo: Exception info object
        """
        logger.warning(f"Flow task {task_id} retrying: {exc}")
        # Store retry in Redis for monitoring
        self._store_task_result(
            task_id, "retry", {"error": str(exc), "attempt": self.request.retries + 1}
        )

    def _store_task_result(self, task_id: str, status: str, data: Any):
        """
        Store task result in Redis for monitoring using synchronous operations.

        Args:
            task_id: Unique task identifier
            status: Task status (success, failure, retry)
            data: Result data to store

        Note:
            Uses synchronous Redis client for compatibility with Celery task context.
            Failures are logged but don't raise exceptions to prevent task failure.
        """
        try:
            import json
            from app.core.redis_manager import get_redis_manager
            from app.config.settings.tasks import REDIS_TASK_RESULT_EXPIRY

            # Use centralized RedisManager sync client for Celery task context
            manager = get_redis_manager()
            redis_client = manager.get_sync_client()

            # Store task result with expiration
            result_data = {
                "task_id": task_id,
                "status": status,
                "timestamp": now_sao_paulo().isoformat(),
                "data": data,
            }

            redis_client.setex(
                f"task_result:{task_id}",
                REDIS_TASK_RESULT_EXPIRY,
                json.dumps(result_data),
            )

        except Exception as e:
            logger.error(f"Failed to store task result in Redis: {e}")
