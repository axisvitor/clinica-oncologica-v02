"""
Celery task configuration settings.

This module contains configuration for Celery tasks including timeouts,
batch sizes, concurrency limits, and retry policies.

All settings are configurable via environment variables with sensible defaults.
See .env.example for complete documentation of all available settings.

ENV Variable Naming Convention: TASK_{SUBCATEGORY}_{ATTRIBUTE}_{UNIT}
"""

import os
from typing import Dict


# ============================================================================
# FLOW PROCESSING SETTINGS - NEW NAMING: TASK_FLOW_*
# ============================================================================

# Timeout for processing a single patient flow (seconds)
FLOW_PROCESSING_TIMEOUT = int(os.getenv("TASK_FLOW_PROCESSING_TIMEOUT_SECONDS", "30"))

# Number of patients to process per batch
FLOW_BATCH_SIZE = int(os.getenv("TASK_FLOW_BATCH_SIZE", "10"))

# Maximum number of concurrent flow processing tasks
FLOW_MAX_CONCURRENT = int(os.getenv("TASK_FLOW_MAX_CONCURRENT", "50"))

# Maximum retries for flow processing tasks
FLOW_MAX_RETRIES = int(os.getenv("TASK_FLOW_MAX_RETRIES", "3"))

# Base delay for flow task retries (seconds)
FLOW_RETRY_DELAY = int(os.getenv("TASK_FLOW_RETRY_DELAY_SECONDS", "300"))


# ============================================================================
# TASK TIME LIMITS - NEW NAMING: TASK_TIME_LIMIT_SECONDS
# ============================================================================

# Hard time limit for tasks (seconds) - 1 hour default
TASK_TIME_LIMIT = int(os.getenv("TASK_TIME_LIMIT_SECONDS", "3600"))

# Soft time limit for tasks (seconds) - 55 minutes default
TASK_SOFT_TIME_LIMIT = int(os.getenv("TASK_SOFT_TIME_LIMIT_SECONDS", "3300"))


# ============================================================================
# RETRY CONFIGURATION (Global Defaults) - NEW NAMING: TASK_*
# ============================================================================

# Maximum retries for general tasks
MAX_RETRIES = int(os.getenv("TASK_MAX_RETRIES", "3"))

# Exponential backoff factor (multiplier for each retry)
RETRY_BACKOFF_FACTOR = int(os.getenv("TASK_RETRY_BACKOFF_FACTOR", "2"))

# Base retry delay (seconds)
RETRY_BACKOFF_BASE = int(os.getenv("TASK_RETRY_BACKOFF_BASE_SECONDS", "300"))


# ============================================================================
# MESSAGE PROCESSING SETTINGS - NEW NAMING: TASK_MESSAGE_*
# ============================================================================

# Timeout for sending a single message (seconds)
MESSAGE_SEND_TIMEOUT = int(os.getenv("TASK_MESSAGE_SEND_TIMEOUT_SECONDS", "60"))

# Maximum retries for message sending
MESSAGE_MAX_RETRIES = int(os.getenv("TASK_MESSAGE_MAX_RETRIES", "3"))

# Base delay for message retry (seconds)
MESSAGE_RETRY_DELAY = int(os.getenv("TASK_MESSAGE_RETRY_DELAY_SECONDS", "60"))

# Maximum messages to process per batch
MESSAGE_BATCH_SIZE = int(os.getenv("TASK_MESSAGE_BATCH_SIZE", "100"))

# Maximum failed messages to retry per batch
MESSAGE_RETRY_BATCH_SIZE = int(os.getenv("TASK_MESSAGE_RETRY_BATCH_SIZE", "50"))


# ============================================================================
# QUIZ PROCESSING SETTINGS - NEW NAMING: TASK_QUIZ_*
# ============================================================================

# Timeout for quiz processing operations (seconds)
QUIZ_PROCESSING_TIMEOUT = int(os.getenv("TASK_QUIZ_PROCESSING_TIMEOUT_SECONDS", "600"))

# Timeout for quiz report generation (seconds)
QUIZ_REPORT_TIMEOUT = int(os.getenv("TASK_QUIZ_REPORT_TIMEOUT_SECONDS", "300"))

