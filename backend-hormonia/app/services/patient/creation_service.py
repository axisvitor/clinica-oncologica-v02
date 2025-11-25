"""
Patient Creation Service with Race Condition Protection - HIGH-003 Implementation

DEPRECATION WARNING (QW-011):
This module is DEPRECATED in favor of:
    app/domain/patient/onboarding/creation_service.py (CreationService)

The domain-based CreationService is now the canonical implementation used by
the OnboardingCoordinator. This service is maintained for backwards compatibility
and will be removed in a future version.

Migration:
    # Instead of:
    from app.services.patient.creation_service import PatientCreationService
    service = PatientCreationService(db)

    # Use:
    from app.domain.patient.onboarding.creation_service import CreationService
    # Or preferably use the OnboardingCoordinator factory:
    from app.services.patient.onboarding_factory import get_onboarding_coordinator

This service handles patient creation with proper race condition handling
using database-level constraints instead of check-then-act pattern.

Race Condition Fix:
- Before: Check existence → Create (TOCTOU vulnerability)
- After: Try create → Catch IntegrityError (atomic operation)

Performance Impact:
- Eliminates duplicate creation race conditions
- Maintains data integrity under concurrent load
- No performance degradation
"""
import warnings
import logging
from typing import Any, Optional
from uuid import UUID
from datetime import datetime

# from sqlalchemy.orm import
from sqlalchemy.exc import IntegrityError

from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)


class PatientCreationService:
    """
    Safe patient creation service with race condition protection.

    .. deprecated::
        Use `app.domain.patient.onboarding.creation_service.CreationService` instead.
        This class is maintained for backwards compatibility only.

    Strategy:
    - Use database unique constraints as source of truth
    - Try-except pattern instead of check-then-act
    - Flush early to detect constraint violations before commit

    Constraints Protected:
    - uq_patient_cpf_doctor (CPF unique per doctor)
    - uq_patient_phone (Phone globally unique)
    - uq_patient_email_doctor (Email unique per doctor)
    """

    def __init__(self, db: Any):
        """Initialize creation service."""
        warnings.warn(
            "PatientCreationService is deprecated. "
            "Use app.domain.patient.onboarding.creation_service.CreationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.db = db

    def create_patient_safe(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID
    ) -> Patient:
        """
        Create patient with race condition protection.

        Args:
            patient_data: Validated patient data
            doctor_id: Doctor UUID

        Returns:
            Created Patient instance

        Raises:
            ValidationError: If unique constraint is violated
                - duplicate_cpf: CPF already exists for this doctor
                - duplicate_phone: Phone already exists
                - duplicate_email: Email already exists for this doctor

        Implementation:
        This method uses database-level constraints to prevent race conditions.
        The pattern is:

        1. Create patient object
        2. Add to session
        3. Flush (forces DB constraint check)
        4. If IntegrityError → rollback and raise ValidationError
        5. If success → commit

        This is superior to check-then-act because it's atomic at DB level.

        Example Race Condition Prevention:

        Request A: Check CPF (not exists) → Create patient
        Request B: Check CPF (not exists) → Create patient
        Result: Duplicate patients (BAD!)

        With this fix:

        Request A: Create → Flush → Constraint OK → Commit
        Request B: Create → Flush → IntegrityError → Rollback
        Result: Only one patient created (GOOD!)
        """
        try:
            # Create patient instance
            patient = Patient(
                phone=patient_data.phone,
                name=patient_data.name,
                email=patient_data.email,
                birth_date=patient_data.birth_date,
                cpf=patient_data.cpf,
                treatment_type=patient_data.treatment_type,
                treatment_start_date=patient_data.treatment_start_date,
                diagnosis=patient_data.diagnosis,
                treatment_phase=patient_data.treatment_phase,
                doctor_id=doctor_id,
                created_at=datetime.utcnow(),
            )

            # Add to session
            self.db.add(patient)

            # Flush to detect constraint violations EARLY
            # This is critical - it forces constraint check before commit
            self.db.flush()

            logger.info(
                f"Patient created successfully: {patient.id}",
                extra={
                    "patient_id": str(patient.id),
                    "doctor_id": str(doctor_id),
                }
            )

            return patient

        except IntegrityError as e:
            # Rollback transaction
            self.db.rollback()

            # Parse constraint violation
            error_message = str(e.orig).lower()

            # Detect which constraint was violated
            if 'uq_patient_cpf_doctor' in error_message or 'cpf' in error_message:
                logger.warning(
                    f"Duplicate CPF detected: {patient_data.cpf}",
                    extra={
                        "cpf_masked": self._mask_cpf(patient_data.cpf),
                        "doctor_id": str(doctor_id),
                    }
                )
                raise ValidationError(
                    message="Paciente com este CPF já existe para este médico",
                    field="cpf",
                    code="duplicate_cpf"
                )

            elif 'uq_patient_phone' in error_message or 'phone' in error_message:
                logger.warning(
                    f"Duplicate phone detected: {patient_data.phone}",
                    extra={
                        "phone_masked": self._mask_phone(patient_data.phone),
                    }
                )
                raise ValidationError(
                    message="Paciente com este telefone já existe",
                    field="phone",
                    code="duplicate_phone"
                )

            elif 'uq_patient_email_doctor' in error_message or 'email' in error_message:
                logger.warning(
                    f"Duplicate email detected: {patient_data.email}",
                    extra={
                        "email_masked": self._mask_email(patient_data.email),
                        "doctor_id": str(doctor_id),
                    }
                )
                raise ValidationError(
                    message="Paciente com este email já existe para este médico",
                    field="email",
                    code="duplicate_email"
                )

            else:
                # Unknown constraint violation
                logger.error(
                    f"Unknown integrity error during patient creation: {e}",
                    exc_info=True
                )
                raise ValidationError(
                    message="Erro ao criar paciente: violação de restrição de unicidade",
                    field="unknown",
                    code="integrity_error"
                )

        except Exception as e:
            # Unexpected error - rollback and re-raise
            self.db.rollback()
            logger.error(
                f"Unexpected error during patient creation: {e}",
                exc_info=True
            )
            raise

    # Privacy helpers for logging

    @staticmethod
    def _mask_cpf(cpf: Optional[str]) -> str:
        """Mask CPF for logging (LGPD compliance)."""
        if not cpf or len(cpf) < 11:
            return "***"
        return f"{cpf[:3]}.***.***-{cpf[-2:]}"

    @staticmethod
    def _mask_phone(phone: Optional[str]) -> str:
        """Mask phone for logging (LGPD compliance)."""
        if not phone or len(phone) < 4:
            return "***"
        return f"+55***{phone[-4:]}"

    @staticmethod
    def _mask_email(email: Optional[str]) -> str:
        """Mask email for logging (LGPD compliance)."""
        if not email or '@' not in email:
            return "***@***.***"
        local, domain = email.split('@', 1)
        masked_local = f"{local[:2]}***" if len(local) > 2 else "***"
        return f"{masked_local}@{domain}"


__all__ = ["PatientCreationService"]
