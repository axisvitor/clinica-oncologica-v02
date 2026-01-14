"""
Cleanup and maintenance tasks.

This module contains Celery tasks for cleaning up old flow data,
archiving completed flows, and maintaining the database.
"""

import json
import logging
from typing import Any
from datetime import datetime, timedelta, timezone

from app.task_queue import task_queue as celery_app
from app.database import get_db
from app.repositories.flow import FlowStateRepository
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageStatus

from .base import FlowTaskBase

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=FlowTaskBase)
def cleanup_old_flow_data(self, days_old: int = 90) -> dict[str, Any]:
    """
    Cleanup old flow data for maintenance.

    Args:
        days_old: Age threshold for cleanup in days

    Returns:
        dict[str, Any]: Cleanup results containing:
            - deleted_flows: Number of deleted flow states
            - deleted_messages: Number of deleted messages
            - deleted_analytics: Number of deleted analytics records
            - cleanup_date: Date of cleanup operation

    Raises:
        Exception: If cleanup operation fails
    """
    try:
        logger.info(f"Starting cleanup of flow data older than {days_old} days")

        # Get database session
        db = next(get_db())

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

            # Initialize repositories
            FlowStateRepository(db)

            results = {
                "completed_flows_cleaned": 0,
                "old_messages_cleaned": 0,
                "analytics_cleaned": 0,
                "cutoff_date": cutoff_date.isoformat(),
                "start_time": datetime.now(timezone.utc).isoformat(),
            }

            # Clean up completed flows older than threshold
            completed_flows = (
                db.query(PatientFlowState)
                .filter(
                    PatientFlowState.completed_at < cutoff_date,
                    PatientFlowState.completed_at.isnot(None),
                )
                .all()
            )

            for flow in completed_flows:
                # Archive important data before deletion
                archive_data = {
                    "patient_id": str(flow.patient_id),
                    "flow_type": flow.flow_type,
                    "completed_at": flow.completed_at.isoformat(),
                    "final_state": flow.state_data,
                }

                # Store in Redis for historical reference using synchronous client
                try:
                    import redis
                    from app.config import settings

                    redis_client = redis.from_url(
                        settings.REDIS_URL,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                    )

                    from app.config.settings.tasks import ARCHIVE_RETENTION_DAYS

                    redis_client.setex(
                        f"archived_flow:{flow.id}",
                        86400 * ARCHIVE_RETENTION_DAYS,
                        json.dumps(archive_data),
                    )

                    redis_client.close()

                except Exception as redis_error:
                    logger.warning(
                        f"Failed to archive flow data to Redis: {redis_error}"
                    )

                db.delete(flow)
                results["completed_flows_cleaned"] += 1

            # Clean up old flow messages
            old_messages = (
                db.query(Message)
                .filter(
                    Message.created_at < cutoff_date,
                    Message.status.in_(
                        [
                            MessageStatus.DELIVERED,
                            MessageStatus.READ,
                            MessageStatus.FAILED,
                        ]
                    ),
                )
                .all()
            )

            for message in old_messages:
                db.delete(message)
                results["old_messages_cleaned"] += 1

            # Commit cleanup
            db.commit()

            results["end_time"] = datetime.now(timezone.utc).isoformat()

            logger.info(f"Flow data cleanup completed: {results}")
            return results

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Flow data cleanup failed: {e}")
        raise
