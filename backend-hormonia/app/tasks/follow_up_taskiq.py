"""
Taskiq follow-up tasks — async-native replacements for Celery follow_up tasks (M009-S04).

3 tasks migrated from Celery to Taskiq:
  1. execute_pending_follow_ups — interval 300s (core follow-up processor)
  2. process_escalation_alerts  — interval 600s (escalation processing)
  3. cleanup_old_contexts       — cron 0 6 * * * (daily 03:00 BRT → 06:00 UTC)

Key translation patterns from Celery → Taskiq:
  - 15+ async_to_sync() bridges removed → direct await for all FollowUpSystemService
    and redis_store methods (rehydrate_from_redis, get_pending_actions,
    sync_memory_to_redis, claim_pending_action, update_action_status,
    acquire_follow_up_lock, release_follow_up_lock, get_last_follow_up_sent_at,
    set_last_follow_up_sent_at)
  - DatabaseTask base class removed: SmartRetryMiddleware handles retries
  - self.log_task_start/success/error → log_task_start/success/error from taskiq_base
  - self.create_success_result/create_error_result → plain dict returns
  - process_alert_notification.delay() → await process_alert_notification.kiq()
    from alerts_taskiq (T02 output)
  - Prometheus metrics preserved (compatible with async code)
  - Distributed lock / dedup patterns preserved (not Celery-specific)
  - Pure helper functions imported from app.tasks.follow_up to avoid duplication

Cross-module imports:
  - alerts_taskiq.process_alert_notification — used by _send_escalation_notification,
    _send_provider_alert

Schedule labels (3 tasks are periodic):
  - execute_pending_follow_ups: interval 300s (every 5 minutes)
  - process_escalation_alerts: interval 600s (every 10 minutes)
  - cleanup_old_contexts: cron 0 6 * * * (daily 06:00 UTC = 03:00 BRT)
"""

import inspect
import logging
import time
from datetime import timedelta
from typing import Any, Dict
from uuid import UUID

from app.database import get_scoped_session
from app.monitoring.metrics import (
    follow_up_action_duration_seconds,
    follow_up_actions_total,
    follow_up_messages_deduplicated_total,
    follow_up_messages_sent_total,
    follow_up_pending_actions,
)
from app.taskiq_broker import broker
from app.tasks.helpers.follow_up_helpers import (
    FOLLOW_UP_DEDUP_WINDOW_SECONDS,
    FOLLOW_UP_DEDUP_LOCK_SECONDS,
    _get_last_follow_up_sent_at_db,
    _is_follow_up_eligible,
    _update_patient_last_message_sent_at,
)
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger("app.tasks.follow_up_taskiq")


# ===========================================================================
# Async helper functions — bridge-free versions of Celery sync wrappers
# ===========================================================================

async def _acquire_follow_up_lock_async(follow_up_service, patient_id: UUID) -> bool:
    """Acquire follow-up dedup lock via async redis_store method."""
    return await follow_up_service.redis_store.acquire_follow_up_lock(
        patient_id=patient_id, ttl_seconds=FOLLOW_UP_DEDUP_LOCK_SECONDS
    )


async def _release_follow_up_lock_async(follow_up_service, patient_id: UUID) -> None:
    """Release follow-up dedup lock via async redis_store method."""
    if not follow_up_service.redis_store.is_redis_available():
        return

    try:
        await follow_up_service.redis_store.release_follow_up_lock(
            patient_id=patient_id
        )
    except Exception as e:
        logger.warning(
            "Failed to release follow-up lock",
            extra={"patient_id": str(patient_id), "error": str(e)},
        )


async def _get_last_follow_up_sent_at_async(
    follow_up_service, patient_id: UUID
):
    """Get last follow-up sent timestamp from Redis via async method."""
    try:
        return await follow_up_service.redis_store.get_last_follow_up_sent_at(
            patient_id
        )
    except Exception as e:
        logger.warning(
            "Failed to fetch follow-up dedup timestamp",
            extra={"patient_id": str(patient_id), "error": str(e)},
        )
        return None


