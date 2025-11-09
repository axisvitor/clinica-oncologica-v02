"""
Flow Automation Tasks
Celery tasks for automatic flow management and patient engagement
"""

from celery import shared_task
from celery.schedules import crontab
from datetime import datetime, timedelta
from typing import Optional
import logging
import asyncio
from sqlalchemy import text

from app.database import get_db_session
from app.services.flow_engine import FlowEngine
from app.services.patient import PatientService
from app.services.monthly_quiz_service import MonthlyQuizService
from app.models.patient import Patient
from app.models.flow import PatientFlowState

logger = logging.getLogger(__name__)


@shared_task(name="flow_automation.check_and_start_pending_flows")
def check_and_start_pending_flows() -> dict:
    """
    Check for patients without active flows and start them automatically.
    This task should be scheduled to run every hour via Celery Beat.

    Returns:
        dict: Summary of flows started
    """
    async def _process():
        flows_started = 0
        errors = []

        async with get_db_session() as db:
            try:
                # Query for patients without active flows
                query = text("""
                    SELECT DISTINCT p.*
                    FROM patients p
                    LEFT JOIN patient_flow_states pfs
                        ON p.id = pfs.patient_id
                        AND pfs.status IN ('active', 'scheduled', 'in_progress')
                    WHERE pfs.id IS NULL
                        AND p.created_at > NOW() - INTERVAL '7 days'
                        AND p.status = 'active'
                        AND p.deleted_at IS NULL
                    LIMIT 50
                """)

                result = await db.execute(query)
                patients_without_flow = result.fetchall()

                logger.info(f"Found {len(patients_without_flow)} patients without active flows")

                flow_engine = FlowEngine()
                patient_service = PatientService(db)

                for patient_row in patients_without_flow:
                    try:
                        # Determine appropriate template based on patient data
                        template_name = _determine_template_for_patient(patient_row)

                        if template_name:
                            # Start the flow
                            await flow_engine.start_flow(
                                patient_id=patient_row.id,
                                template_name=template_name,
                                user_id=None  # System-initiated
                            )

                            flows_started += 1
                            logger.info(
                                f"Started automatic flow '{template_name}' "
                                f"for patient {patient_row.id} ({patient_row.name})"
                            )
                        else:
                            logger.warning(
                                f"Could not determine template for patient "
                                f"{patient_row.id} ({patient_row.name})"
                            )

                    except Exception as e:
                        error_msg = f"Failed to start flow for patient {patient_row.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

            except Exception as e:
                logger.error(f"Error querying patients without flows: {e}")
                errors.append(str(e))

        return {
            "flows_started": flows_started,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }

    # Run async function
    return asyncio.run(_process())


@shared_task(name="flow_automation.send_daily_reminders")
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

        async with get_db_session() as db:
            try:
                # Query for patients with pending quiz sessions
                query = text("""
                    SELECT DISTINCT p.*, qs.id as session_id
                    FROM patients p
                    INNER JOIN quiz_sessions qs
                        ON p.id = qs.patient_id
                    WHERE qs.status = 'in_progress'
                        AND qs.created_at < NOW() - INTERVAL '24 hours'
                        AND qs.created_at > NOW() - INTERVAL '7 days'
                        AND p.status = 'active'
                        AND p.deleted_at IS NULL
                    LIMIT 100
                """)

                result = await db.execute(query)
                patients_with_pending_quiz = result.fetchall()

                logger.info(f"Found {len(patients_with_pending_quiz)} patients with pending quizzes")

                # Send reminders
                from app.domain.messaging.delivery import MessageSender
                message_sender = MessageSender(db)

                for patient_row in patients_with_pending_quiz:
                    try:
                        # Send reminder message
                        reminder_message = (
                            f"Olá {patient_row.name}! 👋\n\n"
                            f"Você tem um questionário pendente que é importante "
                            f"para acompanharmos seu tratamento.\n\n"
                            f"Por favor, reserve alguns minutos para completá-lo. "
                            f"Sua participação é fundamental! 💪\n\n"
                            f"Equipe Hormonia"
                        )

                        await message_sender.send_whatsapp_message(
                            phone=patient_row.phone,
                            message=reminder_message,
                            patient_id=patient_row.id
                        )

                        reminders_sent += 1
                        logger.info(f"Sent reminder to patient {patient_row.id} ({patient_row.name})")

                    except Exception as e:
                        error_msg = f"Failed to send reminder to patient {patient_row.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

            except Exception as e:
                logger.error(f"Error querying patients with pending quizzes: {e}")
                errors.append(str(e))

        return {
            "reminders_sent": reminders_sent,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }

    # Run async function
    return asyncio.run(_process())


