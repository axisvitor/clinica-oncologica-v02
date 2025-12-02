"""
Core CRUD operations for Patient repository.
"""
import hashlib
import json
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.patient import Patient
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class PatientRepositoryBase(BaseRepository[Patient]):
    """
    Base patient repository with core CRUD operations.
    """

    def __init__(self, db: Session):
        super().__init__(db, Patient)
        self._redis_client = None

    @property
    def redis(self):
        """Lazy load Redis client for caching"""
        if self._redis_client is None:
            try:
                from app.core.redis_unified import get_redis_client
                self._redis_client = get_redis_client('sync')
            except Exception:
                # Redis optional - gracefully degrade if unavailable
                self._redis_client = False
        return self._redis_client if self._redis_client else None

    def get_by_id(self, patient_id: UUID, eager_load: bool = True, include: List[str] = None) -> Optional[Patient]:
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
            Patient.id == patient_id,
            Patient.deleted_at.is_(None)
        )

        if eager_load:
            # PERFORMANCE: Load related entities to prevent N+1 queries
            query = query.options(
                selectinload(Patient.quiz_sessions),
                selectinload(Patient.flow_states),
                joinedload(Patient.doctor)
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

        return self.db.query(Patient).filter(
            Patient.phone_hash == phone_hash,
            Patient.deleted_at.is_(None)
        ).first()

    def get_by_doctor(self, doctor_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True) -> List[Patient]:
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
            Patient.doctor_id == doctor_id,
            Patient.deleted_at.is_(None)
        )

        if eager_load:
            # PERFORMANCE: Load quiz sessions and flow states to prevent N+1 queries
            query = query.options(
                selectinload(Patient.quiz_sessions),
                selectinload(Patient.flow_states)
            )

        return query.offset(skip).limit(limit).all()

    def get_all_active(self, skip: int = 0, limit: int = 100, eager_load: bool = True) -> List[Patient]:
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
        query = self.db.query(Patient).filter(
            Patient.deleted_at.is_(None)
        )

        if eager_load:
            # PERFORMANCE: Load all related entities to prevent N+1 queries
            query = query.options(
                selectinload(Patient.quiz_sessions),
                selectinload(Patient.flow_states),
                joinedload(Patient.doctor)
            )

        return query.offset(skip).limit(limit).all()

    def get_all_deleted(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Get all soft-deleted patients"""
        return self.db.query(Patient).filter(
            Patient.deleted_at.isnot(None)
        ).offset(skip).limit(limit).all()

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

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Patient]:
        """
        Get patient by idempotency key.

        QW-004: Database-level idempotency support

        Args:
            idempotency_key: Unique request identifier

        Returns:
            Patient if found, None otherwise
        """
        return self.db.query(Patient).filter(
            Patient.idempotency_key == idempotency_key,
            Patient.deleted_at.is_(None)
        ).first()