# Maximum retries for quiz operations
QUIZ_MAX_RETRIES = int(os.getenv("TASK_QUIZ_MAX_RETRIES", "3"))

# Base delay for quiz retries (seconds)
QUIZ_RETRY_DELAY = int(os.getenv("TASK_QUIZ_RETRY_DELAY_SECONDS", "60"))

# Quiz question task retry delay (seconds)
QUIZ_QUESTION_RETRY_DELAY = int(
    os.getenv("TASK_QUIZ_QUESTION_RETRY_DELAY_SECONDS", "60")
)

# Quiz response task retry delay (seconds)
QUIZ_RESPONSE_RETRY_DELAY = int(
    os.getenv("TASK_QUIZ_RESPONSE_RETRY_DELAY_SECONDS", "30")
)

# Quiz response max retries
QUIZ_RESPONSE_MAX_RETRIES = int(os.getenv("TASK_QUIZ_RESPONSE_MAX_RETRIES", "2"))

# Quiz trigger check retry delay (seconds)
QUIZ_TRIGGER_RETRY_DELAY = int(
    os.getenv("TASK_QUIZ_TRIGGER_RETRY_DELAY_SECONDS", "120")
)

# Quiz cleanup retry delay (seconds)
QUIZ_CLEANUP_RETRY_DELAY = int(os.getenv("TASK_QUIZ_CLEANUP_RETRY_DELAY_SECONDS", "60"))

# Quiz cleanup max retries
QUIZ_CLEANUP_MAX_RETRIES = int(os.getenv("TASK_QUIZ_CLEANUP_MAX_RETRIES", "2"))

# Quiz progress update retry delay (seconds)
QUIZ_PROGRESS_RETRY_DELAY = int(
    os.getenv("TASK_QUIZ_PROGRESS_RETRY_DELAY_SECONDS", "30")
)

# Quiz report generation retry delay (seconds)
QUIZ_REPORT_RETRY_DELAY = int(os.getenv("TASK_QUIZ_REPORT_RETRY_DELAY_SECONDS", "120"))

# Quiz reminder retry delay (seconds)
QUIZ_REMINDER_RETRY_DELAY = int(
    os.getenv("TASK_QUIZ_REMINDER_RETRY_DELAY_SECONDS", "60")
)

# Quiz link monitoring retry delay (seconds)
QUIZ_LINK_MONITORING_RETRY_DELAY = int(
    os.getenv("TASK_QUIZ_LINK_MONITORING_RETRY_DELAY_SECONDS", "120")
)

# Maximum quiz triggers to check per batch
QUIZ_TRIGGER_BATCH_SIZE = int(os.getenv("TASK_QUIZ_TRIGGER_BATCH_SIZE", "100"))

# Maximum quiz session timeout (hours)
QUIZ_SESSION_TIMEOUT_HOURS = int(os.getenv("TASK_QUIZ_SESSION_TIMEOUT_HOURS", "48"))

# Maximum expired links to process per batch
QUIZ_EXPIRED_LINKS_BATCH_SIZE = int(
    os.getenv("TASK_QUIZ_EXPIRED_LINKS_BATCH_SIZE", "100")
)

# Maximum DLQ items to process per batch
QUIZ_DLQ_BATCH_SIZE = int(os.getenv("TASK_QUIZ_DLQ_BATCH_SIZE", "50"))


# ============================================================================
# WEBHOOK DLQ SETTINGS - NEW NAMING: TASK_WEBHOOK_DLQ_*
# ============================================================================

# Timeout for webhook DLQ processing (seconds)
WEBHOOK_DLQ_PROCESSING_TIMEOUT = int(
    os.getenv("TASK_WEBHOOK_DLQ_PROCESSING_TIMEOUT_SECONDS", "180")
)


# ============================================================================
# HEALTH MONITORING SETTINGS - NEW NAMING: TASK_HEALTH_*
# ============================================================================

# Timeout for health check operations (seconds)
HEALTH_CHECK_TIMEOUT = int(os.getenv("TASK_HEALTH_CHECK_TIMEOUT_SECONDS", "30"))

