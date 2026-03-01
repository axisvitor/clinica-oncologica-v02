"""
Task monitoring and health check functionality.

This module contains Celery tasks for monitoring the health of the flow processing
system, including database, Redis, and external service connectivity checks.
"""

import logging
from typing import Any
from sqlalchemy import text

from app.task_queue import task_queue as celery_app
from app.database import get_scoped_session
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageStatus
from app.models.patient import Patient
from app.ai.client import get_gemini_client
from app.services.flow_alerts import FlowAlertsService
from app.utils.async_helpers import run_async_in_sync, run_async_in_thread

from .base import FlowTaskBase
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=FlowTaskBase)
def monitor_flow_task_health(self) -> dict[str, Any]:
    """
    Monitor flow task health and Redis connection.

    Returns:
        dict[str, Any]: Health monitoring results containing:
            - database_connection: Database connection status
            - redis_connection: Redis connection status
            - gemini_client: Gemini client status
            - active_flows_count: Number of active flows
            - pending_messages_count: Number of pending messages
            - failed_tasks_count: Number of failed tasks
            - overall_healthy: Overall health status
            - timestamp: Monitoring timestamp

    Raises:
        Exception: If health monitoring fails
    """
    try:
        logger.info("Starting flow task health monitoring")

        with get_scoped_session() as db:
            health_results = {
                "database_connection": False,
                "redis_connection": False,
                "gemini_client": False,
                "active_flows_count": 0,
                "pending_messages_count": 0,
                "failed_tasks_count": 0,
                "timestamp": now_sao_paulo().isoformat(),
            }

            # Test database connection
            try:
                db.execute(text("SELECT 1"))
                health_results["database_connection"] = True
            except Exception as e:
                logger.error(f"Database health check failed: {e}")

            # Test Redis connection using centralized RedisManager
            try:
                from app.core.redis_manager import get_redis_manager

                manager = get_redis_manager()
                redis_client = manager.get_sync_client()
                redis_client.ping()
                health_results["redis_connection"] = True
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")

            # Test Gemini client using proper async handling
            try:
                gemini_client = get_gemini_client()
                from app.config.settings.tasks import HEALTH_CHECK_TIMEOUT

                try:
                    health_results["gemini_client"] = run_async_in_sync(
                        gemini_client.health_check(),
                        timeout=HEALTH_CHECK_TIMEOUT,
                    )
                except RuntimeError:
                    health_results["gemini_client"] = run_async_in_thread(
                        gemini_client.health_check(),
                        timeout=HEALTH_CHECK_TIMEOUT,
                    )
            except Exception as e:
                logger.error(f"Gemini client health check failed: {e}")

            # Count active flows (lightweight, capped)
            try:
                from app.config.settings.tasks import HEALTH_ACTIVE_FLOWS_LIMIT

                active_flows = (
                    db.query(PatientFlowState.id)
                    .join(Patient)
                    .filter(
                        PatientFlowState.completed_at.is_(None),
                        Patient.deleted_at.is_(None),
                    )
                    .limit(HEALTH_ACTIVE_FLOWS_LIMIT)
                    .all()
                )
                health_results["active_flows_count"] = len(active_flows)
            except Exception as e:
                logger.error(f"Failed to count active flows: {e}")

            # Count pending messages (lightweight, capped)
            try:
                from app.config.settings.tasks import HEALTH_ACTIVE_FLOWS_LIMIT

                pending_messages = (
                    db.query(Message.id)
                    .filter(Message.status == MessageStatus.PENDING)
                    .limit(HEALTH_ACTIVE_FLOWS_LIMIT)
                    .all()
                )
                health_results["pending_messages_count"] = len(pending_messages)
            except Exception as e:
                logger.error(f"Failed to count pending messages: {e}")

            # Check for failed tasks in Redis using centralized RedisManager
            try:
                from app.core.redis_manager import get_redis_manager

                manager = get_redis_manager()
                redis_client = manager.get_sync_client()

                failed_count = 0
                scanned_count = 0
                max_scan = 500

                for task_key in redis_client.scan_iter(match="task_result:*", count=100):
                    scanned_count += 1
                    if scanned_count > max_scan:
                        break
                    task_data = redis_client.get(task_key)
                    if task_data and "failure" in str(task_data):
                        failed_count += 1

                health_results["failed_tasks_count"] = failed_count
                health_results["failed_tasks_scanned"] = min(scanned_count, max_scan)
            except Exception as e:
                logger.error(f"Failed to check task failures: {e}")

            # Overall health status
            health_results["overall_healthy"] = all(
                [
                    health_results["database_connection"],
                    health_results["redis_connection"],
                    health_results["gemini_client"],
                ]
            )

            logger.info(f"Flow task health monitoring completed: {health_results}")
            return health_results

    except Exception as e:
        logger.error(f"Flow task health monitoring failed: {e}")
        return {
            "error": str(e),
            "timestamp": now_sao_paulo().isoformat(),
            "overall_healthy": False,
        }


@celery_app.task(bind=True, base=FlowTaskBase, max_retries=3, default_retry_delay=60)
def evaluate_flow_alerts(self) -> dict[str, Any]:
    """
    Evaluate flow analytics alerts and dispatch notifications.
    """
    with get_scoped_session() as db:
        try:
            service = FlowAlertsService(db)
            alerts = run_async_in_sync(service.evaluate_alerts(), timeout=60)

            return {
                "alerts_created": len(alerts),
                "timestamp": now_sao_paulo().isoformat(),
            }
        except Exception as exc:
            logger.error(f"Flow alerts evaluation failed: {exc}")
            raise self.retry(exc=exc, countdown=60)
