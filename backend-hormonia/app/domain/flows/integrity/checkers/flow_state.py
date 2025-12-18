"""
Flow state integrity checker.
"""

import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.flow_types import FlowType
from app.models.flow import PatientFlowState
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from ..types import CorruptionIssue, CorruptionType, CorruptionSeverity

logger = logging.getLogger(__name__)


class FlowStateChecker:
    """Checker for flow state data integrity."""

    def __init__(self, db: Session):
        self.db = db
        self.flow_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)

        self.flow_type_durations = {
            FlowType.INITIAL_15_DAYS.value: 15,
            FlowType.DAYS_16_45.value: 30,
            FlowType.MONTHLY_RECURRING.value: 30,
        }

    async def check_integrity(
        self, patient_id: Optional[UUID]
    ) -> tuple[list[CorruptionIssue], int]:
        """
        Check flow state data integrity.

        Args:
            patient_id: Optional specific patient to check

        Returns:
            Tuple of (issues_found, total_records_checked)
        """
        issues = []

        try:
            # Get flow states to check
            if patient_id:
                flow_states = self.flow_repo.get_by_patient_id(patient_id)
            else:
                flow_states = self.flow_repo.get_all(limit=1000)

            total_count = len(flow_states)

            for flow_state in flow_states:
                issues.extend(self._check_flow_type(flow_state))
                issues.extend(self._check_current_step(flow_state))
                issues.extend(self._check_date_consistency(flow_state))
                issues.extend(self._check_state_data_json(flow_state))
                issues.extend(self._check_flow_duration(flow_state))
                issues.extend(self._check_patient_reference(flow_state))

            # Check for duplicate active flows
            duplicate_issues = await self._check_duplicate_active_flows(patient_id)
            issues.extend(duplicate_issues)

            return issues, total_count

        except Exception as e:
            logger.error(f"Flow state integrity check failed: {e}")
            return [], 0

    def _check_flow_type(self, flow_state: PatientFlowState) -> list[CorruptionIssue]:
        """Check if flow type is valid."""
        if flow_state.flow_type not in [ft.value for ft in FlowType]:
            return [
                CorruptionIssue(
                    id=f"invalid_flow_type_{flow_state.id}",
                    corruption_type=CorruptionType.INVALID_STATE,
                    severity=CorruptionSeverity.HIGH,
                    description=f"Invalid flow type: {flow_state.flow_type}",
                    affected_records=[{"flow_state_id": str(flow_state.id)}],
                    suggested_fix="Update flow_type to valid value or reset flow",
                    auto_fixable=True,
                )
            ]
        return []

    def _check_current_step(
        self, flow_state: PatientFlowState
    ) -> list[CorruptionIssue]:
        """Check if current step is valid."""
        if flow_state.current_step < 1:
            return [
                CorruptionIssue(
                    id=f"invalid_step_{flow_state.id}",
                    corruption_type=CorruptionType.INVALID_STATE,
                    severity=CorruptionSeverity.MEDIUM,
                    description=f"Invalid current step: {flow_state.current_step}",
                    affected_records=[{"flow_state_id": str(flow_state.id)}],
                    suggested_fix="Reset current_step to 1",
                    auto_fixable=True,
                )
            ]
        return []

    def _check_date_consistency(
        self, flow_state: PatientFlowState
    ) -> list[CorruptionIssue]:
        """Check date consistency."""
        if flow_state.completed_at and flow_state.completed_at < flow_state.started_at:
            return [
                CorruptionIssue(
                    id=f"invalid_dates_{flow_state.id}",
                    corruption_type=CorruptionType.INCONSISTENT_DATES,
                    severity=CorruptionSeverity.HIGH,
                    description="Completion date before start date",
                    affected_records=[{"flow_state_id": str(flow_state.id)}],
                    suggested_fix="Correct completion date or mark as incomplete",
                    auto_fixable=False,
                )
            ]
        return []

    def _check_state_data_json(
        self, flow_state: PatientFlowState
    ) -> list[CorruptionIssue]:
        """Check state_data JSON validity."""
        if flow_state.state_data:
            try:
                json.dumps(flow_state.state_data)
            except (TypeError, ValueError) as e:
                return [
                    CorruptionIssue(
                        id=f"corrupted_json_{flow_state.id}",
                        corruption_type=CorruptionType.CORRUPTED_JSON,
                        severity=CorruptionSeverity.HIGH,
                        description=f"Corrupted state_data JSON: {str(e)}",
                        affected_records=[{"flow_state_id": str(flow_state.id)}],
                        suggested_fix="Reset state_data to empty dict",
                        auto_fixable=True,
                    )
                ]
        return []

    def _check_flow_duration(
        self, flow_state: PatientFlowState
    ) -> list[CorruptionIssue]:
        """Check flow duration consistency."""
        if flow_state.completed_at:
            duration_days = (flow_state.completed_at - flow_state.started_at).days
            expected_duration = self.flow_type_durations.get(flow_state.flow_type, 30)

            if duration_days > expected_duration * 2:
                return [
                    CorruptionIssue(
                        id=f"excessive_duration_{flow_state.id}",
                        corruption_type=CorruptionType.INVALID_STATE,
                        severity=CorruptionSeverity.MEDIUM,
                        description=f"Flow duration ({duration_days} days) exceeds expected ({expected_duration} days)",
                        affected_records=[{"flow_state_id": str(flow_state.id)}],
                        suggested_fix="Review flow completion status",
                        auto_fixable=False,
                    )
                ]
        return []

    def _check_patient_reference(
        self, flow_state: PatientFlowState
    ) -> list[CorruptionIssue]:
        """Check patient reference validity."""
        if not self.patient_repo.get(flow_state.patient_id):
            return [
                CorruptionIssue(
                    id=f"missing_patient_{flow_state.id}",
                    corruption_type=CorruptionType.MISSING_REFERENCES,
                    severity=CorruptionSeverity.CRITICAL,
                    description=f"Flow state references non-existent patient {flow_state.patient_id}",
                    affected_records=[{"flow_state_id": str(flow_state.id)}],
                    suggested_fix="Delete orphaned flow state or restore patient record",
                    auto_fixable=False,
                )
            ]
        return []

    async def _check_duplicate_active_flows(
        self, patient_id: Optional[UUID]
    ) -> list[CorruptionIssue]:
        """Check for duplicate active flows for patients."""
        issues = []

        try:
            query = (
                self.db.query(
                    PatientFlowState.patient_id,
                    func.count(PatientFlowState.id).label("count"),
                )
                .filter(PatientFlowState.completed_at.is_(None))
                .group_by(PatientFlowState.patient_id)
                .having(func.count(PatientFlowState.id) > 1)
            )

            if patient_id:
                query = query.filter(PatientFlowState.patient_id == patient_id)

            duplicates = query.all()

            for patient_id_dup, count in duplicates:
                duplicate_flows = self.flow_repo.get_by_patient_id(patient_id_dup)
                active_flows = [f for f in duplicate_flows if not f.completed_at]

                if len(active_flows) > 1:
                    issues.append(
                        CorruptionIssue(
                            id=f"duplicate_active_flows_{patient_id_dup}",
                            corruption_type=CorruptionType.DUPLICATE_RECORDS,
                            severity=CorruptionSeverity.HIGH,
                            description=f"Patient has {len(active_flows)} active flows",
                            affected_records=[
                                {"flow_state_id": str(f.id)} for f in active_flows
                            ],
                            suggested_fix="Keep most recent flow, complete others",
                            auto_fixable=True,
                        )
                    )

            return issues

        except Exception as e:
            logger.error(f"Duplicate flow check failed: {e}")
            return []
