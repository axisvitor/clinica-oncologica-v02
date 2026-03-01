"""
Celery task scheduling for message delivery.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from app.models.message import Message
from app.utils.distributed_lock import (
    async_message_delivery_lock,
    LockAcquisitionError,
    LockTimeoutError,
)
from .shared import get_celery_task_status

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Handles Celery task scheduling for message delivery."""

    async def schedule_celery_task(
        self, message: Message, delivery_time: datetime
    ) -> Dict[str, Any]:
        """
        Schedule Celery task for message delivery with distributed locking.

        Uses distributed locks to ensure messages are scheduled in the correct order
        and prevent race conditions in message delivery.

        Args:
            message: Message to schedule (must have ID already)
            delivery_time: When to deliver the message

        Returns:
            Task scheduling result
        """
        try:
            # Acquire lock for message delivery ordering
            async with async_message_delivery_lock(
                message.patient_id, timeout=10
            ) as lock:
                logger.debug(
                    f"Acquired message delivery lock for patient {message.patient_id}"
                )

                # Import here to avoid circular imports
                from app.tasks.messaging import send_scheduled_message

                # Schedule task with ETA, using the message id
                task_result = send_scheduled_message.apply_async(
                    args=[str(message.id)],
                    eta=delivery_time,
                )

                logger.info(
                    f"Scheduled Celery task {task_result.id} for message {message.id} "
                    f"at {delivery_time.isoformat()}"
                )

                # Log lock metrics if contention occurred
                lock_metrics = lock.get_metrics()
                if lock_metrics.get("contention_count", 0) > 0:
                    logger.info(
                        f"Message delivery lock contention: "
                        f"{lock_metrics['contention_count']} contentions, "
                        f"avg wait: {lock_metrics['average_wait_time']:.3f}s"
                    )

                return {
                    "task_id": task_result.id,
                    "eta": delivery_time.isoformat(),
                    "status": "scheduled",
                    "message_id": str(message.id),
                    "lock_metrics": lock_metrics,
                }

        except (LockTimeoutError, LockAcquisitionError) as e:
            logger.error(
                f"Failed to acquire lock for message {message.id} scheduling: {e}"
            )
            return {
                "task_id": None,
                "error": f"Lock error: {str(e)}",
                "status": "failed",
            }
        except Exception as e:
            logger.error(
                f"Failed to schedule Celery task for message {message.id}: {e}"
            )
            return {"task_id": None, "error": str(e), "status": "failed"}

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get Celery task status.

        Args:
            task_id: Celery task ID

        Returns:
            Task status information
        """
        return await get_celery_task_status(task_id, logger)

    def cancel_celery_task(self, task_id: str) -> bool:
        """
        Cancel a Celery task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            from app.task_queue import task_queue as celery_app

            celery_app.control.revoke(task_id, terminate=True)
            logger.info(f"Cancelled Celery task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel Celery task {task_id}: {e}")
            return False
