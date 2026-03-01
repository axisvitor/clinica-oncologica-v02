"""
PatientSyncService - Patient synchronization and consistency.

Handles:
- Duplicate detection (CPF, email, phone)
- Patient merging
- Relationship migration
- Data consistency checks

File: backend-hormonia/app/services/patient/sync_service.py
LOC: ~180
Responsibility: Synchronization and consistency
Pattern: Single Responsibility
"""

from __future__ import annotations

import logging
from inspect import iscoroutinefunction
from datetime import date
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ValidationError
from app.models.flow import PatientFlowState
from app.models.patient import FlowState, Patient
from app.repositories.patient import PatientRepository
from app.utils.db_retry import with_db_retry

logger = logging.getLogger(__name__)


class PatientSyncService:
    """
    Service for patient synchronization and consistency.

    Responsibilities:
    - Check for duplicate patients
    - Merge duplicate records
    - Migrate patient relationships
    - Maintain data consistency
    """

    def __init__(self, db: Any, patient_repository: Optional[PatientRepository] = None):
        """
        Initialize sync service.

        Args:
            db: Database session
            patient_repository: Patient repository instance
        """
        self.db = db
        self.repository = patient_repository or PatientRepository(db)
        self._logger = logging.getLogger(__name__)

    @property
    def _is_async_session(self) -> bool:
        execute = getattr(self.db, "execute", None)
        return isinstance(self.db, AsyncSession) or iscoroutinefunction(execute)

    async def _get_patient_by_id(self, patient_id: UUID) -> Optional[Patient]:
        if self._is_async_session:
            stmt = select(Patient).filter(Patient.id == patient_id, Patient.deleted_at.is_(None))
            return (await self.db.execute(stmt)).scalars().first()
        return self.repository.get_by_id(patient_id)

    async def _commit(self) -> None:
        if self._is_async_session:
            await self.db.commit()
            return
        self.db.commit()

    async def _rollback(self) -> None:
        if self._is_async_session:
            await self.db.rollback()
            return
        self.db.rollback()

    async def _refresh(self, instance: Patient) -> None:
        if self._is_async_session:
            await self.db.refresh(instance)
            return
        self.db.refresh(instance)

    def _check_duplicate_by_hashed_field(
        self,
        value: str,
        hash_builder: Callable[[str], Optional[str]],
        patient_field: Any,
        error_label: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """Shared duplicate-check query path for hashed patient fields."""
        try:
            field_hash = hash_builder(value)
            if not field_hash:
                return None
            stmt = select(Patient).filter(
                patient_field == field_hash, Patient.deleted_at.is_(None)
            )

            if doctor_id:
                stmt = stmt.filter(Patient.doctor_id == doctor_id)

            if exclude_patient_id:
                stmt = stmt.filter(Patient.id != exclude_patient_id)

            result = self.db.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            self._logger.error(f"{error_label} duplicate check failed: {e}")
            return None

    @with_db_retry(max_retries=3)
    def check_duplicate_cpf(
        self,
        cpf: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """
        Check for existing patient with same CPF.

        Args:
            cpf: CPF to check (normalized)
            doctor_id: Filter by doctor
            exclude_patient_id: Exclude this patient ID

        Returns:
            Existing patient or None
        """
        from app.services.encryption import get_cpf_encryption_service

        service = get_cpf_encryption_service()
        return self._check_duplicate_by_hashed_field(
            value=cpf,
            hash_builder=service.hash_cpf,
            patient_field=Patient.cpf_hash,
            error_label="CPF",
            doctor_id=doctor_id,
            exclude_patient_id=exclude_patient_id,
        )

    @with_db_retry(max_retries=3)
    def check_duplicate_email(
        self,
        email: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """
        Check for existing patient with same email.

        Args:
            email: Email to check (normalized)
            doctor_id: Filter by doctor
            exclude_patient_id: Exclude this patient ID

        Returns:
            Existing patient or None
        """
        from app.services.encryption import get_lgpd_encryption_service

        service = get_lgpd_encryption_service()
        normalized_email = email.lower()
        return self._check_duplicate_by_hashed_field(
            value=normalized_email,
            hash_builder=service.hash_email,
            patient_field=Patient.email_hash,
            error_label="Email",
            doctor_id=doctor_id,
            exclude_patient_id=exclude_patient_id,
        )

    @with_db_retry(max_retries=3)
    def check_duplicate_phone(
        self,
        phone: str,
        doctor_id: Optional[UUID] = None,
        exclude_patient_id: Optional[UUID] = None,
    ) -> Optional[Patient]:
        """
        Check for existing patient with same phone.

        Args:
            phone: Phone to check (E.164 format)
            doctor_id: Filter by doctor
            exclude_patient_id: Exclude this patient ID

        Returns:
            Existing patient or None
        """
        from app.services.encryption import get_lgpd_encryption_service

        service = get_lgpd_encryption_service()
        return self._check_duplicate_by_hashed_field(
            value=phone,
            hash_builder=service.hash_phone,
            patient_field=Patient.phone_hash,
            error_label="Phone",
            doctor_id=doctor_id,
            exclude_patient_id=exclude_patient_id,
        )

    @with_db_retry(max_retries=3)
    async def merge_patients(
        self, primary_patient_id: UUID, duplicate_patient_id: UUID
    ) -> Patient:
        """
        Merge duplicate patient records.

        Args:
            primary_patient_id: ID of patient to keep
            duplicate_patient_id: ID of patient to merge and delete

        Returns:
            Updated primary patient

        Raises:
            ValidationError: If patients not found or same ID
        """
        try:
            primary_patient = await self._get_patient_by_id(primary_patient_id)
            duplicate_patient = await self._get_patient_by_id(duplicate_patient_id)

            if not primary_patient or not duplicate_patient:
                raise ValidationError("One or both patients not found")

            if primary_patient.id == duplicate_patient.id:
                raise ValidationError("Cannot merge patient with itself")

            # Merge metadata
            merge_metadata: dict[str, Any] = {}
            primary_patient_data = getattr(primary_patient, "patient_data", None)
            duplicate_patient_data = getattr(duplicate_patient, "patient_data", None)
            if isinstance(primary_patient_data, dict):
                merge_metadata.update(primary_patient_data)
            if isinstance(duplicate_patient_data, dict):
                for key, value in duplicate_patient_data.items():
                    if key not in merge_metadata and value:
                        merge_metadata[key] = value

            # Update primary patient with merged data
            updates = {
                "patient_data": merge_metadata,
                "email": primary_patient.email or duplicate_patient.email,
                "birth_date": primary_patient.birth_date or duplicate_patient.birth_date,
                "treatment_type": primary_patient.treatment_type or duplicate_patient.treatment_type,
                "treatment_start_date": primary_patient.treatment_start_date
                or duplicate_patient.treatment_start_date,
            }

            # Migrate related records
            await self._migrate_patient_relationships(duplicate_patient_id, primary_patient_id)

            # Update primary patient
            if self._is_async_session:
                for field, value in updates.items():
                    setattr(primary_patient, field, value)
                self.db.add(primary_patient)
                await self._commit()
                await self._refresh(primary_patient)
                updated_patient = primary_patient
            else:
                updated_patient = self.repository.update(primary_patient, updates)

            # Soft delete duplicate
            await self._soft_delete_patient(duplicate_patient_id)

            self._logger.info(f"Patients merged: {duplicate_patient_id} -> {primary_patient_id}")

            return updated_patient

        except Exception as e:
            self._logger.error(f"Patient merge failed: {e}")
            await self._rollback()
            raise

    @with_db_retry(max_retries=3)
    async def _migrate_patient_relationships(
        self, from_patient_id: UUID, to_patient_id: UUID
    ) -> None:
        """Migrate all relationships from duplicate to primary patient."""
        try:
            from app.models.message import Message

            from app.models.alert import Alert

            if self._is_async_session:
                await self.db.execute(
                    update(Message)
                    .where(Message.patient_id == from_patient_id)
                    .values(patient_id=to_patient_id)
                )
                await self.db.execute(
                    update(PatientFlowState)
                    .where(PatientFlowState.patient_id == from_patient_id)
                    .values(patient_id=to_patient_id)
                )
                await self.db.execute(
                    update(Alert)
                    .where(Alert.patient_id == from_patient_id)
                    .values(patient_id=to_patient_id)
                )
            else:
                self.db.query(Message).filter(Message.patient_id == from_patient_id).update(
                    {"patient_id": to_patient_id}
                )
                self.db.query(PatientFlowState).filter(
                    PatientFlowState.patient_id == from_patient_id
                ).update({"patient_id": to_patient_id})
                self.db.query(Alert).filter(Alert.patient_id == from_patient_id).update(
                    {"patient_id": to_patient_id}
                )

            await self._commit()

        except Exception as e:
            self._logger.error(f"Relationship migration failed: {e}")
            await self._rollback()
            raise

    @with_db_retry(max_retries=3)
    async def _soft_delete_patient(self, patient_id: UUID) -> None:
        """Soft delete patient by updating metadata."""
        try:
            patient = await self._get_patient_by_id(patient_id)
            if patient:
                patient_data = patient.patient_data if isinstance(patient.patient_data, dict) else {}
                patient_data["deleted"] = True
                patient_data["deleted_at"] = date.today().isoformat()
                patient.patient_data = patient_data
                patient.flow_state = FlowState.INACTIVE
                if self._is_async_session:
                    self.db.add(patient)
                await self._commit()

        except Exception as e:
            self._logger.error(f"Soft delete failed: {e}")
            await self._rollback()
            raise