@shared_task(name="flow_automation.resume_paused_flows")
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

        async with get_db_session() as db:
            try:
                # Query for paused flows that should be resumed
                query = text("""
                    SELECT pfs.*
                    FROM patient_flow_states pfs
                    INNER JOIN patients p ON pfs.patient_id = p.id
                    WHERE pfs.status = 'paused'
                        AND pfs.updated_at < NOW() - INTERVAL '48 hours'
                        AND p.status = 'active'
                        AND p.deleted_at IS NULL
                    LIMIT 50
                """)

                result = await db.execute(query)
                paused_flows = result.fetchall()

                logger.info(f"Found {len(paused_flows)} paused flows to potentially resume")

                flow_engine = FlowEngine()

                for flow_row in paused_flows:
                    try:
                        # Resume the flow
                        await flow_engine.resume_flow(flow_row.id)

                        flows_resumed += 1
                        logger.info(f"Resumed flow {flow_row.id} for patient {flow_row.patient_id}")

                    except Exception as e:
                        error_msg = f"Failed to resume flow {flow_row.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

            except Exception as e:
                logger.error(f"Error querying paused flows: {e}")
                errors.append(str(e))

        return {
            "flows_resumed": flows_resumed,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }

    # Run async function
    return asyncio.run(_process())


@shared_task(name="flow_automation.cleanup_expired_quiz_links")
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

        async with get_db_session() as db:
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
                        AND (session_metadata->>'expires_at')::timestamp < NOW()
                    RETURNING id
                """)

                result = await db.execute(query)
                expired_sessions = result.fetchall()
                links_cleaned = len(expired_sessions)

                await db.commit()

                logger.info(f"Cleaned up {links_cleaned} expired quiz links")

            except Exception as e:
                await db.rollback()
                logger.error(f"Error cleaning up expired quiz links: {e}")
                errors.append(str(e))

        return {
            "links_cleaned": links_cleaned,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }

    # Run async function
    return asyncio.run(_process())


def _determine_template_for_patient(patient) -> Optional[str]:
    """
    Determine the appropriate flow template based on patient data.

    Args:
        patient: Patient record from database

    Returns:
        Template name or None if cannot determine
    """
    # Check for treatment type
    if hasattr(patient, 'treatment_type') and patient.treatment_type:
        treatment_lower = patient.treatment_type.lower()

        if 'hormone' in treatment_lower or 'hormonal' in treatment_lower:
            return 'hormonia_fluxo_hormonal'
        elif 'quimio' in treatment_lower or 'chemo' in treatment_lower:
            return 'hormonia_fluxo_quimio'
        elif 'radio' in treatment_lower or 'radiation' in treatment_lower:
            return 'hormonia_fluxo_radio'

    # Check for cancer type in metadata
    if hasattr(patient, 'metadata') and patient.metadata:
        cancer_type = patient.metadata.get('cancer_type', '').lower()

        if 'mama' in cancer_type or 'breast' in cancer_type:
            return 'hormonia_fluxo_mama'
        elif 'prostata' in cancer_type or 'prostate' in cancer_type:
            return 'hormonia_fluxo_prostata'
        elif 'pulmao' in cancer_type or 'lung' in cancer_type:
            return 'hormonia_fluxo_pulmao'

    # Default template
    return 'hormonia_fluxo_padrao'


# Celery Beat Schedule Configuration
# Add this to your celery configuration
CELERYBEAT_SCHEDULE = {
    'check-pending-flows': {
        'task': 'flow_automation.check_and_start_pending_flows',
        'schedule': timedelta(hours=1),  # Every hour
        'options': {'queue': 'default'}
    },
    'send-daily-reminders': {
        'task': 'flow_automation.send_daily_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
        'options': {'queue': 'default'}
    },
    'resume-paused-flows': {
        'task': 'flow_automation.resume_paused_flows',
        'schedule': timedelta(hours=6),  # Every 6 hours
        'options': {'queue': 'default'}
    },
    'cleanup-expired-links': {
        'task': 'flow_automation.cleanup_expired_quiz_links',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'options': {'queue': 'default'}
    }
}