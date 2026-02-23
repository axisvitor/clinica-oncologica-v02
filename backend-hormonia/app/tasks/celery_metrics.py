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
import threading
from typing import Dict, Any, Optional
import time
from datetime import datetime
from functools import wraps

from app.core.redis_manager import get_redis_manager

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
_task_metadata_lock = threading.Lock()

# How long metadata may remain without terminal signals (safety net for missed postrun)
_TASK_METADATA_MAX_AGE_SECONDS = 6 * 60 * 60
# Grace period for failure/revoked/rejected tasks waiting for possible postrun
_TASK_TERMINAL_METADATA_TTL_SECONDS = 5 * 60

# Redis key used to store rolling task duration samples
_DURATION_REDIS_KEY = "celery:metrics:avg_task_duration"


def _push_duration_to_redis(duration: float) -> None:
    """
    Push a task duration sample to the Redis rolling list.

    Keeps the last 100 samples with a 24-hour TTL.
    Silently swallows all exceptions — metrics writes must never affect task execution.
    """
    try:
        client = get_redis_manager().get_sync_client()
        pipe = client.pipeline()
        pipe.lpush(_DURATION_REDIS_KEY, str(duration))
        pipe.ltrim(_DURATION_REDIS_KEY, 0, 99)  # Keep last 100 samples
        pipe.expire(_DURATION_REDIS_KEY, 86400)  # 24h TTL
        pipe.execute()
    except Exception:
        pass


def _resolve_task_name(sender=None, task=None) -> str:
    """Resolve task name safely from Celery signal payloads."""
    if sender is not None and hasattr(sender, "name"):
        return sender.name
    if task is not None and hasattr(task, "name"):
        return task.name
    return "unknown"


def _register_task_metadata(
    task_id: Optional[str],
    task_name: str,
    eta: Optional[Any] = None,
) -> None:
    """Store metadata required to compute duration and cleanup lifecycle."""
    if not task_id:
        return

    now = time.time()
    with _task_metadata_lock:
        _task_metadata[task_id] = {
            "task_name": task_name,
            "start_time": now,
            "eta": eta,
            "active_decremented": False,
            "terminal_status": None,
            "terminal_at": None,
        }


def _mark_task_terminal(
    task_id: Optional[str],
    fallback_task_name: str,
    status: str,
) -> bool:
    """
    Mark task metadata as terminal and decrement active gauge once.

    Returns True when metadata exists for task_id.
    """
    if not task_id:
        return False

    should_decrement_active = False
    task_name = fallback_task_name

    with _task_metadata_lock:
        metadata = _task_metadata.get(task_id)
        if not metadata:
            return False

        metadata["terminal_status"] = status
        metadata["terminal_at"] = time.time()
        task_name = metadata.get("task_name", fallback_task_name)

        if not metadata.get("active_decremented", False):
            metadata["active_decremented"] = True
            should_decrement_active = True

    if should_decrement_active:
        celery_task_active.labels(task_name=task_name).dec()

    return True


def _finalize_task_metadata(
    task_id: Optional[str],
    fallback_task_name: str,
    observe_duration: bool,
) -> bool:
    """
    Remove task metadata and finalize active/duration metrics idempotently.

    Returns True when metadata existed and was finalized.
    """
    if not task_id:
        return False

    with _task_metadata_lock:
        metadata = _task_metadata.pop(task_id, None)

    if not metadata:
        return False

    task_name = metadata.get("task_name", fallback_task_name)
    if not metadata.get("active_decremented", False):
        celery_task_active.labels(task_name=task_name).dec()

    if observe_duration:
        start_time = metadata.get("start_time")
        if isinstance(start_time, (float, int)):
            duration = max(0.0, time.time() - start_time)
            celery_task_duration.labels(task_name=task_name).observe(duration)
            _push_duration_to_redis(duration)
            logger.debug(f"Task {task_name} [{task_id}] completed in {duration:.2f}s")

    return True


def _cleanup_stale_task_metadata() -> int:
    """
    Cleanup metadata leaked by missing lifecycle signals.

    - Terminal tasks are removed after a short grace period.
    - Non-terminal tasks are removed after a long max-age safety timeout.
    """
    now = time.time()
    stale_task_ids = []

    with _task_metadata_lock:
        for task_id, metadata in _task_metadata.items():
            start_time = metadata.get("start_time", now)
            terminal_at = metadata.get("terminal_at")

            terminal_expired = (
                isinstance(terminal_at, (float, int))
                and now - terminal_at >= _TASK_TERMINAL_METADATA_TTL_SECONDS
            )
            max_age_expired = (
                isinstance(start_time, (float, int))
                and now - start_time >= _TASK_METADATA_MAX_AGE_SECONDS
            )

            if terminal_expired or max_age_expired:
                stale_task_ids.append(task_id)

    for stale_task_id in stale_task_ids:
        _finalize_task_metadata(
            task_id=stale_task_id,
            fallback_task_name="unknown",
            observe_duration=False,
        )

    if stale_task_ids:
        logger.warning(
            "Cleaned %d stale celery task metadata entries",
            len(stale_task_ids),
        )

    return len(stale_task_ids)


