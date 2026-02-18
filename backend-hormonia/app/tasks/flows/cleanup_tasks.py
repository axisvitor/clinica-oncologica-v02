"""
Cleanup and maintenance tasks.

This module contains Celery tasks for cleaning up old flow data,
archiving completed flows, and maintaining the database.
"""

import json
import logging
from typing import Any
from datetime import timedelta

from app.task_queue import task_queue as celery_app
from app.database import get_scoped_session
from app.repositories.flow import FlowStateRepository
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageStatus

from .base import FlowTaskBase
from app.utils.timezone import now_sao_paulo

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

        with get_scoped_session() as db:
            cutoff_date = now_sao_paulo() - timedelta(days=days_old)

            # Initialize repositories
            FlowStateRepository(db)

            results = {
                "completed_flows_cleaned": 0,
                "old_messages_cleaned": 0,
                "analytics_cleaned": 0,
                "cutoff_date": cutoff_date.isoformat(),
                "start_time": now_sao_paulo().isoformat(),
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

                # Store in Redis for historical reference via centralized RedisManager
                try:
                    from app.core.redis_manager import get_cache_redis_manager
                    from app.config.settings.tasks import ARCHIVE_RETENTION_DAYS

                    manager = get_cache_redis_manager()
                    redis_client = manager.get_sync_client()

                    redis_client.setex(
                        f"archived_flow:{flow.id}",
                        86400 * ARCHIVE_RETENTION_DAYS,
                        json.dumps(archive_data),
                    )

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

            results["end_time"] = now_sao_paulo().isoformat()

            logger.info(f"Flow data cleanup completed: {results}")
            return results

    except Exception as e:
        logger.error(f"Flow data cleanup failed: {e}")
        raise
