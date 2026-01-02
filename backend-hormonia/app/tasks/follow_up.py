"""
Celery task for executing pending follow-up actions.

This task processes pending follow-up actions from FollowUpSystemService,
ensuring that data is not lost during service restarts.

Quick Win #5 - Sprint 1
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from uuid import UUID

from celery import shared_task

from app.tasks.base import DatabaseTask, get_db_session
from app.tasks.config import task_configs


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    base=DatabaseTask,
    name="tasks.follow_up.execute_pending_follow_ups",
    max_retries=task_configs.alerts.max_retries,
    default_retry_delay=task_configs.alerts.default_retry_delay,
    soft_time_limit=300,  # 5 minutes
    time_limit=360,  # 6 minutes hard limit
    queue="follow_up",
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
            now = datetime.now(timezone.utc)
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
                f"Found {len(actions_to_execute)} pending follow-up actions to execute"
            )

            for action_id, action in actions_to_execute:
                try:
                    # Execute the action based on its type
                    result = _execute_follow_up_action(db, follow_up_service, action)
                    executed_at = datetime.now(timezone.utc)

                    if result.get("success"):
                        action.status = "completed"
                        action.executed_at = executed_at
                        action.execution_result = result
                        executed_count += 1

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
                            f"for patient {action.patient_id}"
                        )
                    else:
                        action.status = "failed"
                        action.executed_at = executed_at
                        action.execution_result = result
                        failed_count += 1

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
                    )
                    failed_count += 1
                    errors.append({"action_id": str(action_id), "error": str(e)})

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
            return _send_empathetic_response(db, patient_id, params)

        elif action_type == FollowUpType.MEDICAL_CLARIFICATION:
            return _send_medical_clarification(db, patient_id, params)

        elif action_type == FollowUpType.ESCALATION_NOTIFICATION:
            return _send_escalation_notification(db, patient_id, params)

        elif action_type == FollowUpType.PROVIDER_ALERT:
            return _send_provider_alert(db, patient_id, params)

        elif action_type == FollowUpType.CONVERSATION_CONTINUATION:
            return _send_conversation_continuation(db, patient_id, params)

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


def _send_empathetic_response(
    db, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send empathetic response message to patient."""
    try:
        from app.domain.messaging.core import MessageService
        from app.models.message import MessageType

        content = params.get("message_content", "")
        if not content:
            return {"success": False, "error": "No message content provided"}

        message_service = MessageService(db)
        message = message_service.schedule_message(
            patient_id=patient_id,
            content=content,
            scheduled_for=datetime.now(timezone.utc),
            message_type=MessageType.TEXT,
            message_metadata={"follow_up_type": "empathetic_response"},
        )

        return {
            "success": True,
            "message_id": str(message.id),
            "type": "empathetic_response",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def _send_medical_clarification(
    db, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send medical clarification request to patient."""
    try:
        from app.domain.messaging.core import MessageService
        from app.models.message import MessageType

        content = params.get("message_content", "")
        if not content:
            return {"success": False, "error": "No message content provided"}

        message_service = MessageService(db)
        message = message_service.schedule_message(
            patient_id=patient_id,
            content=content,
            scheduled_for=datetime.now(timezone.utc),
            message_type=MessageType.TEXT,
            message_metadata={"follow_up_type": "medical_clarification"},
        )

        return {
            "success": True,
            "message_id": str(message.id),
            "type": "medical_clarification",
        }

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
            "patient_name": patient.name,
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
            "patient_name": patient.name,
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
    db, patient_id: UUID, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Send conversation continuation message to patient."""
    try:
        from app.domain.messaging.core import MessageService
        from app.models.message import MessageType

        content = params.get("message_content", "")
        if not content:
            return {"success": False, "error": "No message content provided"}

        message_service = MessageService(db)
        message = message_service.schedule_message(
            patient_id=patient_id,
            content=content,
            scheduled_for=datetime.now(timezone.utc),
            message_type=MessageType.TEXT,
            message_metadata={"follow_up_type": "conversation_continuation"},
        )

        return {
            "success": True,
            "message_id": str(message.id),
            "type": "conversation_continuation",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@shared_task(
    bind=True,
    base=DatabaseTask,
    name="tasks.follow_up.process_escalation_alerts",
    max_retries=3,
    default_retry_delay=60,
    queue="follow_up",
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

            follow_up_service = FollowUpSystemService(db)

            now = datetime.now(timezone.utc)
            processed_count = 0
            escalated_count = 0

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


@shared_task(
    bind=True,
    base=DatabaseTask,
    name="tasks.follow_up.cleanup_old_contexts",
    max_retries=2,
    default_retry_delay=120,
    queue="follow_up",
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

            now = datetime.now(timezone.utc)
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
