from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState, FlowTemplateVersion, FlowKind
from app.models.patient import Patient
from app.repositories.base import BaseRepository


class FlowStateRepository(BaseRepository[PatientFlowState]):
    """Repository for PatientFlowState model"""

    def __init__(self, db: Session):
        super().__init__(db, PatientFlowState)

    def get_by_patient(
        self, patient_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[PatientFlowState]:
        """
        Get flow states by patient with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default to prevent N+1 queries.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - patient.doctor: Doctor information via patient (nested joinedload - 1:1)
        - template_version: Flow template version (joinedload - 1:1)
        - template_version.kind: FlowKind via template_version (nested joinedload - 1:1)

        Args:
            patient_id: UUID of the patient
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of flow states with relationships pre-loaded
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(PatientFlowState)
            .filter(PatientFlowState.patient_id == patient_id)
            .order_by(PatientFlowState.started_at.desc())
        )

        if eager_load:
            # PERFORMANCE: Nested eager loading for related entities
            # This prevents additional queries when accessing patient.doctor or template_version.kind
            query = query.options(
                joinedload(PatientFlowState.patient).joinedload(Patient.doctor),
                joinedload(PatientFlowState.template_version).joinedload(
                    FlowTemplateVersion.kind
                ),
            )

        return query.offset(skip).limit(limit).all()

    def get_active_flow(self, patient_id: UUID) -> Optional[PatientFlowState]:
        """Get active flow for a specific patient (if not deleted)"""
        return (
            self.db.query(PatientFlowState)
            .join(Patient)
            .filter(
                PatientFlowState.patient_id == patient_id,
                PatientFlowState.completed_at.is_(None),
                Patient.deleted_at.is_(None)
            )
            .order_by(PatientFlowState.started_at.desc())
            .first()
        )

    def get_by_template_version(
        self, template_version_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[PatientFlowState]:
        """Get flow states by template version ID"""
        return (
            self.db.query(PatientFlowState)
            .filter(PatientFlowState.flow_template_version_id == template_version_id)
            .order_by(PatientFlowState.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_completed_flows(
        self, patient_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[PatientFlowState]:
        """Get completed flows for a patient"""
        return (
            self.db.query(PatientFlowState)
            .filter(PatientFlowState.patient_id == patient_id)
            .filter(PatientFlowState.completed_at.is_not(None))
            .order_by(PatientFlowState.completed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_patient_flow(self, patient_id: UUID) -> Optional[PatientFlowState]:
        """Get active flow for a patient (alias for get_active_flow)"""
        return self.get_active_flow(patient_id)

    def get_active_flows(
        self, limit: int = 1000, eager_load: bool = True
    ) -> List[PatientFlowState]:
        """
        Get all active flows for non-deleted patients.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default with nested relationships.
        SAFETY: Automatically filters out patients that have been soft-deleted.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - patient.doctor: Doctor information via patient (nested joinedload - 1:1)
        - template_version: Flow template version (joinedload - 1:1)
        - template_version.kind: FlowKind via template_version (nested joinedload - 1:1)

        Args:
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of active flow states with relationships pre-loaded
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(PatientFlowState)
            .join(Patient)  # Join to filter by patient status
            .filter(
                PatientFlowState.completed_at.is_(None),
                Patient.deleted_at.is_(None)  # Exclude deleted patients
            )
            # FAIR ORDERING: Prevent starvation by processing oldest flows first
            # 1. next_scheduled_at (oldest due first, nulls = never scheduled = highest priority)
            # 2. last_interaction_at (those not interacted with recently)
            # 3. started_at (oldest flows first as fallback for consistent ordering)
            # 4. id (deterministic tie-breaker for identical timestamps)
            .order_by(
                PatientFlowState.next_scheduled_at.asc().nullsfirst(),
                PatientFlowState.last_interaction_at.asc().nullsfirst(),
                PatientFlowState.started_at.asc(),
                PatientFlowState.id.asc()
            )
        )

        if eager_load:
            # PERFORMANCE: Nested eager loading prevents N+1 queries for related entities
            query = query.options(
                joinedload(PatientFlowState.patient).joinedload(Patient.doctor),
                joinedload(PatientFlowState.template_version).joinedload(
                    FlowTemplateVersion.kind
                ),
            )

        return query.limit(limit).all()

    def get_flows_by_type_and_day(
        self, flow_type: str, target_day: int, limit: int = 100
    ) -> List[PatientFlowState]:
        """Get flows by flow_type via template_version that are on a specific day"""
        from datetime import datetime, timezone
        from sqlalchemy import func, cast, Integer

        # Calculate flows that should be on target_day today
        today = datetime.now(timezone.utc).date()

        return (
            self.db.query(PatientFlowState)
            .join(
                FlowTemplateVersion,
                PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
            )
            .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
            .filter(FlowKind.kind_key == flow_type)
            .filter(PatientFlowState.completed_at.is_(None))
            .filter(
                cast(
                    func.date_part(
                        "day", func.age(today, func.date(PatientFlowState.started_at))
                    ),
                    Integer,
                )
                == target_day - 1
            )
            .limit(limit)
            .all()
        )
