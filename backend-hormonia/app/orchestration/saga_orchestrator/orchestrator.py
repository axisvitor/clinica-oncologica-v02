"""
Saga Orchestrator - Main Orchestrator Class.

This module provides the main SagaOrchestrator class that coordinates
the patient onboarding saga, managing distributed transactions for
patient creation with data consistency guarantees.
"""

import hashlib
import logging
import uuid
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.schemas.patient import PatientCreate
from app.repositories.patient import PatientRepository
from app.services.patient.flow_service import PatientFlowService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.domain.messaging.core import MessageService
from app.core.redis_client import get_redis_client
from app.core.distributed_lock import acquire_lock, LockAcquisitionError
from app.integrations.evolution import EvolutionClient
from app.utils.phone_validator import normalize_phone

from .exceptions import SagaCompensationError
from .steps import SagaStepExecutor
from .compensation import SagaCompensator
from .persistence import SagaPersistence
from .types import SagaStatusInfo, FailedSagaSummary, ResumeResult

logger = logging.getLogger(__name__)


class SagaOrchestrator:
    """
    Saga Orchestrator for Patient Onboarding.

    Manages distributed transactions for patient creation, ensuring data
    consistency across database, flow engine, and external services (WhatsApp).

    This orchestrator implements the Saga pattern with:
    - Distributed locking for concurrency control
    - Step-by-step execution with rollback support
    - Idempotent compensation for failure recovery
    - Unit of Work pattern for atomic commits
    """

    def __init__(
        self,
        db: Session,
        redis_client: Optional[Any] = None,
        evolution_client: Optional[EvolutionClient] = None,
    ):
        self.db = db
        self.redis = redis_client or get_redis_client()
        self.evolution_client = evolution_client

        # Initialize repositories and services
        self.patient_repo = PatientRepository(db)
        self.flow_service = PatientFlowService(db)
        self.whatsapp_service = UnifiedWhatsAppService(db)
        self.message_service = MessageService(db)

        # Initialize sub-components
        self.step_executor = SagaStepExecutor(
            db=db,
            patient_repo=self.patient_repo,
            flow_service=self.flow_service,
            whatsapp_service=self.whatsapp_service,
            message_service=self.message_service,
        )
        self.compensator = SagaCompensator(
            db=db,
            patient_repo=self.patient_repo,
            redis_client=self.redis,
        )
        self.persistence = SagaPersistence(db)

    async def execute_patient_onboarding_saga(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID,
        current_user: Any = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[Patient]:
        """
        Execute the patient onboarding saga.

        Steps:
        1. Create patient in database
        2. Initialize flow state
        3. Send welcome WhatsApp message

        Args:
            patient_data: Patient creation data
            doctor_id: ID of the doctor creating the patient
            current_user: Current user object
            idempotency_key: QW-004: Unique key to prevent duplicate requests

        Returns:
            Created Patient object if successful, None if failed

        Raises:
            LockAcquisitionError: If unable to acquire distributed lock
        """
        # Generate lock key based on phone number (unique identifier)
        normalized_phone = normalize_phone(patient_data.phone) or patient_data.phone
        phone_hash = hashlib.sha256(normalized_phone.encode()).hexdigest()[:32]
        lock_key = f"saga:onboarding:{str(doctor_id)}:{phone_hash}"

        async with acquire_lock(lock_key, timeout=5.0, ttl=60):
            saga_id = uuid.uuid4()

            saga = PatientOnboardingSaga(
                id=saga_id,
                doctor_id=doctor_id,
                patient_data=patient_data.model_dump(mode="json"),
                status=SagaStatus.STARTED,
                current_step=0,
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(saga)
            self.db.flush()

            logger.info(
                f"Starting patient onboarding saga {saga_id} for doctor {doctor_id}"
            )

            try:
                # --- STEP 1: Create Patient ---
                patient = await self.step_executor.step_create_patient(
                    saga, patient_data, doctor_id, idempotency_key
                )
                if not patient:
                    raise Exception("Failed to create patient")

                # --- STEP 2: Initialize Flow ---
                await self.step_executor.step_initialize_flow(
                    saga, patient, current_user
                )

                # --- STEP 3: Send Welcome Message ---
                await self.step_executor.step_send_welcome_message(saga, patient)

                # --- Complete Saga ---
                saga.status = SagaStatus.COMPLETED
                saga.completed_at = datetime.now(timezone.utc)

                # UNIT OF WORK: Single commit at the end
                self.db.commit()

                logger.info(f"Saga {saga_id} completed successfully")
                return patient

            except Exception as e:
                logger.error(
                    f"Saga {saga_id} failed with {type(e).__name__}",
                    exc_info=True,
                )

                self.db.rollback()

                # Create failure record
                try:
                    failure_saga = PatientOnboardingSaga(
                        id=saga_id,
                        doctor_id=doctor_id,
                        patient_data=patient_data.model_dump(mode="json"),
                        status=SagaStatus.FAILED,
                        current_step=0,
                        started_at=datetime.now(timezone.utc),
                        failed_at=datetime.now(timezone.utc),
                        error_message=str(e),
                        error_type=type(e).__name__,
                    )
                    self.db.add(failure_saga)
                    self.db.commit()
                    logger.info(f"Saga {saga_id} failure record created")

                    # Trigger compensation (best effort)
                    try:
                        await self.compensator.compensate_saga(failure_saga)
                    except Exception as comp_err:
                        logger.error(
                            f"Saga {saga_id} compensation failed: {comp_err}"
                        )

                except Exception as record_err:
                    logger.error(
                        f"Failed to create saga {saga_id} failure record: {record_err}",
                        exc_info=True,
                    )

                return None

    async def resume_saga(self, saga_id: UUID) -> ResumeResult:
        """
        Resume a failed or interrupted saga.

        Args:
            saga_id: UUID of the saga to resume

        Returns:
            Dict with result status

        Note:
            Uses distributed lock to prevent concurrent resume attempts.
            FIX: Saga is re-fetched AFTER lock acquisition to prevent TOCTOU.
        """
        lock_key = f"saga:resume:{saga_id}"
        try:
            async with acquire_lock(lock_key, timeout=5.0, ttl=60):
                saga = self.persistence.get_saga_by_id(saga_id)
                if not saga:
                    return ResumeResult(
                        status="error",
                        message=None,
                        error="Saga not found",
                    )

                return await self._resume_saga_internal(saga)
        except LockAcquisitionError:
            logger.warning(f"Could not acquire lock for saga resume: {saga_id}")
            return ResumeResult(
                status="error",
                message=None,
                error="Saga resume already in progress",
            )

    async def _resume_saga_internal(
        self, saga: PatientOnboardingSaga
    ) -> ResumeResult:
        """Internal resume logic (called within lock context)."""
        if saga.status == SagaStatus.COMPLETED:
            return ResumeResult(
                status="completed",
                message="Saga already completed",
                error=None,
            )

        logger.info(f"Resuming saga {saga.id} from step {saga.current_step}")

        try:
            patient = None
            if saga.patient_id:
                patient = self.patient_repo.get_by_id(saga.patient_id)

            patient_data_dict = saga.patient_data

            # Step 0 -> 1: Create Patient
            if saga.current_step < 1:
                patient_create = PatientCreate(**patient_data_dict)
                patient = await self.step_executor.step_create_patient(
                    saga, patient_create, saga.doctor_id
                )
                if not patient:
                    raise Exception("Failed to recover patient creation")

            if not patient and saga.patient_id:
                patient = self.patient_repo.get_by_id(saga.patient_id)

            if not patient:
                raise Exception("Patient not found for resumption")

            # Step 1 -> 2: Initialize Flow
            if saga.current_step <= 1:
                await self.step_executor.step_initialize_flow(saga, patient, None)

            # Step 2 -> 3: Send Welcome Message
            if saga.current_step <= 2:
                await self.step_executor.step_send_welcome_message(saga, patient)

            # Complete
            saga.status = SagaStatus.COMPLETED
            saga.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            return ResumeResult(
                status="completed",
                message=None,
                error=None,
            )

        except Exception as e:
            logger.error(f"Failed to resume saga {saga.id}: {e}", exc_info=True)
            self.db.rollback()
            saga.error_message = str(e)
            self.db.commit()
            return ResumeResult(
                status="failed",
                message=None,
                error=str(e),
            )

    async def get_saga_status(self, saga_id: UUID) -> Optional[SagaStatusInfo]:
        """
        Get current status of a saga for monitoring.

        Args:
            saga_id: UUID of the saga

        Returns:
            Dict with saga status info or None if not found
        """
        return self.persistence.get_saga_status(saga_id)

    async def list_failed_sagas(
        self, doctor_id: Optional[UUID] = None, limit: int = 50
    ) -> List[FailedSagaSummary]:
        """
        List failed sagas for manual review or retry.

        Args:
            doctor_id: Optional filter by doctor
            limit: Maximum number of results

        Returns:
            List of failed saga summaries
        """
        return self.persistence.list_failed_sagas(doctor_id, limit)

    # Keep backward compatibility for _compensate_saga
    async def _compensate_saga(self, saga: PatientOnboardingSaga) -> None:
        """
        Execute compensation steps in reverse order.

        Delegates to SagaCompensator for actual compensation logic.
        """
        await self.compensator.compensate_saga(saga)

    # Keep backward compatibility for _track_compensation_failure
    async def _track_compensation_failure(
        self, saga_id: UUID, step: int, error: Exception
    ) -> None:
        """
        Track compensation failures for audit.

        Delegates to SagaCompensator for actual tracking.
        """
        await self.compensator._track_compensation_failure(saga_id, step, error)
