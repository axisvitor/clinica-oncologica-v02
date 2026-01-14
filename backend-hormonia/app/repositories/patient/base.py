"""
Core CRUD operations for Patient repository.

This module provides base CRUD operations for the Patient model,
including create, update, read, and delete operations with
LGPD compliance and Redis caching support.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.patient import Patient
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class PatientRepositoryBase(BaseRepository[Patient]):
    """
    Base patient repository with core CRUD operations.

    Handles all database interactions for patients including
    CRUD operations with LGPD compliance, Redis caching support,
    and optimized query execution.

    Attributes:
        db: SQLAlchemy database session.
        model: Patient model class.
        _redis_client: Optional Redis client for caching.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the patient repository.

        Args:
            db: SQLAlchemy database session.
        """
        super().__init__(db, Patient)
        self._redis_client = None
        self._logger = logger

    @property
    def redis(self):
        """Lazy load Redis client for caching"""
        if self._redis_client is None:
            try:
                from app.core.redis_unified import get_redis_client

                self._redis_client = get_redis_client("sync")
            except Exception as e:
                # Redis optional - gracefully degrade if unavailable
                logger.debug(f"Redis client not available, caching disabled: {e}")
                self._redis_client = False
        return self._redis_client if self._redis_client else None

    def create(self, obj_in: Dict[str, Any], auto_commit: bool = True) -> Patient:
        """
        Create a new patient record.

        Args:
            obj_in: Dictionary with patient data.
            auto_commit: If True (default), commits the transaction immediately.
                         Set to False when using within a saga/Unit of Work pattern
                         where the caller manages the transaction commit.

        Returns:
            The created Patient instance.

        Note:
            When auto_commit=False, the caller is responsible for calling
            db.commit() after all saga steps complete successfully.
        """
        data = dict(obj_in)

        phone = data.pop("phone", None)
        email = data.pop("email", None)
        cpf = data.pop("cpf", None)
        is_active = data.pop("is_active", None)
        timezone = data.pop("timezone", None)

        allergies = data.pop("allergies", None)
        current_medications = data.pop("current_medications", None)
        comorbidities = data.pop("comorbidities", None)
        blood_type = data.pop("blood_type", None)
        emergency_contact_name = data.pop("emergency_contact_name", None)
        emergency_contact_phone = data.pop("emergency_contact_phone", None)

        metadata_payload = data.pop("metadata", None)
        patient_data_payload = data.pop("patient_data", None)

        merged_patient_data: Dict[str, Any] = {}
        if isinstance(patient_data_payload, dict):
            merged_patient_data.update(patient_data_payload)
        if isinstance(metadata_payload, dict):
            merged_patient_data.update(metadata_payload)

        if (
            allergies is not None
            or current_medications is not None
            or comorbidities is not None
        ):
            medical_history = merged_patient_data.get("medical_history")
            if not isinstance(medical_history, dict):
                medical_history = {}
            if allergies is not None:
                medical_history["allergies"] = allergies
            if current_medications is not None:
                medical_history["medications"] = current_medications
            if comorbidities is not None:
                medical_history["conditions"] = comorbidities
            merged_patient_data["medical_history"] = medical_history

        if blood_type is not None:
            merged_patient_data["blood_type"] = blood_type

        if emergency_contact_name is not None or emergency_contact_phone is not None:
            emergency_contact = merged_patient_data.get("emergency_contact")
            if not isinstance(emergency_contact, dict):
                emergency_contact = {}
            if emergency_contact_name is not None:
                emergency_contact["name"] = emergency_contact_name
            if emergency_contact_phone is not None:
                emergency_contact["phone"] = emergency_contact_phone

            if emergency_contact.get("name") and emergency_contact.get("phone"):
                merged_patient_data["emergency_contact"] = emergency_contact
            else:
                custom_fields = merged_patient_data.get("custom_fields")
                if not isinstance(custom_fields, dict):
                    custom_fields = {}
                if emergency_contact_name is not None:
                    custom_fields["emergency_contact_name"] = emergency_contact_name
                if emergency_contact_phone is not None:
                    custom_fields["emergency_contact_phone"] = emergency_contact_phone
                merged_patient_data["custom_fields"] = custom_fields

        integrity_hash = merged_patient_data.pop("integrity_hash", None)
        if integrity_hash is not None:
            custom_fields = merged_patient_data.get("custom_fields")
            if not isinstance(custom_fields, dict):
                custom_fields = {}
            custom_fields["integrity_hash"] = integrity_hash
            merged_patient_data["custom_fields"] = custom_fields

        if timezone:
            preferences = merged_patient_data.get("preferences")
            if not isinstance(preferences, dict):
                preferences = {}
            preferences["timezone"] = timezone
            merged_patient_data["preferences"] = preferences

        if merged_patient_data:
            data["patient_data"] = merged_patient_data

        patient = Patient(**data)

        if phone is not None:
            patient.set_phone(phone)
        if email is not None:
            patient.set_email(email)
        if cpf is not None:
            patient.set_cpf(cpf)

        try:
            self.db.add(patient)
            if auto_commit:
                # Standard behavior: commit immediately
                self.db.commit()
                self.db.refresh(patient)
            else:
                # Saga/Unit of Work pattern: flush only, caller commits
                self.db.flush()
                self.db.refresh(patient)
        except Exception:
            self.db.rollback()
            raise

        self._invalidate_caches_for_model(patient)
        return patient

    def update(
        self, db_obj: Patient, obj_in: Dict[str, Any], auto_commit: bool = True
    ) -> Patient:
        """
        Update an existing patient record.

        Args:
            db_obj: Existing Patient instance to update.
            obj_in: Dictionary with updated patient data.
            auto_commit: If True (default), commits the transaction immediately.
                         Set to False when using within a saga/Unit of Work pattern.

        Returns:
            The updated Patient instance.
        """
        data = dict(obj_in)

        phone_present = "phone" in data
        email_present = "email" in data
        cpf_present = "cpf" in data
        is_active_present = "is_active" in data
        timezone_present = "timezone" in data

        phone = data.pop("phone", None)
        email = data.pop("email", None)
        cpf = data.pop("cpf", None)
        is_active = data.pop("is_active", None)
        timezone = data.pop("timezone", None)

        allergies = data.pop("allergies", None)
        current_medications = data.pop("current_medications", None)
        comorbidities = data.pop("comorbidities", None)
        blood_type = data.pop("blood_type", None)
        emergency_contact_name = data.pop("emergency_contact_name", None)
        emergency_contact_phone = data.pop("emergency_contact_phone", None)

        metadata_payload = data.pop("metadata", None)
        patient_data_payload = data.pop("patient_data", None)

        clinical_fields_present = any(
            [
                allergies,
                current_medications,
                comorbidities,
                blood_type,
                emergency_contact_name,
                emergency_contact_phone,
            ]
        )

        if phone_present:
            db_obj.set_phone(phone)
        if email_present:
            db_obj.set_email(email)
        if cpf_present:
            db_obj.set_cpf(cpf)

        if (
            metadata_payload is not None
            or patient_data_payload is not None
            or timezone_present
            or clinical_fields_present
        ):
            merged_patient_data: Dict[str, Any] = dict(db_obj.patient_data or {})

            if isinstance(patient_data_payload, dict):
                merged_patient_data.update(patient_data_payload)
            if isinstance(metadata_payload, dict):
                merged_patient_data.update(metadata_payload)

            if (
                allergies is not None
                or current_medications is not None
                or comorbidities is not None
            ):
                medical_history = merged_patient_data.get("medical_history")
                if not isinstance(medical_history, dict):
                    medical_history = {}
                if allergies is not None:
                    medical_history["allergies"] = allergies
                if current_medications is not None:
                    medical_history["medications"] = current_medications
                if comorbidities is not None:
                    medical_history["conditions"] = comorbidities
                merged_patient_data["medical_history"] = medical_history

            if blood_type is not None:
                merged_patient_data["blood_type"] = blood_type

            if (
                emergency_contact_name is not None
                or emergency_contact_phone is not None
            ):
                emergency_contact = merged_patient_data.get("emergency_contact")
                if not isinstance(emergency_contact, dict):
                    emergency_contact = {}
                if emergency_contact_name is not None:
                    emergency_contact["name"] = emergency_contact_name
                if emergency_contact_phone is not None:
                    emergency_contact["phone"] = emergency_contact_phone

                if emergency_contact.get("name") and emergency_contact.get("phone"):
                    merged_patient_data["emergency_contact"] = emergency_contact
                else:
                    custom_fields = merged_patient_data.get("custom_fields")
                    if not isinstance(custom_fields, dict):
                        custom_fields = {}
                    if emergency_contact_name is not None:
                        custom_fields["emergency_contact_name"] = emergency_contact_name
                    if emergency_contact_phone is not None:
                        custom_fields["emergency_contact_phone"] = (
                            emergency_contact_phone
                        )
                    merged_patient_data["custom_fields"] = custom_fields

            integrity_hash = merged_patient_data.pop("integrity_hash", None)
            if integrity_hash is not None:
                custom_fields = merged_patient_data.get("custom_fields")
                if not isinstance(custom_fields, dict):
                    custom_fields = {}
                custom_fields["integrity_hash"] = integrity_hash
                merged_patient_data["custom_fields"] = custom_fields

            if timezone_present:
                preferences = merged_patient_data.get("preferences")
                if not isinstance(preferences, dict):
                    preferences = {}
                preferences["timezone"] = timezone
                merged_patient_data["preferences"] = preferences

            db_obj.patient_data = merged_patient_data

        for field, value in data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        try:
            self.db.add(db_obj)
            if auto_commit:
                # Standard behavior: commit immediately
                self.db.commit()
                self.db.refresh(db_obj)
            else:
                # Saga/Unit of Work pattern: flush only, caller commits
                self.db.flush()
                self.db.refresh(db_obj)
        except Exception:
            self.db.rollback()
            raise

        self._invalidate_caches_for_model(db_obj)
        return db_obj

    def get_by_id(
        self, patient_id: UUID, eager_load: bool = True, include: List[str] = None
    ) -> Optional[Patient]:
        """
        Get patient by ID (only active patients) with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading prevents N+1 queries.

        Relationships loaded when eager_load=True:
        - quiz_sessions: Patient's quiz sessions (selectinload - 1:many)
        - flow_states: Patient's flow states (selectinload - 1:many)
        - doctor: Patient's assigned doctor (joinedload - 1:1)

        Args:
            patient_id: UUID of the patient
            eager_load: Enable eager loading (default: True for performance)
            include: List of relationships to load (ignored, kept for API compatibility)

        Returns:
            Patient with relationships pre-loaded or None
        """
        query = self.db.query(Patient).filter(
            Patient.id == patient_id, Patient.deleted_at.is_(None)
        )

        if eager_load:
            # PERFORMANCE: Load related entities to prevent N+1 queries
            query = query.options(
                selectinload(Patient.quiz_sessions),
                selectinload(Patient.flow_states),
                joinedload(Patient.doctor),
            )

        return query.first()

    def get_by_id_including_deleted(self, patient_id: UUID) -> Optional[Patient]:
        """Get patient by ID including soft-deleted patients"""
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_by_phone(self, phone: str) -> Optional[Patient]:
        """
        Get patient by phone (only active patients).

        LGPD Compliance: Searches by phone_hash (plaintext column removed in migration 030).
        """
        from app.services.encryption import get_lgpd_encryption_service

        service = get_lgpd_encryption_service()
        phone_hash = service.hash_phone(phone)

        return (
            self.db.query(Patient)
            .filter(Patient.phone_hash == phone_hash, Patient.deleted_at.is_(None))
            .first()
        )

    def get_by_doctor(
        self, doctor_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Patient]:
        """
        Get active patients for a doctor with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading prevents N+1 queries.

        Relationships loaded when eager_load=True:
        - quiz_sessions: Patient's quiz sessions (selectinload - 1:many)
        - flow_states: Patient's flow states (selectinload - 1:many)

        Args:
            doctor_id: UUID of the doctor
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of patients with relationships pre-loaded
        """
        query = self.db.query(Patient).filter(
            Patient.doctor_id == doctor_id, Patient.deleted_at.is_(None)
        )

        if eager_load:
            # PERFORMANCE: Load quiz sessions and flow states to prevent N+1 queries
            query = query.options(
                selectinload(Patient.quiz_sessions), selectinload(Patient.flow_states)
            )

        return query.offset(skip).limit(limit).all()

    def get_all_active(
        self, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Patient]:
        """
        Get all active (non-deleted) patients with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading prevents N+1 queries.

        Relationships loaded when eager_load=True:
        - quiz_sessions: Patient's quiz sessions (selectinload - 1:many)
        - flow_states: Patient's flow states (selectinload - 1:many)
        - doctor: Patient's assigned doctor (joinedload - 1:1)

        Args:
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of active patients with relationships pre-loaded
        """
        query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))

        if eager_load:
            # PERFORMANCE: Load all related entities to prevent N+1 queries
            query = query.options(
                selectinload(Patient.quiz_sessions),
                selectinload(Patient.flow_states),
                joinedload(Patient.doctor),
            )

        return query.offset(skip).limit(limit).all()

    def get_all_deleted(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get all soft-deleted patients"""
        return (
            self.db.query(Patient)
            .filter(Patient.deleted_at.isnot(None))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_active(self, **filters) -> int:
        """Count active patients with optional filters"""
        query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))

        for field, value in filters.items():
            if hasattr(Patient, field) and value is not None:
                query = query.filter(getattr(Patient, field) == value)

        return query.count()

    def count_deleted(self) -> int:
        """Count soft-deleted patients"""
        return self.db.query(Patient).filter(Patient.deleted_at.isnot(None)).count()

    def _get_idempotency_cutoff(self) -> datetime:
        """Return cutoff timestamp for valid idempotency keys."""
        return datetime.now(timezone.utc) - timedelta(hours=24)

    def clear_expired_idempotency_keys(
        self, cutoff: Optional[datetime] = None
    ) -> int:
        """
        Clear expired idempotency keys to avoid permanent blocking.

        Args:
            cutoff: Timestamp threshold for expiration (defaults to 24 hours).

        Returns:
            Number of records updated.
        """
        cutoff = cutoff or self._get_idempotency_cutoff()
        cleared = (
            self.db.query(Patient)
            .filter(
                Patient.idempotency_key.isnot(None),
                Patient.created_at < cutoff,
            )
            .update({Patient.idempotency_key: None}, synchronize_session=False)
        )
        if cleared:
            try:
                self.db.flush()
            except Exception as flush_error:
                self._logger.debug(
                    f"Failed to flush idempotency cleanup: {flush_error}"
                )
        return cleared

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Patient]:
        """
        Get patient by idempotency key.

        QW-004: Database-level idempotency support

        Args:
            idempotency_key: Unique request identifier

        Returns:
            Patient if found, None otherwise
        """
        cutoff = self._get_idempotency_cutoff()
        self.clear_expired_idempotency_keys(cutoff)
        return (
            self.db.query(Patient)
            .filter(
                Patient.idempotency_key == idempotency_key,
                Patient.deleted_at.is_(None),
                Patient.created_at >= cutoff,
            )
            .first()
        )

    def get_active_patients(self, limit: int = 500, eager_load: bool = False) -> List[Patient]:
        """
        Get active (non-deleted) patients for bulk operations.

        This is an alias for get_all_active with reasonable defaults for
        background task processing (no eager loading to reduce memory).

        Args:
            limit: Maximum number of patients to return (default 500)
            eager_load: Whether to load relationships (default False for performance)

        Returns:
            List of active Patient objects
        """
        return self.get_all_active(skip=0, limit=limit, eager_load=eager_load)
