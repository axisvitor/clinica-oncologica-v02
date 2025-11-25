"""
Task Management Constants

Centralized configuration for:
- Cache TTL settings
- Task operation limits
- Priority mappings
"""

# Cache TTL configurations (SHORT TTLs for dynamic task data)
CACHE_TTL_ACTIVE_TASKS = 120  # 2 minutes for active tasks
CACHE_TTL_TASK_HISTORY = 600  # 10 minutes for completed tasks
CACHE_TTL_STATISTICS = 300  # 5 minutes for statistics
CACHE_TTL_QUEUE_STATUS = 60  # 1 minute for queue status

# Task operation limits
MAX_BULK_OPERATION_SIZE = 100  # Maximum tasks in bulk operation
MAX_LOG_ENTRIES = 1000  # Maximum log entries per task
DEFAULT_PAGE_LIMIT = 50  # Default pagination limit
MAX_PAGE_LIMIT = 100  # Maximum pagination limit

# Priority mappings (Celery priority scale: 0-10)
PRIORITY_MAPPING = {
    "low": 3,
    "medium": 6,
    "high": 9,
    "critical": 10
}

# Retry strategy defaults
DEFAULT_BASE_DELAY = 60  # 1 minute
DEFAULT_MAX_DELAY = 3600  # 1 hour
DEFAULT_MAX_RETRIES = 3

# Analysis period limits (in hours)
MIN_ANALYSIS_PERIOD = 1
MAX_ANALYSIS_PERIOD = 168  # 1 week

# Task cleanup defaults
DEFAULT_RETENTION_DAYS = 30
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 365

# Queue names
DEFAULT_QUEUE = "celery"
HIGH_PRIORITY_QUEUE = "high_priority"
LOW_PRIORITY_QUEUE = "low_priority"

# Task size estimate (for cleanup calculations)
TASK_SIZE_KB = 1.0  # Approximate size per task in KB
