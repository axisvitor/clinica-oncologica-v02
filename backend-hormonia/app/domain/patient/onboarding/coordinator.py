"""
OnboardingCoordinator - High-level patient onboarding orchestration.

This coordinator orchestrates the complete patient onboarding workflow
by coordinating between specialized services.

File: app/domain/patient/onboarding/coordinator.py
LOC: ~100
Responsibility: Workflow orchestration ONLY

ISSUE-005 Phase 5 (FINAL):
- Orchestrates ValidationService, SagaIntegrationService, NotificationService, CompletionService
- NO business logic - pure coordination
- 100% dependency injection
- Single point of entry for patient onboarding
"""
from typing import Optional, TYPE_CHECKING
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError
from app.utils.db_retry import with_db_retry

if TYPE_CHECKING:
    from app.models.user import User
    from app.services.patient.integrity_service import PatientIntegrityService
    from app.domain.patient.onboarding.validation_service import ValidationService
    from app.domain.patient.onboarding.saga_integration_service import SagaIntegrationService
    from app.domain.patient.onboarding.notification_service import NotificationService
    from app.domain.patient.onboarding.completion_service import CompletionService
    from app.domain.patient.onboarding.creation_service import CreationService

logger = logging.getLogger(__name__)


class OnboardingCoordinator:
    """
    Coordinator for patient onboarding workflow.

    SINGLE RESPONSIBILITY: Orchestrate service calls in correct order.

    This coordinator has NO business logic - it only:
    1. Validates patient data (via IntegrityService)
    2. Attempts saga creation (via SagaIntegrationService)
    3. Falls back to direct creation (via CreationService)
    4. Sends notifications (via NotificationService)
    5. Completes partial onboarding (via CompletionService)

    CRITICAL: This is a COORDINATOR, not a SERVICE.
    All business logic is delegated to specialized services.
    """

    def __init__(
        self,
        db: Session,
        integrity_service: "PatientIntegrityService",
        validation_service: "ValidationService",
        saga_service: "SagaIntegrationService",
        notification_service: "NotificationService",
        completion_service: "CompletionService",
        creation_service: Optional["CreationService"] = None,
    ):
        """
        Initialize OnboardingCoordinator with dependency injection.

        100% DEPENDENCY INJECTION - all services injected via constructor.

        Args:
            db: Database session
            integrity_service: Service for patient data validation (SINGLE SOURCE OF TRUTH)
            validation_service: Service for duplicate detection
            saga_service: Service for saga pattern orchestration
            notification_service: Service for notification delivery
            completion_service: Service for partial onboarding completion
            creation_service: Optional service for direct patient creation
        """
        self.db = db
        self.integrity_service = integrity_service
        self.validation_service = validation_service
        self.saga_service = saga_service
        self.notification_service = notification_service
        self.completion_service = completion_service
        self.creation_service = creation_service

    @with_db_retry(max_retries=3)
    async def create_patient(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID,
        current_user: Optional["User"] = None,
        idempotency_key: Optional[str] = None,
    ) -> Patient:
        """
        Orchestrate patient creation workflow.

        Workflow:
        1. Validar dados do paciente (IntegrityService)
        2. Executar Saga Pattern (obrigatório); em caso de falha, erro explícito
        3. Notificações/fluxos são tratados pela própria saga

        Args:
            patient_data: Patient creation data
            doctor_id: ID of the doctor creating the patient
            current_user: Current authenticated user (optional)
            idempotency_key: QW-004: Unique key to prevent duplicate requests (optional)

        Returns:
            Created patient object

        Raises:
            ValidationError: If validation fails
            IntegrityError: If database integrity constraints are violated
        """
        # Step 1: Validate data using SINGLE SOURCE OF TRUTH
        await self.integrity_service.validate_patient_data(
            patient_data=patient_data,
            doctor_id=doctor_id,
            is_update=False
        )
        logger.info(f"Patient data validated for doctor {doctor_id}")

        # Step 2: Execução obrigatória via Saga Pattern
        if not self.saga_service.is_enabled():
            raise ValidationError("Saga Pattern desabilitado ou não configurado")

        logger.info(f"Attempting patient creation via Saga Pattern for doctor {doctor_id}")
        patient = await self.saga_service.create_patient_via_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
            current_user=current_user,
            idempotency_key=idempotency_key,  # QW-004: Pass idempotency key to saga
        )

        if not patient:
            raise ValidationError("Falha ao criar paciente via Saga Pattern")

        logger.info(
            f"Patient created successfully via Saga: {patient.id} - {patient.name}"
        )
        return patient

    async def _create_patient_direct(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID,
        current_user: Optional["User"] = None,
    ) -> Patient:
        """
        Direct patient creation workflow (saga fallback).

        Workflow:
        1. Check for existing patient (ValidationService)
        2. If exists: Complete partial onboarding (CompletionService)
        3. If not exists: Create new patient (CreationService)
        4. Send notifications (NotificationService)

        Args:
            patient_data: Patient creation data
            doctor_id: Doctor ID
            current_user: Current authenticated user

        Returns:
            Created or updated patient object
        """
        # Step 1: Check for existing patient (prevent duplicates)
        existing_patient = await self.validation_service.find_existing_patient(
            cpf=patient_data.cpf,
            email=patient_data.email,
            phone=patient_data.phone,
            doctor_id=doctor_id
        )

        if existing_patient:
            logger.warning(
                f"Patient already exists: {existing_patient.id}, completing onboarding",
                extra={
                    "patient_id": str(existing_patient.id),
                    "doctor_id": str(doctor_id)
                }
            )
            # Step 2: Complete partial onboarding
            patient = await self.completion_service.complete_partial_onboarding(
                existing_patient=existing_patient,
                patient_data=patient_data,
                current_user=current_user
            )
            return patient

        # Step 3: Create new patient via CreationService
        if not self.creation_service:
            # Fallback to inline creation if CreationService not provided
            from app.domain.patient.onboarding.creation_service import CreationService
            from concurrent.futures import ThreadPoolExecutor

            _executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="coordinator_sync")
            self.creation_service = CreationService(
                db=self.db,
                integrity_service=self.integrity_service,
                completion_service=self.completion_service,
                notification_service=self.notification_service,
                validation_service=self.validation_service,
                executor=_executor,
            )

        patient = await self.creation_service.create_patient_direct(
            patient_data=patient_data,
            doctor_id=doctor_id,
            current_user=current_user
        )

        return patient
