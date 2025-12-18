"""
Celery Prometheus Metrics Module

Comprehensive metrics collection for Celery tasks including:
- Task execution counters
- Task duration histograms
- Active task gauges
- Failure tracking
- Retry monitoring
- Queue length metrics
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from celery.signals import (
    task_prerun,
    task_postrun,
    task_failure,
    task_retry,
    task_success,
    task_rejected,
    task_revoked,
    worker_ready,
    worker_shutdown,
)
import logging
from typing import Dict, Any
import time
from functools import wraps

logger = logging.getLogger(__name__)

# ============================================================================
# PROMETHEUS METRICS DEFINITIONS
# ============================================================================

# Task execution metrics
celery_task_total = Counter(
    "celery_task_total",
    "Total number of Celery tasks executed",
    ["task_name", "status"],  # status: success, failure, retry, rejected, revoked
)

celery_task_duration = Histogram(
    "celery_task_duration_seconds",
    "Task execution duration in seconds",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0],
)

celery_task_active = Gauge(
    "celery_task_active", "Number of currently executing tasks", ["task_name"]
)

celery_task_failures = Counter(
    "celery_task_failures_total",
    "Total number of task failures",
    ["task_name", "exception_type"],
)

celery_task_retries = Counter(
    "celery_task_retries_total",
    "Total number of task retries",
    ["task_name", "retry_count"],
)

celery_task_rejected = Counter(
    "celery_task_rejected_total", "Total number of rejected tasks", ["task_name"]
)

celery_task_revoked = Counter(
    "celery_task_revoked_total", "Total number of revoked tasks", ["task_name"]
)

celery_queue_length = Gauge(
    "celery_queue_length", "Number of tasks in queue", ["queue_name"]
)

celery_worker_active = Gauge(
    "celery_worker_active", "Number of active Celery workers", ["worker_name"]
)

celery_task_latency = Histogram(
    "celery_task_latency_seconds",
    "Time from task submission to execution start",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
)

celery_task_wait_time = Histogram(
    "celery_task_wait_time_seconds",
    "Time task spent waiting in queue",
    ["task_name"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
)

celery_info = Info("celery_worker_info", "Information about Celery worker")

# Task metadata storage for duration calculation
_task_metadata: Dict[str, Dict[str, Any]] = {}

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================


@task_prerun.connect
def task_prerun_handler(
    sender=None, task_id=None, task=None, args=None, kwargs=None, **extra
):
    """
    Handler called before task execution starts.

    Tracks:
    - Active task count increment
    - Task start time
    - Queue wait time calculation
    """
    try:
        task_name = sender.name if sender else task.name if task else "unknown"

        # Increment active tasks counter
        celery_task_active.labels(task_name=task_name).inc()

        # Store task metadata
        _task_metadata[task_id] = {
            "task_name": task_name,
            "start_time": time.time(),
            "eta": kwargs.get("eta") if kwargs else None,
        }

        # Calculate queue wait time if eta is available
        if kwargs and kwargs.get("eta"):
            wait_time = time.time() - kwargs["eta"]
            if wait_time > 0:
                celery_task_wait_time.labels(task_name=task_name).observe(wait_time)

        logger.debug(f"Task {task_name} [{task_id}] started")

    except Exception as e:
        logger.error(f"Error in task_prerun_handler: {e}", exc_info=True)


@task_postrun.connect
def task_postrun_handler(
    sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, **extra
):
    """
    Handler called after task execution completes (success or failure).

    Tracks:
    - Active task count decrement
    - Task duration
    """
    try:
        task_name = sender.name if sender else task.name if task else "unknown"

        # Decrement active tasks counter
        celery_task_active.labels(task_name=task_name).dec()

        # Calculate and record duration
        if task_id in _task_metadata:
            metadata = _task_metadata.pop(task_id)
            duration = time.time() - metadata["start_time"]
            celery_task_duration.labels(task_name=task_name).observe(duration)
            logger.debug(f"Task {task_name} [{task_id}] completed in {duration:.2f}s")

    except Exception as e:
        logger.error(f"Error in task_postrun_handler: {e}", exc_info=True)


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """
    Handler called when task completes successfully.

    Tracks:
    - Success counter increment
    """
    try:
        task_name = sender.name if sender else "unknown"
        celery_task_total.labels(task_name=task_name, status="success").inc()
        logger.debug(f"Task {task_name} succeeded")

    except Exception as e:
        logger.error(f"Error in task_success_handler: {e}", exc_info=True)


@task_failure.connect
def task_failure_handler(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    traceback=None,
    einfo=None,
    **extra,
):
    """
    Handler called when task fails.

    Tracks:
    - Failure counter increment
    - Exception type tracking
    """
    try:
        task_name = sender.name if sender else "unknown"
        exception_type = type(exception).__name__ if exception else "Unknown"

        # Increment failure counters
        celery_task_total.labels(task_name=task_name, status="failure").inc()
        celery_task_failures.labels(
            task_name=task_name, exception_type=exception_type
        ).inc()

        logger.error(
            f"Task {task_name} [{task_id}] failed with {exception_type}: {exception}",
            exc_info=True,
        )

    except Exception as e:
        logger.error(f"Error in task_failure_handler: {e}", exc_info=True)


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwargs):
    """
    Handler called when task is retried.

    Tracks:
    - Retry counter increment
    - Retry attempt number
    """
    try:
        task_name = sender.name if sender else "unknown"

        # Get retry count from request
        retry_count = str(sender.request.retries) if hasattr(sender, "request") else "0"

        # Increment retry counters
        celery_task_total.labels(task_name=task_name, status="retry").inc()
        celery_task_retries.labels(task_name=task_name, retry_count=retry_count).inc()

        logger.warning(f"Task {task_name} [{task_id}] retry #{retry_count}: {reason}")

    except Exception as e:
        logger.error(f"Error in task_retry_handler: {e}", exc_info=True)


@task_rejected.connect
def task_rejected_handler(sender=None, message=None, exc=None, **kwargs):
    """
    Handler called when task is rejected.

    Tracks:
    - Rejected task counter
    """
    try:
        # Extract task name from message
        task_name = message.headers.get("task", "unknown") if message else "unknown"

        celery_task_total.labels(task_name=task_name, status="rejected").inc()
        celery_task_rejected.labels(task_name=task_name).inc()

        logger.warning(f"Task {task_name} rejected: {exc}")

    except Exception as e:
        logger.error(f"Error in task_rejected_handler: {e}", exc_info=True)


@task_revoked.connect
def task_revoked_handler(
    sender=None, request=None, terminated=None, signum=None, expired=None, **kwargs
):
    """
    Handler called when task is revoked.

    Tracks:
    - Revoked task counter
    """
    try:
        task_name = sender.name if sender else "unknown"

        celery_task_total.labels(task_name=task_name, status="revoked").inc()
        celery_task_revoked.labels(task_name=task_name).inc()

        reason = "expired" if expired else "terminated" if terminated else "manual"
        logger.info(f"Task {task_name} revoked ({reason})")

    except Exception as e:
        logger.error(f"Error in task_revoked_handler: {e}", exc_info=True)


@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """
    Handler called when worker is ready.

    Tracks:
    - Worker activation
    """
    try:
        worker_name = sender.hostname if sender else "unknown"
        celery_worker_active.labels(worker_name=worker_name).set(1)

        # Set worker info
        celery_info.info({"worker": worker_name, "status": "ready"})

        logger.info(f"Celery worker {worker_name} is ready")

    except Exception as e:
        logger.error(f"Error in worker_ready_handler: {e}", exc_info=True)


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """
    Handler called when worker shuts down.

    Tracks:
    - Worker deactivation
    """
    try:
        worker_name = sender.hostname if sender else "unknown"
        celery_worker_active.labels(worker_name=worker_name).set(0)

        logger.info(f"Celery worker {worker_name} shutting down")

    except Exception as e:
        logger.error(f"Error in worker_shutdown_handler: {e}", exc_info=True)


# ============================================================================
# DECORATOR FOR TASK TIME TRACKING
# ============================================================================


def track_task_time(func):
    """
    Decorator to track task execution time.

    Usage:
        @app.task
        @track_task_time
        def my_task():
            ...
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        task_name = func.__name__

        with celery_task_duration.labels(task_name=task_name).time():
            return func(*args, **kwargs)

    return wrapper


# ============================================================================
# QUEUE MONITORING UTILITIES
# ============================================================================


def update_queue_length(queue_name: str, length: int):
    """
    Update queue length metric.

    Args:
        queue_name: Name of the queue
        length: Current queue length
    """
    try:
        celery_queue_length.labels(queue_name=queue_name).set(length)
    except Exception as e:
        logger.error(f"Error updating queue length for {queue_name}: {e}")


def get_task_metrics_summary() -> Dict[str, Any]:
    """
    Get summary of current task metrics.

    Returns:
        Dictionary containing metric summaries
    """
    return {
        "active_tasks": sum(
            metric.labels(task_name=name)._value.get()
            for name, metric in celery_task_active._metrics.items()
        ),
        "total_failures": sum(
            metric._value.get() for metric in celery_task_failures._metrics.values()
        ),
        "total_retries": sum(
            metric._value.get() for metric in celery_task_retries._metrics.values()
        ),
        "queue_lengths": {
            name: metric._value.get()
            for name, metric in celery_queue_length._metrics.items()
        },
    }


# Initialize metrics logging
logger.info("Celery Prometheus metrics initialized")
