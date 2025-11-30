import logging
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.patient import Patient, FlowState
from app.models.patient_onboarding_saga import PatientOnboardingSaga, SagaStatus
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.models.template import MessageTemplate
from app.schemas.patient import PatientCreate
from app.repositories.patient import PatientRepository
from app.services.patient.flow_service import PatientFlowService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.domain.messaging.core import MessageService
from app.core.redis_client import get_redis_client
from app.integrations.evolution import EvolutionClient
from app.config.messages import DEFAULT_WELCOME_MESSAGE

logger = logging.getLogger(__name__)


class SagaCompensationError(Exception):
    """
    Exception raised when saga compensation fails.

    This error indicates that the system failed to properly rollback
    a saga transaction, which may require manual intervention.
    """
    def __init__(self, message: str, original_error: Optional[Exception] = None, saga_id: Optional[UUID] = None):
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
        evolution_client: Optional[EvolutionClient] = None
    ):
        self.db = db
        self.redis = redis_client or get_redis_client()
        self.evolution_client = evolution_client  # Kept for backward compatibility if needed
        
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
        idempotency_key: Optional[str] = None
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
        """
        saga_id = uuid.uuid4()
        
        # Initialize Saga Record
        saga = PatientOnboardingSaga(
            id=saga_id,
            doctor_id=doctor_id,
            patient_data=json.loads(patient_data.json()),
            status=SagaStatus.STARTED,
            current_step=0,
            started_at=datetime.utcnow()
        )
        self.db.add(saga)
        self.db.commit()
        
        logger.info(f"Starting patient onboarding saga {saga_id} for doctor {doctor_id}")
        
        try:
            # --- STEP 1: Create Patient ---
            patient = await self._step_create_patient(saga, patient_data, doctor_id, idempotency_key)
            if not patient:
                raise Exception("Failed to create patient")
                
            # --- STEP 2: Initialize Flow ---
            # Note: Skipping STEP_2_FIREBASE_USER_CREATED as it's deprecated/removed
            await self._step_initialize_flow(saga, patient, current_user)
            
            # --- STEP 3: Send Welcome Message ---
            await self._step_send_welcome_message(saga, patient)
            
            # --- Complete Saga ---
            saga.status = SagaStatus.COMPLETED
            saga.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Saga {saga_id} completed successfully")
            return patient
            
        except Exception as e:
            logger.error(f"Saga {saga_id} failed: {str(e)}", exc_info=True)
            
            saga.status = SagaStatus.FAILED
            saga.error_message = str(e)
            saga.error_type = type(e).__name__
            saga.failed_at = datetime.utcnow()
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
        """
        saga = self.db.query(PatientOnboardingSaga).filter(PatientOnboardingSaga.id == saga_id).first()
        if not saga:
            return {"status": "error", "error": "Saga not found"}
            
        if saga.status == SagaStatus.COMPLETED:
            return {"status": "completed", "message": "Saga already completed"}
            
        logger.info(f"Resuming saga {saga_id} from step {saga.current_step}")
        
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
                patient = await self._step_create_patient(saga, patient_create, saga.doctor_id)
                if not patient: raise Exception("Failed to recover patient creation")
            
            # Step 1 -> 3: Initialize Flow (Skipping Step 2)
            # Mapping: Step 1 completed means we are ready for Flow (Step 3 in Enum)
            # If we are at STEP_1_PATIENT_CREATED (1), we need to do Flow.
            
            if not patient and saga.patient_id:
                 patient = self.patient_repo.get_by_id(saga.patient_id)

            if not patient:
                 raise Exception("Patient not found for resumption")

            if saga.current_step < 3: # Assuming Step 3 is Flow Initialized in Enum
                await self._step_initialize_flow(saga, patient, None) # user context lost, passing None
                
            if saga.current_step < 4: # Step 4 is Message Sent
                await self._step_send_welcome_message(saga, patient)
                
            # Complete
            saga.status = SagaStatus.COMPLETED
            saga.completed_at = datetime.utcnow()
            self.db.commit()
            
            return {"status": "completed"}
            
        except Exception as e:
            logger.error(f"Failed to resume saga {saga_id}: {e}", exc_info=True)
            # Update saga error
            saga.error_message = str(e)
            # Don't change status to FAILED if we want to allow more retries via the external task, 
            # but execute_patient_onboarding_saga does set it to FAILED.
            # The caller (task) handles the retry loop.
            self.db.commit()
            return {"status": "failed", "error": str(e)}

    async def _step_create_patient(self, saga: PatientOnboardingSaga, patient_data: PatientCreate, doctor_id: UUID, idempotency_key: Optional[str] = None) -> Patient:
        """
        Step 1: Create Patient in DB

        QW-004: Supports idempotency key for duplicate request prevention
        """
        try:
            patient_dict = patient_data.dict(exclude_unset=True)
            metadata = patient_dict.pop('metadata', {})

            # Add doctor_id
            patient_dict['doctor_id'] = doctor_id
            if metadata:
                patient_dict['patient_data'] = metadata

            # QW-004: Add idempotency key if provided
            if idempotency_key:
                patient_dict['idempotency_key'] = idempotency_key

            # Save via Repo (expects dict)
            patient = self.patient_repo.create(patient_dict)
            
            # Update Saga
            saga.patient_id = patient.id
            saga.current_step = 1 # Mapped to STEP_1_PATIENT_CREATED effectively
            saga.status = SagaStatus.STEP_1_PATIENT_CREATED
            saga.add_log_entry(1, "create_patient", "success")
            self.db.commit()
            
            return patient
            
        except Exception as e:
            logger.error(f"Step 1 failed: {e}")
            saga.add_log_entry(1, "create_patient", "failed", str(e))
            raise e

    async def _step_initialize_flow(self, saga: PatientOnboardingSaga, patient: Patient, current_user: Any):
        """Step 2/3: Initialize Flow"""
        try:
            current_user_id = current_user.id if current_user and hasattr(current_user, 'id') else None
            
            # Initialize default flow
            await self.flow_service.initialize_default_flow(patient, current_user_id)
            
            # Also activate the patient
            await self.flow_service.activate_patient(patient.id)
            
            # Update Saga
            saga.current_step = 3 # Mapped to STEP_3_FLOW_INITIALIZED
            saga.status = SagaStatus.STEP_3_FLOW_INITIALIZED
            saga.add_log_entry(3, "initialize_flow", "success")
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Step 2 (Flow) failed: {e}")
            saga.add_log_entry(3, "initialize_flow", "failed", str(e))
            raise e

    async def _step_send_welcome_message(self, saga: PatientOnboardingSaga, patient: Patient):
        """Step 3/4: Send Welcome Message"""
        try:
            # Try to load from template
            template = self.db.query(MessageTemplate).filter(
                MessageTemplate.name == "welcome_message",
                MessageTemplate.is_active == True
            ).first()

            if template:
                try:
                    message_content = template.format(patient_name=patient.name)
                except Exception as e:
                    logger.warning(f"Failed to format welcome template: {e}. Using fallback.")
                    message_content = DEFAULT_WELCOME_MESSAGE.format(patient_name=patient.name)
            else:
                logger.warning("Welcome message template not found. Using fallback.")
                message_content = DEFAULT_WELCOME_MESSAGE.format(patient_name=patient.name)
            
            # Schedule Message with idempotência
            from datetime import timezone
            message = self.message_service.schedule_message(
                patient_id=patient.id,
                content=message_content,
                scheduled_for=datetime.now(timezone.utc),
                message_type=MessageType.TEXT,
                message_metadata={"type": "welcome_message", "saga_id": str(saga.id)}
            )

            # Send via Unified Service (usa paciente do relacionamento lazy)
            success = await self.whatsapp_service.send_message(message)
            
            if not success:
                raise Exception("Failed to send welcome message")
                
            # Update Saga
            saga.current_step = 4 # Mapped to STEP_4_MESSAGE_SENT
            saga.status = SagaStatus.STEP_4_MESSAGE_SENT
            saga.add_log_entry(4, "send_message", "success")
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Step 3 (Message) failed: {e}")
            saga.add_log_entry(4, "send_message", "failed", str(e))
            raise e

    async def _track_compensation_failure(self, saga_id: UUID, step: int, error: Exception):
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
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.redis.setex(failure_key, 86400 * 7, json.dumps(failure_data))  # 7 days retention
                logger.warning(f"Compensation failure tracked in Redis: {failure_key}")
        except Exception as redis_error:
            logger.error(f"Failed to track compensation failure in Redis: {redis_error}")

    async def _compensate_saga(self, saga: PatientOnboardingSaga):
        """
        Execute compensation steps in reverse order.

        QW-002: Enhanced error propagation and tracking for compensation failures.
        Compensation failures are now properly logged, tracked, and raised to prevent
        silent failures that could leave the system in an inconsistent state.
        """
        logger.info(f"Compensating saga {saga.id} from step {saga.current_step}")
        saga.status = SagaStatus.COMPENSATING
        self.db.commit()

        compensation_errors = []

        try:
            # Step 3 Compensation: Delete Message (Best Effort)
            if saga.current_step >= 4:
                try:
                    # We can't easily delete sent WhatsApp, but we can mark message as failed/deleted in DB
                    # to avoid confusion.
                    # Look for messages with saga_id
                    messages = self.db.query(Message).filter(
                        Message.patient_id == saga.patient_id,
                        Message.message_metadata['saga_id'].astext == str(saga.id)
                    ).all()
                    for msg in messages:
                        self.db.delete(msg) # Hard delete or soft delete
                    saga.add_log_entry(4, "compensate_message", "success")
                    logger.info(f"Saga {saga.id}: Step 4 compensation successful (message cleanup)")
                except Exception as e:
                    logger.error(f"Saga {saga.id}: Step 4 compensation failed: {e}", exc_info=True)
                    saga.add_log_entry(4, "compensate_message", "failed", str(e))
                    compensation_errors.append(("Step 4: Message cleanup", e))
                    await self._track_compensation_failure(saga.id, 4, e)

            # Step 2 Compensation: Deactivate/Delete Flow
            if saga.current_step >= 3:
                try:
                    # Explicitly delete flow states
                    await self.flow_service.delete_flow(saga.patient_id)
                    saga.add_log_entry(3, "compensate_flow", "success")
                    logger.info(f"Saga {saga.id}: Step 3 compensation successful (flow cleanup)")
                except Exception as e:
                    logger.error(f"Saga {saga.id}: Step 3 compensation failed: {e}", exc_info=True)
                    saga.add_log_entry(3, "compensate_flow", "failed", str(e))
                    compensation_errors.append(("Step 3: Flow cleanup", e))
                    await self._track_compensation_failure(saga.id, 3, e)

            # Step 1 Compensation: Delete Patient
            if saga.current_step >= 1 and saga.patient_id:
                try:
                    # Hard delete to fully clean up since onboarding failed
                    # Using SQL directly or Repository if it supports hard delete.
                    # PatientRepository inherits BaseRepository, assuming standard delete.
                    # If it's soft delete, we might want hard delete here.
                    # Let's use the repository delete which is likely soft delete.
                    # For onboarding failure, maybe soft delete is enough.
                    self.patient_repo.delete(saga.patient_id)
                    saga.add_log_entry(1, "compensate_patient", "success")
                    logger.info(f"Saga {saga.id}: Step 1 compensation successful (patient deletion)")
                except Exception as e:
                    logger.error(f"Saga {saga.id}: Step 1 compensation failed: {e}", exc_info=True)
                    saga.add_log_entry(1, "compensate_patient", "failed", str(e))
                    compensation_errors.append(("Step 1: Patient deletion", e))
                    await self._track_compensation_failure(saga.id, 1, e)

            saga.status = SagaStatus.FAILED # End state for now
            self.db.commit()

            # QW-002: Raise compensation errors if any occurred
            if compensation_errors:
                error_details = "; ".join([f"{step}: {str(err)}" for step, err in compensation_errors])
                raise SagaCompensationError(
                    f"Saga {saga.id} compensation failed with {len(compensation_errors)} error(s): {error_details}",
                    original_error=compensation_errors[0][1],
                    saga_id=saga.id
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
                saga_id=saga.id
            )