# Maximum active flows to fetch for health monitoring
HEALTH_ACTIVE_FLOWS_LIMIT = int(os.getenv("TASK_HEALTH_ACTIVE_FLOWS_LIMIT", "1000"))


# ============================================================================
# STUCK FLOW DETECTION SETTINGS - NEW NAMING: TASK_STUCK_FLOW_*
# ============================================================================

# Hours before an awaiting-response flow is considered stuck
STUCK_FLOW_DETECT_HOURS = int(os.getenv("TASK_STUCK_FLOW_DETECT_HOURS", "4"))

# Maximum automatic recovery attempts before escalating for manual intervention
STUCK_FLOW_MAX_RECOVERY_ATTEMPTS = int(
    os.getenv("TASK_STUCK_FLOW_MAX_RECOVERY_ATTEMPTS", "3")
)

# TTL for per-flow recovery idempotency keys in Redis (seconds)
STUCK_FLOW_RECOVERY_IDEMPOTENCY_TTL = int(
    os.getenv("TASK_STUCK_FLOW_RECOVERY_IDEMPOTENCY_TTL_SECONDS", "900")
)


# ============================================================================
# CLEANUP SETTINGS - NEW NAMING: TASK_CLEANUP_*
# ============================================================================

# Batch size for cleanup operations
CLEANUP_BATCH_SIZE = int(os.getenv("TASK_CLEANUP_BATCH_SIZE", "100"))

# Age threshold for cleanup (days)
CLEANUP_DAYS_OLD = int(os.getenv("TASK_CLEANUP_DAYS_OLD", "90"))

# Archive retention period (days)
ARCHIVE_RETENTION_DAYS = int(os.getenv("TASK_ARCHIVE_RETENTION_DAYS", "365"))


# ============================================================================
# REPORT GENERATION SETTINGS - NEW NAMING: TASK_REPORT_*
# ============================================================================

# Maximum retries for report generation
REPORT_MAX_RETRIES = int(os.getenv("TASK_REPORT_MAX_RETRIES", "3"))

# Base delay for report generation retries (seconds)
REPORT_RETRY_DELAY = int(os.getenv("TASK_REPORT_RETRY_DELAY_SECONDS", "300"))

# Alternative retry delay for reports (seconds)
REPORT_RETRY_DELAY_ALT = int(os.getenv("TASK_REPORT_RETRY_DELAY_ALT_SECONDS", "600"))


# ============================================================================
# SAGA PATTERN SETTINGS - NEW NAMING: TASK_SAGA_*
# ============================================================================

# Global timeout for entire saga execution (seconds) - ISSUE-003 FIX
SAGA_GLOBAL_TIMEOUT_SECONDS = int(os.getenv("TASK_SAGA_GLOBAL_TIMEOUT_SECONDS", "300"))

# Timeout for individual saga step execution (seconds)
SAGA_STEP_TIMEOUT_SECONDS = int(os.getenv("TASK_SAGA_STEP_TIMEOUT_SECONDS", "60"))

# Maximum retries per saga step
SAGA_STEP_MAX_RETRIES = int(os.getenv("TASK_SAGA_STEP_MAX_RETRIES", "3"))

# Initial delay for saga step retries (seconds)
SAGA_RETRY_INITIAL_DELAY_SECONDS = int(
    os.getenv("TASK_SAGA_RETRY_INITIAL_DELAY_SECONDS", "1")
)

# Maximum delay for saga step retries with exponential backoff (seconds)
SAGA_RETRY_MAX_DELAY_SECONDS = int(os.getenv("TASK_SAGA_RETRY_MAX_DELAY_SECONDS", "30"))

# TTL for persisted saga state in Redis (seconds) - 7 days default
SAGA_PERSISTENCE_TTL_SECONDS = int(
    os.getenv("TASK_SAGA_PERSISTENCE_TTL_SECONDS", "604800")
)

# Maximum retries for saga operations (backward compatibility)
SAGA_MAX_RETRIES = int(os.getenv("TASK_SAGA_MAX_RETRIES", "3"))

