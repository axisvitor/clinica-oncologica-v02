"""
Saga Persistence Operations.

This module handles database operations for saga state management,
including querying, status updates, and saga lifecycle operations.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus

from .types import SagaStatusInfo, FailedSagaSummary

logger = logging.getLogger(__name__)


class SagaPersistence:
    """
    Handles saga database operations.

    Provides a clean interface for:
    - Saga record retrieval
    - Status updates
    - Failed saga listing
    - Saga history queries
    """

    def __init__(self, db: Session):
        self.db = db

    def get_saga_by_id(self, saga_id: UUID) -> Optional[PatientOnboardingSaga]:
        """
        Get a saga by its ID.

        Args:
            saga_id: UUID of the saga

        Returns:
            PatientOnboardingSaga or None if not found
        """
        return (
            self.db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.id == saga_id)
            .first()
        )

    def get_saga_status(self, saga_id: UUID) -> Optional[SagaStatusInfo]:
        """
        Get current status of a saga for monitoring.

        Args:
            saga_id: UUID of the saga

        Returns:
            Dict with saga status info or None if not found
        """
        saga = self.get_saga_by_id(saga_id)

        if not saga:
            return None

        return SagaStatusInfo(
            id=str(saga.id),
            status=saga.status.value if saga.status else None,
            current_step=saga.current_step,
            patient_id=str(saga.patient_id) if saga.patient_id else None,
            doctor_id=str(saga.doctor_id) if saga.doctor_id else None,
            started_at=saga.started_at.isoformat() if saga.started_at else None,
            completed_at=saga.completed_at.isoformat() if saga.completed_at else None,
            failed_at=saga.failed_at.isoformat() if saga.failed_at else None,
            error_message=saga.error_message,
            error_type=saga.error_type,
            execution_log=saga.execution_log,
        )

    def list_failed_sagas(
        self, doctor_id: Optional[UUID] = None, limit: int = 50
    ) -> List[FailedSagaSummary]:
        """
        List failed sagas for manual review or retry.

        Args:
            doctor_id: Optional filter by doctor
            limit: Maximum number of results

        Returns:
            List of failed saga summaries
        """
        query = self.db.query(PatientOnboardingSaga).filter(
            PatientOnboardingSaga.status == SagaStatus.FAILED
        )

        if doctor_id:
            query = query.filter(PatientOnboardingSaga.doctor_id == doctor_id)

        query = query.order_by(PatientOnboardingSaga.failed_at.desc()).limit(limit)
        sagas = query.all()

        return [
            FailedSagaSummary(
                id=str(s.id),
                doctor_id=str(s.doctor_id) if s.doctor_id else None,
                current_step=s.current_step,
                error_message=s.error_message,
                error_type=s.error_type,
                failed_at=s.failed_at.isoformat() if s.failed_at else None,
                retry_count=s.retry_count,
            )
            for s in sagas
        ]

    def list_pending_sagas(
        self, limit: int = 100
    ) -> List[PatientOnboardingSaga]:
        """
        List pending/in-progress sagas that may need attention.

        Args:
            limit: Maximum number of results

        Returns:
            List of pending saga records
        """
        # Note: STEP_4_MESSAGE_SENT is intentionally excluded from "pending".
        # Sagas at step 4 are considered terminal from onboarding perspective
        # (message scheduling is non-blocking) and should not be retried as pending.
        return (
            self.db.query(PatientOnboardingSaga)
            .filter(
                PatientOnboardingSaga.status.in_([
                    SagaStatus.STARTED,
                    SagaStatus.STEP_1_PATIENT_CREATED,
                    SagaStatus.STEP_3_FLOW_INITIALIZED,
                    SagaStatus.COMPENSATING,
                ])
            )
            .order_by(PatientOnboardingSaga.started_at.asc())
            .limit(limit)
            .all()
        )

    def list_compensating_sagas(self, limit: int = 50) -> List[PatientOnboardingSaga]:
        """
        List sagas currently in compensation state.

        Args:
            limit: Maximum number of results

        Returns:
            List of compensating saga records
        """
        return (
            self.db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.status == SagaStatus.COMPENSATING)
            .order_by(PatientOnboardingSaga.started_at.asc())
            .limit(limit)
            .all()
        )

    def get_saga_statistics(
        self, doctor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get saga execution statistics.

        Args:
            doctor_id: Optional filter by doctor

        Returns:
            Dictionary with saga statistics
        """
        query = self.db.query(PatientOnboardingSaga)

        if doctor_id:
            query = query.filter(PatientOnboardingSaga.doctor_id == doctor_id)

        # Known tradeoff: this loads all matching sagas in memory.
        # Kept as-is for audit scope; optimize with grouped aggregates if needed.
        sagas = query.all()

        return {
            "total": len(sagas),
            "completed": sum(
                1 for s in sagas if s.status == SagaStatus.COMPLETED
            ),
            "failed": sum(
                1 for s in sagas if s.status == SagaStatus.FAILED
            ),
            "in_progress": sum(
                1
                for s in sagas
                if s.status
                in [
                    SagaStatus.STARTED,
                    SagaStatus.STEP_1_PATIENT_CREATED,
                    SagaStatus.STEP_3_FLOW_INITIALIZED,
                ]
            ),
            "compensating": sum(
                1 for s in sagas if s.status == SagaStatus.COMPENSATING
            ),
        }


__all__ = ["SagaPersistence"]