async def _set_last_follow_up_sent_at_async(
    follow_up_service, patient_id: UUID, sent_at
) -> None:
    """Persist follow-up dedup timestamp to Redis via async method."""
    try:
        await follow_up_service.redis_store.set_last_follow_up_sent_at(
            patient_id=patient_id,
            sent_at=sent_at,
            ttl_seconds=FOLLOW_UP_DEDUP_WINDOW_SECONDS,
        )
    except Exception as e:
        logger.warning(
            "Failed to persist follow-up dedup timestamp",
            extra={"patient_id": str(patient_id), "error": str(e)},
        )


async def _reserve_follow_up_message_slot_async(
    db, follow_up_service, patient_id: UUID, now
):
    """Reserve a follow-up message slot with async Redis dedup check."""
    if FOLLOW_UP_DEDUP_WINDOW_SECONDS <= 0:
        return True, "disabled"

    if not await _acquire_follow_up_lock_async(follow_up_service, patient_id):
        if follow_up_service.redis_store.is_redis_available():
            return False, "lock"
        # Redis unavailable: fallback to DB-based deduplication
        since = now - timedelta(seconds=FOLLOW_UP_DEDUP_WINDOW_SECONDS)
        last_sent_db = _get_last_follow_up_sent_at_db(db, patient_id, since)
        if last_sent_db:
            window_seconds = (now - last_sent_db).total_seconds()
            if window_seconds < FOLLOW_UP_DEDUP_WINDOW_SECONDS:
                return False, "db_fallback"
        return True, "db_fallback_allowed"

    last_sent = await _get_last_follow_up_sent_at_async(follow_up_service, patient_id)
    if last_sent:
        window_seconds = (now - last_sent).total_seconds()
        if window_seconds < FOLLOW_UP_DEDUP_WINDOW_SECONDS:
            await _release_follow_up_lock_async(follow_up_service, patient_id)
            return False, "redis"

    if not follow_up_service.redis_store.is_redis_available():
        since = now - timedelta(seconds=FOLLOW_UP_DEDUP_WINDOW_SECONDS)
        last_sent_db = _get_last_follow_up_sent_at_db(db, patient_id, since)
        if last_sent_db:
            window_seconds = (now - last_sent_db).total_seconds()
            if window_seconds < FOLLOW_UP_DEDUP_WINDOW_SECONDS:
                await _release_follow_up_lock_async(follow_up_service, patient_id)
                return False, "db"

    return True, "allowed"


async def _mark_follow_up_message_sent_async(
    db, follow_up_service, patient_id: UUID, sent_at
) -> None:
    """Mark follow-up as sent in both Redis and DB."""
    await _set_last_follow_up_sent_at_async(follow_up_service, patient_id, sent_at)
    _update_patient_last_message_sent_at(db, patient_id, sent_at)