# Base delay for saga retries (seconds) (backward compatibility)
SAGA_RETRY_DELAY = int(os.getenv("TASK_SAGA_RETRY_DELAY_SECONDS", "60"))


# ============================================================================
# ALERT SETTINGS - NEW NAMING: TASK_ALERT_*
# ============================================================================

# Maximum retries for alert tasks
ALERT_MAX_RETRIES = int(os.getenv("TASK_ALERT_MAX_RETRIES", "3"))

# Alternative max retries for specific alerts
ALERT_MAX_RETRIES_ALT = int(os.getenv("TASK_ALERT_MAX_RETRIES_ALT", "2"))


# ============================================================================
# DEBOUNCE SETTINGS - NEW NAMING: TASK_DEBOUNCE_*
# ============================================================================

# Debounce window for duplicate operations (seconds)
DEBOUNCE_WINDOW_SECONDS = int(os.getenv("TASK_DEBOUNCE_WINDOW_SECONDS", "3"))


# ============================================================================
# REDIS SETTINGS (Task-specific) - NEW NAMING: TASK_REDIS_*
# ============================================================================

# Task result expiration in Redis (seconds)
REDIS_TASK_RESULT_EXPIRY = int(os.getenv("TASK_REDIS_RESULT_EXPIRY_SECONDS", "3600"))

# Socket timeout for Redis operations (seconds)
REDIS_SOCKET_TIMEOUT = int(os.getenv("TASK_REDIS_SOCKET_TIMEOUT_SECONDS", "5"))

# Socket connect timeout for Redis operations (seconds)
REDIS_SOCKET_CONNECT_TIMEOUT = int(
    os.getenv("TASK_REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", "5")
)


# ============================================================================
# CONCURRENCY SETTINGS - NEW NAMING: TASK_ENABLE_* for booleans
# ============================================================================

# Use async database operations
USE_ASYNC_DB = bool(
    os.getenv("TASK_ENABLE_ASYNC_DB", "False").lower() in ("true", "1", "yes")
)

# Enable parallel processing for batches
ENABLE_PARALLEL_PROCESSING = bool(
    os.getenv("TASK_ENABLE_PARALLEL_PROCESSING", "True").lower() in ("true", "1", "yes")
)

# Thread pool size for concurrent operations
THREAD_POOL_SIZE = int(os.getenv("TASK_THREAD_POOL_SIZE", "5"))

# Database connection pool size
CONNECTION_POOL_SIZE = int(os.getenv("TASK_CONNECTION_POOL_SIZE", "10"))


# ============================================================================
# FEATURE FLAGS - NEW NAMING: TASK_ENABLE_*
# ============================================================================

# Enable admin alerts for critical failures
ENABLE_ADMIN_ALERTS = bool(
    os.getenv("TASK_ENABLE_ADMIN_ALERTS", "True").lower() in ("true", "1", "yes")
)

# Admin email for alerts
ADMIN_ALERT_EMAIL = os.getenv("TASK_ADMIN_ALERT_EMAIL", "admin@example.com")

# Enable saga pattern for distributed transactions
ENABLE_SAGA_PATTERN = bool(
    os.getenv("TASK_SAGA_ENABLE_PATTERN", "True").lower() in ("true", "1", "yes")
)

# Enable Redis caching
ENABLE_REDIS_CACHING = bool(
    os.getenv("TASK_ENABLE_REDIS_CACHING", "True").lower() in ("true", "1", "yes")
)


def get_retry_countdown(
    retry_count: int,
    base_delay: int = RETRY_BACKOFF_BASE,
    backoff_factor: int = RETRY_BACKOFF_FACTOR,
) -> int:
    """
    Calculate retry countdown with exponential backoff.

    Args:
        retry_count: Current retry attempt number (0-indexed)
        base_delay: Base delay in seconds (default: RETRY_BACKOFF_BASE)
        backoff_factor: Exponential multiplier (default: RETRY_BACKOFF_FACTOR)

    Returns:
        Countdown in seconds with exponential backoff

    Examples:
        >>> get_retry_countdown(0, 60, 2)  # First retry: 60 * 2^0 = 60s
        60
        >>> get_retry_countdown(1, 60, 2)  # Second retry: 60 * 2^1 = 120s
        120
        >>> get_retry_countdown(2, 60, 2)  # Third retry: 60 * 2^2 = 240s
        240
    """
    return base_delay * (backoff_factor**retry_count)


