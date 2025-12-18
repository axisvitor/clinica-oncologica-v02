"""
Message delivery metrics and monitoring.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.message import Message, MessageStatus
from app.utils.db_retry import with_db_retry

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and calculates message delivery metrics."""

    def __init__(self, db: Session):
        self.db = db

    @with_db_retry(max_retries=3)
    async def get_scheduled_messages(
        self, patient_id: UUID = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get scheduled messages with optional patient filter.

        Args:
            patient_id: Optional patient filter
            limit: Maximum number of messages to return

        Returns:
            List of scheduled messages with task status
        """
        try:
            query = self.db.query(Message).filter(
                Message.status == MessageStatus.SCHEDULED
            )

            if patient_id:
                query = query.filter(Message.patient_id == patient_id)

            messages = query.order_by(Message.scheduled_for).limit(limit).all()

            result = []
            for message in messages:
                task_id = message.message_metadata.get("celery_task_id")
                task_status = await self._get_task_status(task_id) if task_id else None

                result.append(
                    {
                        "message_id": str(message.id),
                        "patient_id": str(message.patient_id),
                        "content": message.content,
                        "scheduled_for": message.scheduled_for.isoformat(),
                        "created_at": message.created_at.isoformat(),
                        "task_id": task_id,
                        "task_status": task_status,
                        "metadata": message.message_metadata,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Failed to get scheduled messages: {e}")
            return []

    @with_db_retry(max_retries=3)
    async def get_delivery_metrics(
        self, patient_id: UUID = None, days_back: int = 7
    ) -> Dict[str, Any]:
        """
        Get message delivery metrics.

        Args:
            patient_id: Optional patient filter
            days_back: Number of days to analyze

        Returns:
            Delivery metrics and statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            query = self.db.query(Message).filter(Message.created_at >= cutoff_date)

            if patient_id:
                query = query.filter(Message.patient_id == patient_id)

            messages = query.all()

            if not messages:
                return {
                    "total_messages": 0,
                    "status_distribution": {},
                    "success_rate": 0.0,
                    "read_rate": 0.0,
                    "avg_delivery_time": None,
                    "period_days": days_back,
                }

            # Calculate metrics
            total_messages = len(messages)
            status_counts = {}
            delivery_times = []

            for message in messages:
                status = message.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

                if message.sent_at and message.delivered_at:
                    delivery_time = (
                        message.delivered_at - message.sent_at
                    ).total_seconds()
                    delivery_times.append(delivery_time)

            successful_messages = sum(
                status_counts.get(status, 0) for status in ["sent", "delivered", "read"]
            )
            delivered_messages = sum(
                status_counts.get(status, 0) for status in ["delivered", "read"]
            )
            read_messages = status_counts.get("read", 0)

            return {
                "total_messages": total_messages,
                "status_distribution": status_counts,
                "success_rate": (successful_messages / total_messages) * 100
                if total_messages > 0
                else 0,
                "read_rate": (read_messages / delivered_messages) * 100
                if delivered_messages > 0
                else 0,
                "avg_delivery_time": sum(delivery_times) / len(delivery_times)
                if delivery_times
                else None,
                "period_days": days_back,
                "analysis_date": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get delivery metrics: {e}")
            return {"error": str(e)}

    async def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get Celery task status.

        Args:
            task_id: Celery task ID

        Returns:
            Task status information
        """
        try:
            from celery.result import AsyncResult

            result = AsyncResult(task_id)

            return {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.ready() else None,
                "traceback": result.traceback if result.failed() else None,
                "date_done": result.date_done,
            }

        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return {"task_id": task_id, "status": "UNKNOWN", "error": str(e)}
