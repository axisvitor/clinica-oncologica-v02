"""
Saga Step Implementations.

This module contains the individual step implementations for the
patient onboarding saga, keeping each step focused and testable.
"""

import logging
from typing import Optional, Any
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.message import MessageType
from app.models.template import MessageTemplate
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.schemas.patient import PatientCreate
from app.repositories.patient import PatientRepository
from app.services.patient.flow_service import PatientFlowService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.domain.messaging.core import MessageService
from app.config.messages import DEFAULT_WELCOME_MESSAGE

logger = logging.getLogger(__name__)


class SagaStepExecutor:
    """
    Executor for individual saga steps.

    Each step is implemented as a separate method, allowing for:
    - Clear separation of concerns
    - Easy testing of individual steps
    - Reusability across different saga implementations
    """

    def __init__(
        self,
        db: Session,
        patient_repo: PatientRepository,
        flow_service: PatientFlowService,
        whatsapp_service: UnifiedWhatsAppService,
        message_service: MessageService,
    ):
        self.db = db
        self.patient_repo = patient_repo
        self.flow_service = flow_service
        self.whatsapp_service = whatsapp_service
        self.message_service = message_service

    async def step_create_patient(
        self,
        saga: PatientOnboardingSaga,
        patient_data: PatientCreate,
        doctor_id: Optional[UUID] = None,
        idempotency_key: Optional[str] = None,
    ) -> Patient:
        """
        Step 1: Create Patient in DB.

        QW-004: Supports idempotency key for duplicate request prevention.

        Args:
            saga: The saga record being executed
            patient_data: Patient creation data
            doctor_id: ID of the doctor creating the patient (optional)
            idempotency_key: Optional key to prevent duplicates

        Returns:
            Created Patient object

        Raises:
            Exception: If patient creation fails
        """
        try:
            patient_dict = patient_data.dict(exclude_unset=True)
            metadata = patient_dict.pop("metadata", {})

            # Only set doctor_id if provided
            if doctor_id:
                patient_dict["doctor_id"] = doctor_id
            if metadata:
                patient_dict["patient_data"] = metadata

            if idempotency_key:
                patient_dict["idempotency_key"] = idempotency_key

            patient = self.patient_repo.create(patient_dict, auto_commit=False)

            saga.patient_id = patient.id
            saga.current_step = 1
            saga.status = SagaStatus.STEP_1_PATIENT_CREATED
            saga.add_log_entry(1, "create_patient", "success")

            try:
                self.db.flush()
            except Exception as flush_error:
                logger.warning(
                    f"Saga {saga.id}: Flush failed in create_patient step: {flush_error}",
                    exc_info=True,
                )

            return patient

        except Exception as e:
            logger.error(f"Step 1 failed: {type(e).__name__}", exc_info=True)
            saga.add_log_entry(1, "create_patient", "failed", str(e))
            raise

    async def step_initialize_flow(
        self,
        saga: PatientOnboardingSaga,
        patient: Patient,
        current_user: Any,
    ) -> None:
        """
        Step 2/3: Initialize Flow.

        Args:
            saga: The saga record being executed
            patient: The patient to initialize flow for
            current_user: Current user context

        Raises:
            Exception: If flow initialization fails
        """
        try:
            current_user_id = (
                current_user.id
                if current_user and hasattr(current_user, "id")
                else None
            )

            await self.flow_service.initialize_default_flow(
                patient, current_user_id, auto_commit=False
            )
            await self.flow_service.activate_patient(patient.id, auto_commit=False)

            saga.current_step = 3
            saga.status = SagaStatus.STEP_3_FLOW_INITIALIZED
            saga.add_log_entry(3, "initialize_flow", "success")

            try:
                self.db.flush()
            except Exception as flush_error:
                logger.warning(
                    f"Saga {saga.id}: Flush failed in initialize_flow step: {flush_error}",
                    exc_info=True,
                )

        except Exception as e:
            logger.error(f"Step 2 (Flow) failed: {type(e).__name__}", exc_info=True)
            saga.add_log_entry(3, "initialize_flow", "failed", str(e))
            raise

    async def step_send_welcome_message(
        self,
        saga: PatientOnboardingSaga,
        patient: Patient,
    ) -> None:
        """
        Step 3/4: Schedule Welcome Message (NON-BLOCKING).

        PERFORMANCE FIX: Instead of calling WhatsApp service directly (which was
        blocking and failing due to AsyncSession mismatch), we now:
        1. Create the message record in the database
        2. Schedule a Celery task to send it asynchronously

        This reduces patient creation time from ~8s to <2s by making the WhatsApp
        send truly asynchronous via Celery background worker.

        Args:
            saga: The saga record being executed
            patient: The patient to send welcome message to
        """
        try:
            template = (
                self.db.query(MessageTemplate)
                .filter(
                    MessageTemplate.name == "welcome_message",
                    MessageTemplate.is_active,
                )
                .first()
            )

            if template:
                try:
                    message_content = template.format(patient_name=patient.name)
                except Exception as e:
                    logger.warning(
                        f"Failed to format welcome template: {e}. Using fallback."
                    )
                    message_content = DEFAULT_WELCOME_MESSAGE.format(
                        patient_name=patient.name
                    )
            else:
                logger.warning("Welcome message template not found. Using fallback.")
                message_content = DEFAULT_WELCOME_MESSAGE.format(
                    patient_name=patient.name
                )

            scheduled_for = saga.started_at or datetime.now(timezone.utc)
            if scheduled_for.tzinfo is None:
                scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)

            message = self.message_service.schedule_message(
                patient_id=patient.id,
                content=message_content,
                scheduled_for=scheduled_for,
                message_type=MessageType.TEXT,
                message_metadata={
                    "message_type": "welcome",
                    "saga_id": str(saga.id),
                },
            )

            # PERFORMANCE FIX: Schedule Celery task to send message asynchronously
            # instead of blocking the saga with direct WhatsApp API call.
            # This prevents the ~5-7s delay caused by:
            # 1. AsyncSession mismatch (UnifiedWhatsAppService expects AsyncSession)
            # 2. Circuit breaker checks and connection setup
            # 3. Potential API timeouts
            #
            # The message is already in PENDING status from schedule_message(),
            # and the Celery task will handle sending and retries.
            try:
                from app.tasks.messaging import send_scheduled_message

                # Schedule task with small delay to ensure DB commit happens first
                send_scheduled_message.apply_async(
                    args=[str(message.id)],
                    countdown=2,  # 2 second delay to ensure transaction commits
                )
                logger.info(
                    f"Saga {saga.id}: Welcome message {message.id} scheduled for async send",
                    extra={"patient_id": str(patient.id), "message_id": str(message.id)},
                )
            except Exception as task_exc:
                # If Celery scheduling fails, message stays in PENDING status
                # and retry_pending_welcome_messages task will pick it up later
                logger.warning(
                    f"Saga {saga.id}: Failed to schedule Celery task for welcome message: "
                    f"{type(task_exc).__name__}",
                    exc_info=True,
                )

            # Update Saga (message scheduling is best-effort; do not fail onboarding)
            saga.current_step = 4
            saga.status = SagaStatus.STEP_4_MESSAGE_SENT
            saga.add_log_entry(4, "send_message", "scheduled_async")

            try:
                self.db.flush()
            except Exception as flush_error:
                logger.warning(
                    f"Saga {saga.id}: Flush failed in send_welcome_message step: "
                    f"{flush_error}",
                    exc_info=True,
                )

        except Exception as e:
            logger.error(
                f"Step 3 (Message) failed: {type(e).__name__}", exc_info=True
            )
            saga.current_step = 4
            saga.status = SagaStatus.STEP_4_MESSAGE_SENT
            saga.add_log_entry(4, "send_message", "failed_nonfatal", str(e))
            try:
                self.db.flush()
            except Exception as flush_err:
                logger.error(
                    f"Failed to flush message step state: {flush_err}", exc_info=True
                )
            return
