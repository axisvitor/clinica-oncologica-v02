"""
CompletionService - Patient onboarding completion logic.

This service handles completing partial/interrupted onboarding processes
for patients that were partially created during saga failure scenarios.

File: app/domain/patient/onboarding/completion_service.py
LOC: ~120
Responsibility: Complete partial patient onboarding

ISSUE-005 Phase 4:
- Extracted from PatientOnboardingService
- Follows Single Responsibility Principle (SRP)
- 100% dependency injection for testability
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, TYPE_CHECKING
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.infrastructure.cache import get_unified_cache_manager as get_cache_manager

if TYPE_CHECKING:
    from app.models.user import User
    from app.services.patient.flow_service import PatientFlowService
    from app.domain.patient.onboarding.notification_service import NotificationService

logger = logging.getLogger(__name__)


class CompletionService:
    """
    Service for completing partial patient onboarding.

    SINGLE RESPONSIBILITY: Complete onboarding for partially created patients.

    This service handles cases where:
    - Saga failed after patient creation
    - Patient exists but onboarding incomplete
    - Flow or notifications need to be (re)initialized
    """

    def __init__(
        self,
        db: Session,
        flow_service: "PatientFlowService",
        notification_service: "NotificationService",
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """
        Initialize CompletionService with dependency injection.

        Args:
            db: Database session
            flow_service: Service for patient flow management
            notification_service: Service for notification delivery
            executor: Optional ThreadPoolExecutor for sync operations
        """
        self.db = db
        self.flow_service = flow_service
        self.notification_service = notification_service
        self._executor = executor or ThreadPoolExecutor(
            max_workers=5, thread_name_prefix="completion_sync"
        )

    async def complete_partial_onboarding(
        self,
        existing_patient: Patient,
        patient_data: PatientCreate,
        current_user: Optional["User"] = None
    ) -> Patient:
        """
        Complete onboarding for a partially created patient.

        CRITICAL: This method prevents duplicate patients by completing the
        onboarding process for patients that were partially created during
        saga failure scenarios.

        Process:
        1. Update patient data with any new information
        2. Send welcome message if not already sent
        3. Initialize flow if not already initialized
        4. Update flow state to active
        5. Publish completion event

        Args:
            existing_patient: The existing patient record
            patient_data: New patient data to update/complete
            current_user: Current authenticated user

        Returns:
            Updated patient object with completed onboarding

        Raises:
            Exception: If critical updates fail
        """
        try:
            logger.info(
                f"Completing partial onboarding for patient: {existing_patient.id}",
                extra={
                    "patient_id": str(existing_patient.id),
                    "current_flow_state": existing_patient.flow_state.value if hasattr(existing_patient.flow_state, 'value') else str(existing_patient.flow_state),
                    "doctor_id": str(existing_patient.doctor_id)
                }
            )

            # 1. Update patient data with any new information (preserve existing)
            updated = await self._update_patient_data(existing_patient, patient_data)

            # 2. Invalidate caches
            await self._invalidate_cache(existing_patient.doctor_id)

            # 3. Publish completion event
            try:
                await self.notification_service.publish_patient_created_event(
                    patient=existing_patient,
                    doctor_id=existing_patient.doctor_id,
                    action="onboarding_completed"
                )
            except Exception as e:
                logger.warning(f"Failed to publish WebSocket event: {e}")

            # 4. Send welcome message if needed
            try:
                success = await self.notification_service.send_welcome_if_needed(
                    existing_patient, current_user
                )
                if success:
                    logger.info(f"Welcome message sent to existing patient: {existing_patient.id}")
                else:
                    logger.info(f"Welcome message already sent to patient: {existing_patient.id}")
            except Exception as e:
                logger.error(
                    f"Failed to send welcome message to patient {existing_patient.id}: {e}"
                )
                # Don't fail completion if WhatsApp fails

            # 5. Initialize flow if not already initialized
            await self._initialize_flow_if_needed(existing_patient, current_user)

            logger.info(
                f"Successfully completed partial onboarding for patient: {existing_patient.id}",
                extra={
                    "patient_id": str(existing_patient.id),
                    "final_flow_state": existing_patient.flow_state.value if hasattr(existing_patient.flow_state, 'value') else str(existing_patient.flow_state)
                }
            )

            return existing_patient

        except Exception as e:
            logger.error(
                f"Error completing partial onboarding for patient {existing_patient.id}: {e}",
                exc_info=True
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, self.db.rollback)
            raise

    async def _update_patient_data(
        self,
        existing_patient: Patient,
        patient_data: PatientCreate
    ) -> bool:
        """
        Update patient data with new information (preserve existing).

        Args:
            existing_patient: Existing patient record
            patient_data: New patient data

        Returns:
            True if any updates were made, False otherwise
        """
        updated = False

        # Update fields only if not already set
        if patient_data.name and not existing_patient.name:
            existing_patient.name = patient_data.name
            updated = True
        if patient_data.email and not existing_patient.email:
            existing_patient.email = patient_data.email
            updated = True
        if patient_data.birth_date and not existing_patient.birth_date:
            existing_patient.birth_date = patient_data.birth_date
            updated = True
        if patient_data.treatment_type and not existing_patient.treatment_type:
            existing_patient.treatment_type = patient_data.treatment_type
            updated = True
        if patient_data.cpf and not existing_patient.cpf:
            existing_patient.cpf = patient_data.cpf
            updated = True

        # Update metadata if provided
        if hasattr(patient_data, 'metadata') and patient_data.metadata:
            if not existing_patient.patient_data:
                existing_patient.patient_data = {}
            existing_patient.patient_data.update(patient_data.metadata)
            updated = True

        if updated:
            # Commit updates
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(self._executor, self.db.commit)
                await loop.run_in_executor(self._executor, lambda: self.db.refresh(existing_patient))
                logger.info(f"Updated patient data: {existing_patient.id}")
            except Exception as e:
                logger.error(
                    f"Failed to commit patient updates in executor: {e}",
                    exc_info=True
                )
                raise

        return updated

    async def _initialize_flow_if_needed(
        self,
        patient: Patient,
        current_user: Optional["User"] = None
    ) -> bool:
        """
        Initialize patient flow if not already initialized.

        Args:
            patient: Patient to initialize flow for
            current_user: Current authenticated user

        Returns:
            True if flow was initialized, False if already exists
        """
        from app.models.flow import PatientFlowState

        # Check if flow already exists
        loop = asyncio.get_event_loop()
        existing_flow = await loop.run_in_executor(
            self._executor,
            lambda: (
                self.db.query(PatientFlowState)
                .filter(PatientFlowState.patient_id == patient.id)
                .first()
            )
        )

        if not existing_flow:
            try:
                current_user_id = current_user.id if current_user else None
                await self.flow_service.initialize_default_flow(
                    patient, current_user_id
                )
                logger.info(f"Initialized flow for existing patient: {patient.id}")
                return True
            except Exception as e:
                logger.error(
                    f"Failed to initialize flow for patient {patient.id}: {e}"
                )
                # Don't fail completion if flow initialization fails
                return False
        else:
            logger.info(f"Flow already initialized for patient: {patient.id}")
            return False

    async def _invalidate_cache(self, doctor_id: UUID) -> None:
        """
        Invalidate patient list cache for doctor.

        Args:
            doctor_id: Doctor ID
        """
        cache_manager = get_cache_manager()
        cache_manager.invalidate_pattern(
            f"patient_list:*:{doctor_id}*", namespace="cache"
        )
        logger.debug(f"Invalidated patient list cache for doctor: {doctor_id}")

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the completion service gracefully.

        Args:
            wait: Whether to wait for pending operations to complete
        """
        if self._executor:
            self._executor.shutdown(wait=wait)
            logger.info(f"CompletionService executor shutdown (wait={wait})")