def get_task_config(task_type: str) -> Dict[str, int]:
    """
    Get task-specific configuration.

    Args:
        task_type: Type of task (flow, message, quiz, cleanup, health, report, saga, alert)

    Returns:
        Dictionary with task configuration including timeouts, batch sizes, retry policies

    Raises:
        KeyError: If task_type is not recognized (returns empty dict instead)
    """
    configs = {
        "flow": {
            "timeout": FLOW_PROCESSING_TIMEOUT,
            "batch_size": FLOW_BATCH_SIZE,
            "max_concurrent": FLOW_MAX_CONCURRENT,
            "max_retries": FLOW_MAX_RETRIES,
            "retry_delay": FLOW_RETRY_DELAY,
            "time_limit": TASK_TIME_LIMIT,
            "soft_time_limit": TASK_SOFT_TIME_LIMIT,
        },
        "message": {
            "timeout": MESSAGE_SEND_TIMEOUT,
            "max_retries": MESSAGE_MAX_RETRIES,
            "retry_delay": MESSAGE_RETRY_DELAY,
            "batch_size": MESSAGE_BATCH_SIZE,
            "retry_batch_size": MESSAGE_RETRY_BATCH_SIZE,
        },
        "quiz": {
            "timeout": QUIZ_PROCESSING_TIMEOUT,
            "report_timeout": QUIZ_REPORT_TIMEOUT,
            "max_retries": QUIZ_MAX_RETRIES,
            "retry_delay": QUIZ_RETRY_DELAY,
            "question_retry_delay": QUIZ_QUESTION_RETRY_DELAY,
            "response_retry_delay": QUIZ_RESPONSE_RETRY_DELAY,
            "response_max_retries": QUIZ_RESPONSE_MAX_RETRIES,
            "trigger_retry_delay": QUIZ_TRIGGER_RETRY_DELAY,
            "trigger_batch_size": QUIZ_TRIGGER_BATCH_SIZE,
            "session_timeout_hours": QUIZ_SESSION_TIMEOUT_HOURS,
            "expired_links_batch_size": QUIZ_EXPIRED_LINKS_BATCH_SIZE,
            "dlq_batch_size": QUIZ_DLQ_BATCH_SIZE,
        },
        "cleanup": {
            "batch_size": CLEANUP_BATCH_SIZE,
            "days_old": CLEANUP_DAYS_OLD,
            "archive_retention": ARCHIVE_RETENTION_DAYS,
        },
        "health": {
            "timeout": HEALTH_CHECK_TIMEOUT,
            "active_flows_limit": HEALTH_ACTIVE_FLOWS_LIMIT,
        },
        "report": {
            "max_retries": REPORT_MAX_RETRIES,
            "retry_delay": REPORT_RETRY_DELAY,
            "retry_delay_alt": REPORT_RETRY_DELAY_ALT,
        },
        "saga": {
            "global_timeout": SAGA_GLOBAL_TIMEOUT_SECONDS,
            "step_timeout": SAGA_STEP_TIMEOUT_SECONDS,
            "step_max_retries": SAGA_STEP_MAX_RETRIES,
            "retry_initial_delay": SAGA_RETRY_INITIAL_DELAY_SECONDS,
            "retry_max_delay": SAGA_RETRY_MAX_DELAY_SECONDS,
            "persistence_ttl": SAGA_PERSISTENCE_TTL_SECONDS,
            "max_retries": SAGA_MAX_RETRIES,  # Backward compatibility
            "retry_delay": SAGA_RETRY_DELAY,  # Backward compatibility
        },
        "alert": {
            "max_retries": ALERT_MAX_RETRIES,
            "max_retries_alt": ALERT_MAX_RETRIES_ALT,
        },
    }

    return configs.get(task_type, {})
