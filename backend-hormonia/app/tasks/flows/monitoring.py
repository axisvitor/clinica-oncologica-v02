"""
Task monitoring and health check functionality.

This module contains Celery tasks for monitoring the health of the flow processing
system, including database, Redis, and external service connectivity checks.
"""

import asyncio
import logging
from typing import Any
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import get_db
from app.repositories.flow import FlowStateRepository
from app.models.message import Message, MessageStatus
from app.integrations.gemini_client import get_gemini_client

from .base import FlowTaskBase

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

        # Get database session
        db = next(get_db())

        try:
            health_results = {
                "database_connection": False,
                "redis_connection": False,
                "gemini_client": False,
                "active_flows_count": 0,
                "pending_messages_count": 0,
                "failed_tasks_count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Test database connection
            try:
                db.execute("SELECT 1")
                health_results["database_connection"] = True
            except Exception as e:
                logger.error(f"Database health check failed: {e}")

            # Test Redis connection using synchronous client
            try:
                import redis
                from app.config import settings

                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )

                redis_client.ping()
                redis_client.close()
                health_results["redis_connection"] = True
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")

            # Test Gemini client using proper async handling
            try:
                gemini_client = get_gemini_client()
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        health_results["gemini_client"] = loop.run_until_complete(
                            gemini_client.health_check()
                        )
                    finally:
                        loop.close()
                except RuntimeError as e:
                    if "cannot be called from a running event loop" in str(e):
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            from app.config.settings.tasks import HEALTH_CHECK_TIMEOUT

                            future = executor.submit(
                                lambda: asyncio.run(gemini_client.health_check())
                            )
                            health_results["gemini_client"] = future.result(
                                timeout=HEALTH_CHECK_TIMEOUT
                            )
                    else:
                        raise
            except Exception as e:
                logger.error(f"Gemini client health check failed: {e}")

            # Count active flows
            try:
                from app.config.settings.tasks import HEALTH_ACTIVE_FLOWS_LIMIT

                flow_repo = FlowStateRepository(db)
                active_flows = flow_repo.get_active_flows(
                    limit=HEALTH_ACTIVE_FLOWS_LIMIT
                )
                health_results["active_flows_count"] = len(active_flows)
            except Exception as e:
                logger.error(f"Failed to count active flows: {e}")

            # Count pending messages
            try:
                pending_messages = (
                    db.query(Message)
                    .filter(Message.status == MessageStatus.PENDING)
                    .count()
                )
                health_results["pending_messages_count"] = pending_messages
            except Exception as e:
                logger.error(f"Failed to count pending messages: {e}")

            # Check for failed tasks in Redis using synchronous client
            try:
                import redis
                from app.config import settings

                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )

                failed_tasks = redis_client.keys("task_result:*")
                failed_count = 0

                for task_key in failed_tasks:
                    task_data = redis_client.get(task_key)
                    if task_data and "failure" in str(task_data):
                        failed_count += 1

                redis_client.close()
                health_results["failed_tasks_count"] = failed_count
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

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Flow task health monitoring failed: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_healthy": False,
        }
