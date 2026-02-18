"""
Background task for executing pending follow-up actions.

This task processes pending follow-up actions from FollowUpSystemService,
ensuring that data is not lost during service restarts.

Quick Win #5 - Sprint 1
"""

import logging
import os
import time
import inspect
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from uuid import UUID

from app.tasks.base import DatabaseTask, get_db_session
from app.tasks.config import task_configs
from app.monitoring.metrics import (
    follow_up_action_duration_seconds,
    follow_up_actions_total,
    follow_up_messages_deduplicated_total,
    follow_up_messages_sent_total,
    follow_up_pending_actions,
)
from app.task_queue import task_queue as celery_app
from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo


logger = logging.getLogger(__name__)

DEFAULT_FOLLOW_UP_DEDUP_WINDOW_SECONDS = 24 * 60 * 60
DEFAULT_FOLLOW_UP_DEDUP_LOCK_SECONDS = 5 * 60


def _parse_positive_int_env(var_name: str, default: int) -> int:
    try:
        value = int(os.getenv(var_name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(value, 0)


FOLLOW_UP_DEDUP_WINDOW_SECONDS = _parse_positive_int_env(
    "FOLLOW_UP_DEDUP_WINDOW_SECONDS", DEFAULT_FOLLOW_UP_DEDUP_WINDOW_SECONDS
)
FOLLOW_UP_DEDUP_LOCK_SECONDS = _parse_positive_int_env(
    "FOLLOW_UP_DEDUP_LOCK_SECONDS", DEFAULT_FOLLOW_UP_DEDUP_LOCK_SECONDS
)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.follow_up.execute_pending_follow_ups",
    max_retries=task_configs.alerts.max_retries,
    default_retry_delay=task_configs.alerts.default_retry_delay,
    soft_time_limit=300,  # 5 minutes
    time_limit=360,  # 6 minutes hard limit
)
def execute_pending_follow_ups(self) -> Dict[str, Any]:
    """
    Execute all pending follow-up actions.

    This task should run every 5 minutes via Celery Beat to process
    any scheduled follow-up actions that are due.

    Returns:
        Dict with execution results summary
    """
    self.log_task_start()

    try:
        with get_db_session() as db:
            from asgiref.sync import async_to_sync
            from app.services.follow_up_system.service import FollowUpSystemService

            follow_up_service = FollowUpSystemService(db)

            # Get pending actions that are due
            now = now_sao_paulo()
            executed_count = 0
            failed_count = 0
            skipped_count = 0
            errors = []

            # Rehydrate state from Redis before processing
            # This ensures we have the latest persisted state after service restarts
            try:
                async_to_sync(follow_up_service.rehydrate_from_redis)()
            except Exception as e:
                logger.warning(f"Failed to rehydrate from Redis: {e}")

            # Get pending actions from Redis store (with in-memory fallback)
            # This replaces direct access to the in-memory pending_actions dict
            try:
                pending_action_dicts = async_to_sync(
                    follow_up_service.redis_store.get_pending_actions
                )(limit=100, before=now)
            except Exception as e:
                logger.warning(f"Redis get_pending_actions failed, using in-memory: {e}")
                pending_action_dicts = []

            # Convert dicts to action tuples, falling back to in-memory if Redis empty
            actions_to_execute = []
            if pending_action_dicts:
                for action_dict in pending_action_dicts:
                    action_id = UUID(action_dict["action_id"])
                    # Get from in-memory cache or reconstruct
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
                    async_to_sync(follow_up_service.sync_memory_to_redis)()
                    logger.info("Synced in-memory actions back to Redis")
                except Exception as sync_err:
                    logger.warning(f"Failed to sync memory to Redis: {sync_err}")

            logger.info(
                f"Found {len(actions_to_execute)} pending follow-up actions to execute",
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
                    # Claim action atomically (when Redis implementation supports it)
                    # to prevent duplicate execution by concurrent workers.
                    claim_method = getattr(
                        follow_up_service.redis_store, "claim_pending_action", None
                    )
                    if claim_method and inspect.iscoroutinefunction(claim_method):
                        claimed = async_to_sync(claim_method)(
                            action_id=action_id, in_progress_at=now_sao_paulo()
                        )
                        if not claimed:
                            skipped_count += 1
                            status_label = "skipped"
                            continue

                    # Execute the action based on its type
                    result = _execute_follow_up_action(db, follow_up_service, action)
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
                            async_to_sync(
                                follow_up_service.redis_store.update_action_status
                            )(
                                action_id=action_id,
                                status="completed",
                                executed_at=executed_at,
                                execution_result=result,
                            )
                        except Exception as redis_err:
                            logger.warning(f"Failed to persist action status to Redis: {redis_err}")

                        logger.info(
                            f"Executed follow-up action {action_id} "
                            f"for patient {action.patient_id}",
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

                        # Persist failed status to Redis
                        try:
                            async_to_sync(
                                follow_up_service.redis_store.update_action_status
                            )(
                                action_id=action_id,
                                status="failed",
                                executed_at=executed_at,
                                execution_result=result,
                            )
                        except Exception as redis_err:
                            logger.warning(f"Failed to persist action status to Redis: {redis_err}")

                        errors.append(
                            {
                                "action_id": str(action_id),
                                "error": result.get("error", "Unknown error"),
                            }
                        )

                except Exception as e:
                    logger.error(
                        f"Error executing follow-up action {action_id}: {e}",
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
                        async_to_sync(
                            follow_up_service.redis_store.update_action_status
                        )(
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

            result = {
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
                "errors": errors[:10] if errors else [],  # Limit to 10 errors
                "timestamp": now.isoformat(),
            }

            follow_up_pending_actions.set(result["remaining_pending"])
            self.log_task_success(result)
            return self.create_success_result(**result)

    except Exception as e:
        logger.error(f"Error in execute_pending_follow_ups task: {e}", exc_info=True)
        self.log_task_error(e)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return self.create_error_result(str(e))


def _execute_follow_up_action(db, follow_up_service, action) -> Dict[str, Any]:
    """
    Execute a single follow-up action based on its type.

    Args:
        db: Database session
        follow_up_service: FollowUpSystemService instance
        action: FollowUpAction to execute

    Returns:
        Dict with execution result
    """
    from app.services.follow_up_system.enums import FollowUpType

    try:
        action_type = action.follow_up_type
        patient_id = action.patient_id
        params = action.parameters

        if action_type == FollowUpType.EMPATHETIC_RESPONSE:
            return _send_empathetic_response(db, follow_up_service, patient_id, params)

        elif action_type == FollowUpType.MEDICAL_CLARIFICATION:
            return _send_medical_clarification(db, follow_up_service, patient_id, params)

        elif action_type == FollowUpType.ESCALATION_NOTIFICATION:
            return _send_escalation_notification(db, patient_id, params)

        elif action_type == FollowUpType.PROVIDER_ALERT:
            return _send_provider_alert(db, patient_id, params)

        elif action_type == FollowUpType.CONVERSATION_CONTINUATION:
            return _send_conversation_continuation(
                db, follow_up_service, patient_id, params
            )

        else:
            logger.warning(f"Unhandled follow-up type: {action_type}")
            return {
                "success": True,
                "skipped": True,
                "reason": f"Unhandled action type: {action_type}",
            }

    except Exception as e:
        logger.error(f"Error executing follow-up action: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _get_last_follow_up_sent_at_db(
    db, patient_id: UUID, since: datetime
) -> Optional[datetime]:
    from app.repositories.patient import PatientRepository
    from app.repositories.message import MessageRepository

    patient_repo = PatientRepository(db)
    patient = patient_repo.get_by_id(patient_id)
    if patient:
        patient_data = patient.patient_data or {}
        last_sent_str = patient_data.get("last_message_sent_at")
        if last_sent_str:
            try:
                parsed = datetime.fromisoformat(last_sent_str)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=SAO_PAULO_TZ)
                if parsed >= since:
                    return parsed
            except ValueError:
                logger.warning(
                    "Invalid last_message_sent_at format on patient data",
                    extra={"patient_id": str(patient_id)},
                )

    message_repo = MessageRepository(db)
    return message_repo.get_recent_follow_up_message_time(patient_id, since)


def _is_follow_up_eligible(follow_up_service, patient_id: UUID) -> Tuple[bool, str]:
    from app.models.enums import FlowState

    patient = follow_up_service.patient_repo.get_by_id(patient_id)
    if not patient:
        return False, "patient_not_found"

    if getattr(patient, "deleted_at", None):
        return False, "patient_deleted"

    flow_state_value = (
        patient.flow_state.value
        if hasattr(patient.flow_state, "value")
        else str(patient.flow_state).lower()
        if patient.flow_state
        else None
    )
    if flow_state_value != FlowState.ACTIVE.value:
        return False, f"patient_flow_state_{flow_state_value or 'unknown'}"

    flow_state = follow_up_service.flow_state_repo.get_active_flow(patient_id)
    if not flow_state:
        return False, "no_active_flow"

    flow_status = (flow_state.status or "").lower()
    if flow_status in {"paused", "completed", "cancelled", "inactive"}:
        return False, f"flow_status_{flow_status}"

    return True, "eligible"


def _update_patient_last_message_sent_at(
    db, patient_id: UUID, sent_at: datetime
) -> bool:
    from app.repositories.patient import PatientRepository

    patient_repo = PatientRepository(db)
    patient = patient_repo.get_by_id(patient_id)
    if not patient:
        logger.warning(
            "Unable to update last_message_sent_at; patient not found",
            extra={"patient_id": str(patient_id)},
        )
        return False

    patient_data = dict(patient.patient_data or {})
    patient_data["last_message_sent_at"] = sent_at.isoformat()
    patient_repo.update(patient, {"patient_data": patient_data})
    return True


def _acquire_follow_up_lock(follow_up_service, patient_id: UUID) -> bool:
    from asgiref.sync import async_to_sync

    return async_to_sync(
        follow_up_service.redis_store.acquire_follow_up_lock
    )(patient_id=patient_id, ttl_seconds=FOLLOW_UP_DEDUP_LOCK_SECONDS)


def _release_follow_up_lock(follow_up_service, patient_id: UUID) -> None:
    from asgiref.sync import async_to_sync

    if not follow_up_service.redis_store.is_redis_available():
        return

    try:
        async_to_sync(
            follow_up_service.redis_store.release_follow_up_lock
        )(patient_id=patient_id)
    except Exception as e:
        logger.warning(
            "Failed to release follow-up lock",
            extra={"patient_id": str(patient_id), "error": str(e)},
        )


def _get_last_follow_up_sent_at(
    follow_up_service, patient_id: UUID
) -> Optional[datetime]:
    from asgiref.sync import async_to_sync

    try:
        return async_to_sync(
            follow_up_service.redis_store.get_last_follow_up_sent_at
        )(patient_id)
    except Exception as e:
        logger.warning(
            "Failed to fetch follow-up dedup timestamp",
            extra={"patient_id": str(patient_id), "error": str(e)},
        )
        return None


def _set_last_follow_up_sent_at(
    follow_up_service, patient_id: UUID, sent_at: datetime
) -> None:
    from asgiref.sync import async_to_sync

    try:
        async_to_sync(
            follow_up_service.redis_store.set_last_follow_up_sent_at
        )(
            patient_id=patient_id,
            sent_at=sent_at,
            ttl_seconds=FOLLOW_UP_DEDUP_WINDOW_SECONDS,
        )
    except Exception as e:
        logger.warning(
            "Failed to persist follow-up dedup timestamp",
            extra={"patient_id": str(patient_id), "error": str(e)},
        )


def _reserve_follow_up_message_slot(
    db, follow_up_service, patient_id: UUID, now: datetime
) -> Tuple[bool, str]:
    if FOLLOW_UP_DEDUP_WINDOW_SECONDS <= 0:
        return True, "disabled"

    if not _acquire_follow_up_lock(follow_up_service, patient_id):
        if follow_up_service.redis_store.is_redis_available():
            return False, "lock"
        # Redis unavailable: fallback to DB-based deduplication instead of dropping follow-up.
        since = now - timedelta(seconds=FOLLOW_UP_DEDUP_WINDOW_SECONDS)
        last_sent_db = _get_last_follow_up_sent_at_db(db, patient_id, since)
        if last_sent_db:
            window_seconds = (now - last_sent_db).total_seconds()
            if window_seconds < FOLLOW_UP_DEDUP_WINDOW_SECONDS:
                return False, "db_fallback"
        return True, "db_fallback_allowed"

    last_sent = _get_last_follow_up_sent_at(follow_up_service, patient_id)
    if last_sent:
        window_seconds = (now - last_sent).total_seconds()
        if window_seconds < FOLLOW_UP_DEDUP_WINDOW_SECONDS:
            _release_follow_up_lock(follow_up_service, patient_id)
            return False, "redis"

    if not follow_up_service.redis_store.is_redis_available():
        since = now - timedelta(seconds=FOLLOW_UP_DEDUP_WINDOW_SECONDS)
        last_sent_db = _get_last_follow_up_sent_at_db(db, patient_id, since)
        if last_sent_db:
            window_seconds = (now - last_sent_db).total_seconds()
            if window_seconds < FOLLOW_UP_DEDUP_WINDOW_SECONDS:
                _release_follow_up_lock(follow_up_service, patient_id)
                return False, "db"

    return True, "allowed"


def _mark_follow_up_message_sent(
    db, follow_up_service, patient_id: UUID, sent_at: datetime
) -> None:
    _set_last_follow_up_sent_at(follow_up_service, patient_id, sent_at)
    _update_patient_last_message_sent_at(db, patient_id, sent_at)


def _schedule_follow_up_message(
    db,
    follow_up_service,
    patient_id: UUID,
    content: str,
    follow_up_type: str,
    message_metadata: Dict[str, Any],
) -> Dict[str, Any]:
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

    allowed, dedup_source = _reserve_follow_up_message_slot(
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

        _mark_follow_up_message_sent(db, follow_up_service, patient_id, now)
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
        _release_follow_up_lock(follow_up_service, patient_id)


def _send_empathetic_response(
    db, follow_up_service, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send empathetic response message to patient."""
    try:
        content = params.get("message_content", "")
        return _schedule_follow_up_message(
            db,
            follow_up_service,
            patient_id,
            content,
            "empathetic_response",
            {"follow_up_type": "empathetic_response"},
        )

    except Exception as e:
        return {"success": False, "error": str(e)}


def _send_medical_clarification(
    db, follow_up_service, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send medical clarification request to patient."""
    try:
        content = params.get("message_content", "")
        return _schedule_follow_up_message(
            db,
            follow_up_service,
            patient_id,
            content,
            "medical_clarification",
            {"follow_up_type": "medical_clarification"},
        )

    except Exception as e:
        return {"success": False, "error": str(e)}


def _send_escalation_notification(
    db, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send escalation notification to healthcare provider."""
    try:
        from app.repositories.patient import PatientRepository
        from app.tasks.alerts import process_alert_notification

        patient_repo = PatientRepository(db)
        patient = patient_repo.get_by_id(patient_id)

        if not patient:
            return {"success": False, "error": f"Patient {patient_id} not found"}

        # Queue alert notification task
        alert_data = {
            "patient_id": str(patient_id),
            "doctor_id": str(patient.doctor_id) if patient.doctor_id else None,
            "escalation_level": params.get("escalation_level", "medium"),
            "concern_type": params.get("concern_type", "general"),
            "description": params.get("description", "Follow-up escalation"),
            "original_message": params.get("original_message", ""),
        }

        # Queue the alert notification
        process_alert_notification.delay(alert_data)

        return {
            "success": True,
            "type": "escalation_notification",
            "alert_queued": True,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def _send_provider_alert(
    db, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send alert to healthcare provider."""
    try:
        from app.repositories.patient import PatientRepository
        from app.tasks.alerts import process_alert_notification

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

        process_alert_notification.delay(alert_data)

        return {"success": True, "type": "provider_alert", "alert_queued": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _send_conversation_continuation(
    db, follow_up_service, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send conversation continuation message to patient."""
    try:
        content = params.get("message_content", "")
        return _schedule_follow_up_message(
            db,
            follow_up_service,
            patient_id,
            content,
            "conversation_continuation",
            {"follow_up_type": "conversation_continuation"},
        )

    except Exception as e:
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.follow_up.process_escalation_alerts",
    max_retries=3,
    default_retry_delay=60,
)
def process_escalation_alerts(self) -> Dict[str, Any]:
    """
    Process and send escalation alerts to healthcare providers.

    This task checks for unacknowledged alerts and escalates them
    according to the escalation policy.

    Returns:
        Dict with processing results
    """
    self.log_task_start()

    try:
        with get_db_session() as db:
            from app.services.follow_up_system.service import FollowUpSystemService
            from app.services.follow_up_system.enums import EscalationLevel
            from asgiref.sync import async_to_sync

            follow_up_service = FollowUpSystemService(db)

            now = now_sao_paulo()
            processed_count = 0
            escalated_count = 0

            try:
                async_to_sync(follow_up_service.rehydrate_from_redis)()
            except Exception as e:
                logger.warning(f"Failed to rehydrate alerts from Redis: {e}")

            # Process unacknowledged alerts
            for alert_id, alert in list(follow_up_service.active_alerts.items()):
                if alert.acknowledged_at is not None:
                    continue

                # Check if alert needs escalation (unacknowledged for > 30 minutes)
                alert_age = now - alert.created_at

                if alert_age > timedelta(minutes=30):
                    # Escalate the alert
                    if alert.escalation_level == EscalationLevel.LOW:
                        alert.escalation_level = EscalationLevel.MEDIUM
                    elif alert.escalation_level == EscalationLevel.MEDIUM:
                        alert.escalation_level = EscalationLevel.HIGH
                    elif alert.escalation_level == EscalationLevel.HIGH:
                        alert.escalation_level = EscalationLevel.CRITICAL

                    escalated_count += 1
                    logger.warning(
                        f"Escalated alert {alert_id} to {alert.escalation_level.value} "
                        f"for patient {alert.patient_id}"
                    )

                processed_count += 1

            result = {
                "processed_count": processed_count,
                "escalated_count": escalated_count,
                "active_alerts": len(follow_up_service.active_alerts),
                "timestamp": now.isoformat(),
            }

            self.log_task_success(result)
            return self.create_success_result(**result)

    except Exception as e:
        logger.error(f"Error in process_escalation_alerts task: {e}", exc_info=True)
        self.log_task_error(e)
        return self.create_error_result(str(e))


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.follow_up.cleanup_old_contexts",
    max_retries=2,
    default_retry_delay=120,
)
def cleanup_old_contexts(self) -> Dict[str, Any]:
    """
    Clean up old conversation contexts to prevent memory bloat.

    Removes conversation contexts that haven't been updated in 7 days.

    Returns:
        Dict with cleanup results
    """
    self.log_task_start()

    try:
        with get_db_session() as db:
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

            result = {
                "cleaned_count": cleaned_count,
                "remaining_contexts": len(follow_up_service.conversation_contexts),
                "timestamp": now.isoformat(),
            }

            self.log_task_success(result)
            return self.create_success_result(**result)

    except Exception as e:
        logger.error(f"Error in cleanup_old_contexts task: {e}", exc_info=True)
        self.log_task_error(e)
        return self.create_error_result(str(e))


# Celery Beat schedule entry (add to celery_config.py):
# "execute-pending-follow-ups": {
#     "task": "tasks.follow_up.execute_pending_follow_ups",
#     "schedule": crontab(minute="*/5"),  # Every 5 minutes
#     "options": {"queue": "follow_up"}
# },
# "process-escalation-alerts": {
#     "task": "tasks.follow_up.process_escalation_alerts",
#     "schedule": crontab(minute="*/10"),  # Every 10 minutes
#     "options": {"queue": "follow_up"}
# },
# "cleanup-old-contexts": {
#     "task": "tasks.follow_up.cleanup_old_contexts",
#     "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
#     "options": {"queue": "follow_up"}
# },
