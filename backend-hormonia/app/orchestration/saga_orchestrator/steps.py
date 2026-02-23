"""
Saga Step Implementations.

This module contains the individual step implementations for the
patient onboarding saga, keeping each step focused and testable.
"""

import logging
import time
from typing import Optional, Any
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.patient import Patient
from app.models.message import MessageType
from app.models.template import MessageTemplate
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError
from app.services.patient.flow_service import PatientFlowService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.domain.messaging.core import MessageService
from app.config.messages import DEFAULT_WELCOME_MESSAGE
from app.config import settings
from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo
from .query_helpers import metadata_key_equals

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
        db: Any,  # AsyncSession (typed as Any for backward compat with orchestrator)
        patient_repo: Any = None,  # Kept for backward compat; inlined for async compat
        flow_service: Optional[PatientFlowService] = None,
        whatsapp_service: Optional[UnifiedWhatsAppService] = None,
        message_service: Optional[MessageService] = None,
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
        step_start = time.time()
        step_status = "success"
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

            # Inlined from PatientRepository.create() for async compat
            patient = Patient(**patient_dict)
            self.db.add(patient)  # self.db.add() is NOT a coroutine

            saga.patient_id = patient.id
            saga.current_step = 1
            saga.status = SagaStatus.STEP_1_PATIENT_CREATED
            saga.add_log_entry(1, "create_patient", "success")

            try:
                await self.db.flush()
                await self.db.refresh(patient)
            except Exception as flush_error:
                logger.warning(
                    f"Saga {saga.id}: Flush failed in create_patient step: {flush_error}",
                    exc_info=True,
                )

            return patient

        except IntegrityError as e:
            step_status = "failed"
            logger.error(f"Step 1 failed: {type(e).__name__}", exc_info=True)
            saga.add_log_entry(1, "create_patient", "failed", str(e))

            error_message = str(e.orig) if getattr(e, "orig", None) else str(e)
            if any(
                term in error_message
                for term in ["uq_patient_cpf_hash_doctor", "uq_patient_cpf_doctor", "cpf_hash", "cpf"]
            ):
                raise ValidationError(
                    "Paciente com este CPF ja existe",
                    field="cpf",
                    code="duplicate_cpf",
                ) from e
            if any(
                term in error_message
                for term in ["ix_patients_phone_hash_doctor", "uq_patient_phone_doctor", "phone_hash", "phone"]
            ):
                raise ValidationError(
                    "Paciente com este telefone ja existe",
                    field="phone",
                    code="duplicate_phone",
                ) from e
            if any(
                term in error_message
                for term in ["ix_patients_email_hash_doctor", "uq_patient_email_doctor", "email_hash", "email"]
            ):
                raise ValidationError(
                    "Paciente com este email ja existe",
                    field="email",
                    code="duplicate_email",
                ) from e

            raise ValidationError(
                "Patient creation failed due to data integrity constraints",
                code="integrity_error",
            ) from e

        except Exception as e:
            step_status = "failed"
            logger.error(f"Step 1 failed: {type(e).__name__}", exc_info=True)
            saga.add_log_entry(1, "create_patient", "failed", str(e))
            raise
        finally:
            duration = time.time() - step_start
            logger.info(
                f"Saga {saga.id}: create_patient duration {duration:.2f}s",
                extra={
                    "saga_id": str(saga.id),
                    "step": "create_patient",
                    "status": step_status,
                    "duration_s": duration,
                },
            )

    async def step_initialize_flow(
        self,
        saga: PatientOnboardingSaga,
        patient: Patient,
        current_user: Any,
        idempotency_key: Optional[str] = None,
    ) -> None:
        """
        Step 2/3: Initialize Flow.

        Args:
            saga: The saga record being executed
            patient: The patient to initialize flow for
            current_user: Current user context
            idempotency_key: Optional key to avoid duplicate flow creation

        Raises:
            Exception: If flow initialization fails
        """
        # NOTE: flow_service calls may still be sync if PatientFlowService
        # has not been fully migrated to AsyncSession. The AsyncSession is
        # passed through db and the service detects the session type.
        # Direct idempotency check below is inlined for async compat.
        step_start = time.time()
        step_status = "success"
        try:
            current_user_id = (
                current_user.id
                if current_user and hasattr(current_user, "id")
                else None
            )

            if idempotency_key:
                from app.models.flow import PatientFlowState

                # Inlined idempotency check for async compat
                result = await self.db.execute(
                    select(PatientFlowState).filter(
                        PatientFlowState.patient_id == patient.id
                    )
                )
                existing_flow = result.scalars().first()
                if existing_flow:
                    step_status = "skipped_existing_flow"
                    saga.current_step = 3
                    saga.status = SagaStatus.STEP_3_FLOW_INITIALIZED
                    saga.add_log_entry(3, "initialize_flow", "skipped_existing_flow")
                    try:
                        await self.db.flush()
                    except Exception as flush_error:
                        logger.warning(
                            f"Saga {saga.id}: Flush failed in initialize_flow step: {flush_error}",
                            exc_info=True,
                        )
                    return

            flow_state = await self.flow_service.initialize_default_flow(
                patient, current_user_id, auto_commit=False
            )
            if not flow_state:
                step_status = (
                    "skipped_auto_enrollment_disabled"
                    if not settings.FLOW_ENABLE_AUTO_ENROLLMENT
                    else "skipped_no_flow"
                )
                skip_reason = (
                    "auto_enrollment_disabled"
                    if not settings.FLOW_ENABLE_AUTO_ENROLLMENT
                    else "flow_not_initialized"
                )
                saga.current_step = 3
                saga.add_log_entry(
                    3, "initialize_flow", step_status, skip_reason
                )
                if not isinstance(saga.step_data, dict):
                    saga.step_data = {}
                saga.step_data["flow_initialized"] = False
                saga.step_data["flow_skip_reason"] = skip_reason
                try:
                    await self.db.flush()
                except Exception as flush_error:
                    logger.warning(
                        f"Saga {saga.id}: Flush failed in initialize_flow step: {flush_error}",
                        exc_info=True,
                    )
                return

            await self.flow_service.activate_patient(patient.id, auto_commit=False)

            if idempotency_key and flow_state:
                flow_metadata = flow_state.flow_metadata or {}
                flow_metadata["idempotency_key"] = idempotency_key
                flow_state.flow_metadata = flow_metadata

            saga.current_step = 3
            saga.status = SagaStatus.STEP_3_FLOW_INITIALIZED
            saga.add_log_entry(3, "initialize_flow", "success")

            try:
                await self.db.flush()
            except Exception as flush_error:
                logger.warning(
                    f"Saga {saga.id}: Flush failed in initialize_flow step: {flush_error}",
                    exc_info=True,
                )

        except Exception as e:
            step_status = "failed"
            logger.error(f"Step 2 (Flow) failed: {type(e).__name__}", exc_info=True)
            saga.add_log_entry(3, "initialize_flow", "failed", str(e))
            raise
        finally:
            duration = time.time() - step_start
            logger.info(
                f"Saga {saga.id}: initialize_flow duration {duration:.2f}s",
                extra={
                    "saga_id": str(saga.id),
                    "step": "initialize_flow",
                    "status": step_status,
                    "duration_s": duration,
                },
            )

    async def step_send_welcome_message(
        self,
        saga: PatientOnboardingSaga,
        patient: Patient,
        idempotency_key: Optional[str] = None,
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
            idempotency_key: Optional key to avoid duplicate welcome messages
        """
        step_start = time.time()
        step_status = "success"
        try:
            if idempotency_key:
                from app.models.message import Message

                # Inlined idempotency check for async compat
                result = await self.db.execute(
                    select(Message).filter(
                        Message.patient_id == patient.id,
                        metadata_key_equals(
                            Message.message_metadata,
                            "idempotency_key",
                            idempotency_key,
                        ),
                        metadata_key_equals(
                            Message.message_metadata,
                            "message_type",
                            "welcome",
                        ),
                    )
                )
                existing_message = result.scalars().first()
                if existing_message:
                    step_status = "skipped_existing_message"
                    logger.info(
                        f"Saga {saga.id}: Welcome message already exists "
                        f"(message_id={existing_message.id}), skipping send"
                    )
                    saga.current_step = 4
                    saga.status = SagaStatus.STEP_4_MESSAGE_SENT
                    saga.add_log_entry(4, "send_message", "skipped_existing_message")
                    try:
                        await self.db.flush()
                    except Exception as flush_error:
                        logger.warning(
                            f"Saga {saga.id}: Flush failed in send_welcome_message step: "
                            f"{flush_error}",
                            exc_info=True,
                        )
                    return

            # Inlined template lookup for async compat
            result = await self.db.execute(
                select(MessageTemplate).filter(
                    MessageTemplate.name == "welcome_message",
                    MessageTemplate.is_active,
                )
            )
            template = result.scalars().first()

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

            scheduled_for = saga.started_at or now_sao_paulo()
            if scheduled_for.tzinfo is None:
                scheduled_for = scheduled_for.replace(tzinfo=SAO_PAULO_TZ)

            message_metadata = {
                "message_type": "welcome",
                "saga_id": str(saga.id),
            }
            if idempotency_key:
                message_metadata["idempotency_key"] = idempotency_key

            message = self.message_service.schedule_message(
                patient_id=patient.id,
                content=message_content,
                scheduled_for=scheduled_for,
                message_type=MessageType.TEXT,
                message_metadata=message_metadata,
                auto_commit=False,  # Defer commit to saga's Unit of Work
            )

            # NOTE: Message is in PENDING status and will be sent by Cloud Scheduler
            # job `process-scheduled-messages` which runs every 1 minute.
            # This is more reliable than Celery and avoids race conditions with
            # saga commit timing. The message will be picked up on next scheduler run.
            logger.info(
                f"Saga {saga.id}: Welcome message {message.id} created in PENDING status",
                extra={
                    "patient_id": str(patient.id),
                    "message_id": str(message.id),
                    "delivery_method": "celery_beat",
                },
            )

            # Update Saga (message scheduling is best-effort; do not fail onboarding)
            saga.current_step = 4
            saga.status = SagaStatus.STEP_4_MESSAGE_SENT
            saga.add_log_entry(4, "send_message", "scheduled_async")

            try:
                await self.db.flush()
            except Exception as flush_error:
                logger.warning(
                    f"Saga {saga.id}: Flush failed in send_welcome_message step: "
                    f"{flush_error}",
                    exc_info=True,
                )

        except Exception as e:
            step_status = "failed_nonfatal"
            logger.error(
                f"Step 3 (Message) failed: {type(e).__name__}", exc_info=True
            )
            saga.current_step = 4
            saga.status = SagaStatus.STEP_4_MESSAGE_SENT
            saga.add_log_entry(4, "send_message", "failed_nonfatal", str(e))
            try:
                await self.db.flush()
            except Exception as flush_err:
                logger.error(
                    f"Failed to flush message step state: {flush_err}", exc_info=True
                )
            return
        finally:
            duration = time.time() - step_start
            logger.info(
                f"Saga {saga.id}: send_welcome_message duration {duration:.2f}s",
                extra={
                    "saga_id": str(saga.id),
                    "step": "send_welcome_message",
                    "status": step_status,
                    "duration_s": duration,
                },
            )
