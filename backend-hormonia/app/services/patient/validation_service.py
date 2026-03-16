"""
PatientValidationService - Patient data validation.

Handles all validation logic for patient data including:
- CPF validation and normalization
- Phone number validation
- Email validation
- Data integrity checks

File: backend-hormonia/app/services/patient/validation_service.py
LOC: ~180
Responsibility: Data validation
Pattern: Single Responsibility
"""

from __future__ import annotations

import logging
import re
from inspect import iscoroutinefunction
from datetime import date, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ValidationError
from app.models.user import User, UserRole
from app.schemas.patient import PatientCreate, PatientUpdate
from app.schemas.validators.cpf import calculate_cpf_check_digit
from app.utils.db_retry import with_db_retry
from app.schemas.validators.phone import PhoneValidationError, validate_and_format_phone

logger = logging.getLogger(__name__)


class PatientValidationService:
    """
    Service for patient data validation.

    Responsibilities:
    - Validate CPF format and check digits
    - Validate phone numbers (E.164 format)
    - Validate email addresses
    - Validate dates and names
    - Check for duplicate detection (CPF, email, phone)
    """

    def __init__(self, db: Any, duplicate_checker=None):
        """
        Initialize validation service.

        Args:
            db: Database session
            duplicate_checker: Service for checking duplicates
        """
        self.db = db
        self._duplicate_checker = duplicate_checker
        self._logger = logging.getLogger(__name__)

    @with_db_retry(max_retries=3)
    def validate_patient_data(
        self,
        patient_data: PatientCreate | PatientUpdate,
        doctor_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
        is_update: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate and normalize patient data.

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
        validation_errors = []
        validated_data = {}

        # Validate CPF
        if hasattr(patient_data, "cpf") and patient_data.cpf:
            cpf_result = self._validate_cpf_field(
                patient_data.cpf, doctor_id, patient_id if is_update else None
            )
            if cpf_result.get("errors"):
                validation_errors.extend(cpf_result["errors"])
            elif cpf_result.get("cpf"):
                validated_data["cpf"] = cpf_result["cpf"]

        # Validate phone
        if hasattr(patient_data, "phone") and patient_data.phone:
            phone_result = self._validate_phone_field(
                patient_data.phone, doctor_id, patient_id if is_update else None
            )
            if phone_result.get("errors"):
                validation_errors.extend(phone_result["errors"])
            elif phone_result.get("phone"):
                validated_data["phone"] = phone_result["phone"]

        # Validate email
        if hasattr(patient_data, "email") and patient_data.email:
            email_result = self._validate_email_field(
                patient_data.email, doctor_id, patient_id if is_update else None
            )
            if email_result.get("errors"):
                validation_errors.extend(email_result["errors"])
            elif email_result.get("email"):
                validated_data["email"] = email_result["email"]

        # Validate doctor
        if not is_update and doctor_id:
            if not self._validate_doctor_exists(doctor_id):
                validation_errors.append(
                    f"Doctor with id {doctor_id} not found or not a doctor"
                )
            else:
                validated_data["doctor_id"] = doctor_id

        # Validate dates and other fields
        validated_data.update(self._validate_additional_fields(patient_data, validation_errors))

        if validation_errors:
            error_message = "; ".join(validation_errors)
            self._logger.error(f"Patient validation failed: {error_message}")
            raise ValidationError(error_message)

        validated_data["validation_errors"] = []
        return validated_data

    @with_db_retry(max_retries=3)
    async def validate_patient_data_async(
        self,
        patient_data: PatientCreate | PatientUpdate,
        doctor_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
        is_update: bool = False,
    ) -> Dict[str, Any]:
        """Async-safe validation path for callers using AsyncSession."""
        validation_errors: list[str] = []
        validated_data: dict[str, Any] = {}

        if hasattr(patient_data, "cpf") and patient_data.cpf:
            cpf_result = await self._validate_cpf_field_async(
                patient_data.cpf,
                doctor_id,
                patient_id if is_update else None,
            )
            if cpf_result.get("errors"):
                validation_errors.extend(cpf_result["errors"])
            elif cpf_result.get("cpf"):
                validated_data["cpf"] = cpf_result["cpf"]

        if hasattr(patient_data, "phone") and patient_data.phone:
            phone_result = await self._validate_phone_field_async(
                patient_data.phone,
                doctor_id,
                patient_id if is_update else None,
            )
            if phone_result.get("errors"):
                validation_errors.extend(phone_result["errors"])
            elif phone_result.get("phone"):
                validated_data["phone"] = phone_result["phone"]

        if hasattr(patient_data, "email") and patient_data.email:
            email_result = await self._validate_email_field_async(
                patient_data.email,
                doctor_id,
                patient_id if is_update else None,
            )
            if email_result.get("errors"):
                validation_errors.extend(email_result["errors"])
            elif email_result.get("email"):
                validated_data["email"] = email_result["email"]

        if not is_update and doctor_id:
            if not await self._validate_doctor_exists_async(doctor_id):
                validation_errors.append(
                    f"Doctor with id {doctor_id} not found or not a doctor"
                )
            else:
                validated_data["doctor_id"] = doctor_id

        validated_data.update(self._validate_additional_fields(patient_data, validation_errors))

        if validation_errors:
            error_message = "; ".join(validation_errors)
            self._logger.error(f"Patient validation failed: {error_message}")
            raise ValidationError(error_message)

        validated_data["validation_errors"] = []
        return validated_data

    def _validate_cpf_field(
        self, cpf: str, doctor_id: Optional[UUID], exclude_patient_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Validate CPF field and check for duplicates."""
        errors = []
        normalized_cpf = self.normalize_cpf(cpf)

        if not normalized_cpf or len(normalized_cpf) != 11:
            if normalized_cpf:
                errors.append(f"CPF must have exactly 11 digits, got {len(normalized_cpf)}")
            return {"errors": errors}

        try:
            self.validate_cpf(normalized_cpf)
            if self._duplicate_checker:
                existing = self._duplicate_checker.check_duplicate_cpf(normalized_cpf, doctor_id, exclude_patient_id)
                if existing:
                    errors.append(f"Patient with CPF already exists: {existing.name}")
            return {"cpf": normalized_cpf, "errors": errors}
        except ValidationError as e:
            return {"errors": [str(e)]}

    def _validate_phone_field(
        self, phone: str, doctor_id: Optional[UUID], exclude_patient_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Validate phone field and check for duplicates."""
        try:
            is_valid, formatted_phone, error = validate_and_format_phone(phone, default_region="BR", strict=False)
            if not is_valid:
                return {"errors": [f"Invalid phone number: {error}"]}

            errors = []
            if self._duplicate_checker:
                self._logger.info(
                    "Normalized phone for duplicate check",
                    extra={
                        "phone_original": phone,
                        "phone_normalized": formatted_phone,
                    },
                )
                existing = self._duplicate_checker.check_duplicate_phone(formatted_phone, doctor_id, exclude_patient_id)
                if existing:
                    errors.append(f"Patient with phone already exists: {existing.name}")
            return {"phone": formatted_phone, "errors": errors}
        except PhoneValidationError as e:
            return {"errors": [f"Phone validation error: {str(e)}"]}

    def _validate_email_field(
        self, email: str, doctor_id: Optional[UUID], exclude_patient_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Validate email field and check for duplicates."""
        try:
            validated_email = validate_email(email, check_deliverability=False)
            normalized_email = validated_email.normalized

            errors = []
            if self._duplicate_checker:
                existing = self._duplicate_checker.check_duplicate_email(normalized_email, doctor_id, exclude_patient_id)
                if existing:
                    errors.append(f"Patient with email already exists: {existing.name}")
            return {"email": normalized_email, "errors": errors}
        except EmailNotValidError as e:
            return {"errors": [f"Invalid email format: {str(e)}"]}

    async def _validate_cpf_field_async(
        self, cpf: str, doctor_id: Optional[UUID], exclude_patient_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Async-safe CPF validation and duplicate detection."""
        errors = []
        normalized_cpf = self.normalize_cpf(cpf)

        if not normalized_cpf or len(normalized_cpf) != 11:
            if normalized_cpf:
                errors.append(f"CPF must have exactly 11 digits, got {len(normalized_cpf)}")
            return {"errors": errors}

        try:
            self.validate_cpf(normalized_cpf)
            if self._duplicate_checker and hasattr(self._duplicate_checker, "check_duplicate_cpf_async"):
                existing = await self._duplicate_checker.check_duplicate_cpf_async(
                    normalized_cpf,
                    doctor_id,
                    exclude_patient_id,
                )
                if existing:
                    errors.append(f"Patient with CPF already exists: {existing.name}")
            elif self._duplicate_checker:
                existing = self._duplicate_checker.check_duplicate_cpf(
                    normalized_cpf,
                    doctor_id,
                    exclude_patient_id,
                )
                if existing:
                    errors.append(f"Patient with CPF already exists: {existing.name}")
            return {"cpf": normalized_cpf, "errors": errors}
        except ValidationError as e:
            return {"errors": [str(e)]}

    async def _validate_phone_field_async(
        self, phone: str, doctor_id: Optional[UUID], exclude_patient_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Async-safe phone validation and duplicate detection."""
        try:
            is_valid, formatted_phone, error = validate_and_format_phone(phone, default_region="BR", strict=False)
            if not is_valid:
                return {"errors": [f"Invalid phone number: {error}"]}

            errors = []
            if self._duplicate_checker and hasattr(self._duplicate_checker, "check_duplicate_phone_async"):
                self._logger.info(
                    "Normalized phone for duplicate check",
                    extra={
                        "phone_original": phone,
                        "phone_normalized": formatted_phone,
                    },
                )
                existing = await self._duplicate_checker.check_duplicate_phone_async(
                    formatted_phone,
                    doctor_id,
                    exclude_patient_id,
                )
                if existing:
                    errors.append(f"Patient with phone already exists: {existing.name}")
            elif self._duplicate_checker:
                existing = self._duplicate_checker.check_duplicate_phone(
                    formatted_phone,
                    doctor_id,
                    exclude_patient_id,
                )
                if existing:
                    errors.append(f"Patient with phone already exists: {existing.name}")
            return {"phone": formatted_phone, "errors": errors}
        except PhoneValidationError as e:
            return {"errors": [f"Phone validation error: {str(e)}"]}

    async def _validate_email_field_async(
        self, email: str, doctor_id: Optional[UUID], exclude_patient_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Async-safe email validation and duplicate detection."""
        try:
            validated_email = validate_email(email, check_deliverability=False)
            normalized_email = validated_email.normalized

            errors = []
            if self._duplicate_checker and hasattr(self._duplicate_checker, "check_duplicate_email_async"):
                existing = await self._duplicate_checker.check_duplicate_email_async(
                    normalized_email,
                    doctor_id,
                    exclude_patient_id,
                )
                if existing:
                    errors.append(f"Patient with email already exists: {existing.name}")
            elif self._duplicate_checker:
                existing = self._duplicate_checker.check_duplicate_email(
                    normalized_email,
                    doctor_id,
                    exclude_patient_id,
                )
                if existing:
                    errors.append(f"Patient with email already exists: {existing.name}")
            return {"email": normalized_email, "errors": errors}
        except EmailNotValidError as e:
            return {"errors": [f"Invalid email format: {str(e)}"]}

    def _validate_doctor_exists(self, doctor_id: UUID) -> bool:
        """Check if doctor exists."""
        try:
            if isinstance(self.db, AsyncSession) or iscoroutinefunction(
                getattr(self.db, "execute", None)
            ):
                self._logger.error(
                    "AsyncSession detected in sync _validate_doctor_exists path; use _validate_doctor_exists_async"
                )
                return False
            result = self.db.execute(select(User).filter(User.id == doctor_id))
            doctor = result.scalars().first()
            return doctor is not None and doctor.role in (UserRole.DOCTOR, UserRole.ADMIN)
        except Exception as e:
            self._logger.error(f"Doctor validation failed: {e}")
            return False

    async def _validate_doctor_exists_async(self, doctor_id: UUID) -> bool:
        """Async-safe doctor existence check for AsyncSession callers."""
        try:
            if isinstance(self.db, AsyncSession) or iscoroutinefunction(
                getattr(self.db, "execute", None)
            ):
                result = await self.db.execute(select(User).filter(User.id == doctor_id))
            else:
                result = self.db.execute(select(User).filter(User.id == doctor_id))

            doctor = result.scalars().first()
            return doctor is not None and doctor.role in (UserRole.DOCTOR, UserRole.ADMIN)
        except Exception as e:
            self._logger.error(f"Doctor validation failed: {e}")
            return False

    def _validate_additional_fields(
        self, patient_data: PatientCreate | PatientUpdate, errors: list
    ) -> Dict[str, Any]:
        """Validate dates, name, and other fields."""
        validated = {}

        # Treatment start date
        if hasattr(patient_data, "treatment_start_date") and patient_data.treatment_start_date:
            max_future_days = getattr(settings, "PATIENT_TREATMENT_START_MAX_FUTURE_DAYS", 30)
            if patient_data.treatment_start_date > date.today() + timedelta(days=max_future_days):
                errors.append(f"Treatment start date cannot be more than {max_future_days} days in the future")
            validated["treatment_start_date"] = patient_data.treatment_start_date

        # Birth date
        if hasattr(patient_data, "birth_date") and patient_data.birth_date:
            if patient_data.birth_date > date.today():
                errors.append("Birth date cannot be in the future")
            min_age = getattr(settings, "PATIENT_MIN_AGE", 0)
            if min_age > 0:
                age = (date.today() - patient_data.birth_date).days // 365
                if age < min_age:
                    errors.append(f"Patient must be at least {min_age} years old")
            validated["birth_date"] = patient_data.birth_date

        # Name
        if hasattr(patient_data, "name") and patient_data.name:
            name = patient_data.name.strip()
            if len(name) < 2:
                errors.append("Name must have at least 2 characters")
            if len(name) > 200:
                errors.append("Name must not exceed 200 characters")
            validated["name"] = name

        # Treatment type
        if hasattr(patient_data, "treatment_type") and patient_data.treatment_type:
            validated["treatment_type"] = patient_data.treatment_type.strip()

        # Diagnosis
        if hasattr(patient_data, "diagnosis") and patient_data.diagnosis:
            if len(patient_data.diagnosis) > 500:
                errors.append("Diagnosis must not exceed 500 characters")
            validated["diagnosis"] = patient_data.diagnosis

        # Treatment phase
        if hasattr(patient_data, "treatment_phase") and patient_data.treatment_phase:
            if len(patient_data.treatment_phase) > 100:
                errors.append("Treatment phase must not exceed 100 characters")
            validated["treatment_phase"] = patient_data.treatment_phase

        return validated

    def normalize_cpf(self, cpf: Optional[str]) -> Optional[str]:
        """
        Normalize CPF by removing non-digit characters.

        Args:
            cpf: CPF string with optional formatting

        Returns:
            CPF with only digits (max 11 chars) or None
        """
        if not cpf:
            return None
        normalized = re.sub(r"[^0-9]", "", cpf)
        if not normalized:
            return None
        if len(normalized) > 11:
            self._logger.warning(f"CPF with more than 11 digits: {len(normalized)} chars")
        elif len(normalized) < 11:
            self._logger.warning(f"CPF with less than 11 digits: {len(normalized)} chars")
        return normalized[:11]

    def validate_cpf(self, cpf: str) -> bool:
        """
        Validate Brazilian CPF format and check digits.

        Raises:
            ValidationError: If CPF is invalid
        """
        cpf = "".join(filter(str.isdigit, cpf))

        if len(cpf) != 11:
            raise ValidationError("CPF must have 11 digits")

        # Check for known invalid CPFs (all same digits)
        if cpf in [f"{i}" * 11 for i in range(10)]:
            raise ValidationError("Invalid CPF: cannot be all same digits")

        # Validate check digits
        if cpf[9] != calculate_cpf_check_digit(cpf[:9]):
            raise ValidationError("Invalid CPF: first check digit is incorrect")

        if cpf[10] != calculate_cpf_check_digit(cpf[:10]):
            raise ValidationError("Invalid CPF: second check digit is incorrect")

        return True