def _clear_all_task_metadata() -> int:
    """Force cleanup of all tracked metadata (worker shutdown safety)."""
    with _task_metadata_lock:
        task_ids = list(_task_metadata.keys())

    for task_id in task_ids:
        _finalize_task_metadata(
            task_id=task_id,
            fallback_task_name="unknown",
            observe_duration=False,
        )

    if task_ids:
        logger.warning(
            "Cleared %d task metadata entries during worker lifecycle cleanup",
            len(task_ids),
        )

    return len(task_ids)


def _extract_message_task_id(message: Any) -> Optional[str]:
    """Best-effort task id extraction from rejected message payload."""
    if message is None:
        return None

    for attr_name in ("headers", "properties"):
        payload = getattr(message, attr_name, None)
        if isinstance(payload, dict):
            task_id = (
                payload.get("id")
                or payload.get("task_id")
                or payload.get("correlation_id")
            )
            if task_id:
                return str(task_id)

    return None


def _eta_to_timestamp_seconds(eta: Any) -> Optional[float]:
    """Normalize ETA to unix timestamp seconds."""
    if eta is None:
        return None
    if isinstance(eta, (int, float)):
        return float(eta)
    if isinstance(eta, datetime):
        return eta.timestamp()
    if isinstance(eta, str):
        parsed_eta = eta.strip()
        if not parsed_eta:
            return None
        try:
            # Accept both ISO8601 and trailing Z UTC format.
            normalized = parsed_eta.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            return None
    return None

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
    _ = extra
    try:
        task_name = _resolve_task_name(sender=sender, task=task)

        # Opportunistic cleanup in case previous terminal events missed postrun
        _cleanup_stale_task_metadata()

        # Increment active tasks counter
        celery_task_active.labels(task_name=task_name).inc()

        # Store task metadata
        _register_task_metadata(
            task_id=task_id,
            task_name=task_name,
            eta=kwargs.get("eta") if kwargs else None,
        )

        # Calculate queue wait time if eta is available
        if kwargs and kwargs.get("eta"):
            eta_timestamp = _eta_to_timestamp_seconds(kwargs.get("eta"))
            wait_time = time.time() - eta_timestamp if eta_timestamp is not None else None
            if wait_time is not None and wait_time > 0:
                celery_task_wait_time.labels(task_name=task_name).observe(wait_time)
                celery_task_latency.labels(task_name=task_name).observe(wait_time)

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
    _ = retval
    _ = extra
    try:
        task_name = _resolve_task_name(sender=sender, task=task)

        # Fallback for tasks without task_id metadata support
        if not task_id:
            celery_task_active.labels(task_name=task_name).dec()
            return

        _finalize_task_metadata(
            task_id=task_id,
            fallback_task_name=task_name,
            observe_duration=True,
        )

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
    _ = traceback
    _ = einfo
    _ = extra
    try:
        task_name = _resolve_task_name(sender=sender)
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

        # Mark terminal in case postrun is missed; cleanup is idempotent.
        _mark_task_terminal(
            task_id=task_id,
            fallback_task_name=task_name,
            status="failure",
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
    _ = einfo
    try:
        task_name = _resolve_task_name(sender=sender)

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
        task_id = _extract_message_task_id(message)

        celery_task_total.labels(task_name=task_name, status="rejected").inc()
        celery_task_rejected.labels(task_name=task_name).inc()

        logger.warning(f"Task {task_name} rejected: {exc}")

        # Rejected tasks may not emit postrun in some worker failure paths.
        _mark_task_terminal(
            task_id=task_id,
            fallback_task_name=task_name,
            status="rejected",
        )

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
    _ = signum
    try:
        task_name = _resolve_task_name(sender=sender)
        task_id = getattr(request, "id", None) if request is not None else None

        celery_task_total.labels(task_name=task_name, status="revoked").inc()
        celery_task_revoked.labels(task_name=task_name).inc()

        reason = "expired" if expired else "terminated" if terminated else "manual"
        logger.info(f"Task {task_name} revoked ({reason})")

        # Revoked tasks may not emit postrun in some worker failure paths.
        _mark_task_terminal(
            task_id=task_id,
            fallback_task_name=task_name,
            status="revoked",
        )

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

        # Safety cleanup at startup in case worker lifecycle ended unexpectedly.
        _cleanup_stale_task_metadata()

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

        # Ensure metadata and active gauges are not leaked across worker lifecycle.
        _clear_all_task_metadata()

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
    active_tasks = 0.0
    total_failures = 0.0
    total_retries = 0.0
    queue_lengths: Dict[str, float] = {}

    for family in celery_task_active.collect():
        for sample in family.samples:
            if sample.name == "celery_task_active":
                active_tasks += float(sample.value)

    for family in celery_task_failures.collect():
        for sample in family.samples:
            if sample.name == "celery_task_failures_total":
                total_failures += float(sample.value)

    for family in celery_task_retries.collect():
        for sample in family.samples:
            if sample.name == "celery_task_retries_total":
                total_retries += float(sample.value)

    for family in celery_queue_length.collect():
        for sample in family.samples:
            if sample.name != "celery_queue_length":
                continue
            queue_name = sample.labels.get("queue_name", "unknown")
            queue_lengths[queue_name] = float(sample.value)

    return {
        "active_tasks": active_tasks,
        "total_failures": total_failures,
        "total_retries": total_retries,
        "queue_lengths": queue_lengths,
    }


# Initialize metrics logging
logger.info("Celery Prometheus metrics initialized")