async def _schedule_follow_up_message_async(
    db,
    follow_up_service,
    patient_id: UUID,
    content: str,
    follow_up_type: str,
    message_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Schedule a follow-up message with async dedup and eligibility checks."""
    if not content:
        return {"success": False, "error": "No message content provided"}

    now = now_sao_paulo()

    eligible, eligibility_reason = _is_follow_up_eligible(
        follow_up_service, patient_id
    )
    if not eligible:
        logger.info(
            "Skipped follow-up message due to ineligible patient/flow state",
            extra={
                "patient_id": str(patient_id),
                "follow_up_type": follow_up_type,
                "eligibility_reason": eligibility_reason,
            },
        )
        return {
            "success": True,
            "skipped": True,
            "reason": "ineligible",
            "eligibility_reason": eligibility_reason,
        }

    allowed, dedup_source = await _reserve_follow_up_message_slot_async(
        db, follow_up_service, patient_id, now
    )
    if not allowed:
        follow_up_messages_deduplicated_total.labels(
            follow_up_type, dedup_source
        ).inc()
        logger.info(
            "Skipped follow-up message due to deduplication window",
            extra={
                "patient_id": str(patient_id),
                "follow_up_type": follow_up_type,
                "dedup_source": dedup_source,
            },
        )
        return {
            "success": True,
            "skipped": True,
            "reason": "deduplicated",
            "dedup_source": dedup_source,
        }

    try:
        from app.domain.messaging.core import MessageService
        from app.models.message import MessageType

        message_service = MessageService(db)
        message = message_service.schedule_message(
            patient_id=patient_id,
            content=content,
            scheduled_for=now,
            message_type=MessageType.TEXT,
            message_metadata=message_metadata,
        )

        await _mark_follow_up_message_sent_async(db, follow_up_service, patient_id, now)
        follow_up_messages_sent_total.labels(follow_up_type).inc()

        return {
            "success": True,
            "message_id": str(message.id),
            "type": follow_up_type,
        }

    except Exception as e:
        logger.error(
            "Failed to schedule follow-up message",
            exc_info=True,
            extra={
                "patient_id": str(patient_id),
                "follow_up_type": follow_up_type,
                "error": str(e),
            },
        )
        return {"success": False, "error": str(e)}

    finally:
        await _release_follow_up_lock_async(follow_up_service, patient_id)


# ===========================================================================
# Follow-up action executors (async versions)
# ===========================================================================

async def _execute_follow_up_action_async(
    db, follow_up_service, action
) -> Dict[str, Any]:
    """Execute a single follow-up action based on its type (async)."""
    from app.services.follow_up_system.enums import FollowUpType

    try:
        action_type = action.follow_up_type
        patient_id = action.patient_id
        params = action.parameters

        if action_type == FollowUpType.EMPATHETIC_RESPONSE:
            return await _send_empathetic_response_async(
                db, follow_up_service, patient_id, params
            )
        elif action_type == FollowUpType.MEDICAL_CLARIFICATION:
            return await _send_medical_clarification_async(
                db, follow_up_service, patient_id, params
            )
        elif action_type == FollowUpType.ESCALATION_NOTIFICATION:
            return await _send_escalation_notification_async(db, patient_id, params)
        elif action_type == FollowUpType.PROVIDER_ALERT:
            return await _send_provider_alert_async(db, patient_id, params)
        elif action_type == FollowUpType.CONVERSATION_CONTINUATION:
            return await _send_conversation_continuation_async(
                db, follow_up_service, patient_id, params
            )
        else:
            logger.warning("Unhandled follow-up type: %s", action_type)
            return {
                "success": True,
                "skipped": True,
                "reason": f"Unhandled action type: {action_type}",
            }

    except Exception as e:
        logger.error("Error executing follow-up action: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def _send_empathetic_response_async(
    db, follow_up_service, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send empathetic response message to patient (async)."""
    try:
        content = params.get("message_content", "")
        return await _schedule_follow_up_message_async(
            db,
            follow_up_service,
            patient_id,
            content,
            "empathetic_response",
            {"follow_up_type": "empathetic_response"},
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _send_medical_clarification_async(
    db, follow_up_service, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send medical clarification request to patient (async)."""
    try:
        content = params.get("message_content", "")
        return await _schedule_follow_up_message_async(
            db,
            follow_up_service,
            patient_id,
            content,
            "medical_clarification",
            {"follow_up_type": "medical_clarification"},
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _send_escalation_notification_async(
    db, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send escalation notification to healthcare provider (async).

    Cross-dispatches to alerts_taskiq.process_alert_notification.
    """
    try:
        from app.repositories.patient import PatientRepository
        from app.tasks.alerts_taskiq import process_alert_notification

        patient_repo = PatientRepository(db)
        patient = patient_repo.get_by_id(patient_id)

        if not patient:
            return {"success": False, "error": f"Patient {patient_id} not found"}

        alert_data = {
            "patient_id": str(patient_id),
            "doctor_id": str(patient.doctor_id) if patient.doctor_id else None,
            "escalation_level": params.get("escalation_level", "medium"),
            "concern_type": params.get("concern_type", "general"),
            "description": params.get("description", "Follow-up escalation"),
            "original_message": params.get("original_message", ""),
        }

        # Cross-dispatch to alerts_taskiq via .kiq()
        await process_alert_notification.kiq(alert_data)

        return {
            "success": True,
            "type": "escalation_notification",
            "alert_queued": True,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def _send_provider_alert_async(
    db, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send alert to healthcare provider (async).

    Cross-dispatches to alerts_taskiq.process_alert_notification.
    """
    try:
        from app.repositories.patient import PatientRepository
        from app.tasks.alerts_taskiq import process_alert_notification

        patient_repo = PatientRepository(db)
        patient = patient_repo.get_by_id(patient_id)

        if not patient:
            return {"success": False, "error": f"Patient {patient_id} not found"}

        alert_data = {
            "patient_id": str(patient_id),
            "doctor_id": str(patient.doctor_id) if patient.doctor_id else None,
            "alert_type": "provider_alert",
            "priority": params.get("priority", "medium"),
            "message": params.get("alert_message", "Provider attention required"),
        }

        await process_alert_notification.kiq(alert_data)

        return {"success": True, "type": "provider_alert", "alert_queued": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def _send_conversation_continuation_async(
    db, follow_up_service, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send conversation continuation message to patient (async)."""
    try:
        content = params.get("message_content", "")
        return await _schedule_follow_up_message_async(
            db,
            follow_up_service,
            patient_id,
            content,
            "conversation_continuation",
            {"follow_up_type": "conversation_continuation"},
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


# ===========================================================================
# 1. execute_pending_follow_ups — periodic (interval 300s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 300}}],
)
async def execute_pending_follow_ups() -> Dict[str, Any]:
    """Execute all pending follow-up actions.

    Core follow-up processor running every 5 minutes. Processes scheduled
    follow-up actions that are due, with Redis state hydration and
    Prometheus metrics tracking.

    Returns:
        Dict with execution results (executed/failed/skipped counts).
    """
    start_time = log_task_start("execute_pending_follow_ups")

    try:
        with get_scoped_session() as db:
            from app.services.follow_up_system.service import FollowUpSystemService

            follow_up_service = FollowUpSystemService(db)
            now = now_sao_paulo()
            executed_count = 0
            failed_count = 0
            skipped_count = 0
            errors = []

            # Rehydrate state from Redis
            try:
                await follow_up_service.rehydrate_from_redis()
            except Exception as e:
                logger.warning("Failed to rehydrate from Redis: %s", e)

            # Get pending actions from Redis store
            try:
                pending_action_dicts = await follow_up_service.redis_store.get_pending_actions(
                    limit=100, before=now
                )
            except Exception as e:
                logger.warning("Redis get_pending_actions failed, using in-memory: %s", e)
                pending_action_dicts = []

            # Convert dicts to action tuples
            actions_to_execute = []
            if pending_action_dicts:
                for action_dict in pending_action_dicts:
                    action_id = UUID(action_dict["action_id"])
                    if action_id in follow_up_service.pending_actions:
                        action = follow_up_service.pending_actions[action_id]
                        actions_to_execute.append((action_id, action))
                    else:
                        action = follow_up_service._dict_to_follow_up_action(action_dict)
                        if action:
                            follow_up_service.pending_actions[action_id] = action
                            actions_to_execute.append((action_id, action))
            else:
                # Fallback to in-memory dict if Redis returned empty
                for action_id, action in list(follow_up_service.pending_actions.items()):
                    if action.status == "pending" and action.scheduled_for <= now:
                        actions_to_execute.append((action_id, action))

            # Sync in-memory state back to Redis after fallback usage
            if not pending_action_dicts and actions_to_execute:
                try:
                    await follow_up_service.sync_memory_to_redis()
                    logger.info("Synced in-memory actions back to Redis")
                except Exception as sync_err:
                    logger.warning("Failed to sync memory to Redis: %s", sync_err)

            logger.info(
                "Found %d pending follow-up actions to execute",
                len(actions_to_execute),
                extra={"pending_actions": len(actions_to_execute)},
            )

            for action_id, action in actions_to_execute:
                action_start = time.perf_counter()
                action_type = (
                    action.follow_up_type.value
                    if hasattr(action.follow_up_type, "value")
                    else str(action.follow_up_type)
                )
                status_label = "failed"
                try:
                    # Claim action atomically to prevent duplicate execution
                    claim_method = getattr(
                        follow_up_service.redis_store, "claim_pending_action", None
                    )
                    if claim_method and inspect.iscoroutinefunction(claim_method):
                        claimed = await claim_method(
                            action_id=action_id, in_progress_at=now_sao_paulo()
                        )
                        if not claimed:
                            skipped_count += 1
                            status_label = "skipped"
                            continue

                    # Execute the action
                    result = await _execute_follow_up_action_async(
                        db, follow_up_service, action
                    )
                    executed_at = now_sao_paulo()

                    if result.get("success"):
                        action.status = "completed"
                        action.executed_at = executed_at
                        action.execution_result = result
                        if result.get("skipped"):
                            skipped_count += 1
                            status_label = "skipped"
                        else:
                            executed_count += 1
                            status_label = "completed"

                        # Persist status update to Redis
                        try:
                            await follow_up_service.redis_store.update_action_status(
                                action_id=action_id,
                                status="completed",
                                executed_at=executed_at,
                                execution_result=result,
                            )
                        except Exception as redis_err:
                            logger.warning(
                                "Failed to persist action status to Redis: %s", redis_err
                            )

                        logger.info(
                            "Executed follow-up action %s for patient %s",
                            action_id,
                            action.patient_id,
                            extra={
                                "action_id": str(action_id),
                                "patient_id": str(action.patient_id),
                                "follow_up_type": action_type,
                                "skipped": result.get("skipped", False),
                            },
                        )
                    else:
                        action.status = "failed"
                        action.executed_at = executed_at
                        action.execution_result = result
                        failed_count += 1
                        status_label = "failed"

                        try:
                            await follow_up_service.redis_store.update_action_status(
                                action_id=action_id,
                                status="failed",
                                executed_at=executed_at,
                                execution_result=result,
                            )
                        except Exception as redis_err:
                            logger.warning(
                                "Failed to persist action status to Redis: %s", redis_err
                            )

                        errors.append(
                            {
                                "action_id": str(action_id),
                                "error": result.get("error", "Unknown error"),
                            }
                        )

                except Exception as e:
                    logger.error(
                        "Error executing follow-up action %s: %s",
                        action_id,
                        e,
                        exc_info=True,
                        extra={
                            "action_id": str(action_id),
                            "patient_id": str(action.patient_id),
                            "follow_up_type": action_type,
                        },
                    )
                    executed_at = now_sao_paulo()
                    action.status = "failed"
                    action.executed_at = executed_at
                    action.execution_result = {"success": False, "error": str(e)}
                    failed_count += 1
                    errors.append({"action_id": str(action_id), "error": str(e)})
                    try:
                        await follow_up_service.redis_store.update_action_status(
                            action_id=action_id,
                            status="failed",
                            executed_at=executed_at,
                            execution_result=action.execution_result,
                        )
                    except Exception as redis_err:
                        logger.warning(
                            "Failed to persist failed action status to Redis: %s",
                            redis_err,
                        )
                finally:
                    duration = time.perf_counter() - action_start
                    follow_up_action_duration_seconds.labels(
                        action_type, status_label
                    ).observe(duration)
                    follow_up_actions_total.labels(action_type, status_label).inc()

            # Clean up completed/failed actions older than 24 hours
            cleanup_threshold = now - timedelta(hours=24)
            cleaned_count = 0

            for action_id, action in list(follow_up_service.pending_actions.items()):
                if action.status in ["completed", "failed"]:
                    if action.executed_at and action.executed_at < cleanup_threshold:
                        del follow_up_service.pending_actions[action_id]
                        cleaned_count += 1

            result_summary = {
                "success": True,
                "executed_count": executed_count,
                "failed_count": failed_count,
                "skipped_count": skipped_count,
                "cleaned_count": cleaned_count,
                "remaining_pending": len(
                    [
                        a
                        for a in follow_up_service.pending_actions.values()
                        if a.status == "pending"
                    ]
                ),
                "errors": errors[:10] if errors else [],
                "timestamp": now.isoformat(),
            }

            follow_up_pending_actions.set(result_summary["remaining_pending"])
            log_task_success(
                "execute_pending_follow_ups",
                start_time,
                executed_count=executed_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
            )
            return result_summary

    except Exception as exc:
        log_task_error("execute_pending_follow_ups", exc, start_time)
        raise


# ===========================================================================
# 2. process_escalation_alerts — periodic (interval 600s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 600}}],
)
async def process_escalation_alerts() -> Dict[str, Any]:
    """Process and send escalation alerts to healthcare providers.

    Checks for unacknowledged alerts and escalates them according
    to the escalation policy (>30 minutes unacknowledged).

    Returns:
        Dict with processing results.
    """
    start_time = log_task_start("process_escalation_alerts")

    try:
        with get_scoped_session() as db:
            from app.services.follow_up_system.enums import EscalationLevel
            from app.services.follow_up_system.service import FollowUpSystemService

            follow_up_service = FollowUpSystemService(db)
            now = now_sao_paulo()
            processed_count = 0
            escalated_count = 0

            try:
                await follow_up_service.rehydrate_from_redis()
            except Exception as e:
                logger.warning("Failed to rehydrate alerts from Redis: %s", e)

            # Process unacknowledged alerts
            for alert_id, alert in list(follow_up_service.active_alerts.items()):
                if alert.acknowledged_at is not None:
                    continue

                alert_age = now - alert.created_at

                if alert_age > timedelta(minutes=30):
                    if alert.escalation_level == EscalationLevel.LOW:
                        alert.escalation_level = EscalationLevel.MEDIUM
                    elif alert.escalation_level == EscalationLevel.MEDIUM:
                        alert.escalation_level = EscalationLevel.HIGH
                    elif alert.escalation_level == EscalationLevel.HIGH:
                        alert.escalation_level = EscalationLevel.CRITICAL

                    escalated_count += 1
                    logger.warning(
                        "Escalated alert %s to %s for patient %s",
                        alert_id,
                        alert.escalation_level.value,
                        alert.patient_id,
                    )

                processed_count += 1

            log_task_success(
                "process_escalation_alerts",
                start_time,
                processed_count=processed_count,
                escalated_count=escalated_count,
            )
            return {
                "success": True,
                "processed_count": processed_count,
                "escalated_count": escalated_count,
                "active_alerts": len(follow_up_service.active_alerts),
                "timestamp": now.isoformat(),
            }

    except Exception as exc:
        log_task_error("process_escalation_alerts", exc, start_time)
        raise


# ===========================================================================
# 3. cleanup_old_contexts — cron daily 06:00 UTC (03:00 BRT)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=120,
    schedule=[{"cron": "0 6 * * *"}],
)
async def cleanup_old_contexts() -> Dict[str, Any]:
    """Clean up old conversation contexts to prevent memory bloat.

    Removes conversation contexts that haven't been updated in 7 days.
    Scheduled at 06:00 UTC = 03:00 BRT.

    Returns:
        Dict with cleanup results.
    """
    start_time = log_task_start("cleanup_old_contexts")

    try:
        with get_scoped_session() as db:
            from app.services.follow_up_system.service import FollowUpSystemService

            follow_up_service = FollowUpSystemService(db)

            now = now_sao_paulo()
            cleanup_threshold = now - timedelta(days=7)
            cleaned_count = 0

            for patient_id, context in list(
                follow_up_service.conversation_contexts.items()
            ):
                if context.last_updated < cleanup_threshold:
                    del follow_up_service.conversation_contexts[patient_id]
                    cleaned_count += 1

            log_task_success(
                "cleanup_old_contexts",
                start_time,
                cleaned_count=cleaned_count,
                remaining_contexts=len(follow_up_service.conversation_contexts),
            )
            return {
                "success": True,
                "cleaned_count": cleaned_count,
                "remaining_contexts": len(follow_up_service.conversation_contexts),
                "timestamp": now.isoformat(),
            }

    except Exception as exc:
        log_task_error("cleanup_old_contexts", exc, start_time)
        raise


__all__ = [
    "execute_pending_follow_ups",
    "process_escalation_alerts",
    "cleanup_old_contexts",
]
