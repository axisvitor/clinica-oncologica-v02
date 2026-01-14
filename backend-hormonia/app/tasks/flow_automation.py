"""
Flow Automation Tasks
Background tasks for automatic flow management and patient engagement
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
from asgiref.sync import async_to_sync
from sqlalchemy import text, select
from app.models.template import MessageTemplate

from app.tasks.base import get_db_session
from app.task_queue import task_queue as celery_app
from app.services.enhanced_flow_engine import get_enhanced_flow_engine

logger = logging.getLogger(__name__)


@celery_app.task(name="flow_automation.check_and_start_pending_flows")
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Run async function (async_to_sync for Celery compatibility)
    return async_to_sync(_process)()


@celery_app.task(name="flow_automation.send_daily_reminders")
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

                        # Create message object required by Unified Service
                        message = Message(
                            patient_id=patient_row.id,
                            direction=MessageDirection.OUTBOUND,
                            type=MessageType.TEXT,
                            content=reminder_content,
                            status=MessageStatus.PENDING,
                            message_metadata={"source": "automation_reminder"},
                        )
                        db.add(message)
                        db.commit()
                        db.refresh(message)

                        send_scheduled_message.delay(str(message.id))

                        reminders_sent += 1
                        logger.info(
                            f"Sent reminder to patient {patient_row.id} ({patient_row.name})"
                        )

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Run async function (async_to_sync for Celery compatibility)
    return async_to_sync(_process)()


@celery_app.task(name="flow_automation.send_daily_flow_questions")
def send_daily_flow_questions() -> dict:
    """
    Send daily flow questions to patients based on their treatment phase.

    This is the CRITICAL task that sends daily check-in messages.
    Uses the patients table directly (flow_state and current_day columns).

    Flow phases based on current_day:
    - Days 1-15: Daily check-ins (initial phase)
    - Days 16-45: Every 3 days (intermediate phase)
    - Days 46+: Weekly check-ins (maintenance phase)

    Should run daily at 8 AM local time via Celery Beat.

    Returns:
        dict: Summary of questions sent
    """

    def _process_sync():
        questions_sent = 0
        errors = []
        skipped = 0

        with get_db_session() as db:
            try:
                from datetime import date
                from app.models.patient import Patient
                from app.models.enums import FlowState

                # Define fallback messages for each flow phase (Portuguese)
                FLOW_MESSAGES = {
                    "initial_15_days": {
                        "content": "Olá {patient_name}! 👋 Como você está se sentindo hoje? "
                        "Estamos aqui para acompanhar sua jornada de tratamento. "
                        "Compartilhe conosco como está passando. 💙",
                        "intent": "daily_checkin_initial",
                    },
                    "days_16_45": {
                        "content": "Olá {patient_name}! 🌟 Esperamos que você esteja bem. "
                        "Como está seu tratamento esta semana? "
                        "Conte-nos se houve alguma mudança. 💪",
                        "intent": "periodic_checkin",
                    },
                    "monthly_recurring": {
                        "content": "Olá {patient_name}! 📋 Esta é sua verificação semanal. "
                        "Como você está se sentindo? Alguma novidade para compartilhar? "
                        "Estamos sempre prontos para ajudar! 💙",
                        "intent": "weekly_checkin",
                    },
                }

                # Query patients with active flow_state directly from patients table
                # FIX: Uses patients.flow_state and patients.current_day (not patient_flow_states)
                # FIX: Uses ORM to get decrypted phone via patient.phone property
                # FIX: Removed hardcoded 200-patient limit - now uses batch processing
                BATCH_SIZE = 100  # Process in batches to avoid memory issues

                # Build base query (no limit - we'll paginate)
                base_query = (
                    db.query(Patient)
                    .filter(
                        Patient.flow_state == FlowState.ACTIVE,  # Use enum for type safety
                        Patient.deleted_at.is_(None),
                        Patient.treatment_start_date.isnot(None),
                        Patient.phone_encrypted.isnot(None),  # Has phone
                    )
                    .order_by(Patient.id)  # Consistent ordering for pagination
                )

                # Get total count for logging
                total_patients = base_query.count()
                logger.info(f"Found {total_patients} patients with active flow_state for daily questions")

                # Process in batches
                offset = 0
                active_patients = []
                while True:
                    batch = base_query.offset(offset).limit(BATCH_SIZE).all()
                    if not batch:
                        break
                    active_patients.extend(batch)
                    offset += BATCH_SIZE
                    # Commit after each batch to avoid long transactions
                    db.commit()

                logger.info(
                    f"Loaded {len(active_patients)} patients in batches of {BATCH_SIZE}"
                )

                today = date.today()

                for patient in active_patients:
                    try:
                        # Get current_day from patient record (updated by flow engine)
                        current_day = patient.current_day or 0

                        # If current_day is 0, calculate from treatment_start_date
                        if current_day == 0 and patient.treatment_start_date:
                            current_day = (today - patient.treatment_start_date).days + 1

                        # Determine flow phase and if we should send today
                        should_send = False
                        flow_phase = "initial_15_days"

                        if current_day <= 15:
                            # INITIAL_15_DAYS: Daily messages
                            flow_phase = "initial_15_days"
                            should_send = True
                        elif current_day <= 45:
                            # DAYS_16_45: Every 3 days
                            flow_phase = "days_16_45"
                            day_in_phase = current_day - 15
                            should_send = day_in_phase % 3 == 0
                        else:
                            # MONTHLY_RECURRING: Weekly check-ins (days 7, 14, 21 of each 30-day cycle)
                            flow_phase = "monthly_recurring"
                            day_in_cycle = (current_day - 45) % 30
                            should_send = day_in_cycle in [0, 7, 14, 21]

                        if not should_send:
                            skipped += 1
                            continue

                        # Get decrypted phone via ORM property
                        patient_phone = patient.phone  # Auto-decrypts via property
                        if not patient_phone:
                            logger.warning(
                                f"Patient {patient.id} has encrypted phone but decryption failed"
                            )
                            skipped += 1
                            continue

                        # Use SequentialMessageHandler for proper multi-message flow
                        try:
                            from app.services.flow.sequential_message_handler import (
                                SequentialMessageHandler,
                            )
                            
                            handler = SequentialMessageHandler(db)
                            
                            # Determine the correct day number for this flow phase
                            if flow_phase == "initial_15_days":
                                day_in_flow = current_day
                            elif flow_phase == "days_16_45":
                                day_in_flow = current_day  # Days 16-45 use actual day number
                            else:  # monthly_recurring
                                day_in_flow = day_in_cycle + 1
                            
                            # Use async_to_sync for Celery compatibility
                            result = async_to_sync(handler.send_day_messages)(
                                patient_id=patient.id,
                                day_number=day_in_flow,
                                flow_kind=flow_phase
                            )
                            
                            if result.get("status") == "error":
                                logger.error(
                                    f"SequentialMessageHandler returned error for patient {patient.id}: "
                                    f"{result.get('message')}"
                                )
                                # Continue to next patient instead of falling back
                                continue
                            
                        except Exception as send_error:
                            logger.error(
                                f"Failed to send via SequentialMessageHandler for patient {patient.id}: {send_error}"
                            )
                            continue

                        db.commit()

                        questions_sent += 1
                        logger.info(
                            f"Sent daily question to patient {patient.id} ({patient.name}) "
                            f"[{flow_phase} day {current_day}]"
                        )

                    except Exception as e:
                        db.rollback()
                        error_msg = f"Failed to send question to patient {patient.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

            except Exception as e:
                logger.error(f"Error processing daily flow questions: {e}")
                errors.append(str(e))

        return {
            "questions_sent": questions_sent,
            "skipped": skipped,
            "errors_count": len(errors),
            "errors": errors[:10],  # Limit error details
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Run synchronously (no async needed for ORM queries)
    return _process_sync()


@celery_app.task(name="flow_automation.resume_paused_flows")
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
                        AND p.status = 'active'
                        AND p.deleted_at IS NULL
                    LIMIT 50
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

            except Exception as e:
                logger.error(f"Error querying paused flows: {e}")
                errors.append(str(e))

        return {
            "flows_resumed": flows_resumed,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Run async function (async_to_sync for Celery compatibility)
    return async_to_sync(_process)()


@celery_app.task(name="flow_automation.cleanup_expired_quiz_links")
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
                        AND (session_metadata->>'expires_at')::timestamp < NOW()
                    RETURNING id
                """)

                result = db.execute(query)
                expired_sessions = result.fetchall()
                links_cleaned = len(expired_sessions)

                db.commit()

                logger.info(f"Cleaned up {links_cleaned} expired quiz links")

            except Exception as e:
                db.rollback()
                logger.error(f"Error cleaning up expired quiz links: {e}")
                errors.append(str(e))

        return {
            "links_cleaned": links_cleaned,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Run async function (async_to_sync for Celery compatibility)
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

    # Check for specific cancer types (now mapped to treatment_type or diagnosis)
    # Fallback for legacy data that might still be in metadata
    if hasattr(patient, "metadata") and patient.metadata:
        cancer_type = patient.metadata.get("cancer_type", "").lower()

        if "mama" in cancer_type or "breast" in cancer_type:
            return "hormonia_fluxo_mama"
        elif "prostata" in cancer_type or "prostate" in cancer_type:
            return "hormonia_fluxo_prostata"
        elif "pulmao" in cancer_type or "lung" in cancer_type:
            return "hormonia_fluxo_pulmao"

    # Default template
    return "hormonia_fluxo_padrao"


# NOTE: Schedule configuration moved to config/cloud-run/cloud-scheduler-jobs.yaml
# for Cloud Scheduler (GCP Cloud Run deployment).

@celery_app.task(name="flow_automation.increment_active_patient_days")
def increment_active_patient_days() -> dict:
    """
    Increment current_day for all active patients.
    
    This ensures that patients who were manually fast-forwarded or whose
    flow relies on current_day counter continue to progress.
    
    Logic:
    - Increments current_day by 1 for all ACTIVE patients
    - Where current_day > 0 (meaning flow has started)
    - Ignores patients with current_day = 0 (calculated dynamically from start_date)
    """
    async def _process():
        updated_count = 0
        errors = []
        
        with get_db_session() as db:
            try:
                # Raw SQL for efficiency on bulk update
                query = text("""
                    UPDATE patients 
                    SET current_day = current_day + 1,
                        updated_at = NOW()
                    WHERE status = 'active' 
                      AND deleted_at IS NULL
                      AND current_day > 0
                """)
                
                result = db.execute(query)
                updated_count = result.rowcount
                db.commit()
                
                logger.info(f"Incremented current_day for {updated_count} active patients")
                
            except Exception as e:
                db.rollback()
                error_msg = f"Failed to increment patient days: {e}"
                logger.error(error_msg, exc_info=True)
                errors.append(str(e))
                
        return {
            "updated_count": updated_count,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    return async_to_sync(_process)()
