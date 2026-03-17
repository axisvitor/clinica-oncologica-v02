"""
Tasks API v2 - Utility Modules

Exports all utility functions and constants for task management.
"""

from .serializers import _serialize_task

from .retry_strategies import _calculate_retry_delay

# Cache TTL configurations (SHORT TTLs for dynamic task data)
CACHE_TTL_ACTIVE_TASKS = 120  # 2 minutes for active tasks
CACHE_TTL_TASK_HISTORY = 600  # 10 minutes for completed tasks
CACHE_TTL_STATISTICS = 300  # 5 minutes for statistics
CACHE_TTL_QUEUE_STATUS = 60  # 1 minute for queue status

__all__ = [
    "_serialize_task",
    "_calculate_retry_delay",
    "CACHE_TTL_ACTIVE_TASKS",
    "CACHE_TTL_TASK_HISTORY",
    "CACHE_TTL_STATISTICS",
    "CACHE_TTL_QUEUE_STATUS",
]
