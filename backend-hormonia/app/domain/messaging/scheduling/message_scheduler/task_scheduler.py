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
                from app.tasks.flows import send_flow_message

                # Prepare message data for Celery task
                message_data = {
                    "content": message.content,
                    "type": message.type.value,
                    "metadata": message.message_metadata,
                    "flow_context": message.message_metadata.get("flow_context", {}),
                }

                # Schedule task with ETA, passing message_id to UPDATE existing message
                task_result = send_flow_message.apply_async(
                    args=[str(message.patient_id), message_data, str(message.id)],
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

    def cancel_celery_task(self, task_id: str) -> bool:
        """
        Cancel a Celery task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            from app.celery_app import celery_app

            celery_app.control.revoke(task_id, terminate=True)
            logger.info(f"Cancelled Celery task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel Celery task {task_id}: {e}")
            return False
