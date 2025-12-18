"""
Flow state corrections.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.flow_types import FlowType
from app.models.flow_analytics import FlowMessage
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from .backup_manager import BackupManager
from ..types import CorrectionResult

logger = logging.getLogger(__name__)


class FlowStateCorrector:
    """Corrector for flow state issues."""

    def __init__(self, db: Session):
        self.db = db
        self.flow_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.backup_manager = BackupManager()

    async def fix_invalid_flow_type(
        self, issue_id: str, create_backup: bool
    ) -> CorrectionResult:
        """Fix invalid flow type issue."""
        try:
            flow_state_id = UUID(issue_id.split("_")[-1])
            flow_state = self.flow_repo.get(flow_state_id)

            if not flow_state:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Flow state not found",
                )

            backup_data = None
            if create_backup:
                backup_data = self.backup_manager.create_flow_state_backup(
                    flow_state, "flow_type", flow_state.flow_type
                )

            # Determine correct flow type based on patient enrollment
            patient = self.patient_repo.get(flow_state.patient_id)
            if patient and patient.enrollment_date:
                days_since_enrollment = (
                    datetime.utcnow() - patient.enrollment_date
                ).days

                if days_since_enrollment <= 15:
                    new_flow_type = FlowType.INITIAL_15_DAYS.value
                elif days_since_enrollment <= 45:
                    new_flow_type = FlowType.DAYS_16_45.value
                else:
                    new_flow_type = FlowType.MONTHLY_RECURRING.value
            else:
                new_flow_type = FlowType.INITIAL_15_DAYS.value

            # Apply fix
            flow_state.flow_type = new_flow_type
            if backup_data:
                self.backup_manager.store_backup_in_state_data(flow_state, backup_data)

            self.db.commit()

            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "new_flow_type": new_flow_type,
                    "backup_data": backup_data,
                },
            )

        except Exception:
            self.db.rollback()
            raise

    async def fix_invalid_step(
        self, issue_id: str, create_backup: bool
    ) -> CorrectionResult:
        """Fix invalid step issue."""
        try:
            flow_state_id = UUID(issue_id.split("_")[-1])
            flow_state = self.flow_repo.get(flow_state_id)

            if not flow_state:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Flow state not found",
                )

            backup_data = None
            if create_backup:
                backup_data = self.backup_manager.create_flow_state_backup(
                    flow_state, "current_step", flow_state.current_step
                )

            # Reset to step 1
            flow_state.current_step = 1
            if backup_data:
                self.backup_manager.store_backup_in_state_data(flow_state, backup_data)

            self.db.commit()

            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={"new_step": 1, "backup_data": backup_data},
            )

        except Exception:
            self.db.rollback()
            raise

    async def fix_corrupted_json(
        self, issue_id: str, create_backup: bool
    ) -> CorrectionResult:
        """Fix corrupted flow state JSON."""
        try:
            flow_state_id = UUID(issue_id.split("_")[-1])
            flow_state = self.flow_repo.get(flow_state_id)

            if not flow_state:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Flow state not found",
                )

            backup_data = None
            if create_backup:
                backup_data = {
                    "original_state_data": str(flow_state.state_data),
                    "backup_timestamp": datetime.utcnow().isoformat(),
                }

            # Reset to empty dict with marker
            flow_state.state_data = {"reset_due_to_corruption": True}
            if backup_data:
                flow_state.state_data["corruption_backup"] = backup_data

            self.db.commit()

            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "action": "reset_state_data",
                    "backup_data": backup_data,
                },
            )

        except Exception:
            self.db.rollback()
            raise

    async def fix_duplicate_active_flows(
        self, issue_id: str, create_backup: bool
    ) -> CorrectionResult:
        """Fix duplicate active flows."""
        try:
            patient_id = UUID(issue_id.split("_")[-1])

            active_flows = [
                f
                for f in self.flow_repo.get_by_patient_id(patient_id)
                if not f.completed_at
            ]

            if len(active_flows) <= 1:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=True,
                    records_affected=0,
                    backup_created=False,
                    correction_details={"message": "No duplicate flows found"},
                )

            # Keep most recent, complete others
            active_flows.sort(key=lambda f: f.started_at, reverse=True)
            keep_flow = active_flows[0]
            complete_flows = active_flows[1:]

            backup_data = None
            if create_backup:
                backup_data = self.backup_manager.create_duplicate_flows_backup(
                    keep_flow, complete_flows
                )

            # Complete duplicate flows
            for flow in complete_flows:
                flow.completed_at = datetime.utcnow()
                flow.state_data = flow.state_data or {}
                flow.state_data["completed_reason"] = "duplicate_resolution"
                if backup_data:
                    flow.state_data["correction_backup"] = backup_data

            self.db.commit()

            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=len(complete_flows),
                backup_created=create_backup,
                correction_details={
                    "kept_flow_id": str(keep_flow.id),
                    "completed_flow_ids": [str(f.id) for f in complete_flows],
                    "backup_data": backup_data,
                },
            )

        except Exception:
            self.db.rollback()
            raise

    async def fix_orphaned_flow_message(
        self, issue_id: str, create_backup: bool
    ) -> CorrectionResult:
        """Fix orphaned flow message."""
        try:
            flow_message_id = UUID(issue_id.split("_")[-1])
            flow_message = (
                self.db.query(FlowMessage)
                .filter(FlowMessage.id == flow_message_id)
                .first()
            )

            if not flow_message:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Flow message not found",
                )

            backup_data = None
            if create_backup:
                backup_data = self.backup_manager.create_flow_message_backup(
                    flow_message
                )

            # Delete orphaned message
            self.db.delete(flow_message)
            self.db.commit()

            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "action": "deleted_orphaned_message",
                    "backup_data": backup_data,
                },
            )

        except Exception:
            self.db.rollback()
            raise
