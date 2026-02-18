"""
PatientIntegrityService - Patient data integrity facade.

This service maintains backward compatibility while delegating to specialized services:
- PatientValidationService: Data validation
- PatientSyncService: Synchronization and consistency
- PatientAuditService: Audit and integrity tracking

File: backend-hormonia/app/services/patient/integrity_service.py
LOC: ~120
Responsibility: Facade for integrity operations
Pattern: Facade, Composition
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.patient.audit_service import PatientAuditService
from app.services.patient.sync_service import PatientSyncService
from app.services.patient.validation_service import PatientValidationService
from app.utils.db_retry import with_db_retry

logger = logging.getLogger(__name__)


class PatientIntegrityService:
    """
    Facade service for patient data integrity validation and management.

    This service provides backward compatibility while delegating to:
    - validation_service: All validation logic
    - sync_service: Duplicate detection and merging
    - audit_service: Integrity hashing and audit

    Responsibilities:
    - Coordinate validation, sync, and audit operations
    - Maintain backward compatibility with existing code
    - Provide unified interface for patient integrity
    """

    def __init__(
        self,
        db: Any,
        patient_repository: Optional[PatientRepository] = None,
    ):
        """
        Initialize integrity service with composition.

        Args:
            db: Database session
            patient_repository: Optional patient repository
        """
        self.db = db
        self.repository = patient_repository or PatientRepository(db)
        self._logger = logging.getLogger(__name__)

        # Initialize composed services
        self._sync_service = PatientSyncService(db, self.repository)
        self._validation_service = PatientValidationService(db, self._sync_service)
        self._audit_service = PatientAuditService()
        # Backward compatibility: route validation duplicate checks through this
        # facade so existing mocks on `_check_duplicate_*` keep working.
        self._validation_service._duplicate_checker = self

    # ========================================================================
    # VALIDATION - Delegates to PatientValidationService
    # ========================================================================

    @with_db_retry(max_retries=3)
    def validate_patient_data(
        self,
        patient_data: PatientCreate | PatientUpdate,
        doctor_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
        is_update: bool = False,
    ) -> Dict[str, Any]:
        """
        SINGLE SOURCE OF TRUTH for all patient data validation.

        Delegates to PatientValidationService.

        Args:
            patient_data: Patient creation or update data
            doctor_id: Doctor ID (required for creation)
            patient_id: Patient ID (required for updates)
            is_update: True if this is an update operation

        Returns:
            Dict with validated and normalized data

        Raises:
            ValidationError: If validation fails
        """
        return self._validation_service.validate_patient_data(
            patient_data=patient_data,
            doctor_id=doctor_id,
            patient_id=patient_id,
            is_update=is_update,
        )

    def _normalize_cpf(self, cpf: Optional[str]) -> Optional[str]:
        """
        Normalize CPF by removing non-digit characters.

        Delegates to PatientValidationService.
        """
        return self._validation_service.normalize_cpf(cpf)

    def _validate_cpf(self, cpf: str) -> bool:
        """
        Validate Brazilian CPF format and check digits.

        Delegates to PatientValidationService.
        """
        return self._validation_service.validate_cpf(cpf)

    # ========================================================================
    # SYNCHRONIZATION - Delegates to PatientSyncService
    # ========================================================================

    def check_duplicate_cpf(
        self,
        cpf: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """Public duplicate-check contract used by validation service."""
        return self._check_duplicate_cpf(cpf, doctor_id, exclude_patient_id)

    def check_duplicate_email(
        self,
        email: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """Public duplicate-check contract used by validation service."""
        return self._check_duplicate_email(email, doctor_id, exclude_patient_id)

    def check_duplicate_phone(
        self,
        phone: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """Public duplicate-check contract used by validation service."""
        return self._check_duplicate_phone(phone, doctor_id, exclude_patient_id)

    def _delegate_duplicate_check(
        self,
        checker: Callable[[str, Optional[UUID], Optional[UUID]], Optional[Patient]],
        value: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """Shared call-path for duplicate checks delegated to sync service."""
        return checker(value, doctor_id, exclude_patient_id)

    def _normalize_phone_for_duplicate_check(self, phone: str) -> Optional[str]:
        """Normalize phone to E.164 before duplicate checks."""
        if not phone:
            return None

        from app.schemas.validators.phone import PhoneValidationMode, normalize_phone

        try:
            normalized_phone = normalize_phone(
                phone, mode=PhoneValidationMode.BR_TO_E164, allow_none=True
            )
        except ValueError:
            self._logger.warning(
                "Phone normalization failed for duplicate check",
                extra={"phone_original": phone, "phone_normalized": None},
            )
            return None

        self._logger.info(
            "Phone normalized for duplicate check",
            extra={"phone_original": phone, "phone_normalized": normalized_phone},
        )
        return normalized_phone

    @with_db_retry(max_retries=3)
    def _check_duplicate_cpf(
        self,
        cpf: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """
        Check for existing patient with same CPF.

        Delegates to PatientSyncService.
        """
        return self._delegate_duplicate_check(
            self._sync_service.check_duplicate_cpf, cpf, doctor_id, exclude_patient_id
        )

    @with_db_retry(max_retries=3)
    def _check_duplicate_email(
        self,
        email: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """
        Check for existing patient with same email.

        Delegates to PatientSyncService.
        """
        return self._delegate_duplicate_check(
            self._sync_service.check_duplicate_email, email, doctor_id, exclude_patient_id
        )

    @with_db_retry(max_retries=3)
    def _check_duplicate_phone(
        self,
        phone: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """
        Check for existing patient with same phone.

        Delegates to PatientSyncService.
        """
        normalized_phone = self._normalize_phone_for_duplicate_check(phone)
        if not normalized_phone:
            return None
        return self._delegate_duplicate_check(
            self._sync_service.check_duplicate_phone,
            normalized_phone,
            doctor_id,
            exclude_patient_id,
        )

    @with_db_retry(max_retries=3)
    async def merge_patients(
        self, primary_patient_id: UUID, duplicate_patient_id: UUID
    ) -> Patient:
        """
        Merge duplicate patient records.

        Delegates to PatientSyncService.

        Args:
            primary_patient_id: ID of patient to keep
            duplicate_patient_id: ID of patient to merge and delete

        Returns:
            Updated primary patient

        Raises:
            ValidationError: If patients not found or same ID
        """
        return await self._sync_service.merge_patients(
            primary_patient_id, duplicate_patient_id
        )

    @with_db_retry(max_retries=3)
    async def _migrate_patient_relationships(
        self, from_patient_id: UUID, to_patient_id: UUID
    ) -> None:
        """
        Migrate all relationships from duplicate to primary patient.

        Delegates to PatientSyncService.
        """
        return await self._sync_service._migrate_patient_relationships(
            from_patient_id, to_patient_id
        )

    @with_db_retry(max_retries=3)
    async def _soft_delete_patient(self, patient_id: UUID) -> None:
        """
        Soft delete patient by updating metadata.

        Delegates to PatientSyncService.
        """
        return await self._sync_service._soft_delete_patient(patient_id)

    # ========================================================================
    # AUDIT - Delegates to PatientAuditService
    # ========================================================================

    def generate_patient_hash(self, patient_data: Dict[str, Any]) -> str:
        """
        Generate integrity hash for patient data.

        Delegates to PatientAuditService.

        Args:
            patient_data: Patient data dictionary

        Returns:
            SHA256 hash string
        """
        return self._audit_service.generate_patient_hash(patient_data)
