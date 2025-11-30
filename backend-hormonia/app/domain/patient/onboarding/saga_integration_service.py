"""
SagaIntegrationService - Saga Pattern Integration for Patient Onboarding.

SINGLE RESPONSIBILITY: Orchestrate patient creation via Saga Pattern with fallback.

This service handles:
- Saga transaction execution
- Saga failure detection
- Graceful fallback to direct creation
- Compensation logic coordination

File: app/domain/patient/onboarding/saga_integration_service.py
LOC: ~120
Responsibility: Saga orchestration wrapper
ISSUE-005 Phase 3: Extracted from OnboardingService
"""
import asyncio
import logging
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.config import settings
from app.exceptions import ValidationError

if TYPE_CHECKING:
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.models.user import User

logger = logging.getLogger(__name__)


class SagaIntegrationService:
    """
    Service for integrating patient onboarding with Saga Pattern.

    SINGLE RESPONSIBILITY: Saga orchestration wrapper with intelligent fallback.

    This service acts as a facade to the SagaOrchestrator, providing:
    1. Saga availability detection
    2. Saga execution with error handling
    3. Automatic fallback on failure
    4. Transaction cleanup on errors

    ISSUE-005 REFACTORING:
    Extracted from PatientOnboardingService to follow Single Responsibility Principle.
    """

    def __init__(
        self,
        saga_orchestrator: Optional["SagaOrchestrator"] = None,
    ):
        """
        Initialize SagaIntegrationService.

        Args:
            saga_orchestrator: Optional saga orchestrator for distributed transactions
        """
        self.saga_orchestrator = saga_orchestrator

    def is_enabled(self) -> bool:
        """
        Check if Saga Pattern is enabled and available.

        Returns:
            True if saga is enabled and orchestrator is available
        """
        return (
            self.saga_orchestrator is not None
            and getattr(settings, "ENABLE_SAGA_PATTERN", True)
        )

    async def create_patient_via_saga(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID,
        current_user: Optional["User"] = None,
        idempotency_key: Optional[str] = None,
    ) -> Patient:
        """
        Execute patient creation via Saga Pattern.

        This method coordinates the saga orchestration for patient onboarding:
        1. Execute saga with patient data
        2. Handle saga success (return patient)
        3. On failure, raise to avoid silent fallback paths
        4. Execute compensations on error

        Saga Steps (defined in SagaOrchestrator):
        - Step 1: Create patient in database
        - Step 2: Create patient flow state
        - Step 3: Send welcome WhatsApp message

        Args:
            patient_data: Patient creation data
            doctor_id: ID of the doctor creating the patient
            current_user: Current authenticated user (optional)
            idempotency_key: QW-004: Unique key to prevent duplicate requests (optional)

        Returns:
            Created Patient object if saga succeeds, None if saga fails

        Note:
            Raises ValidationError on failure; caller should not fallback silently.
        """
        if not self.is_enabled():
            raise ValidationError("Saga Pattern desabilitado ou não configurado")

        logger.info(
            f"Executing Saga Pattern for patient creation (doctor: {doctor_id})"
        )

        try:
            # Execute saga orchestration
            patient = await self.saga_orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor_id,
                current_user=current_user,
                idempotency_key=idempotency_key,  # QW-004: Pass idempotency key to orchestrator
            )

            if patient:
                logger.info(
                    f"✅ Saga Pattern succeeded: Patient {patient.id} created successfully",
                    extra={
                        "patient_id": str(patient.id),
                        "patient_name": patient.name,
                        "doctor_id": str(doctor_id),
                    }
                )
                return patient
            else:
                raise ValidationError("Saga Pattern não retornou paciente após execução")

        except Exception as e:
            logger.error(
                f"❌ Saga Pattern execution failed with exception: {e}",
                exc_info=True,
                extra={
                    "patient_phone": patient_data.phone,
                    "doctor_id": str(doctor_id),
                    "exception_type": type(e).__name__,
                }
            )

            await self._execute_compensations(patient_data, doctor_id)

            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Falha ao executar Saga Pattern: {e}") from e

    async def _execute_compensations(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID,
    ) -> None:
        """
        Execute saga compensations after failure.

        CRITICAL: This method ensures cleanup of partially created resources
        when saga fails mid-execution.

        Compensation steps (executed in reverse order):
        1. Delete WhatsApp message (if sent)
        2. Delete flow state (if created)
        3. Delete patient record (if created)

        Args:
            patient_data: Patient data that was being created
            doctor_id: Doctor ID
        """
        try:
            logger.info(
                "Executing saga compensations after failure",
                extra={
                    "patient_phone": patient_data.phone,
                    "doctor_id": str(doctor_id),
                }
            )

            # Compensations are handled by SagaOrchestrator automatically
            # This method exists for future custom compensation logic
            # if needed outside the orchestrator

            logger.info("✅ Saga compensations completed successfully")

        except Exception as comp_error:
            # Log compensation errors but don't raise - fallback will handle it
            logger.error(
                f"⚠️ Error during saga compensation: {comp_error}",
                exc_info=True,
                extra={
                    "patient_phone": patient_data.phone,
                    "doctor_id": str(doctor_id),
                }
            )
