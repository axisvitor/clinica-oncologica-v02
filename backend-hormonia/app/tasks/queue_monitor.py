"""
Celery Queue Length Monitor

Periodically monitors Redis queue lengths and updates Prometheus metrics.
Runs as a background task in the Celery beat scheduler.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from celery import Celery
from redis import Redis
from app.tasks.celery_metrics import update_queue_length
from app.core.redis_manager import get_sync_redis_client as get_redis_client
from app.utils.async_helpers import run_async

logger = logging.getLogger(__name__)

# Default queues to monitor
DEFAULT_QUEUES = [
    "celery",  # Default queue
]


class QueueMonitor:
    """
    Monitor Celery queue lengths and update metrics.
    """

    def __init__(
        self,
        celery_app: Celery,
        redis_client: Optional[Redis] = None,
        queues: Optional[List[str]] = None,
        update_interval: int = 10,
    ):
        """
        Initialize queue monitor.

        Args:
            celery_app: Celery application instance
            redis_client: Redis client (uses default if None)
            queues: List of queue names to monitor
            update_interval: Seconds between updates
        """
        self.celery_app = celery_app
        self.redis_client = redis_client or get_redis_client()
        self.queues = queues or DEFAULT_QUEUES
        self.update_interval = update_interval
        self._running = False

    async def get_queue_length(self, queue_name: str) -> int:
        """
        Get current length of a queue from Redis.

        Args:
            queue_name: Name of the queue

        Returns:
            Number of messages in queue
        """
        try:
            # Celery uses Redis lists with specific key format
            queue_key = f"celery:queue:{queue_name}"
            length = await asyncio.to_thread(self.redis_client.llen, queue_key)
            return length or 0

        except Exception as e:
            logger.error(f"Error getting length for queue {queue_name}: {e}")
            return 0

    async def get_all_queue_lengths(self) -> Dict[str, int]:
        """
        Get lengths of all monitored queues.

        Returns:
            Dictionary mapping queue names to lengths
        """
        lengths = {}

        for queue_name in self.queues:
            length = await self.get_queue_length(queue_name)
            lengths[queue_name] = length

        return lengths

    async def discover_active_queues(self) -> List[str]:
        """
        Discover all active queues from Celery workers.

        Returns:
            List of active queue names
        """
        try:
            inspector = self.celery_app.control.inspect()
            active_queues_data = inspector.active_queues()

            if not active_queues_data:
                logger.warning("No active queues found from workers")
                return self.queues

            # Extract unique queue names
            queue_names = set()
            for worker, queues in active_queues_data.items():
                for queue in queues:
                    queue_names.add(queue["name"])

            discovered = list(queue_names)
            logger.info(f"Discovered {len(discovered)} active queues: {discovered}")
            return discovered

        except Exception as e:
            logger.error(f"Error discovering active queues: {e}")
            return self.queues

    async def update_metrics(self):
        """
        Update Prometheus metrics for all queue lengths.
        """
        try:
            # Get current queue lengths
            lengths = await self.get_all_queue_lengths()

            # Update metrics
            for queue_name, length in lengths.items():
                update_queue_length(queue_name, length)

                # Log if queue is backed up
                if length > 100:
                    logger.warning(f"Queue {queue_name} has {length} pending tasks")

            logger.debug(f"Updated queue metrics: {lengths}")

        except Exception as e:
            logger.error(f"Error updating queue metrics: {e}", exc_info=True)

    async def run(self):
        """
        Main monitoring loop.
        """
        self._running = True
        logger.info(
            f"Starting queue monitor for {len(self.queues)} queues, "
            f"update interval: {self.update_interval}s"
        )

        # Discover active queues on startup
        discovered_queues = await self.discover_active_queues()
        self.queues = list(set(self.queues + discovered_queues))

        while self._running:
            try:
                await self.update_metrics()
                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                logger.info("Queue monitor cancelled")
                break

            except Exception as e:
                logger.error(f"Error in queue monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.update_interval)

        logger.info("Queue monitor stopped")

    def stop(self):
        """
        Stop the monitoring loop.
        """
        self._running = False


# ============================================================================
# CELERY BEAT TASK
# ============================================================================


async def monitor_queue_lengths_task(
    celery_app: Celery, redis_client: Optional[Redis] = None
):
    """
    Background task to monitor queue lengths.

    This should be called periodically by Celery Beat.

    Args:
        celery_app: Celery application instance
        redis_client: Redis client
    """
    monitor = QueueMonitor(
        celery_app=celery_app, redis_client=redis_client, update_interval=10
    )

    try:
        await monitor.update_metrics()
    except Exception as e:
        logger.error(f"Error in queue monitoring task: {e}", exc_info=True)


# ============================================================================
# SYNCHRONOUS WRAPPER FOR CELERY
# ============================================================================


def monitor_queue_lengths_sync(celery_app: Celery):
    """
    Synchronous wrapper for queue monitoring task.

    Used in Celery beat schedule.

    Args:
        celery_app: Celery application instance
    """
    try:
        run_async(monitor_queue_lengths_task(celery_app))

    except Exception as e:
        logger.error(f"Error in sync queue monitor: {e}", exc_info=True)


# ============================================================================
# STANDALONE MONITORING SERVICE
# ============================================================================


async def run_queue_monitor_service(celery_app: Celery, update_interval: int = 10):
    """
    Run queue monitor as a standalone service.

    This can be run in a separate process for continuous monitoring.

    Args:
        celery_app: Celery application instance
        update_interval: Seconds between updates
    """
    monitor = QueueMonitor(celery_app=celery_app, update_interval=update_interval)

    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("Queue monitor interrupted by user")
        monitor.stop()
    except Exception as e:
        logger.error(f"Fatal error in queue monitor service: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Allow running as standalone service
    from app.celery_app import app as celery_app

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Long timeout keeps the service effectively unbounded while using shared async helper.
    run_async(run_queue_monitor_service(celery_app), timeout=2_147_483_647)
