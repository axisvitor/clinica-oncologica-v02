"""
Task monitoring and logging utilities for Celery tasks.
Enhanced with async support and better error handling.
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
from celery.events.state import State
import concurrent.futures

from app.celery_app import celery_app


logger = logging.getLogger(__name__)


class TaskMonitor:
    """Monitor Celery task execution and performance."""

    def __init__(self):
        self.state = State()

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get currently active tasks."""
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()

            if not active_tasks:
                return []

            all_active = []
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    task_info = {
                        "worker": worker,
                        "task_id": task.get("id"),
                        "task_name": task.get("name"),
                        "args": task.get("args", []),
                        "kwargs": task.get("kwargs", {}),
                        "time_start": task.get("time_start"),
                        "acknowledged": task.get("acknowledged", False),
                        "delivery_info": task.get("delivery_info", {}),
                    }
                    all_active.append(task_info)

            return all_active

        except Exception as exc:
            logger.error(f"Error getting active tasks: {exc}")
            return []

    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get scheduled (reserved) tasks."""
        try:
            inspect = celery_app.control.inspect()
            scheduled_tasks = inspect.scheduled()

            if not scheduled_tasks:
                return []

            all_scheduled = []
            for worker, tasks in scheduled_tasks.items():
                for task in tasks:
                    task_info = {
                        "worker": worker,
                        "task_id": task.get("request", {}).get("id"),
                        "task_name": task.get("request", {}).get("task"),
                        "args": task.get("request", {}).get("args", []),
                        "kwargs": task.get("request", {}).get("kwargs", {}),
                        "eta": task.get("eta"),
                        "priority": task.get("priority", 6),
                    }
                    all_scheduled.append(task_info)

            return all_scheduled

        except Exception as exc:
            logger.error(f"Error getting scheduled tasks: {exc}")
            return []

    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()

            if not stats:
                return {}

            worker_info = {}
            for worker, worker_stats in stats.items():
                worker_info[worker] = {
                    "broker": worker_stats.get("broker", {}),
                    "pool": worker_stats.get("pool", {}),
                    "prefetch_count": worker_stats.get("prefetch_count", 0),
                    "clock": worker_stats.get("clock", 0),
                    "pid": worker_stats.get("pid"),
                    "total_tasks": worker_stats.get("total", {}),
                    "rusage": worker_stats.get("rusage", {}),
                }

            return worker_info

        except Exception as exc:
            logger.error(f"Error getting worker stats: {exc}")
            return {}

    def get_queue_lengths(self) -> Dict[str, int]:
        """Get queue lengths for monitoring."""
        try:
            # This would require Redis connection to check queue lengths
            # For now, return empty dict - can be implemented with Redis client
            return {}

        except Exception as exc:
            logger.error(f"Error getting queue lengths: {exc}")
            return {}

    def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent task execution history."""
        try:
            # This would require storing task history in database or Redis
            # For now, return empty list - can be implemented with task result backend
            return []

        except Exception as exc:
            logger.error(f"Error getting task history: {exc}")
            return []

    def get_failed_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently failed tasks."""
        try:
            # This would require querying the result backend for failed tasks
            # For now, return empty list - can be implemented with result backend queries
            return []

        except Exception as exc:
            logger.error(f"Error getting failed tasks: {exc}")
            return []


class TaskLogger:
    """Enhanced logging for Celery tasks."""

    @staticmethod
    def log_task_start(
        task_name: str, task_id: str, args: List[Any], kwargs: Dict[str, Any]
    ):
        """Log task start with context."""
        logger.info(
            f"Task started: {task_name}",
            extra={
                "task_id": task_id,
                "task_name": task_name,
                "args": args,
                "kwargs": kwargs,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "task_start",
            },
        )

    @staticmethod
    def log_task_success(task_name: str, task_id: str, result: Any, runtime: float):
        """Log successful task completion."""
        logger.info(
            f"Task completed successfully: {task_name}",
            extra={
                "task_id": task_id,
                "task_name": task_name,
                "result": result,
                "runtime_seconds": runtime,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "task_success",
            },
        )

    @staticmethod
    def log_task_failure(
        task_name: str, task_id: str, error: str, traceback: str, runtime: float
    ):
        """Log task failure with error details."""
        logger.error(
            f"Task failed: {task_name}",
            extra={
                "task_id": task_id,
                "task_name": task_name,
                "error": error,
                "traceback": traceback,
                "runtime_seconds": runtime,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "task_failure",
            },
        )

    @staticmethod
    def log_task_retry(
        task_name: str, task_id: str, error: str, retry_count: int, countdown: int
    ):
        """Log task retry attempt."""
        logger.warning(
            f"Task retry: {task_name}",
            extra={
                "task_id": task_id,
                "task_name": task_name,
                "error": error,
                "retry_count": retry_count,
                "countdown": countdown,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "task_retry",
            },
        )


# Global monitor instance
task_monitor = TaskMonitor()
task_logger = TaskLogger()


def get_task_monitoring_data() -> Dict[str, Any]:
    """Get comprehensive task monitoring data."""
    return {
        "active_tasks": task_monitor.get_active_tasks(),
        "scheduled_tasks": task_monitor.get_scheduled_tasks(),
        "worker_stats": task_monitor.get_worker_stats(),
        "queue_lengths": task_monitor.get_queue_lengths(),
        "timestamp": datetime.utcnow().isoformat(),
    }


async def get_task_monitoring_data_async() -> Dict[str, Any]:
    """Get comprehensive task monitoring data asynchronously."""
    try:
        # Run synchronous operations in thread pool to avoid blocking
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Get all monitoring data concurrently
            futures = {
                "active_tasks": executor.submit(task_monitor.get_active_tasks),
                "scheduled_tasks": executor.submit(task_monitor.get_scheduled_tasks),
                "worker_stats": executor.submit(task_monitor.get_worker_stats),
                "queue_lengths": executor.submit(task_monitor.get_queue_lengths),
            }

            # Wait for all results with timeout
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=10.0)  # 10 second timeout
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Timeout getting {key} monitoring data")
                    results[key] = (
                        [] if key in ["active_tasks", "scheduled_tasks"] else {}
                    )
                except Exception as e:
                    logger.error(f"Error getting {key} monitoring data: {e}")
                    results[key] = (
                        [] if key in ["active_tasks", "scheduled_tasks"] else {}
                    )

            results["timestamp"] = datetime.utcnow().isoformat()
            return results

    except Exception as e:
        logger.error(f"Error in async task monitoring: {e}")
        return {
            "active_tasks": [],
            "scheduled_tasks": [],
            "worker_stats": {},
            "queue_lengths": {},
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }


async def health_check_async() -> Dict[str, Any]:
    """Perform async health check of task monitoring system."""
    try:
        # Test basic connectivity
        start_time = datetime.utcnow()

        # Get monitoring data with timeout
        monitoring_data = await asyncio.wait_for(
            get_task_monitoring_data_async(), timeout=15.0
        )

        end_time = datetime.utcnow()
        response_time = (end_time - start_time).total_seconds()

        # Check if we have any workers
        worker_count = len(monitoring_data.get("worker_stats", {}))
        active_task_count = len(monitoring_data.get("active_tasks", []))

        status = "healthy" if worker_count > 0 else "degraded"
        if "error" in monitoring_data:
            status = "unhealthy"

        return {
            "status": status,
            "response_time_seconds": response_time,
            "worker_count": worker_count,
            "active_task_count": active_task_count,
            "timestamp": datetime.utcnow().isoformat(),
            "details": monitoring_data,
        }

    except asyncio.TimeoutError:
        return {
            "status": "unhealthy",
            "error": "Health check timed out",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
