"""
CreationService - Direct patient creation logic.

This service handles direct patient creation in the database
without saga orchestration.

File: app/domain/patient/onboarding/creation_service.py
LOC: ~150
Responsibility: Database patient creation
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError
from app.infrastructure.cache import get_unified_cache_manager as get_cache_manager

if TYPE_CHECKING:
    from app.models.user import User
    from app.services.patient.integrity_service import PatientIntegrityService
    from app.domain.patient.onboarding.validation_service import ValidationService
    from app.domain.patient.onboarding.notification_service import NotificationService
    from app.domain.patient.onboarding.completion_service import CompletionService
    from app.services.patient.flow_service import PatientFlowService

logger = logging.getLogger(__name__)


class CreationService:
    """
    Service for direct patient creation (without saga).

    SINGLE RESPONSIBILITY: Create patient records in database.

    This service handles:
    - Patient record creation
    - Database transaction management
    - Cache invalidation
    - Integration with notification and flow services
    """

    def __init__(
        self,
        db: Session,
        integrity_service: "PatientIntegrityService",
        completion_service: "CompletionService",
        notification_service: "NotificationService",
        validation_service: Optional["ValidationService"] = None,
        flow_service: Optional["PatientFlowService"] = None,
    ):
        """
        Initialize CreationService with dependency injection.

        Args:
            db: Database session
            integrity_service: Service for patient data integrity
            completion_service: Service for partial onboarding completion
            notification_service: Service for notification delivery
            validation_service: Optional validation service
            flow_service: Optional flow service
        """
        self.db = db
        self.integrity_service = integrity_service
        self.completion_service = completion_service
        self.notification_service = notification_service
        self.validation_service = validation_service
        self.flow_service = flow_service

    async def create_patient_direct(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID,
        current_user: Optional["User"] = None,
    ) -> Patient:
        """
        Create patient directly in database.

        Steps:
        1. Prepare patient data
        2. Create new patient record
        3. Invalidate caches
        4. Send notifications
        5. Initialize flow

        Args:
            patient_data: Patient creation data
            doctor_id: Doctor ID
            current_user: Current user (optional)

        Returns:
            Created Patient object

        Raises:
            ValidationError: If validation fails
            IntegrityError: If database integrity constraints are violated
        """
        try:
            # Prepare patient data
            patient_dict = patient_data.dict(exclude_unset=True)

            # Normalize metadata field
            metadata_payload = patient_dict.pop("metadata", None)
            patient_dict["doctor_id"] = doctor_id

            # Prepare patient_data (metadata) with integrity hash
            patient_metadata = dict(metadata_payload or {})
            integrity_hash = self.integrity_service.generate_patient_hash(patient_dict)
            patient_metadata["integrity_hash"] = integrity_hash
            patient_dict["patient_data"] = patient_metadata

            # Create patient via repository
            from app.repositories.patient import PatientRepository
            repository = PatientRepository(self.db)

            logger.info(
                "Creating new patient",
                extra={
                    "cpf": patient_data.cpf,
                    "email": patient_data.email,
                    "phone": patient_data.phone,
                    "doctor_id": str(doctor_id)
                }
            )

            # Use FastAPI's global thread pool (prevents thread leak)
            try:
                patient = await run_in_threadpool(repository.create, patient_dict)
            except Exception as e:
                logger.error(
                    f"Failed to create patient: {e}",
                    exc_info=True
                )
                raise

            # Invalidate caches
            await self._invalidate_cache(doctor_id)

            logger.info(
                f"Patient created successfully (direct): {patient.id} - {patient.name}"
            )

        except ValidationError as e:
            logger.error(f"Patient validation failed: {e}")
            raise
        except IntegrityError as e:
            logger.error(f"Database integrity error during patient creation: {e}")
            await run_in_threadpool(self.db.rollback)
            raise ValidationError(
                "Patient creation failed due to data integrity constraints"
            )
        except Exception as e:
            logger.error(f"Unexpected error during patient creation: {e}")
            await run_in_threadpool(self.db.rollback)
            raise

        # Publish WebSocket event
        try:
            await self.notification_service.publish_patient_created_event(
                patient=patient,
                doctor_id=doctor_id,
                action="created"
            )
        except Exception as e:
            logger.warning(f"Failed to publish WebSocket event: {e}")

        # Send welcome message
        try:
            await self.notification_service.send_welcome_message(patient, current_user)
        except Exception as e:
            logger.error(
                f"Failed to send welcome message to patient {patient.id}: {e}"
            )
            # Don't fail patient creation if WhatsApp fails

        # Initialize flow (if flow_service available)
        if self.flow_service:
            try:
                current_user_id = current_user.id if current_user else None
                await self.flow_service.initialize_default_flow(
                    patient, current_user_id
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize flow for patient {patient.id}: {e}"
                )
                # Don't fail patient creation if flow initialization fails

        return patient

    async def _invalidate_cache(self, doctor_id: UUID) -> None:
        """
        Invalidate patient list cache.

        Args:
            doctor_id: Doctor ID
        """
        cache_manager = get_cache_manager()
        cache_manager.invalidate_pattern(
            f"patient_list:*:{doctor_id}*", namespace="cache"
        )
        logger.debug(f"Invalidated patient list cache for doctor: {doctor_id}")

