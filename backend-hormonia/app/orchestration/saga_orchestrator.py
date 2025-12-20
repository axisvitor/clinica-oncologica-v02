import logging
import json
import uuid
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.patient_onboarding_saga import PatientOnboardingSaga, SagaStatus
from app.models.message import Message, MessageType, MessageStatus
from app.models.template import MessageTemplate
from app.schemas.patient import PatientCreate
from app.repositories.patient import PatientRepository
from app.services.patient.flow_service import PatientFlowService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.domain.messaging.core import MessageService
from app.core.redis_client import get_redis_client
from app.core.distributed_lock import acquire_lock, LockAcquisitionError
from app.integrations.evolution import EvolutionClient
from app.config.messages import DEFAULT_WELCOME_MESSAGE
from app.utils.phone_validator import normalize_phone

logger = logging.getLogger(__name__)


class SagaCompensationError(Exception):
    """
    Exception raised when saga compensation fails.

    This error indicates that the system failed to properly rollback
    a saga transaction, which may require manual intervention.
    """

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        saga_id: Optional[UUID] = None,
    ):
        self.message = message
        self.original_error = original_error
        self.saga_id = saga_id
        super().__init__(self.message)


class SagaOrchestrator:
    """
    Saga Orchestrator for Patient Onboarding.

    Manages distributed transactions for patient creation, ensuring data consistency
    across database, flow engine, and external services (WhatsApp).
    """

    def __init__(
        self,
        db: Session,
        redis_client: Optional[Any] = None,
        evolution_client: Optional[EvolutionClient] = None,
    ):
        self.db = db
        self.redis = redis_client or get_redis_client()
        self.evolution_client = (
            evolution_client  # Kept for backward compatibility if needed
        )

        # Services
        self.patient_repo = PatientRepository(db)
        self.flow_service = PatientFlowService(db)
        self.whatsapp_service = UnifiedWhatsAppService(db)
        self.message_service = MessageService(db)

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
            idempotency_key: QW-004: Unique key to prevent duplicate requests (optional)

        Returns:
            Created Patient object if successful, None if failed (and compensated)

        Raises:
            LockAcquisitionError: If unable to acquire distributed lock (concurrent request)
        """
        # Generate lock key based on phone number (unique identifier pre-creation)
        # Hash to avoid PII in Redis keys
        # FIX: Normalize phone to E.164-like format before hashing to prevent
        # duplicate patients when phone comes in different formats (e.g.,
        # "11 9876-54321" vs "+55 11 98765-4321" would generate same hash)
        normalized_phone = normalize_phone(patient_data.phone) or patient_data.phone
        phone_hash = hashlib.sha256(normalized_phone.encode()).hexdigest()[:16]
        lock_key = f"saga:onboarding:{str(doctor_id)[:8]}:{phone_hash}"

        # Acquire distributed lock to prevent concurrent saga execution for same patient
        # TTL of 60s covers the entire saga execution with margin
        async with acquire_lock(lock_key, timeout=5.0, ttl=60):
            saga_id = uuid.uuid4()

            # Initialize Saga Record
            # OPTIMIZATION: Use model_dump (Pydantic v2) instead of json.loads(x.json())
            saga = PatientOnboardingSaga(
                id=saga_id,
                doctor_id=doctor_id,
                patient_data=patient_data.model_dump(mode="json"),
                status=SagaStatus.STARTED,
                current_step=0,
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(saga)
            self.db.commit()

            logger.info(
                f"Starting patient onboarding saga {saga_id} for doctor {doctor_id}"
            )

            try:
                # --- STEP 1: Create Patient ---
                patient = await self._step_create_patient(
                    saga, patient_data, doctor_id, idempotency_key
                )
                if not patient:
                    raise Exception("Failed to create patient")

                # --- STEP 2: Initialize Flow ---
                # Note: Skipping STEP_2_FIREBASE_USER_CREATED as it's deprecated/removed
                await self._step_initialize_flow(saga, patient, current_user)

                # --- STEP 3: Send Welcome Message ---
                await self._step_send_welcome_message(saga, patient)

                # --- Complete Saga ---
                saga.status = SagaStatus.COMPLETED
                saga.completed_at = datetime.now(timezone.utc)
                self.db.commit()

                logger.info(f"Saga {saga_id} completed successfully")
                return patient

            except Exception as e:
                logger.error(
                    f"Saga {saga_id} failed with {type(e).__name__}",
                    exc_info=True,
                )

                saga.status = SagaStatus.FAILED
                saga.error_message = str(e)
                saga.error_type = type(e).__name__
                saga.failed_at = datetime.now(timezone.utc)
                self.db.commit()

                # Trigger compensation
                await self._compensate_saga(saga)
                return None

    async def resume_saga(self, saga_id: UUID) -> Dict[str, Any]:
        """
        Resume a failed or interrupted saga.

        Args:
            saga_id: UUID of the saga to resume

        Returns:
            Dict with result status

        Note:
            Uses distributed lock to prevent concurrent resume attempts.
        """
        saga = (
            self.db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.id == saga_id)
            .first()
        )
        if not saga:
            return {"status": "error", "error": "Saga not found"}

        # Acquire lock to prevent concurrent resume
        lock_key = f"saga:resume:{saga.id}"
        try:
            async with acquire_lock(lock_key, timeout=5.0, ttl=60):
                return await self._resume_saga_internal(saga)
        except LockAcquisitionError:
            logger.warning(f"Could not acquire lock for saga resume: {saga.id}")
            return {"status": "error", "error": "Saga resume already in progress"}

    async def _resume_saga_internal(
        self, saga: PatientOnboardingSaga
    ) -> Dict[str, Any]:
        """Internal resume logic (called within lock context)."""

        if saga.status == SagaStatus.COMPLETED:
            return {"status": "completed", "message": "Saga already completed"}

        logger.info(f"Resuming saga {saga.id} from step {saga.current_step}")

        try:
            patient = None
            if saga.patient_id:
                patient = self.patient_repo.get_by_id(saga.patient_id)

            # Recover Patient Data context
            patient_data_dict = saga.patient_data
            # We need to reconstruct PatientCreate but it might be partial if we are mid-way.
            # Actually we mainly need 'patient' object for subsequent steps.

            # Resume logic based on current_step

            # Step 0 -> 1: Create Patient
            if saga.current_step < 1:
                patient_create = PatientCreate(**patient_data_dict)
                patient = await self._step_create_patient(
                    saga, patient_create, saga.doctor_id
                )
                if not patient:
                    raise Exception("Failed to recover patient creation")

            # Step 1 -> 3: Initialize Flow (Skipping Step 2)
            # Mapping: Step 1 completed means we are ready for Flow (Step 3 in Enum)
            # If we are at STEP_1_PATIENT_CREATED (1), we need to do Flow.

            if not patient and saga.patient_id:
                patient = self.patient_repo.get_by_id(saga.patient_id)

            if not patient:
                raise Exception("Patient not found for resumption")

            if saga.current_step < 3:  # Assuming Step 3 is Flow Initialized in Enum
                await self._step_initialize_flow(
                    saga, patient, None
                )  # user context lost, passing None

            if saga.current_step < 4:  # Step 4 is Message Sent
                await self._step_send_welcome_message(saga, patient)

            # Complete
            saga.status = SagaStatus.COMPLETED
            saga.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            return {"status": "completed"}

        except Exception as e:
            logger.error(f"Failed to resume saga {saga.id}: {e}", exc_info=True)
            # Update saga error
            saga.error_message = str(e)
            # Don't change status to FAILED if we want to allow more retries via the external task,
            # but execute_patient_onboarding_saga does set it to FAILED.
            # The caller (task) handles the retry loop.
            self.db.commit()
            return {"status": "failed", "error": str(e)}

    async def _step_create_patient(
        self,
        saga: PatientOnboardingSaga,
        patient_data: PatientCreate,
        doctor_id: UUID,
        idempotency_key: Optional[str] = None,
    ) -> Patient:
        """
        Step 1: Create Patient in DB

        QW-004: Supports idempotency key for duplicate request prevention
        """
        try:
            patient_dict = patient_data.dict(exclude_unset=True)
            metadata = patient_dict.pop("metadata", {})

            # Add doctor_id
            patient_dict["doctor_id"] = doctor_id
            if metadata:
                patient_dict["patient_data"] = metadata

            # QW-004: Add idempotency key if provided
            if idempotency_key:
                patient_dict["idempotency_key"] = idempotency_key

            # Save via Repo (expects dict)
            patient = self.patient_repo.create(patient_dict)

            # Update Saga
            saga.patient_id = patient.id
            saga.current_step = 1  # Mapped to STEP_1_PATIENT_CREATED effectively
            saga.status = SagaStatus.STEP_1_PATIENT_CREATED
            saga.add_log_entry(1, "create_patient", "success")
            self.db.commit()

            return patient

        except Exception as e:
            logger.error(f"Step 1 failed: {type(e).__name__}", exc_info=True)
            saga.add_log_entry(1, "create_patient", "failed", str(e))
            raise e

    async def _step_initialize_flow(
        self, saga: PatientOnboardingSaga, patient: Patient, current_user: Any
    ):
        """Step 2/3: Initialize Flow"""
        try:
            current_user_id = (
                current_user.id
                if current_user and hasattr(current_user, "id")
                else None
            )

            # Initialize default flow
            await self.flow_service.initialize_default_flow(patient, current_user_id)

            # Also activate the patient
            await self.flow_service.activate_patient(patient.id)

            # Update Saga
            saga.current_step = 3  # Mapped to STEP_3_FLOW_INITIALIZED
            saga.status = SagaStatus.STEP_3_FLOW_INITIALIZED
            saga.add_log_entry(3, "initialize_flow", "success")
            self.db.commit()

        except Exception as e:
            logger.error(f"Step 2 (Flow) failed: {type(e).__name__}", exc_info=True)
            saga.add_log_entry(3, "initialize_flow", "failed", str(e))
            raise e

    async def _step_send_welcome_message(
        self, saga: PatientOnboardingSaga, patient: Patient
    ):
        """Step 3/4: Send Welcome Message"""
        try:
            # Try to load from template
            template = (
                self.db.query(MessageTemplate)
                .filter(
                    MessageTemplate.name == "welcome_message", MessageTemplate.is_active
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

            # Schedule Message with idempotência
            scheduled_for = saga.started_at or datetime.now(timezone.utc)
            if scheduled_for.tzinfo is None:
                scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
            message = self.message_service.schedule_message(
                patient_id=patient.id,
                content=message_content,
                scheduled_for=scheduled_for,
                message_type=MessageType.TEXT,
                message_metadata={"message_type": "welcome", "saga_id": str(saga.id)},
            )

            # Send via Unified Service (usa paciente do relacionamento lazy)
            success = False
            send_error = None
            try:
                success = await self.whatsapp_service.send_message(message)
            except Exception as send_exc:
                send_error = send_exc
                logger.warning(
                    f"Saga {saga.id}: Welcome message send failed (non-fatal): {type(send_exc).__name__}",
                    exc_info=True,
                )

            if success:
                try:
                    self.message_service.mark_as_sent(message.id, "queued")
                except Exception as mark_exc:
                    logger.warning(
                        f"Saga {saga.id}: Failed to mark welcome message as sent: {type(mark_exc).__name__}",
                        exc_info=True,
                    )
            else:
                try:
                    # Keep welcome message in PENDING so retry_pending_welcome_messages can pick it up
                    message.status = MessageStatus.PENDING
                    message.message_metadata = {
                        **(message.message_metadata or {}),
                        "welcome_send_failed": True,
                        "welcome_send_error_type": type(send_error).__name__
                        if send_error
                        else None,
                        "welcome_send_failed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    self.db.commit()
                except Exception as update_exc:
                    logger.warning(
                        f"Saga {saga.id}: Failed to keep welcome message pending: {type(update_exc).__name__}",
                        exc_info=True,
                    )

            # Update Saga (welcome sending is best-effort; do not fail onboarding)
            saga.current_step = 4  # Mapped to STEP_4_MESSAGE_SENT
            saga.status = SagaStatus.STEP_4_MESSAGE_SENT
            if success:
                saga.add_log_entry(4, "send_message", "success")
            else:
                saga.add_log_entry(
                    4,
                    "send_message",
                    "failed_nonfatal",
                    str(send_error) if send_error else "send_message returned False",
                )
            self.db.commit()

        except Exception as e:
            logger.error(f"Step 3 (Message) failed: {type(e).__name__}", exc_info=True)
            saga.current_step = 4  # Step attempted; non-fatal
            saga.status = SagaStatus.STEP_4_MESSAGE_SENT
            saga.add_log_entry(4, "send_message", "failed_nonfatal", str(e))
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
            return

    async def _track_compensation_failure(
        self, saga_id: UUID, step: int, error: Exception
    ):
        """
        Track compensation failures for audit and manual recovery.

        QW-002: Proper error tracking for compensation failures

        Args:
            saga_id: UUID of the saga
            step: Step number that failed
            error: Exception that occurred
        """
        try:
            if self.redis:
                # Store compensation failure in Redis for monitoring
                failure_key = f"saga:compensation_failure:{saga_id}"
                failure_data = {
                    "saga_id": str(saga_id),
                    "step": step,
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self.redis.setex(
                    failure_key, 86400 * 7, json.dumps(failure_data)
                )  # 7 days retention
                logger.warning(f"Compensation failure tracked in Redis: {failure_key}")
        except Exception as redis_error:
            logger.error(
                f"Failed to track compensation failure in Redis: {redis_error}"
            )

    async def _compensate_saga(self, saga: PatientOnboardingSaga):
        """
        Execute compensation steps in reverse order with atomic transaction.

        QW-002: Enhanced error propagation and tracking for compensation failures.

        ATOMIC COMPENSATION:
        - All compensation steps are executed within a single transaction
        - If any step fails with retry exhausted, we rollback and track failure
        - Uses distributed lock to prevent concurrent compensation
        - Each step has its own retry logic with exponential backoff
        """
        # Acquire compensation lock to prevent concurrent compensations
        lock_key = f"saga:compensate:{saga.id}"
        try:
            async with acquire_lock(lock_key, timeout=5.0, ttl=120):
                await self._compensate_saga_internal(saga)
        except LockAcquisitionError:
            logger.warning(f"Saga {saga.id}: Compensation already in progress")
            return

    async def _compensate_saga_internal(self, saga: PatientOnboardingSaga):
        """Internal compensation logic within lock context."""
        logger.info(f"Compensating saga {saga.id} from step {saga.current_step}")
        saga.status = SagaStatus.COMPENSATING
        # Don't commit yet - we want atomic transaction

        compensation_errors = []

        try:
            # Step 4 Compensation: Mark Message as Cancelled (Best Effort)
            # WhatsApp messages can't be unsent, but we mark as cancelled in DB
            if saga.current_step >= 4:
                await self._compensate_step_with_retry(
                    saga=saga,
                    step_num=4,
                    step_name="compensate_message",
                    compensate_fn=self._compensate_message,
                    compensation_errors=compensation_errors,
                )

            # Step 3 Compensation: Delete/Deactivate Flow
            if saga.current_step >= 3:
                await self._compensate_step_with_retry(
                    saga=saga,
                    step_num=3,
                    step_name="compensate_flow",
                    compensate_fn=self._compensate_flow,
                    compensation_errors=compensation_errors,
                )

            # Step 1 Compensation: Delete Patient
            if saga.current_step >= 1 and saga.patient_id:
                await self._compensate_step_with_retry(
                    saga=saga,
                    step_num=1,
                    step_name="compensate_patient",
                    compensate_fn=self._compensate_patient,
                    compensation_errors=compensation_errors,
                )

            saga.status = SagaStatus.FAILED  # End state
            # Atomic commit of all compensations
            self.db.commit()

            # QW-002: Raise compensation errors if any occurred
            if compensation_errors:
                error_details = "; ".join(
                    [f"{step}: {str(err)}" for step, err in compensation_errors]
                )
                raise SagaCompensationError(
                    f"Saga {saga.id} compensation failed with {len(compensation_errors)} error(s): {error_details}",
                    original_error=compensation_errors[0][1],
                    saga_id=saga.id,
                )

        except SagaCompensationError:
            # Re-raise SagaCompensationError to propagate properly
            raise
        except Exception as e:
            logger.error(f"Critical error during compensation: {e}", exc_info=True)
            await self._track_compensation_failure(saga.id, 0, e)
            raise SagaCompensationError(
                f"Critical compensation error for saga {saga.id}: {str(e)}",
                original_error=e,
                saga_id=saga.id,
            )

    async def _compensate_step_with_retry(
        self,
        saga: PatientOnboardingSaga,
        step_num: int,
        step_name: str,
        compensate_fn,
        compensation_errors: List[Tuple[int, Exception]],
        max_retries: int = 3,
    ):
        """
        Execute a compensation step with retry logic.

        QW-002: Implements exponential backoff for transient failures.

        Args:
            saga: The saga being compensated
            step_num: Step number for logging
            step_name: Name of the compensation step
            compensate_fn: Async function to execute for compensation
            compensation_errors: List to append errors to
            max_retries: Maximum number of retry attempts
        """
        import asyncio

        last_error = None
        for attempt in range(max_retries):
            try:
                await compensate_fn(saga)
                saga.add_log_entry(step_num, step_name, "compensated")
                logger.info(
                    f"Saga {saga.id}: {step_name} compensation succeeded on attempt {attempt + 1}"
                )
                return  # Success
            except Exception as e:
                last_error = e
                wait_time = (2**attempt) * 0.5  # 0.5s, 1s, 2s
                logger.warning(
                    f"Saga {saga.id}: {step_name} compensation attempt {attempt + 1}/{max_retries} "
                    f"failed: {e}. Retrying in {wait_time}s..."
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)

        # All retries exhausted
        logger.error(
            f"Saga {saga.id}: {step_name} compensation failed after {max_retries} attempts"
        )
        saga.add_log_entry(step_num, step_name, "compensation_failed", str(last_error))
        compensation_errors.append((step_num, last_error))
        await self._track_compensation_failure(saga.id, step_num, last_error)

    async def _compensate_message(self, saga: PatientOnboardingSaga):
        """
        Compensate Step 4: Mark welcome message as cancelled.

        Note: WhatsApp messages cannot be unsent, but we mark as cancelled
        in our database for audit trail and to prevent retries.
        """
        try:
            # Find messages sent by this saga
            # Note: Using JSONB key access with .astext for reliable comparison
            messages = (
                self.db.query(Message)
                .filter(
                    Message.patient_id == saga.patient_id,
                    Message.message_metadata["saga_id"].astext == str(saga.id),
                )
                .all()
            )

            for message in messages:
                message.status = MessageStatus.CANCELLED
                message.message_metadata = {
                    **(message.message_metadata or {}),
                    "cancelled_by": "saga_compensation",
                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                }

            if messages:
                logger.info(
                    f"Saga {saga.id}: Marked {len(messages)} message(s) as cancelled"
                )
            else:
                logger.info(f"Saga {saga.id}: No messages found to compensate")

        except Exception as e:
            logger.error(f"Saga {saga.id}: Message compensation error: {e}")
            raise

    async def _compensate_flow(self, saga: PatientOnboardingSaga):
        """
        Compensate Step 3: Delete or deactivate flow state.

        Removes the flow state created for the patient to ensure
        clean state for any future retry.
        """
        try:
            if not saga.patient_id:
                logger.info(f"Saga {saga.id}: No patient_id to compensate flow")
                return

            # Find and delete flow states for this patient
            flow_states = (
                self.db.query(PatientFlowState)
                .filter(PatientFlowState.patient_id == saga.patient_id)
                .all()
            )

            for flow_state in flow_states:
                self.db.delete(flow_state)

            if flow_states:
                logger.info(f"Saga {saga.id}: Deleted {len(flow_states)} flow state(s)")
            else:
                logger.info(f"Saga {saga.id}: No flow states found to compensate")

        except Exception as e:
            logger.error(f"Saga {saga.id}: Flow compensation error: {e}")
            raise

    async def _compensate_patient(self, saga: PatientOnboardingSaga):
        """
        Compensate Step 1: Delete patient record.

        This is a hard delete since the patient was never fully onboarded.
        For LGPD compliance, we ensure all related data is also removed.
        """
        try:
            if not saga.patient_id:
                logger.info(f"Saga {saga.id}: No patient_id to compensate")
                return

            patient = self.patient_repo.get_by_id(saga.patient_id)
            if not patient:
                logger.info(
                    f"Saga {saga.id}: Patient {saga.patient_id} already deleted"
                )
                return

            # Use repository's delete which handles cascades properly
            # Note: Related messages and flow_states should already be compensated
            self.db.delete(patient)

            logger.info(f"Saga {saga.id}: Deleted patient {saga.patient_id}")

        except Exception as e:
            logger.error(f"Saga {saga.id}: Patient compensation error: {e}")
            raise

    async def get_saga_status(self, saga_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get current status of a saga for monitoring.

        Args:
            saga_id: UUID of the saga

        Returns:
            Dict with saga status info or None if not found
        """
        saga = (
            self.db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.id == saga_id)
            .first()
        )

        if not saga:
            return None

        return {
            "id": str(saga.id),
            "status": saga.status.value if saga.status else None,
            "current_step": saga.current_step,
            "patient_id": str(saga.patient_id) if saga.patient_id else None,
            "doctor_id": str(saga.doctor_id) if saga.doctor_id else None,
            "started_at": saga.started_at.isoformat() if saga.started_at else None,
            "completed_at": saga.completed_at.isoformat()
            if saga.completed_at
            else None,
            "failed_at": saga.failed_at.isoformat() if saga.failed_at else None,
            "error_message": saga.error_message,
            "error_type": saga.error_type,
            "execution_log": saga.execution_log,
        }

    async def list_failed_sagas(
        self, doctor_id: Optional[UUID] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List failed sagas for manual review or retry.

        Args:
            doctor_id: Optional filter by doctor
            limit: Maximum number of results

        Returns:
            List of failed saga summaries
        """
        query = self.db.query(PatientOnboardingSaga).filter(
            PatientOnboardingSaga.status == SagaStatus.FAILED
        )

        if doctor_id:
            query = query.filter(PatientOnboardingSaga.doctor_id == doctor_id)

        query = query.order_by(PatientOnboardingSaga.failed_at.desc()).limit(limit)
        sagas = query.all()

        return [
            {
                "id": str(s.id),
                "doctor_id": str(s.doctor_id) if s.doctor_id else None,
                "current_step": s.current_step,
                "error_message": s.error_message,
                "error_type": s.error_type,
                "failed_at": s.failed_at.isoformat() if s.failed_at else None,
                "retry_count": s.retry_count,
            }
            for s in sagas
        ]
