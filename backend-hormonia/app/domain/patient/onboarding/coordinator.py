"""
OnboardingCoordinator - High-level patient onboarding orchestration.

This coordinator orchestrates the complete patient onboarding workflow
by coordinating between specialized services.

File: app/domain/patient/onboarding/coordinator.py
LOC: ~100
Responsibility: Workflow orchestration ONLY

ISSUE-005 Phase 5 (FINAL):
- Orchestrates ValidationService, SagaOrchestrator, NotificationService, CompletionService
- NO business logic - pure coordination
- 100% dependency injection
- Single point of entry for patient onboarding

Phase 2 Simplification:
- Removed SagaIntegrationService wrapper (0% business logic)
- Now calls SagaOrchestrator directly
"""

from __future__ import annotations

# Standard library imports
import logging
from typing import TYPE_CHECKING, Optional
from uuid import UUID

# Third-party imports
from sqlalchemy.orm import Session

# Local application imports
from app.config import settings
from app.exceptions import ValidationError
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.utils.db_retry import with_db_retry

if TYPE_CHECKING:
    from app.domain.patient.onboarding.completion_service import CompletionService
    from app.domain.patient.onboarding.creation_service import CreationService
    from app.domain.patient.onboarding.notification_service import NotificationService
    from app.domain.patient.onboarding.validation_service import ValidationService
    from app.models.user import User
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.services.patient.integrity_service import PatientIntegrityService


class OnboardingCoordinator:
    """
    Coordinator for patient onboarding workflow.

    SINGLE RESPONSIBILITY: Orchestrate service calls in correct order.

    This coordinator has NO business logic - it only:
    1. Validates patient data (via IntegrityService)
    2. Executes saga pattern (via SagaOrchestrator directly)
    3. Sends notifications (via NotificationService)
    4. Completes partial onboarding (via CompletionService)

    CRITICAL: This is a COORDINATOR, not a SERVICE.
    All business logic is delegated to specialized services.

    Phase 2 Simplification:
    - Removed SagaIntegrationService wrapper (0% business logic)
    - Now calls SagaOrchestrator directly

    Attributes:
        db: Database session.
        integrity_service: Service for patient data validation.
        validation_service: Service for duplicate detection.
        saga_orchestrator: Saga orchestrator for distributed transactions.
        notification_service: Service for notification delivery.
        completion_service: Service for partial onboarding completion.
        creation_service: Optional service for direct patient creation.
        _logger: Service logger (private).
    """

    def __init__(
        self,
        db: Session,
        integrity_service: "PatientIntegrityService",
        validation_service: "ValidationService",
        saga_orchestrator: Optional["SagaOrchestrator"],
        notification_service: Optional["NotificationService"],
        completion_service: "CompletionService",
        creation_service: Optional["CreationService"] = None,
    ):
        """
        Initialize OnboardingCoordinator with dependency injection.

        100% DEPENDENCY INJECTION - all services injected via constructor.

        Args:
            db: Database session for operations.
            integrity_service: Service for patient data validation (SINGLE SOURCE OF TRUTH).
            validation_service: Service for duplicate detection.
            saga_orchestrator: Saga orchestrator for distributed transactions (direct usage).
            notification_service: Service for notification delivery.
            completion_service: Service for partial onboarding completion.
            creation_service: Optional service for direct patient creation.
        """
        self.db = db
        self.integrity_service = integrity_service
        self.validation_service = validation_service
        self.saga_orchestrator = saga_orchestrator
        self.notification_service = notification_service
        self.completion_service = completion_service
        self.creation_service = creation_service
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _is_saga_enabled(self) -> bool:
        """
        Check if Saga Pattern is enabled and available.

        Returns:
            True if saga is enabled and orchestrator is available.
        """
        return self.saga_orchestrator is not None and getattr(
            settings, "ENABLE_SAGA_PATTERN", True
        )

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
            patient_data: Patient creation data.
            doctor_id: ID of the doctor creating the patient.
            current_user: Current authenticated user (optional).
            idempotency_key: QW-004: Unique key to prevent duplicate requests (optional).

        Returns:
            Created patient object.

        Raises:
            ValidationError: If validation fails or saga execution fails.
        """
        # Step 1: Validate data using SINGLE SOURCE OF TRUTH
        # Note: validate_patient_data is synchronous, don't use await
        self.integrity_service.validate_patient_data(
            patient_data=patient_data, doctor_id=doctor_id, is_update=False
        )
        self._logger.info(
            "Patient data validated",
            extra={"doctor_id": str(doctor_id)}
        )

        # Step 2: Execução obrigatória via Saga Pattern (direct call to orchestrator)
        if not self._is_saga_enabled():
            raise ValidationError("Saga Pattern desabilitado ou não configurado")

        self._logger.info(
            "Attempting patient creation via Saga Pattern",
            extra={"doctor_id": str(doctor_id)}
        )

        try:
            patient = await self.saga_orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor_id,
                current_user=current_user,
                idempotency_key=idempotency_key,  # QW-004: Pass idempotency key to orchestrator
            )

            if not patient:
                raise ValidationError(
                    "Saga Pattern não retornou paciente após execução"
                )

            self._logger.info(
                "Patient created successfully via Saga",
                extra={
                    "patient_id": str(patient.id),
                    "doctor_id": str(doctor_id),
                }
            )
            return patient

        except Exception as e:
            self._logger.error(
                "Saga Pattern execution failed",
                exc_info=True,
                extra={
                    "doctor_id": str(doctor_id),
                    "exception_type": type(e).__name__,
                }
            )
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Falha ao executar Saga Pattern: {e}") from e
