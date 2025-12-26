"""
PatientCRUDService - Basic CRUD operations for patients.

This service handles only basic create, read, update, delete operations
following Single Responsibility Principle.

File: backend-hormonia/app/services/patient/crud_service.py
LOC: ~150
Responsibility: CRUD operations with transaction management
"""

from __future__ import annotations

# Standard library imports
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

# Third-party imports
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from app.exceptions import NotFoundError
from app.infrastructure.cache import get_unified_cache_manager as get_cache_manager
from app.models.patient import Patient, FlowState
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientUpdate
from app.services.cache import CacheInvalidationService, CacheKeyBuilder, InvalidationStrategy
from app.utils.db_retry import with_db_retry
from app.utils.transaction_manager import sync_transaction

logger = logging.getLogger(__name__)

# Thread pool for running async cache operations from sync context
_cache_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cache_invalidation")


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

    def __init__(
        self,
        db: Any,
        repository: Optional[PatientRepository] = None,
        cache_invalidation_service: Optional[CacheInvalidationService] = None,
    ):
        self.db = db
        self.repository = repository or PatientRepository(db)
        self._logger = logging.getLogger(__name__)

        # Initialize cache services
        self._cache_invalidation = cache_invalidation_service or CacheInvalidationService(
            redis_client=None,  # Will be set from cache manager if available
            key_builder=CacheKeyBuilder(namespace="hormonia", version="v1"),
            max_retries=3,
            retry_delay=0.1,
            retry_backoff=2.0,
        )

        # Try to get Redis client from cache manager
        try:
            cache_manager = get_cache_manager()
            if hasattr(cache_manager, 'redis_client'):
                self._cache_invalidation.redis_client = cache_manager.redis_client
        except Exception as e:
            self._logger.debug(f"Could not get Redis client from cache manager: {e}")

    def _run_cache_invalidation(self, entity: str, identifier: str, cascade: bool = True) -> None:
        """
        Safely run async cache invalidation from sync context.

        Uses ThreadPoolExecutor to avoid RuntimeError from asyncio.run() when
        called from within an existing event loop (e.g., FastAPI async endpoints).

        This is a fire-and-forget operation - failures are logged but don't block.
        """
        async def _invalidate():
            try:
                await self._cache_invalidation.invalidate_entity(
                    entity=entity,
                    identifier=identifier,
                    cascade=cascade,
                )
            except Exception as e:
                self._logger.warning(f"Cache invalidation failed for {entity}/{identifier}: {e}")

        def _run_in_thread():
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_invalidate())
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Thread cache invalidation error: {e}")

        try:
            # Submit to thread pool (fire-and-forget)
            _cache_executor.submit(_run_in_thread)
        except Exception as e:
            self._logger.warning(f"Failed to submit cache invalidation task: {e}")

    @with_db_retry(max_retries=3)
    def get_patient(self, patient_id: UUID) -> Patient:
        """
        Get patient by ID.

        Args:
            patient_id: UUID of the patient to retrieve

        Returns:
            Patient instance

        Raises:
            NotFoundError: If patient does not exist
        """
        self._logger.debug(f"Fetching patient: {patient_id}")
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")
        return patient

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
        self._logger.debug(f"Listing patients for doctor: {doctor_id}, page: {page}")
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
        """
        Update patient information with transaction management.

        Args:
            patient_id: UUID of the patient to update
            patient_data: Updated patient data

        Returns:
            Updated Patient instance

        Raises:
            NotFoundError: If patient does not exist

        Transaction Strategy:
            1. Start transaction
            2. Update patient in DB
            3. Commit transaction
            4. Invalidate cache (best-effort, outside transaction)
            5. Rollback on any DB error
        """
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        update_dict = patient_data.dict(exclude_unset=True)

        # Use transaction context manager for atomic operations
        with sync_transaction(self.db) as session:
            # Update patient within transaction
            updated_patient = self.repository.update(patient, update_dict)
            # Transaction auto-commits here if no exception

        # Cache invalidation AFTER successful DB commit (best-effort, fire-and-forget)
        # Uses thread pool to avoid RuntimeError from asyncio.run() in async context
        self._run_cache_invalidation(entity="patient", identifier=str(patient_id), cascade=True)

        self._logger.info(f"Patient updated: {patient_id}")
        return updated_patient

    @with_db_retry(max_retries=3)
    def delete_patient(self, patient_id: UUID) -> bool:
        """
        Soft delete patient with transaction management.

        Args:
            patient_id: UUID of the patient to soft delete

        Returns:
            True if deletion successful, False if patient not found

        Transaction Strategy:
            1. Start transaction
            2. Set deleted_at timestamp
            3. Commit transaction
            4. Invalidate cache (best-effort, outside transaction)
            5. Rollback on any DB error
        """
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return False

        doctor_id = patient.doctor_id  # Save for cache invalidation

        try:
            # Use transaction context manager for atomic operations
            with sync_transaction(self.db) as session:
                patient.deleted_at = datetime.now(timezone.utc)
                session.add(patient)
                # Transaction auto-commits here if no exception

            # Cache invalidation AFTER successful DB commit (best-effort, fire-and-forget)
            self._run_cache_invalidation(entity="patient", identifier=str(patient_id), cascade=True)

            self._logger.info(f"Patient soft deleted: {patient_id}")
            return True

        except Exception as e:
            # Transaction manager handles rollback automatically
            self._logger.error(
                f"Failed to soft delete patient {patient_id}: {e}",
                exc_info=True
            )
            return False

    @with_db_retry(max_retries=3)
    def restore_patient(self, patient_id: UUID) -> bool:
        """
        Restore a soft-deleted patient with transaction management.

        Args:
            patient_id: UUID of the patient to restore

        Returns:
            True if restoration successful, False if patient not found

        Transaction Strategy:
            1. Start transaction
            2. Clear deleted_at timestamp
            3. Commit transaction
            4. Invalidate cache (best-effort, outside transaction)
            5. Rollback on any DB error
        """
        patient = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.deleted_at.isnot(None))
            .first()
        )

        if not patient:
            return False

        doctor_id = patient.doctor_id  # Save for cache invalidation

        try:
            # Use transaction context manager for atomic operations
            with sync_transaction(self.db) as session:
                patient.deleted_at = None
                session.add(patient)
                # Transaction auto-commits here if no exception

            # Cache invalidation AFTER successful DB commit (best-effort, fire-and-forget)
            self._run_cache_invalidation(entity="patient", identifier=str(patient_id), cascade=True)

            self._logger.info(f"Patient restored: {patient_id}")
            return True

        except Exception as e:
            # Transaction manager handles rollback automatically
            self._logger.error(
                f"Failed to restore patient {patient_id}: {e}",
                exc_info=True
            )
            return False

    @staticmethod
    def invalidate_patient_cache_static(patient_id: UUID, doctor_id: UUID) -> None:
        """
        Static method to invalidate patient caches using centralized service.
        Can be called without service instance (e.g., from router after create).

        This is a best-effort operation - failures are logged but don't affect the main flow.
        Uses ThreadPoolExecutor to safely run async code from any context.
        """
        def _run_invalidation():
            try:
                # Create temporary cache invalidation service
                cache_service = CacheInvalidationService(
                    key_builder=CacheKeyBuilder(namespace="hormonia", version="v1"),
                    max_retries=3,
                )

                # Try to get Redis client
                try:
                    cache_manager = get_cache_manager()
                    if hasattr(cache_manager, 'redis_client'):
                        cache_service.redis_client = cache_manager.redis_client
                except Exception as e:
                    logger.debug(f"Cache manager init failed, using local fallback: {e}")

                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(cache_service.invalidate_entity(
                        entity="patient",
                        identifier=str(patient_id),
                        cascade=True,
                    ))
                    logger.debug(f"Invalidated caches for patient (static): {patient_id}")
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Cache invalidation failed for patient {patient_id}: {e}")

        try:
            # Submit to thread pool (fire-and-forget)
            _cache_executor.submit(_run_invalidation)
        except Exception as e:
            # Best-effort: log warning but don't raise
            logger.warning(f"Failed to submit cache invalidation for patient {patient_id}: {e}")
