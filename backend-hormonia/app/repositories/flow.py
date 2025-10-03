from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState, FlowTemplateVersion
from app.repositories.base import BaseRepository


class FlowStateRepository(BaseRepository[PatientFlowState]):
    """Repository for PatientFlowState model"""
    
    def __init__(self, db: Session):
        super().__init__(db, PatientFlowState)
    
    def get_by_patient(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> List[PatientFlowState]:
        """Get flow states by patient"""
        return (
            self.db.query(PatientFlowState)
            .filter(PatientFlowState.patient_id == patient_id)
            .order_by(PatientFlowState.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_active_flow(self, patient_id: UUID) -> Optional[PatientFlowState]:
        """Get active flow for a patient (not completed)"""
        return (
            self.db.query(PatientFlowState)
            .filter(PatientFlowState.patient_id == patient_id)
            .filter(PatientFlowState.completed_at.is_(None))
            .order_by(PatientFlowState.started_at.desc())
            .first()
        )
    
    def get_by_template_version(self, template_version_id: UUID, skip: int = 0, limit: int = 100) -> List[PatientFlowState]:
        """Get flow states by template version ID"""
        return (
            self.db.query(PatientFlowState)
            .filter(PatientFlowState.template_version_id == template_version_id)
            .order_by(PatientFlowState.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_completed_flows(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> List[PatientFlowState]:
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
    
    def get_active_flows(self, limit: int = 1000) -> List[PatientFlowState]:
        """Get all active flows"""
        return (
            self.db.query(PatientFlowState)
            .filter(PatientFlowState.completed_at.is_(None))
            .order_by(PatientFlowState.started_at.desc())
            .limit(limit)
            .all()
        )
    
    def get_flows_by_type_and_day(self, flow_type: str, target_day: int, limit: int = 100) -> List[PatientFlowState]:
        """Get flows by flow_type via template_version that are on a specific day"""
        from datetime import datetime
        from sqlalchemy import func, cast, Integer
        from app.models.flow import FlowKind

        # Calculate flows that should be on target_day today
        today = datetime.utcnow().date()

        return (
            self.db.query(PatientFlowState)
            .join(FlowTemplateVersion, PatientFlowState.template_version_id == FlowTemplateVersion.id)
            .join(FlowKind, FlowTemplateVersion.kind_id == FlowKind.id)
            .filter(FlowKind.flow_type == flow_type)
            .filter(PatientFlowState.completed_at.is_(None))
            .filter(
                cast(func.date_part('day', func.age(today, func.date(PatientFlowState.started_at))), Integer) == target_day - 1
            )
            .limit(limit)
            .all()
        )