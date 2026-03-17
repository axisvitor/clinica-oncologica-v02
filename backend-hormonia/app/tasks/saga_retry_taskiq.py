"""
Taskiq saga retry tasks — async-native replacements for Celery saga retry tasks (M009-S03).

All 3 saga-domain tasks migrated from Celery to Taskiq:
  1. retry_patient_onboarding_saga  — on-demand with retry (SmartRetryMiddleware)
  2. scan_and_retry_failed_sagas    — 300s interval, dispatches retry tasks
  3. cleanup_old_completed_sagas    — 86400s interval, DB housekeeping

Key translation patterns from Celery → Taskiq:
  - self.retry(countdown=60*(2**retries)) → SmartRetryMiddleware (retry_on_error=True, delay=60)
  - .apply_async(countdown=N) → await schedule_task_at(task, delivery_time, *args)
  - run_async(SagaOrchestrator().resume_saga()) → await SagaOrchestrator().resume_saga()
  - get_scoped_session() (sync) → AsyncSession via TaskiqDepends
  - Structured logging via log_task_start/success/error from taskiq_base

Schedule labels (2 of 3 tasks are periodic):
  - scan_and_retry_failed_sagas:  interval 300s  (every 5 min)
  - cleanup_old_completed_sagas:  interval 86400s (daily)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import Context, TaskiqDepends

from app.taskiq_broker import broker
from app.tasks.taskiq_base import (
    DbSession,
    log_task_error,
    log_task_start,
    log_task_success,
    schedule_task_at,
)

# Domain models
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus

# Saga orchestrator — accepts Any session (works with both sync and async)
from app.orchestration.saga_orchestrator import SagaOrchestrator

# Async Redis client for SagaOrchestrator
from app.core.redis_client import get_async_redis_client

# Monitoring
from app.core.monitoring_config import capture_exception, capture_message

# Config
from app.config import settings

# Pure helper from Celery module — reused without duplication
from app.tasks.helpers.saga_helpers import (
    _calculate_exponential_backoff,
    _alert_admin_max_retries_exceeded,
)

# Timezone helper
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger("app.tasks.saga_retry_taskiq")


# ---------------------------------------------------------------------------
# 1. retry_patient_onboarding_saga — on-demand with retry
#
# Celery: self.retry(countdown=60*(2**self.request.retries), max_retries=3)
# Taskiq: SmartRetryMiddleware handles exponential backoff automatically
#         via labels retry_on_error=True, max_retries=5, delay=60
#
# Celery: run_async(orchestrator.resume_saga(saga_id))
# Taskiq: await orchestrator.resume_saga(saga_id) — direct async call
# ---------------------------------------------------------------------------


@broker.task(
    task_name="saga_retry_taskiq.retry_patient_onboarding_saga",
    retry_on_error=True,
    max_retries=5,
    delay=60,
)
async def retry_patient_onboarding_saga(
    saga_id: str,
    context: Context = TaskiqDepends(),
    db: AsyncSession = DbSession,
) -> dict:
    """
    Retry a specific failed patient onboarding saga.

    Attempts to resume the saga from its last successful step using
    ``SagaOrchestrator.resume_saga()``. On failure, SmartRetryMiddleware
    handles exponential backoff retries (up to 5 attempts, base delay 60s).

    If retries are exhausted (checked via ``context.message.labels``),
    the saga is marked as permanently failed and an admin alert is created.

    Args:
        saga_id: UUID string of the saga to retry.
        context: Taskiq context (injected) — provides retry count via labels.
        db: AsyncSession (injected via TaskiqDepends).

    Returns:
        dict with status, message, saga_id, and retry details.
    """
    retries = int(context.message.labels.get("_retries", 0))
    _max_retries = 5
    start = log_task_start(
        "retry_patient_onboarding_saga",
        saga_id=saga_id,
        attempt=retries,
    )

    try:
        # Fetch saga from database
        result = await db.execute(
            select(PatientOnboardingSaga).filter(
                PatientOnboardingSaga.id == UUID(saga_id)
            )
        )
        saga = result.scalars().first()

        if not saga:
            logger.error(f"Saga not found: {saga_id}")
            log_task_success(
                "retry_patient_onboarding_saga", start, saga_id=saga_id, status="not_found"
            )
            return {"status": "error", "message": "Saga not found", "saga_id": saga_id}

        # Check if saga is eligible for retry
        retryable_statuses = [
            SagaStatus.FAILED,
            SagaStatus.COMPENSATING,
            SagaStatus.RETRY_SCHEDULED,
        ]
        if saga.status not in retryable_statuses:
            logger.info(f"Saga {saga_id} not retryable: {saga.status}")
            log_task_success(
                "retry_patient_onboarding_saga", start, saga_id=saga_id, status="skipped"
            )
            return {
                "status": "skipped",
                "message": f"Saga status is {saga.status}, not retryable",
                "saga_id": saga_id,
            }

        # Check max retries from saga's own counter
        saga_max = getattr(settings, "SAGA_MAX_RETRIES", 3)
        if saga.retry_count >= saga_max:
            logger.warning(f"Saga {saga_id} exceeded max retries ({saga.retry_count})")
            await _alert_admin_max_retries_exceeded(saga, db)
            log_task_success(
                "retry_patient_onboarding_saga",
                start,
                saga_id=saga_id,
                status="max_retries_exceeded",
            )
            return {
                "status": "max_retries_exceeded",
                "message": f"Saga has been retried {saga.retry_count} times",
                "saga_id": saga_id,
            }

        # Backoff check
        now = now_sao_paulo()
        if saga.next_retry_at and now < saga.next_retry_at:
            log_task_success(
                "retry_patient_onboarding_saga", start, saga_id=saga_id, status="backoff"
            )
            return {
                "status": "backoff",
                "message": "Waiting for scheduled retry window",
                "next_retry_at": saga.next_retry_at.isoformat(),
                "saga_id": saga_id,
            }

        if saga.status == SagaStatus.RETRY_SCHEDULED:
            saga.status = SagaStatus.FAILED
            saga.next_retry_at = None
            await db.commit()

        # Exponential backoff check against last_retry_at
        backoff_seconds = _calculate_exponential_backoff(saga.retry_count)
        if saga.last_retry_at:
            next_retry_time = saga.last_retry_at + timedelta(seconds=backoff_seconds)
            if now < next_retry_time:
                logger.info(
                    f"Saga {saga_id} not ready for retry (backoff: {backoff_seconds}s)"
                )
                log_task_success(
                    "retry_patient_onboarding_saga", start, saga_id=saga_id, status="backoff"
                )
                return {
                    "status": "backoff",
                    "message": f"Waiting for backoff period ({backoff_seconds}s)",
                    "next_retry_at": next_retry_time.isoformat(),
                    "saga_id": saga_id,
                }

        # Increment retry count
        saga.retry_count += 1
        saga.last_retry_at = now
        await db.commit()

        logger.info(
            f"Retrying saga {saga_id} (attempt {saga.retry_count}/{saga_max})"
        )

        # Resume saga — direct async call (no run_async bridge)
        redis_client = await get_async_redis_client()
        orchestrator = SagaOrchestrator(db=db, redis_client=redis_client)
        resume_result = await orchestrator.resume_saga(saga_id=UUID(saga_id))

        if resume_result.status == "completed":
            logger.info(f"Saga {saga_id} completed successfully on retry")
            capture_message(
                f"Saga retry successful: {saga_id}",
                level="info",
                extra={"saga_id": saga_id, "retry_count": saga.retry_count},
            )
            log_task_success(
                "retry_patient_onboarding_saga",
                start,
                saga_id=saga_id,
                status="success",
                retry_count=saga.retry_count,
            )
            return {
                "status": "success",
                "message": "Saga completed successfully",
                "saga_id": saga_id,
                "retry_count": saga.retry_count,
            }
        else:
            logger.warning(
                f"Saga {saga_id} failed on retry: {resume_result.error}"
            )
            log_task_success(
                "retry_patient_onboarding_saga",
                start,
                saga_id=saga_id,
                status="failed",
                retry_count=saga.retry_count,
            )
            # Will be picked up by scan_and_retry_failed_sagas if under max retries
            return {
                "status": "failed",
                "message": resume_result.error or "Unknown error",
                "saga_id": saga_id,
                "retry_count": saga.retry_count,
            }

    except Exception as e:
        logger.error(f"Error retrying saga {saga_id}: {e}", exc_info=True)
        capture_exception(e)

        # SmartRetryMiddleware DLQ pattern: check if retries exhausted
        if retries >= _max_retries:
            log_task_error(
                "retry_patient_onboarding_saga",
                e,
                start,
                saga_id=saga_id,
                permanently_failed=True,
                dlq_routed=True,
            )
            return {
                "status": "permanently_failed",
                "message": str(e),
                "saga_id": saga_id,
                "attempts": _max_retries,
                "permanently_failed": True,
                "dlq_routed": True,
            }

        # Let SmartRetryMiddleware handle the retry with exponential backoff
        log_task_error(
            "retry_patient_onboarding_saga", e, start, saga_id=saga_id, attempt=retries
        )
        raise


# ---------------------------------------------------------------------------
# 2. scan_and_retry_failed_sagas — periodic scanner (300s interval)
#
# Celery: retry_patient_onboarding_saga.apply_async(args=[...], countdown=N)
# Taskiq: await schedule_task_at(retry_patient_onboarding_saga, delivery_time, saga_id)
# ---------------------------------------------------------------------------


@broker.task(
    task_name="saga_retry_taskiq.scan_and_retry_failed_sagas",
    schedule=[{"interval": {"seconds": 300}}],
)
async def scan_and_retry_failed_sagas(
    db: AsyncSession = DbSession,
) -> dict:
    """
    Periodic task scanning for failed sagas and scheduling retries.

    Runs every 5 minutes. Finds sagas in FAILED / COMPENSATING / RETRY_SCHEDULED
    status that are eligible for retry, then dispatches
    ``retry_patient_onboarding_saga`` for each via ``schedule_task_at()``
    (replacing Celery's ``.apply_async(countdown=)`` pattern).

    Args:
        db: AsyncSession (injected via TaskiqDepends).

    Returns:
        dict with total_found, scheduled, max_retries_exceeded counts.
    """
    start = log_task_start("scan_and_retry_failed_sagas")

    try:
        logger.info("Starting scan for failed sagas...")

        # Find failed sagas eligible for retry (async query)
        saga_max = getattr(settings, "SAGA_MAX_RETRIES", 3)
        result = await db.execute(
            select(PatientOnboardingSaga).filter(
                and_(
                    PatientOnboardingSaga.status.in_(
                        [
                            SagaStatus.FAILED,
                            SagaStatus.COMPENSATING,
                            SagaStatus.RETRY_SCHEDULED,
                        ]
                    ),
                    PatientOnboardingSaga.retry_count < saga_max,
                )
            )
        )
        failed_sagas: List[PatientOnboardingSaga] = list(result.scalars().all())

        # Filter by backoff readiness
        now = now_sao_paulo()
        eligible_sagas = []
        for saga in failed_sagas:
            if _is_ready_for_retry_async(saga, now):
                eligible_sagas.append(saga)

        if not eligible_sagas:
            logger.info("No failed sagas found for retry")
            log_task_success(
                "scan_and_retry_failed_sagas", start, count=0
            )
            return {
                "status": "success",
                "message": "No failed sagas to retry",
                "count": 0,
            }

        logger.info(f"Found {len(eligible_sagas)} failed sagas eligible for retry")

        # Schedule retry tasks for each saga
        scheduled_count = 0
        max_retries_count = 0

        for saga in eligible_sagas:
            try:
                if saga.retry_count >= saga_max:
                    logger.warning(f"Saga {saga.id} exceeded max retries, skipping")
                    max_retries_count += 1
                    continue

                backoff_seconds = _calculate_exponential_backoff(saga.retry_count)
                saga.status = SagaStatus.RETRY_SCHEDULED
                saga.next_retry_at = now + timedelta(seconds=backoff_seconds)
                await db.commit()

                # Schedule via schedule_task_at (replaces .apply_async(countdown=))
                delivery_time = datetime.now(timezone.utc) + timedelta(
                    seconds=backoff_seconds
                )
                await schedule_task_at(
                    retry_patient_onboarding_saga,
                    delivery_time,
                    str(saga.id),
                )

                scheduled_count += 1
                logger.info(
                    f"Scheduled retry for saga {saga.id} in {backoff_seconds}s"
                )

            except Exception as e:
                logger.error(f"Failed to schedule retry for saga {saga.id}: {e}")
                saga.status = SagaStatus.FAILED
                saga.next_retry_at = None
                await db.commit()
                continue

        logger.info(
            f"Scan complete: {scheduled_count} retries scheduled, "
            f"{max_retries_count} max retries exceeded"
        )
        log_task_success(
            "scan_and_retry_failed_sagas",
            start,
            total_found=len(eligible_sagas),
            scheduled=scheduled_count,
            max_retries_exceeded=max_retries_count,
        )

        return {
            "status": "success",
            "message": f"Scheduled {scheduled_count} retry tasks",
            "total_found": len(eligible_sagas),
            "scheduled": scheduled_count,
            "max_retries_exceeded": max_retries_count,
        }

    except Exception as e:
        logger.error(f"Error scanning for failed sagas: {e}", exc_info=True)
        capture_exception(e)
        log_task_error("scan_and_retry_failed_sagas", e, start)
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 3. cleanup_old_completed_sagas — daily housekeeping (86400s interval)
#
# Celery: sync get_scoped_session + db.query().filter().all() + db.delete()
# Taskiq: async DB via TaskiqDepends + select() + await db.delete()
# ---------------------------------------------------------------------------


@broker.task(
    task_name="saga_retry_taskiq.cleanup_old_completed_sagas",
    schedule=[{"interval": {"seconds": 86400}}],
)
async def cleanup_old_completed_sagas(
    db: AsyncSession = DbSession,
) -> dict:
    """
    Clean up completed sagas older than retention period.

    Runs daily. Deletes ``PatientOnboardingSaga`` records that have
    status COMPLETED and ``completed_at`` older than the configured
    retention period (default: 30 days).

    Args:
        db: AsyncSession (injected via TaskiqDepends).

    Returns:
        dict with deleted_count and status.
    """
    start = log_task_start("cleanup_old_completed_sagas")

    try:
        retention_days = getattr(settings, "SAGA_RETENTION_DAYS", 30)
        cutoff_date = now_sao_paulo() - timedelta(days=retention_days)

        logger.info(
            f"Starting cleanup of completed sagas older than {retention_days} days"
        )

        # Find old completed sagas
        result = await db.execute(
            select(PatientOnboardingSaga).filter(
                and_(
                    PatientOnboardingSaga.status == SagaStatus.COMPLETED,
                    PatientOnboardingSaga.completed_at < cutoff_date,
                )
            )
        )
        old_sagas: List[PatientOnboardingSaga] = list(result.scalars().all())

        if not old_sagas:
            logger.info("No old completed sagas to clean up")
            log_task_success(
                "cleanup_old_completed_sagas", start, deleted_count=0
            )
            return {
                "status": "success",
                "message": "No old sagas to clean up",
                "deleted_count": 0,
            }

        # Delete old sagas
        deleted_count = 0
        for saga in old_sagas:
            try:
                await db.delete(saga)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete saga {saga.id}: {e}")
                continue

        await db.commit()

        logger.info(f"Cleanup complete: {deleted_count} old sagas deleted")
        log_task_success(
            "cleanup_old_completed_sagas",
            start,
            deleted_count=deleted_count,
            retention_days=retention_days,
        )

        return {
            "status": "success",
            "message": f"Deleted {deleted_count} old completed sagas",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"Error cleaning up old sagas: {e}", exc_info=True)
        capture_exception(e)
        await db.rollback()
        log_task_error("cleanup_old_completed_sagas", e, start)
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_ready_for_retry_async(saga: PatientOnboardingSaga, now: datetime) -> bool:
    """
    Check if saga is ready for retry based on backoff period or scheduled time.

    Mirrors ``_is_ready_for_retry`` from Celery module but uses a pre-fetched
    ``now`` timestamp to avoid repeated clock calls inside a loop.

    Args:
        saga: The saga record to check.
        now: Current time (pre-fetched).

    Returns:
        True if the saga is ready for a retry attempt.
    """
    # Respect scheduled retry time
    if saga.next_retry_at:
        return now >= saga.next_retry_at

    # Never retried → ready immediately
    if not saga.last_retry_at:
        return True

    # Check exponential backoff elapsed
    backoff_seconds = _calculate_exponential_backoff(saga.retry_count)
    next_retry_time = saga.last_retry_at + timedelta(seconds=backoff_seconds)
    return now >= next_retry_time
