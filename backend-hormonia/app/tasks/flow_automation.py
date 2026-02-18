"""
Flow Automation Tasks
Background tasks for automatic flow management and patient engagement
"""

from typing import Optional
import logging
from datetime import datetime
from asgiref.sync import async_to_sync
from sqlalchemy import text, select
from sqlalchemy.exc import SQLAlchemyError
from app.models.template import MessageTemplate

from app.tasks.base import get_db_session
from app.task_queue import task_queue as celery_app
from app.services.enhanced_flow_engine import get_enhanced_flow_engine
from app.services.flow.sequential_message_handler import SequentialMessageHandler
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.config.settings.tasks import (
    FLOW_MAX_RETRIES,
    FLOW_RETRY_DELAY,
    TASK_TIME_LIMIT,
    TASK_SOFT_TIME_LIMIT,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


_FLOW_AUTOMATION_TASK_OPTIONS = {
    "max_retries": FLOW_MAX_RETRIES,
    "default_retry_delay": FLOW_RETRY_DELAY,
    "autoretry_for": (SQLAlchemyError, ConnectionError, TimeoutError, OSError),
    "retry_backoff": FLOW_RETRY_DELAY,
    "retry_backoff_max": max(FLOW_RETRY_DELAY * 8, FLOW_RETRY_DELAY),
    "retry_jitter": True,
    "time_limit": TASK_TIME_LIMIT,
    "soft_time_limit": TASK_SOFT_TIME_LIMIT,
}


@celery_app.task(
    name="app.tasks.flow_automation.check_and_start_pending_flows",
    **_FLOW_AUTOMATION_TASK_OPTIONS,
)
def check_and_start_pending_flows() -> dict:
    """
    Check for patients without active flows and start them automatically.
    This task should be scheduled to run every 15 minutes via Celery Beat.

    Returns:
        dict: Summary of flows started
    """

    async def _process():
        flows_started = 0
        errors = []

        with get_db_session() as db:
            try:
                # Query for patients without active flows
                query = text("""
                    SELECT p.*
                    FROM patients p
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM patient_flow_states pfs
                        WHERE pfs.patient_id = p.id
                          AND pfs.status IN ('active', 'scheduled', 'in_progress')
                    )
                        AND p.created_at > NOW() - INTERVAL '7 days'
                        AND p.flow_state = 'active'
                        AND p.deleted_at IS NULL
                    LIMIT 50
                    FOR UPDATE SKIP LOCKED
                """)

                result = db.execute(query)
                patients_without_flow = result.fetchall()

                logger.info(
                    f"Found {len(patients_without_flow)} patients without active flows"
                )

                flow_engine = get_enhanced_flow_engine(db)

                for patient_row in patients_without_flow:
                    try:
                        # Determine appropriate template based on patient data
                        template_name = _determine_template_for_patient(patient_row)

                        if template_name:
                            # Start the flow
                            # Enhanced engine uses enroll_patient instead of start_flow
                            await flow_engine.enroll_patient(
                                patient_id=patient_row.id, flow_type=template_name
                            )

                            flows_started += 1
                            logger.info(
                                f"Started automatic flow '{template_name}' "
                                f"for patient_id={patient_row.id}"
                            )
                        else:
                            logger.warning(
                                f"Could not determine template for "
                                f"patient_id={patient_row.id}"
                            )

                    except Exception as e:
                        error_msg = f"Failed to start flow for patient {patient_row.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        db.rollback()

            except Exception:
                logger.exception("Error querying patients without flows")
                raise

        return {
            "flows_started": flows_started,
            "errors": errors,
            "timestamp": now_sao_paulo().isoformat(),
        }

    # Run async function (async_to_sync for Celery compatibility)
    return async_to_sync(_process)()


@celery_app.task(
    name="app.tasks.flow_automation.send_daily_reminders",
    **_FLOW_AUTOMATION_TASK_OPTIONS,
)
def send_daily_reminders() -> dict:
    """
    Send daily reminders to patients with pending quizzes or messages.
    This task should be scheduled to run daily at 9 AM via Celery Beat.

    Returns:
        dict: Summary of reminders sent
    """

    async def _process():
        reminders_sent = 0
        errors = []

        with get_db_session() as db:
            try:
                # Fetch reminder template
                template_query = select(MessageTemplate).where(
                    MessageTemplate.name == "daily_reminder_generic",
                    MessageTemplate.is_active,
                )
                template_result = db.execute(template_query)
                template = template_result.scalar_one_or_none()

                # Query for patients with pending quiz sessions
                query = text("""
                    SELECT DISTINCT p.*, qs.id as session_id, qs.session_metadata
                    FROM patients p
                    INNER JOIN quiz_sessions qs
                        ON p.id = qs.patient_id
                    WHERE qs.status = 'in_progress'
                        AND qs.created_at < NOW() - INTERVAL '24 hours'
                        AND qs.created_at > NOW() - INTERVAL '7 days'
                        AND p.flow_state = 'active'
                        AND p.deleted_at IS NULL
                    LIMIT 100
                """)

                result = db.execute(query)
                patients_with_pending_quiz = result.fetchall()

                logger.info(
                    f"Found {len(patients_with_pending_quiz)} patients with pending quizzes"
                )

                # Send reminders
                from app.tasks.messaging import send_scheduled_message
                from app.models.message import (
                    Message,
                    MessageType,
                    MessageDirection,
                    MessageStatus,
                )

                for patient_row in patients_with_pending_quiz:
                    try:
                        # Send reminder message
                        if template:
                            try:
                                reminder_content = template.content.format(
                                    patient_name=patient_row.name
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to format template: {e}. Using fallback."
                                )
                                reminder_content = _get_reminder_message(
                                    patient_row.name
                                )
                        else:
                            reminder_content = _get_reminder_message(patient_row.name)

                        session_metadata = dict(patient_row.session_metadata or {})
                        last_daily_reminder_raw = session_metadata.get(
                            "last_daily_reminder_sent_at"
                        )
                        if isinstance(last_daily_reminder_raw, str):
                            try:
                                last_daily_reminder = datetime.fromisoformat(
                                    last_daily_reminder_raw
                                )
                                if last_daily_reminder.tzinfo is None:
                                    last_daily_reminder = last_daily_reminder.replace(
                                        tzinfo=now_sao_paulo().tzinfo
                                    )
                                if (
                                    now_sao_paulo() - last_daily_reminder
                                ).total_seconds() < 20 * 3600:
                                    continue
                            except ValueError:
                                pass

                        # Create message object required by Unified Service
                        message = Message(
                            patient_id=patient_row.id,
                            direction=MessageDirection.OUTBOUND,
                            type=MessageType.TEXT,
                            content=reminder_content,
                            status=MessageStatus.PENDING,
                            message_metadata={
                                "source": "automation_reminder",
                                "quiz_session_id": str(patient_row.session_id),
                            },
                        )
                        db.add(message)
                        db.commit()
                        db.refresh(message)

                        db.execute(
                            text(
                                """
                                UPDATE quiz_sessions
                                SET session_metadata = jsonb_set(
                                    COALESCE(session_metadata, '{}'::jsonb),
                                    '{last_daily_reminder_sent_at}',
                                    to_jsonb(:sent_at::text),
                                    true
                                )
                                WHERE id = :session_id
                                """
                            ),
                            {
                                "session_id": patient_row.session_id,
                                "sent_at": now_sao_paulo().isoformat(),
                            },
                        )
                        db.commit()

                        send_scheduled_message.delay(str(message.id))

                        reminders_sent += 1
                        logger.info(
                            f"Sent reminder to patient_id={patient_row.id}"
                        )

                    except Exception as e:
                        error_msg = f"Failed to send reminder to patient {patient_row.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        db.rollback()

            except Exception:
                logger.exception("Error querying patients with pending quizzes")
                raise

        return {
            "reminders_sent": reminders_sent,
            "errors": errors,
            "timestamp": now_sao_paulo().isoformat(),
        }

    # Run async function (async_to_sync for Celery compatibility)
    return async_to_sync(_process)()


@celery_app.task(
    name="app.tasks.flow_automation.resume_paused_flows",
    **_FLOW_AUTOMATION_TASK_OPTIONS,
)
def resume_paused_flows() -> dict:
    """
    Check for flows that were paused and should be resumed.
    This task should run every 6 hours via Celery Beat.

    Returns:
        dict: Summary of flows resumed
    """

    async def _process():
        flows_resumed = 0
        errors = []

        with get_db_session() as db:
            try:
                # Query for paused flows that should be resumed
                query = text("""
                    SELECT pfs.*
                    FROM patient_flow_states pfs
                    INNER JOIN patients p ON pfs.patient_id = p.id
                    WHERE pfs.status = 'paused'
                        AND pfs.updated_at < NOW() - INTERVAL '48 hours'
                        AND p.flow_state = 'active'
                        AND p.deleted_at IS NULL
                    LIMIT 50
                    FOR UPDATE OF pfs SKIP LOCKED
                """)

                result = db.execute(query)
                paused_flows = result.fetchall()

                logger.info(
                    f"Found {len(paused_flows)} paused flows to potentially resume"
                )

                flow_engine = get_enhanced_flow_engine(db)

                for flow_row in paused_flows:
                    try:
                        # Resume the flow
                        await flow_engine.resume_patient_flow(flow_row.id)

                        flows_resumed += 1
                        logger.info(
                            f"Resumed flow {flow_row.id} for patient {flow_row.patient_id}"
                        )

                    except Exception as e:
                        error_msg = f"Failed to resume flow {flow_row.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        db.rollback()

            except Exception:
                logger.exception("Error querying paused flows")
                raise

        return {
            "flows_resumed": flows_resumed,
            "errors": errors,
            "timestamp": now_sao_paulo().isoformat(),
        }

    # Run async function (async_to_sync for Celery compatibility)
    return async_to_sync(_process)()


@celery_app.task(
    name="app.tasks.flow_automation.cleanup_expired_quiz_links",
    **_FLOW_AUTOMATION_TASK_OPTIONS,
)
def cleanup_expired_quiz_links() -> dict:
    """
    Clean up expired quiz links and update their status.
    This task should run daily via Celery Beat.

    Returns:
        dict: Summary of links cleaned
    """

    async def _process():
        links_cleaned = 0
        errors = []

        with get_db_session() as db:
            try:
                # Update expired quiz sessions
                query = text("""
                    UPDATE quiz_sessions
                    SET status = 'expired',
                        session_metadata = jsonb_set(
                            COALESCE(session_metadata, '{}'::jsonb),
                            '{link_status}',
                            '"expired"'
                        )
                    WHERE status = 'in_progress'
                        AND session_metadata->>'expires_at' IS NOT NULL
                        AND session_metadata->>'expires_at' ~ '^\\d{4}-\\d{2}-\\d{2}T'
                        AND (session_metadata->>'expires_at')::timestamp < NOW()
                    RETURNING id
                """)

                result = db.execute(query)
                expired_sessions = result.fetchall()
                links_cleaned = len(expired_sessions)

                db.commit()

                logger.info(f"Cleaned up {links_cleaned} expired quiz links")

            except Exception:
                db.rollback()
                logger.exception("Error cleaning up expired quiz links")
                raise

        return {
            "links_cleaned": links_cleaned,
            "errors": errors,
            "timestamp": now_sao_paulo().isoformat(),
        }

    # Run async function (async_to_sync for Celery compatibility)
    return async_to_sync(_process)()


@celery_app.task(
    name="app.tasks.flow_automation.send_flow_day_for_patient",
    **_FLOW_AUTOMATION_TASK_OPTIONS,
)
def send_flow_day_for_patient(
    patient_id: str,
    day_number: Optional[int] = None,
    flow_kind: Optional[str] = None,
) -> dict:
    """
    Send a specific flow day for a single patient.

    Args:
        patient_id: Patient UUID string
        day_number: Optional day number to send. If None, selects first day with multiple messages.
        flow_kind: Optional flow kind override (onboarding, daily_follow_up, quiz_mensal)

    Returns:
        dict: Result payload with status and send result
    """

    async def _process():
        with get_db_session() as db:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                return {
                    "status": "error",
                    "message": "patient_not_found",
                    "patient_id": patient_id,
                }

            flow_state = (
                db.query(PatientFlowState)
                .filter(PatientFlowState.patient_id == patient.id)
                .filter(PatientFlowState.status == "active")
                .order_by(PatientFlowState.updated_at.desc())
                .first()
            )

            resolved_flow_kind = flow_kind
            if not resolved_flow_kind and flow_state and flow_state.step_data:
                resolved_flow_kind = flow_state.step_data.get("flow_kind")
            if not resolved_flow_kind:
                current_day = getattr(patient, "current_day", None) or 1
                if current_day <= 15:
                    resolved_flow_kind = "onboarding"
                elif current_day <= 45:
                    resolved_flow_kind = "daily_follow_up"
                else:
                    resolved_flow_kind = "quiz_mensal"

            # Load template steps for the flow kind
            row = db.execute(
                text(
                    """
                    SELECT ftv.steps
                    FROM flow_template_versions ftv
                    JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
                    WHERE fk.kind_key = :kind AND ftv.is_active = true
                    ORDER BY ftv.updated_at DESC
                    LIMIT 1
                    """
                ),
                {"kind": resolved_flow_kind},
            ).fetchone()

            steps = row[0] if row and row[0] else []

            resolved_day = day_number
            if resolved_day is None:
                for step in steps:
                    messages = step.get("messages") or []
                    if len(messages) > 1:
                        resolved_day = step.get("day")
                        break

            if resolved_day is None:
                return {
                    "status": "error",
                    "message": "no_multi_message_day_found",
                    "patient_id": str(patient.id),
                    "flow_kind": resolved_flow_kind,
                }

            if not any((step or {}).get("day") == resolved_day for step in steps):
                return {
                    "status": "error",
                    "message": "invalid_day_for_flow_template",
                    "patient_id": str(patient.id),
                    "flow_kind": resolved_flow_kind,
                    "day_number": resolved_day,
                }

            handler = SequentialMessageHandler(db)
            result = await handler.send_day_messages(
                patient_id=patient.id,
                day_number=resolved_day,
                flow_kind=resolved_flow_kind,
            )
            return {
                "status": "ok",
                "patient_id": str(patient.id),
                "flow_kind": resolved_flow_kind,
                "day_number": resolved_day,
                "result": result,
            }

    return async_to_sync(_process)()


def _get_reminder_message(patient_name: str) -> str:
    """
    Generate reminder message content.

    TODO: Migrate this to database MessageTemplate (template_name='daily_reminder_generic')
    to allow dynamic updates without code changes.
    """
    return (
        f"Olá {patient_name}! 👋\n\n"
        f"Você tem um questionário pendente que é importante "
        f"para acompanharmos seu tratamento.\n\n"
        f"Por favor, reserve alguns minutos para completá-lo. "
        f"Sua participação é fundamental! 💪\n\n"
        f"Equipe Hormonia"
    )


def _get_reminder_template() -> str:
    """
    Get the reminder message template.
    """
    return (
        "Olá {patient_name}! 👋\n\n"
        "Você tem um questionário pendente que é importante "
        "para acompanharmos seu tratamento.\n\n"
        "Por favor, reserve alguns minutos para completá-lo. "
        "Sua participação é fundamental! 💪\n\n"
        "Equipe Hormonia"
    )


def _format_reminder_message(patient_name: str) -> str:
    """
    Format the reminder message with the patient's name.
    """
    template = _get_reminder_template()
    return template.format(patient_name=patient_name)


def _determine_template_for_patient(patient) -> Optional[str]:
    """
    Determine the appropriate flow template based on patient data.

    Args:
        patient: Patient record from database

    Returns:
        Template name or None if cannot determine
    """
    # Check for treatment type
    if hasattr(patient, "treatment_type") and patient.treatment_type:
        treatment_lower = patient.treatment_type.lower()

        if "hormone" in treatment_lower or "hormonal" in treatment_lower:
            return "hormonia_fluxo_hormonal"
        elif "quimio" in treatment_lower or "chemo" in treatment_lower:
            return "hormonia_fluxo_quimio"
        elif "radio" in treatment_lower or "radiation" in treatment_lower:
            return "hormonia_fluxo_radio"

    # Default template
    return "hormonia_fluxo_padrao"


# NOTE: Schedule configuration is in app/celery_app.py beat_schedule.
