"""
Celery tasks for quiz link resilience and reminder management.

Handles:
- Token expiry checking and regeneration
- Resilient reminder sending with retry logic
- Fallback to WhatsApp conversational flow
- Dead letter queue management
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from uuid import UUID

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.celery_app import celery_app
from app.tasks.base import BaseTask, get_db_session
from app.services.quiz_link_resilience import (
    QuizLinkResilienceService,
    FailureReason,
    CircuitBreakerState
)
from app.services.monthly_quiz_service import MonthlyQuizService
from app.services.monthly_quiz_message_integration import MonthlyQuizMessageIntegration
from app.core.monthly_quiz_config import get_monthly_quiz_config

logger = logging.getLogger(__name__)


class QuizLinkTask(BaseTask):
    """Base task class for quiz link operations."""

    autoretry_for = (Exception,)
    retry_kwargs = {
        'max_retries': 3,
        'countdown': 60
    }
    retry_backoff = True
    retry_backoff_max = 14400  # 4 hours max
    retry_jitter = True


@celery_app.task(
    bind=True,
    base=QuizLinkTask,
    name="app.tasks.quiz_link_tasks.check_expired_links"
)
def check_expired_links(self, limit: int = 100) -> Dict[str, Any]:
    """
    Periodic task to check for expired quiz links and trigger regeneration.

    Args:
        limit: Maximum number of expired links to process

    Returns:
        Dictionary with processing results
    """
    task_logger = self.get_task_logger()
    task_logger.info(f"Starting check_expired_links task (limit: {limit})")

    try:
        with get_db_session() as db:
            resilience_service = QuizLinkResilienceService(db)

            # Find expired links
            expired_links = resilience_service.check_expired_links(limit=limit)

            if not expired_links:
                task_logger.info("No expired links found")
                return self.create_success_result(
                    expired_count=0,
                    processed_count=0
                )

            # Process each expired link
            results = {
                "regenerated": [],
                "fallback": [],
                "failed": []
            }

            for link_info in expired_links:
                try:
                    # Trigger token rotation task
                    rotate_expired_token.delay(
                        session_id=str(link_info["session_id"]),
                        patient_id=str(link_info["patient_id"]),
                        quiz_template_id=str(link_info["quiz_template_id"])
                    )
                    results["regenerated"].append(str(link_info["session_id"]))

                except Exception as e:
                    task_logger.error(
                        f"Failed to process expired link for session "
                        f"{link_info['session_id']}: {e}"
                    )
                    results["failed"].append({
                        "session_id": str(link_info["session_id"]),
                        "error": str(e)
                    })

            task_logger.info(
                f"Processed {len(expired_links)} expired links: "
                f"{len(results['regenerated'])} queued for regeneration, "
                f"{len(results['failed'])} failed"
            )

            return self.create_success_result(
                expired_count=len(expired_links),
                processed_count=len(results["regenerated"]),
                results=results
            )

    except Exception as e:
        task_logger.error(f"check_expired_links task failed: {e}", exc_info=True)
        return self.create_error_result(error=str(e))


@celery_app.task(
    bind=True,
    base=QuizLinkTask,
    name="app.tasks.quiz_link_tasks.rotate_expired_token"
)
def rotate_expired_token(
    self,
    session_id: str,
    patient_id: str,
    quiz_template_id: str
) -> Dict[str, Any]:
    """
    Generate new token for expired link with fallback logic.

    Args:
        session_id: Quiz session ID
        patient_id: Patient ID
        quiz_template_id: Quiz template ID

    Returns:
        Dictionary with rotation result
    """
    task_logger = self.get_task_logger()
    task_logger.info(f"Starting rotate_expired_token for session {session_id}")

    try:
        with get_db_session() as db:
            resilience_service = QuizLinkResilienceService(db)

            # Handle expired token (regenerate or fallback)
            result = resilience_service.handle_expired_token(
                session_id=UUID(session_id),
                patient_id=UUID(patient_id),
                quiz_template_id=UUID(quiz_template_id)
            )

            action = result.get("action")

            if action == "regenerated":
                # Send new link via reminder
                send_quiz_reminder.delay(
                    session_id=session_id,
                    patient_id=patient_id,
                    token=result["new_token"],
                    is_regenerated=True
                )
                task_logger.info(f"Token regenerated for session {session_id}")

            elif action == "fallback_to_whatsapp":
                # Trigger WhatsApp conversational flow
                fallback_to_whatsapp.delay(
                    session_id=session_id,
                    patient_id=patient_id,
                    quiz_template_id=quiz_template_id
                )
                task_logger.info(f"Fallback to WhatsApp triggered for session {session_id}")

            return self.create_success_result(**result)

    except Exception as e:
        task_logger.error(f"rotate_expired_token failed: {e}", exc_info=True)

        # Track failure
        try:
            with get_db_session() as db:
                resilience_service = QuizLinkResilienceService(db)
                resilience_service.track_failure(
                    session_id=UUID(session_id),
                    reason=FailureReason.TOKEN_EXPIRED,
                    details={"error": str(e)}
                )
        except Exception as track_error:
            task_logger.error(f"Failed to track failure: {track_error}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)

        return self.create_error_result(error=str(e))


@celery_app.task(
    bind=True,
    base=QuizLinkTask,
    name="app.tasks.quiz_link_tasks.send_quiz_reminder"
)
def send_quiz_reminder(
    self,
    session_id: str,
    patient_id: str,
    token: str,
    is_regenerated: bool = False,
    retry_count: int = 0
) -> Dict[str, Any]:
    """
    Send quiz reminder with retry logic and circuit breaker pattern.

    Args:
        session_id: Quiz session ID
        patient_id: Patient ID
        token: Quiz access token
        is_regenerated: Whether this is a regenerated link
        retry_count: Current retry attempt

    Returns:
        Dictionary with reminder sending result
    """
    task_logger = self.get_task_logger()
    task_logger.info(
        f"Starting send_quiz_reminder for session {session_id} "
        f"(retry: {retry_count}/{3})"
    )

    config = get_monthly_quiz_config()

    try:
        with get_db_session() as db:
            resilience_service = QuizLinkResilienceService(db)
            message_integration = MonthlyQuizMessageIntegration(db)

            # Get session to determine delivery method
            session = resilience_service.session_repository.get(UUID(session_id))
            if not session:
                raise ValueError(f"Session {session_id} not found")

            metadata = session.session_metadata or {}
            preferred_channel = metadata.get("delivery_method", "whatsapp")

            # Check circuit breaker
            should_use_alt, alt_channel = resilience_service.should_use_alternative_channel(
                preferred_channel
            )

            delivery_channel = alt_channel if should_use_alt else preferred_channel

            # Build message
            link_url = f"{config.MONTHLY_QUIZ_BASE_URL}?token={token}"

            message_type = "regenerated_reminder" if is_regenerated else "reminder"

            if is_regenerated:
                message_text = (
                    f"Seu link do quiz mensal foi renovado! 🔄\n\n"
                    f"Acesse aqui: {link_url}\n\n"
                    f"O link anterior expirou, mas você ainda pode responder o quiz."
                )
            else:
                message_text = (
                    f"Lembrete: Seu quiz mensal está aguardando! 📋\n\n"
                    f"Acesse aqui: {link_url}\n\n"
                    f"Por favor, responda antes que o link expire."
                )

            # Send message via appropriate channel
            result = message_integration.send_quiz_link_message(
                patient_id=UUID(patient_id),
                link_url=link_url,
                custom_message=message_text,
                delivery_method=delivery_channel
            )

            if not result.get("success"):
                raise Exception(f"Failed to send message: {result.get('error')}")

            task_logger.info(
                f"Quiz reminder sent successfully for session {session_id} "
                f"via {delivery_channel}"
            )

            return self.create_success_result(
                session_id=session_id,
                delivery_channel=delivery_channel,
                used_alternative=should_use_alt
            )

    except Exception as e:
        task_logger.error(f"send_quiz_reminder failed: {e}", exc_info=True)

        # Track failure
        try:
            with get_db_session() as db:
                resilience_service = QuizLinkResilienceService(db)
                resilience_service.track_failure(
                    session_id=UUID(session_id),
                    reason=FailureReason.DELIVERY_FAILED,
                    details={
                        "error": str(e),
                        "retry_count": retry_count,
                        "channel": delivery_channel if 'delivery_channel' in locals() else "unknown"
                    }
                )
        except Exception as track_error:
            task_logger.error(f"Failed to track failure: {track_error}")

        # Retry with exponential backoff
        if retry_count < 3:  # Max 3 retries
            retry_delay = [3600, 7200, 14400][retry_count]  # 1h, 2h, 4h
            task_logger.info(
                f"Retrying send_quiz_reminder in {retry_delay}s "
                f"(attempt {retry_count + 1}/3)"
            )

            send_quiz_reminder.apply_async(
                args=(session_id, patient_id, token, is_regenerated, retry_count + 1),
                countdown=retry_delay
            )

            return self.create_success_result(
                status="retrying",
                retry_count=retry_count + 1,
                retry_delay=retry_delay
            )
        else:
            # Max retries exceeded - send to dead letter queue
            task_logger.error(
                f"Max retries exceeded for session {session_id}. "
                f"Moving to dead letter queue."
            )

            try:
                with get_db_session() as db:
                    resilience_service = QuizLinkResilienceService(db)
                    resilience_service.create_dead_letter_record(
                        session_id=UUID(session_id),
                        reason="max_retries_exceeded",
                        payload={
                            "session_id": session_id,
                            "patient_id": patient_id,
                            "token": token,
                            "is_regenerated": is_regenerated,
                            "retry_count": retry_count,
                            "error": str(e)
                        }
                    )
            except Exception as dlq_error:
                task_logger.error(f"Failed to create DLQ record: {dlq_error}")

            return self.create_error_result(
                error=str(e),
                max_retries_exceeded=True
            )


@celery_app.task(
    bind=True,
    base=QuizLinkTask,
    name="app.tasks.quiz_link_tasks.fallback_to_whatsapp"
)
def fallback_to_whatsapp(
    self,
    session_id: str,
    patient_id: str,
    quiz_template_id: str
) -> Dict[str, Any]:
    """
    Switch to WhatsApp conversational flow when link-based approach fails.

    Args:
        session_id: Quiz session ID
        patient_id: Patient ID
        quiz_template_id: Quiz template ID

    Returns:
        Dictionary with fallback result
    """
    task_logger = self.get_task_logger()
    task_logger.info(f"Starting fallback_to_whatsapp for session {session_id}")

    try:
        with get_db_session() as db:
            # Import here to avoid circular imports
            from app.services.quiz_flow_integration_service import QuizFlowIntegrationService

            flow_service = QuizFlowIntegrationService(db)

            # Initiate conversational quiz flow
            result = flow_service.initiate_monthly_quiz_flow(
                patient_id=UUID(patient_id),
                quiz_template_id=UUID(quiz_template_id)
            )

            task_logger.info(
                f"Successfully initiated WhatsApp conversational flow "
                f"for session {session_id}"
            )

            return self.create_success_result(
                session_id=session_id,
                fallback_method="whatsapp_conversational",
                flow_initiated=True,
                flow_result=result
            )

    except Exception as e:
        task_logger.error(f"fallback_to_whatsapp failed: {e}", exc_info=True)
        return self.create_error_result(error=str(e))


@celery_app.task(
    bind=True,
    base=QuizLinkTask,
    name="app.tasks.quiz_link_tasks.process_dead_letter_queue"
)
def process_dead_letter_queue(self, limit: int = 50) -> Dict[str, Any]:
    """
    Process items from dead letter queue for manual intervention.

    Args:
        limit: Maximum number of DLQ items to process

    Returns:
        Dictionary with processing results
    """
    task_logger = self.get_task_logger()
    task_logger.info(f"Starting process_dead_letter_queue (limit: {limit})")

    try:
        with get_db_session() as db:
            resilience_service = QuizLinkResilienceService(db)

            # Query sessions with DLQ records
            from app.models.quiz import QuizSession
            sessions = db.query(QuizSession).filter(
                QuizSession.session_metadata["dead_letter_queue"].astext.isnot(None)
            ).limit(limit).all()

            processed = []
            for session in sessions:
                metadata = session.session_metadata or {}
                dlq_records = metadata.get("dead_letter_queue", [])

                if dlq_records:
                    task_logger.warning(
                        f"Session {session.id} has {len(dlq_records)} DLQ records. "
                        f"Manual intervention required."
                    )
                    processed.append({
                        "session_id": str(session.id),
                        "patient_id": str(session.patient_id),
                        "dlq_count": len(dlq_records),
                        "latest_failure": dlq_records[-1] if dlq_records else None
                    })

            task_logger.info(f"Found {len(processed)} sessions with DLQ records")

            return self.create_success_result(
                dlq_sessions_count=len(processed),
                sessions_needing_intervention=processed
            )

    except Exception as e:
        task_logger.error(f"process_dead_letter_queue failed: {e}", exc_info=True)
        return self.create_error_result(error=str(e))


@celery_app.task(
    bind=True,
    base=QuizLinkTask,
    name="app.tasks.quiz_link_tasks.monitor_resilience_metrics"
)
def monitor_resilience_metrics(self) -> Dict[str, Any]:
    """
    Monitor and report resilience metrics.

    Returns:
        Dictionary with resilience metrics
    """
    task_logger = self.get_task_logger()
    task_logger.info("Starting monitor_resilience_metrics")

    try:
        with get_db_session() as db:
            resilience_service = QuizLinkResilienceService(db)

            # Calculate metrics for last 24 hours
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(hours=24)

            metrics = resilience_service.get_resilience_metrics(
                start_date=start_date,
                end_date=end_date
            )

            task_logger.info(
                f"Resilience metrics (24h): "
                f"Expiry rate: {metrics.link_expiry_rate:.2%}, "
                f"Success rate: {metrics.reminder_success_rate:.2%}, "
                f"Fallback rate: {metrics.fallback_activation_rate:.2%}"
            )

            # Alert on high failure rates
            if metrics.link_expiry_rate > 0.3:  # 30% expiry rate
                task_logger.warning(
                    f"HIGH LINK EXPIRY RATE: {metrics.link_expiry_rate:.2%}"
                )

            if metrics.reminder_success_rate < 0.7:  # 70% success threshold
                task_logger.warning(
                    f"LOW REMINDER SUCCESS RATE: {metrics.reminder_success_rate:.2%}"
                )

            return self.create_success_result(
                metrics={
                    "total_links_created": metrics.total_links_created,
                    "expired_links_count": metrics.expired_links_count,
                    "regenerated_links_count": metrics.regenerated_links_count,
                    "fallback_activations": metrics.fallback_activations,
                    "reminder_success_count": metrics.reminder_success_count,
                    "reminder_failure_count": metrics.reminder_failure_count,
                    "link_expiry_rate": metrics.link_expiry_rate,
                    "reminder_success_rate": metrics.reminder_success_rate,
                    "fallback_activation_rate": metrics.fallback_activation_rate,
                    "average_completion_time_minutes": metrics.average_completion_time_minutes,
                    "channel_health": metrics.channel_health
                }
            )

    except Exception as e:
        task_logger.error(f"monitor_resilience_metrics failed: {e}", exc_info=True)
        return self.create_error_result(error=str(e))