"""
PatientCRUDService - Basic CRUD operations for patients.

This service handles only basic create, read, update, delete operations
following Single Responsibility Principle.

File: backend-hormonia/app/services/patient/crud_service.py
LOC: ~100
Responsibility: CRUD operations only
"""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID


from app.models.patient import Patient, FlowState
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientUpdate
from app.exceptions import NotFoundError
from app.infrastructure.cache import (
    get_unified_cache_manager as get_cache_manager,
    invalidate_patient_cache,
)
from app.utils.db_retry import with_db_retry
import logging

logger = logging.getLogger(__name__)


class PatientCRUDService:
    """
    Service for basic CRUD operations on patients.

    Responsibilities:
    - Get patient by ID
    - Get patient by phone
    - List patients with pagination and filters
    - Update patient data
    - Delete patient (soft delete)
    - Restore deleted patient

    This service does NOT handle:
    - Patient creation (handled by PatientOnboardingService)
    - Flow management (handled by PatientFlowService)
    - Data validation (handled by PatientIntegrityService)
    """

    def __init__(self, db: Any, repository: PatientRepository):
        self.db = db
        self.repository = repository

    @with_db_retry(max_retries=3)
    def get_patient(self, patient_id: UUID) -> Optional[Patient]:
        """Get patient by ID."""
        logger.debug(f"Fetching patient: {patient_id}")
        return self.repository.get_by_id(patient_id)

    @with_db_retry(max_retries=3)
    def get_patient_by_phone(self, phone: str) -> Optional[Patient]:
        """Get patient by phone number."""
        return self.repository.get_by_phone(phone)

    @with_db_retry(max_retries=3)
    def list_patients(
        self,
        *,
        doctor_id: UUID,
        page: int = 1,
        size: int = 20,
        search: Optional[str] = None,
        flow_state: Optional[FlowState] = None,
        treatment_type: Optional[str] = None,
        start_date_from: Optional[datetime] = None,
        start_date_to: Optional[datetime] = None,
        include_related: bool = False,
    ) -> tuple[List[Patient], int]:
        """
        List patients with pagination and filtering.

        Returns:
            Tuple of (patients list, total count)
        """
        logger.debug(f"Listing patients for doctor: {doctor_id}, page: {page}")
        return self.repository.get_paginated(
            doctor_id=doctor_id,
            page=page,
            limit=size,
            search=search,
            flow_state=flow_state,
            treatment_type=treatment_type,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            eager_load=include_related,
        )

    @with_db_retry(max_retries=3)
    def update_patient(self, patient_id: UUID, patient_data: PatientUpdate) -> Patient:
        """Update patient information."""
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        update_dict = patient_data.dict(exclude_unset=True)
        updated_patient = self.repository.update(patient, update_dict)

        # Invalidate caches
        self._invalidate_patient_caches(patient_id, patient.doctor_id)

        logger.info(f"Patient updated: {patient_id}")
        return updated_patient

    @with_db_retry(max_retries=3)
    def delete_patient(self, patient_id: UUID) -> bool:
        """Soft delete patient (marks as deleted without removing from DB)."""
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return False

        patient.deleted_at = datetime.utcnow()

        try:
            self.db.commit()
            self._invalidate_patient_caches(patient_id, patient.doctor_id)
            logger.info(f"Patient soft deleted: {patient_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to soft delete patient {patient_id}: {e}")
            return False

    @with_db_retry(max_retries=3)
    def restore_patient(self, patient_id: UUID) -> bool:
        """Restore a soft-deleted patient."""
        patient = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.deleted_at.isnot(None))
            .first()
        )

        if not patient:
            return False

        patient.deleted_at = None

        try:
            self.db.commit()
            self._invalidate_patient_caches(patient_id, patient.doctor_id)
            logger.info(f"Patient restored: {patient_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to restore patient {patient_id}: {e}")
            return False

    def _invalidate_patient_caches(self, patient_id: UUID, doctor_id: UUID) -> None:
        """Invalidate all caches related to a patient."""
        invalidate_patient_cache(str(patient_id))

        cache_manager = get_cache_manager()
        cache_manager.invalidate_pattern(
            f"patient_by_id:*:{patient_id}*", namespace="cache"
        )
        cache_manager.invalidate_pattern(
            f"patient_list:*:{doctor_id}*", namespace="cache"
        )

        logger.debug(f"Invalidated caches for patient: {patient_id}")
