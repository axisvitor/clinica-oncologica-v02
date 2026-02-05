"""
ValidationService - Patient onboarding validation logic.

This service handles validation of patient data during onboarding,
including duplicate detection and data integrity checks.

File: app/domain/patient/onboarding/validation_service.py
LOC: ~150
Responsibility: Patient validation and duplicate detection
"""

from __future__ import annotations

# Standard library imports
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from uuid import UUID

# Third-party imports
from sqlalchemy.orm import Session

# Local application imports
from app.exceptions import ValidationError
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.core.executors import get_validation_executor


class ValidationService:
    """
    Service for patient onboarding validation.

    SINGLE RESPONSIBILITY: Validate patient data and detect duplicates.

    This service extracts validation logic from OnboardingService,
    following the Single Responsibility Principle (SRP).

    Attributes:
        db: Database session.
        _logger: Service logger (private).
        _executor: Thread pool executor for sync operations.
    """

    def __init__(
        self,
        db: Session,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """
        Initialize ValidationService with dependency injection.

        Args:
            db: Database session for operations.
            executor: Thread pool executor for sync operations (optional).
        """
        self.db = db
        # Use centralized executor from app.core.executors
        self._executor = executor or get_validation_executor()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def find_existing_patient(
        self,
        cpf: Optional[str],
        email: Optional[str],
        phone: str,
        doctor_id: UUID,
    ) -> Optional[Patient]:
        """
        Find existing patient by CPF, email, or phone for the given doctor.

        CRITICAL: This method prevents duplicate patient creation by checking
        all unique identifiers with proper database constraints.

        Args:
            cpf: Patient's CPF (may be None).
            email: Patient's email (may be None).
            phone: Patient's phone (required).
            doctor_id: Doctor's ID for scoped uniqueness.

        Returns:
            Existing Patient object or None.

        Note:
            Uses database unique constraints:
            - uq_patient_cpf_doctor
            - uq_patient_email_doctor
            - uq_patient_phone_doctor
        """
        loop = asyncio.get_event_loop()

        try:
            # Priority 1: Check by CPF (most unique identifier for Brazilian patients)
            if cpf:
                patient = await loop.run_in_executor(
                    self._executor, lambda: self._query_by_cpf(cpf, doctor_id)
                )
                if patient:
                    self._logger.info(
                        "Found existing patient by CPF",
                        extra={"patient_id": str(patient.id), "doctor_id": str(doctor_id)}
                    )
                    return patient

            # Priority 2: Check by email (if provided)
            if email:
                patient = await loop.run_in_executor(
                    self._executor, lambda: self._query_by_email(email, doctor_id)
                )
                if patient:
                    self._logger.info(
                        "Found existing patient by email",
                        extra={"patient_id": str(patient.id), "doctor_id": str(doctor_id)}
                    )
                    return patient

            # Priority 3: Check by phone (always provided)
            if phone:
                patient = await loop.run_in_executor(
                    self._executor, lambda: self._query_by_phone(phone, doctor_id)
                )
                if patient:
                    self._logger.info(
                        "Found existing patient by phone",
                        extra={"patient_id": str(patient.id), "doctor_id": str(doctor_id)}
                    )
                    return patient

            return None

        except Exception:
            self._logger.error(
                "Error finding existing patient",
                extra={
                    "cpf": cpf,
                    "email": email,
                    "phone": phone,
                    "doctor_id": str(doctor_id),
                },
                exc_info=True
            )
            # On error, return None to allow creation attempt
            # Database constraints will catch any actual duplicates
            return None

    def _query_by_cpf(self, cpf: str, doctor_id: UUID) -> Optional[Patient]:
        """
        Query patient by CPF and doctor ID.

        Args:
            cpf: Patient's CPF.
            doctor_id: Doctor's ID.

        Returns:
            Patient object or None.
        """
        # LGPD: Use cpf_hash for lookup (plaintext column removed in migration 030)
        from app.services.encryption import get_cpf_encryption_service

        service = get_cpf_encryption_service()
        cpf_hash = service.hash_cpf(cpf)

        return (
            self.db.query(Patient)
            .filter(
                Patient.cpf_hash == cpf_hash,
                Patient.doctor_id == doctor_id,
                Patient.deleted_at.is_(None),  # Only active patients
            )
            .first()
        )

    def _query_by_email(self, email: str, doctor_id: UUID) -> Optional[Patient]:
        """
        Query patient by email and doctor ID.

        LGPD Compliance: Uses email_hash for lookup (plaintext column removed in migration 030).

        Args:
            email: Patient's email.
            doctor_id: Doctor's ID.

        Returns:
            Patient object or None.
        """
        from app.services.encryption import get_lgpd_encryption_service

        service = get_lgpd_encryption_service()
        email_hash = service.hash_email(email.lower())

        return (
            self.db.query(Patient)
            .filter(
                Patient.email_hash == email_hash,
                Patient.doctor_id == doctor_id,
                Patient.deleted_at.is_(None),
            )
            .first()
        )

    def _query_by_phone(self, phone: str, doctor_id: UUID) -> Optional[Patient]:
        """
        Query patient by phone and doctor ID.

        Args:
            phone: Patient's phone.
            doctor_id: Doctor's ID.

        Returns:
            Patient object or None.
        """
        # LGPD: Use phone_hash for lookup (plaintext column removed in migration 030)
        from app.services.encryption import get_lgpd_encryption_service

        service = get_lgpd_encryption_service()
        phone_hash = service.hash_phone(phone)

        return (
            self.db.query(Patient)
            .filter(
                Patient.phone_hash == phone_hash,
                Patient.doctor_id == doctor_id,
                Patient.deleted_at.is_(None),
            )
            .first()
        )

    async def validate_patient_uniqueness(
        self,
        patient_data: PatientCreate,
        doctor_id: UUID,
    ) -> None:
        """
        Validate that patient doesn't already exist.

        Args:
            patient_data: Patient creation data.
            doctor_id: Doctor's ID.

        Raises:
            ValidationError: If patient already exists.
        """
        existing_patient = await self.find_existing_patient(
            cpf=patient_data.cpf,
            email=patient_data.email,
            phone=patient_data.phone,
            doctor_id=doctor_id,
        )

        if existing_patient:
            raise ValidationError(
                f"Patient already exists with ID: {existing_patient.id}. "
                f"Use update endpoint to modify existing patient data."
            )

    async def validate_phone_format(self, phone: str) -> None:
        """
        Validate phone number format.

        Args:
            phone: Phone number to validate.

        Raises:
            ValidationError: If phone format is invalid.
        """
        if not phone:
            raise ValidationError("Phone number is required")

        from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

        try:
            normalize_phone(phone, mode=PhoneValidationMode.BR_TO_E164, allow_none=False)
        except ValueError as exc:
            raise ValidationError(f"Invalid phone number format: {exc}") from exc

    async def validate_cpf_format(self, cpf: Optional[str]) -> None:
        """
        Validate CPF format (Brazilian tax ID).

        Args:
            cpf: CPF to validate (optional).

        Raises:
            ValidationError: If CPF format is invalid.
        """
        if not cpf:
            return  # CPF is optional

        # Remove all non-digit characters
        digits_only = "".join(filter(str.isdigit, cpf))

        # CPF must have exactly 11 digits
        if len(digits_only) != 11:
            raise ValidationError(
                f"Invalid CPF format. Expected 11 digits, got {len(digits_only)}"
            )

        # Check if all digits are the same (invalid CPF)
        if len(set(digits_only)) == 1:
            raise ValidationError("Invalid CPF: all digits are the same")

    async def validate_email_format(self, email: Optional[str]) -> None:
        """
        Validate email format.

        Args:
            email: Email to validate (optional).

        Raises:
            ValidationError: If email format is invalid.
        """
        if not email:
            return  # Email is optional

        # Basic email validation
        if "@" not in email or "." not in email:
            raise ValidationError("Invalid email format")

        # Check for minimum length
        if len(email) < 5:
            raise ValidationError("Email too short")

        # Check for maximum length
        if len(email) > 255:
            raise ValidationError("Email too long (max 255 characters)")

    async def validate_patient_data_format(
        self,
        patient_data: PatientCreate,
    ) -> None:
        """
        Validate all patient data formats.

        This method validates:
        - Phone number format
        - CPF format (if provided)
        - Email format (if provided)

        Args:
            patient_data: Patient creation data.

        Raises:
            ValidationError: If any validation fails.
        """
        await self.validate_phone_format(patient_data.phone)
        await self.validate_cpf_format(patient_data.cpf)
        await self.validate_email_format(patient_data.email)

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown executor gracefully.

        Args:
            wait: Whether to wait for pending operations to complete.
        """
        self._executor.shutdown(wait=wait)
        self._logger.info("ValidationService executor shutdown complete")
