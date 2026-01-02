"""
CreationService - Direct patient creation logic.

This service handles direct patient creation in the database
without saga orchestration.

File: app/domain/patient/onboarding/creation_service.py
LOC: ~150
Responsibility: Database patient creation
"""

from __future__ import annotations

# Standard library imports
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Optional
from uuid import UUID

# Third-party imports
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

# Local application imports
from app.exceptions import ValidationError
from app.infrastructure.cache import get_unified_cache_manager as get_cache_manager
from app.models.patient import Patient
from app.schemas.patient import PatientCreate

if TYPE_CHECKING:
    from app.domain.patient.onboarding.completion_service import CompletionService
    from app.domain.patient.onboarding.notification_service import NotificationService
    from app.domain.patient.onboarding.validation_service import ValidationService
    from app.models.user import User
    from app.services.patient.flow_service import PatientFlowService
    from app.services.patient.integrity_service import PatientIntegrityService


class CreationService:
    """
    Service for direct patient creation (without saga).

    SINGLE RESPONSIBILITY: Create patient records in database.

    This service handles:
    - Patient record creation
    - Database transaction management
    - Cache invalidation
    - Integration with notification and flow services

    Attributes:
        db: Database session.
        integrity_service: Service for patient data integrity.
        completion_service: Service for partial onboarding completion.
        notification_service: Service for notification delivery.
        validation_service: Optional validation service.
        flow_service: Optional flow service.
        executor: Optional thread pool executor for background tasks.
        _logger: Service logger (private).
    """

    def __init__(
        self,
        db: Session,
        integrity_service: "PatientIntegrityService",
        completion_service: "CompletionService",
        notification_service: "NotificationService",
        validation_service: Optional["ValidationService"] = None,
        flow_service: Optional["PatientFlowService"] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """
        Initialize CreationService with dependency injection.

        Args:
            db: Database session for operations.
            integrity_service: Service for patient data integrity.
            completion_service: Service for partial onboarding completion.
            notification_service: Service for notification delivery.
            validation_service: Optional validation service.
            flow_service: Optional flow service.
            executor: Optional thread pool executor for background tasks.
        """
        self.db = db
        self.integrity_service = integrity_service
        self.completion_service = completion_service
        self.notification_service = notification_service
        self.validation_service = validation_service
        self.flow_service = flow_service
        self.executor = executor
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

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
            patient_data: Patient creation data.
            doctor_id: Doctor ID.
            current_user: Current user (optional).

        Returns:
            Created Patient object.

        Raises:
            ValidationError: If validation fails or database integrity constraints are violated.
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

            self._logger.info(
                "Creating new patient",
                extra={
                    "has_cpf": bool(patient_data.cpf),
                    "has_email": bool(patient_data.email),
                    "has_phone": bool(patient_data.phone),
                    "doctor_id": str(doctor_id),
                }
            )

            # Use FastAPI's global thread pool (prevents thread leak)
            try:
                patient = await run_in_threadpool(repository.create, patient_dict)
            except Exception:
                self._logger.error("Failed to create patient", exc_info=True)
                raise

            # Invalidate caches
            await self._invalidate_cache(doctor_id)

            self._logger.info(
                "Patient created successfully (direct)",
                extra={"patient_id": str(patient.id)}
            )

        except ValidationError as e:
            self._logger.error("Patient validation failed", extra={"error": str(e)})
            raise
        except IntegrityError as e:
            await run_in_threadpool(self.db.rollback)
            error_message = str(e.orig).lower()

            if any(term in error_message for term in ["uq_patient_cpf_hash_doctor", "uq_patient_cpf_doctor", "cpf_hash", "cpf"]):
                raise ValidationError(
                    message="Paciente com este CPF já existe para este médico",
                    field="cpf",
                    code="duplicate_cpf",
                )
            elif any(term in error_message for term in ["uq_patient_phone", "phone_hash", "phone"]):
                raise ValidationError(
                    message="Paciente com este telefone já existe",
                    field="phone",
                    code="duplicate_phone",
                )
            elif any(term in error_message for term in ["uq_patient_email_doctor", "email_hash", "email"]):
                raise ValidationError(
                    message="Paciente com este email já existe para este médico",
                    field="email",
                    code="duplicate_email",
                )
            else:
                self._logger.error("Database integrity error during patient creation", exc_info=True)
                raise ValidationError(
                    "Patient creation failed due to data integrity constraints",
                    code="integrity_error"
                )
        except Exception:
            self._logger.error("Unexpected error during patient creation", exc_info=True)
            await run_in_threadpool(self.db.rollback)
            raise

        # Publish WebSocket event
        try:
            await self.notification_service.publish_patient_created_event(
                patient=patient, doctor_id=doctor_id, action="created"
            )
        except Exception as e:
            self._logger.warning("Failed to publish WebSocket event", extra={"error": str(e)})

        # Send welcome message
        try:
            await self.notification_service.send_welcome_message(patient, current_user)
        except Exception as e:
            self._logger.error(
                "Failed to send welcome message",
                extra={"patient_id": str(patient.id), "error": str(e)}
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
                self._logger.error(
                    "Failed to initialize flow",
                    extra={"patient_id": str(patient.id), "error": str(e)}
                )
                # Don't fail patient creation if flow initialization fails

        return patient

    async def _invalidate_cache(self, doctor_id: UUID) -> None:
        """
        Invalidate patient list cache.

        Args:
            doctor_id: Doctor ID for cache invalidation.
        """
        cache_manager = get_cache_manager()
        cache_manager.invalidate_pattern(
            f"patient_list:*:{doctor_id}*", namespace="cache"
        )
        self._logger.debug(
            "Invalidated patient list cache",
            extra={"doctor_id": str(doctor_id)}
        )
