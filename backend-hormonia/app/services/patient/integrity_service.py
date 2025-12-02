"""
PatientIntegrityService - Patient data integrity validation and management.

This service is the SINGLE SOURCE OF TRUTH for all patient validations.
All validation logic is centralized here following the DRY principle.

File: backend-hormonia/app/services/patient/integrity_service.py
LOC: ~400
Responsibility: Data validation and integrity
Pattern: Single Responsibility, DRY
"""
from datetime import date, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import UUID
import hashlib
import logging
import re

from sqlalchemy import func, text
from email_validator import validate_email, EmailNotValidError

from app.models.patient import Patient, FlowState
from app.models.user import User
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate
from app.exceptions import ValidationError
from app.config import settings
from app.utils.db_retry import with_db_retry
from app.utils.phone_validator import validate_and_format_phone, PhoneValidationError

logger = logging.getLogger(__name__)


class PatientIntegrityService:
    """
    Service for patient data integrity validation and management.

    Responsibilities:
    - Validate patient creation data
    - Check for duplicate patients (CPF, email, phone)
    - Validate CPF format and check digits
    - Generate integrity hashes
    - Merge duplicate patient records
    - Migrate patient relationships
    """

    def __init__(self, db: Any, patient_repository: PatientRepository):
        self.db = db
        self.repository = patient_repository

    # ========================================================================
    # COMPREHENSIVE VALIDATION - SINGLE SOURCE OF TRUTH
    # ========================================================================

    @with_db_retry(max_retries=3)
    async def validate_patient_data(
        self,
        patient_data: PatientCreate | PatientUpdate,
        doctor_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
        is_update: bool = False
    ) -> Dict[str, Any]:
        """
        SINGLE SOURCE OF TRUTH for all patient data validation.

        This method consolidates ALL validation logic previously scattered across:
        - API layer (patients_crud.py)
        - Service layer (patient.py)
        - Utils layer (patients_utils.py)

        Args:
            patient_data: Patient creation or update data
            doctor_id: Doctor ID (required for creation)
            patient_id: Patient ID (required for updates)
            is_update: True if this is an update operation

        Returns:
            Dict with validated and normalized data:
            {
                "cpf": str,
                "phone": str,  # E.164 format
                "email": str,
                "validation_errors": List[str]
            }

        Raises:
            ValidationError: If validation fails
        """
        validation_errors = []
        validated_data = {}

        try:
            # 1. Normalize and validate CPF
            if hasattr(patient_data, 'cpf') and patient_data.cpf:
                normalized_cpf = self._normalize_cpf(patient_data.cpf)

                # Validate CPF format
                if normalized_cpf:
                    if len(normalized_cpf) != 11:
                        validation_errors.append(
                            f"CPF must have exactly 11 digits, got {len(normalized_cpf)}"
                        )
                    else:
                        # Validate CPF check digits
                        try:
                            self._validate_cpf(normalized_cpf)
                            validated_data['cpf'] = normalized_cpf

                            # Check uniqueness
                            existing_cpf = await self._check_duplicate_cpf(
                                normalized_cpf,
                                doctor_id,
                                exclude_patient_id=patient_id if is_update else None
                            )
                            if existing_cpf:
                                validation_errors.append(
                                    f"Patient with CPF already exists: {existing_cpf.name}"
                                )
                        except ValidationError as e:
                            validation_errors.append(str(e))

            # 2. Validate and format phone to E.164
            if hasattr(patient_data, 'phone') and patient_data.phone:
                try:
                    is_valid, formatted_phone, error = validate_and_format_phone(
                        patient_data.phone,
                        default_region="BR",
                        strict=False
                    )

                    if not is_valid:
                        validation_errors.append(f"Invalid phone number: {error}")
                    else:
                        validated_data['phone'] = formatted_phone

                        # Check uniqueness
                        existing_phone = await self._check_duplicate_phone(
                            formatted_phone,
                            doctor_id,
                            exclude_patient_id=patient_id if is_update else None
                        )
                        if existing_phone:
                            validation_errors.append(
                                f"Patient with phone already exists: {existing_phone.name}"
                            )

                except PhoneValidationError as e:
                    validation_errors.append(f"Phone validation error: {str(e)}")

            # 3. Validate email format and uniqueness
            if hasattr(patient_data, 'email') and patient_data.email:
                try:
                    validated_email = validate_email(patient_data.email)
                    validated_data['email'] = validated_email.normalized

                    # Check uniqueness
                    existing_email = await self._check_duplicate_email(
                        validated_email.normalized,
                        doctor_id,
                        exclude_patient_id=patient_id if is_update else None
                    )
                    if existing_email:
                        validation_errors.append(
                            f"Patient with email already exists: {existing_email.name}"
                        )

                except EmailNotValidError as e:
                    validation_errors.append(f"Invalid email format: {str(e)}")

            # 4. Validate doctor exists (for creation only)
            if not is_update and doctor_id:
                doctor = self.db.query(User).filter(User.id == doctor_id).first()
                if not doctor:
                    validation_errors.append(
                        f"Doctor with id {doctor_id} not found"
                    )
                validated_data['doctor_id'] = doctor_id

            # 5. Validate treatment dates
            if hasattr(patient_data, 'treatment_start_date') and patient_data.treatment_start_date:
                max_future_days = getattr(
                    settings, "PATIENT_TREATMENT_START_MAX_FUTURE_DAYS", 30
                )
                if patient_data.treatment_start_date > date.today() + timedelta(days=max_future_days):
                    validation_errors.append(
                        f"Treatment start date cannot be more than {max_future_days} days in the future"
                    )
                validated_data['treatment_start_date'] = patient_data.treatment_start_date

            # 6. Validate birth_date
            if hasattr(patient_data, 'birth_date') and patient_data.birth_date:
                if patient_data.birth_date > date.today():
                    validation_errors.append("Birth date cannot be in the future")

                # Check minimum age (optional)
                min_age = getattr(settings, "PATIENT_MIN_AGE", 0)
                if min_age > 0:
                    age = (date.today() - patient_data.birth_date).days // 365
                    if age < min_age:
                        validation_errors.append(f"Patient must be at least {min_age} years old")

                validated_data['birth_date'] = patient_data.birth_date

            # 7. Validate name
            if hasattr(patient_data, 'name') and patient_data.name:
                name = patient_data.name.strip()
                if len(name) < 2:
                    validation_errors.append("Name must have at least 2 characters")
                if len(name) > 200:
                    validation_errors.append("Name must not exceed 200 characters")
                validated_data['name'] = name

            # 8. Validate treatment_type
            if hasattr(patient_data, 'treatment_type') and patient_data.treatment_type:
                validated_data['treatment_type'] = patient_data.treatment_type.strip()

            # 9. Validate diagnosis
            if hasattr(patient_data, 'diagnosis') and patient_data.diagnosis:
                if len(patient_data.diagnosis) > 500:
                    validation_errors.append("Diagnosis must not exceed 500 characters")
                validated_data['diagnosis'] = patient_data.diagnosis

            # 10. Validate treatment_phase
            if hasattr(patient_data, 'treatment_phase') and patient_data.treatment_phase:
                if len(patient_data.treatment_phase) > 100:
                    validation_errors.append("Treatment phase must not exceed 100 characters")
                validated_data['treatment_phase'] = patient_data.treatment_phase

            # If there are validation errors, raise exception
            if validation_errors:
                error_message = "; ".join(validation_errors)
                logger.error(f"Patient validation failed: {error_message}")
                raise ValidationError(error_message)

            validated_data['validation_errors'] = []
            return validated_data

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected validation error: {e}")
            raise ValidationError(f"Patient validation failed: {str(e)}")

    def _normalize_cpf(self, cpf: Optional[str]) -> Optional[str]:
        """
        Normalize CPF by removing non-digit characters.

        Args:
            cpf: CPF string with optional formatting (dots, dashes)

        Returns:
            CPF with only digits (max 11 chars) or None
        """
        if not cpf:
            return None
        # Remove all non-digit characters
        normalized = re.sub(r'[^0-9]', '', cpf)
        # Limit to 11 digits (CPF max length)
        return normalized[:11] if normalized else None

    @with_db_retry(max_retries=3)
    async def validate_patient_creation(
        self, patient_data: PatientCreate, doctor_id: UUID
    ) -> None:
        """
        Comprehensive validation for patient creation.

        Validates:
        - Email format
        - CPF format and check digits
        - Duplicate detection (CPF, email, phone)
        - Treatment date constraints

        Raises:
            ValidationError: If any validation fails
        """
        try:
            # Validate email format
            if patient_data.email:
                try:
                    validate_email(patient_data.email)
                except EmailNotValidError as e:
                    raise ValidationError(f"Invalid email format: {e}")

            # Validate CPF if provided
            cpf = None
            if hasattr(patient_data, "cpf") and patient_data.cpf:
                cpf = patient_data.cpf
            elif hasattr(patient_data, "patient_data") and patient_data.patient_data:
                cpf = patient_data.patient_data.get("cpf")

            if cpf:
                self._validate_cpf(cpf)
                # Check for duplicates by CPF
                existing_cpf = await self._check_duplicate_cpf(cpf)
                if existing_cpf:
                    raise ValidationError(
                        f"Patient with CPF {cpf} already exists: {existing_cpf.name}"
                    )

            # Check for duplicates by email
            if patient_data.email:
                existing_email = await self._check_duplicate_email(patient_data.email)
                if existing_email:
                    raise ValidationError(
                        f"Patient with email {patient_data.email} already exists: "
                        f"{existing_email.name}"
                    )

            # Check for duplicates by phone
            existing_phone = self.repository.get_by_phone(patient_data.phone)
            if existing_phone:
                raise ValidationError(
                    f"Patient with phone {patient_data.phone} already exists: "
                    f"{existing_phone.name}"
                )

            # Validate treatment date
            if patient_data.treatment_type and patient_data.treatment_start_date:
                max_future_days = getattr(
                    settings, "PATIENT_TREATMENT_START_MAX_FUTURE_DAYS", 30
                )
                if patient_data.treatment_start_date > date.today() + timedelta(
                    days=max_future_days
                ):
                    raise ValidationError(
                        f"Treatment start date cannot be more than {max_future_days} "
                        "days in the future"
                    )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Patient validation error: {e}")
            raise ValidationError(f"Patient validation failed: {str(e)}")

    @with_db_retry(max_retries=3)
    async def _check_duplicate_cpf(
        self,
        cpf: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None
    ) -> Optional[Patient]:
        """
        Check for existing patient with same CPF.

        Args:
            cpf: CPF to check
            doctor_id: Filter by doctor (scoped uniqueness)
            exclude_patient_id: Exclude this patient ID (for updates)

        Note:
            This check is advisory only. The definitive check happens
            at database constraint level (HIGH-003 fix) to prevent
            race conditions.
        """
        try:
            # LGPD: Use cpf_hash for lookup (plaintext column removed in migration 030)
            from app.services.encryption import get_cpf_encryption_service
            service = get_cpf_encryption_service()
            cpf_hash = service.hash_cpf(cpf)

            query = self.db.query(Patient).filter(
                Patient.cpf_hash == cpf_hash,
                Patient.deleted_at.is_(None)
            )

            # Scope to doctor if provided
            if doctor_id:
                query = query.filter(Patient.doctor_id == doctor_id)

            # Exclude current patient on update
            if exclude_patient_id:
                query = query.filter(Patient.id != exclude_patient_id)

            return query.first()

        except Exception as e:
            logger.error(f"CPF duplicate check failed: {e}")
            return None

    @with_db_retry(max_retries=3)
    async def _check_duplicate_email(
        self,
        email: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None
    ) -> Optional[Patient]:
        """
        Check for existing patient with same email.

        Args:
            email: Email to check (case-insensitive)
            doctor_id: Filter by doctor (scoped uniqueness)
            exclude_patient_id: Exclude this patient ID (for updates)
        """
        try:
            # LGPD: Use email_hash for lookup (plaintext column removed in migration 030)
            from app.services.encryption import get_lgpd_encryption_service
            service = get_lgpd_encryption_service()
            email_hash = service.hash_email(email.lower())

            query = self.db.query(Patient).filter(
                Patient.email_hash == email_hash,
                Patient.deleted_at.is_(None)
            )

            # Scope to doctor if provided
            if doctor_id:
                query = query.filter(Patient.doctor_id == doctor_id)

            # Exclude current patient on update
            if exclude_patient_id:
                query = query.filter(Patient.id != exclude_patient_id)

            return query.first()

        except Exception as e:
            logger.error(f"Email duplicate check failed: {e}")
            return None

    @with_db_retry(max_retries=3)
    async def _check_duplicate_phone(
        self,
        phone: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None
    ) -> Optional[Patient]:
        """
        Check for existing patient with same phone.

        Args:
            phone: Phone to check (E.164 format)
            doctor_id: Filter by doctor (scoped uniqueness)
            exclude_patient_id: Exclude this patient ID (for updates)
        """
        try:
            # LGPD: Use phone_hash for lookup (plaintext column removed in migration 030)
            from app.services.encryption import get_lgpd_encryption_service
            service = get_lgpd_encryption_service()
            phone_hash = service.hash_phone(phone)

            query = self.db.query(Patient).filter(
                Patient.phone_hash == phone_hash,
                Patient.deleted_at.is_(None)
            )

            # Scope to doctor if provided
            if doctor_id:
                query = query.filter(Patient.doctor_id == doctor_id)

            # Exclude current patient on update
            if exclude_patient_id:
                query = query.filter(Patient.id != exclude_patient_id)

            return query.first()

        except Exception as e:
            logger.error(f"Phone duplicate check failed: {e}")
            return None

    def _validate_cpf(self, cpf: str) -> bool:
        """
        Validate Brazilian CPF format and check digits.

        Raises:
            ValidationError: If CPF is invalid
        """
        try:
            # Remove non-numeric characters
            cpf = "".join(filter(str.isdigit, cpf))

            # Check if CPF has 11 digits
            if len(cpf) != 11:
                raise ValidationError("CPF must have 11 digits")

            # Check for known invalid CPFs (all same digits)
            if cpf in [
                "00000000000",
                "11111111111",
                "22222222222",
                "33333333333",
                "44444444444",
                "55555555555",
                "66666666666",
                "77777777777",
                "88888888888",
                "99999999999",
            ]:
                raise ValidationError("Invalid CPF: cannot be all same digits")

            # Validate CPF check digits
            def calc_digit(cpf_partial):
                total = sum(
                    int(digit) * (len(cpf_partial) + 1 - i)
                    for i, digit in enumerate(cpf_partial)
                )
                remainder = total % 11
                return "0" if remainder < 2 else str(11 - remainder)

            # Check first digit
            if cpf[9] != calc_digit(cpf[:9]):
                raise ValidationError("Invalid CPF: first check digit is incorrect")

            # Check second digit
            if cpf[10] != calc_digit(cpf[:10]):
                raise ValidationError("Invalid CPF: second check digit is incorrect")

            return True

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"CPF validation error: {e}")
            raise ValidationError(f"CPF validation failed: {str(e)}")

    def generate_patient_hash(self, patient_data: Dict[str, Any]) -> str:
        """
        Generate integrity hash for patient data.

        Creates a SHA256 hash from critical patient fields to ensure
        data integrity and detect unauthorized changes.
        """
        try:
            # Create hash from critical fields
            hash_fields = {
                "phone": patient_data.get("phone", ""),
                "name": patient_data.get("name", ""),
                "email": patient_data.get("email", ""),
                "cpf": patient_data.get("patient_data", {}).get("cpf", "")
                if patient_data.get("patient_data")
                else "",
            }

            # Sort fields for consistent hashing
            hash_string = "|".join(f"{k}:{v}" for k, v in sorted(hash_fields.items()))

            return hashlib.sha256(hash_string.encode("utf-8")).hexdigest()

        except Exception as e:
            logger.error(f"Hash generation failed: {e}")
            return ""

    @with_db_retry(max_retries=3)
    async def merge_patients(
        self, primary_patient_id: UUID, duplicate_patient_id: UUID
    ) -> Patient:
        """
        Merge duplicate patient records.

        The primary patient keeps its identity, while data from the
        duplicate is merged in. All relationships are migrated to
        the primary patient.

        Args:
            primary_patient_id: ID of patient to keep
            duplicate_patient_id: ID of patient to merge and delete

        Returns:
            Updated primary patient

        Raises:
            ValidationError: If patients not found or same ID
        """
        try:
            primary_patient = self.repository.get_by_id(primary_patient_id)
            duplicate_patient = self.repository.get_by_id(duplicate_patient_id)

            if not primary_patient or not duplicate_patient:
                raise ValidationError("One or both patients not found")

            if primary_patient.id == duplicate_patient.id:
                raise ValidationError("Cannot merge patient with itself")

            # Merge metadata
            merge_metadata = {}
            if primary_patient.patient_data:
                merge_metadata.update(primary_patient.patient_data)
            if duplicate_patient.patient_data:
                for key, value in duplicate_patient.patient_data.items():
                    if key not in merge_metadata and value:
                        merge_metadata[key] = value

            # Update primary patient with merged data
            updates = {
                "patient_data": merge_metadata,
                "email": primary_patient.email or duplicate_patient.email,
                "birth_date": primary_patient.birth_date or duplicate_patient.birth_date,
                "treatment_type": primary_patient.treatment_type
                or duplicate_patient.treatment_type,
                "treatment_start_date": primary_patient.treatment_start_date
                or duplicate_patient.treatment_start_date,
            }

            # Migrate related records
            await self._migrate_patient_relationships(
                duplicate_patient_id, primary_patient_id
            )

            # Update primary patient
            updated_patient = self.repository.update(primary_patient, updates)

            # Soft delete duplicate patient
            await self._soft_delete_patient(duplicate_patient_id)

            logger.info(
                f"Patients merged successfully: {duplicate_patient_id} -> {primary_patient_id}"
            )

            return updated_patient

        except Exception as e:
            logger.error(f"Patient merge failed: {e}")
            self.db.rollback()
            raise

    @with_db_retry(max_retries=3)
    async def _migrate_patient_relationships(
        self, from_patient_id: UUID, to_patient_id: UUID
    ) -> None:
        """Migrate all relationships from duplicate to primary patient."""
        try:
            # Update messages
            from app.models.message import Message

            self.db.query(Message).filter(Message.patient_id == from_patient_id).update(
                {"patient_id": to_patient_id}
            )

            # Update flow states
            from app.models.flow import PatientFlowState

            self.db.query(PatientFlowState).filter(
                PatientFlowState.patient_id == from_patient_id
            ).update({"patient_id": to_patient_id})

            # Update alerts
            from app.models.alert import Alert

            self.db.query(Alert).filter(Alert.patient_id == from_patient_id).update(
                {"patient_id": to_patient_id}
            )

            self.db.commit()

        except Exception as e:
            logger.error(f"Relationship migration failed: {e}")
            self.db.rollback()
            raise

    @with_db_retry(max_retries=3)
    async def _soft_delete_patient(self, patient_id: UUID) -> None:
        """Soft delete patient by updating metadata."""
        try:
            patient = self.repository.get_by_id(patient_id)
            if patient:
                patient.patient_data = patient.patient_data or {}
                patient.patient_data["deleted"] = True
                patient.patient_data["deleted_at"] = date.today().isoformat()
                patient.flow_state = FlowState.INACTIVE
                self.db.commit()

        except Exception as e:
            logger.error(f"Soft delete failed: {e}")
            self.db.rollback()
            raise
