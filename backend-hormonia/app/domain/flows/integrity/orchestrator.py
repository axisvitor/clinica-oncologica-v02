"""
Data integrity orchestrator - main coordinator for checks and corrections.
"""
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from .checkers import FlowStateChecker, MessageChecker, ReferenceChecker
from .corrections import BackupManager, FlowStateCorrector, MessageCorrector
from .types import (
    CorruptionIssue,
    CorruptionSeverity,
    CorruptionType,
    CorrectionResult,
    IntegrityCheckResult,
)

logger = logging.getLogger(__name__)


class FlowDataIntegrityChecker:
    """Service for detecting and correcting flow data corruption."""

    def __init__(self, db: Session):
        self.db = db

        # Initialize checkers
        self.flow_state_checker = FlowStateChecker(db)
        self.message_checker = MessageChecker(db)
        self.reference_checker = ReferenceChecker(db)

        # Initialize correctors
        self.flow_state_corrector = FlowStateCorrector(db)
        self.message_corrector = MessageCorrector(db)

        # Backup manager
        self.backup_manager = BackupManager()

        logger.info("Flow data integrity checker initialized")

    async def run_comprehensive_check(
        self,
        patient_id: Optional[UUID] = None,
        check_messages: bool = True,
        check_flow_states: bool = True,
        check_references: bool = True
    ) -> IntegrityCheckResult:
        """
        Run comprehensive data integrity check.

        Args:
            patient_id: Optional specific patient to check
            check_messages: Whether to check message integrity
            check_flow_states: Whether to check flow state integrity
            check_references: Whether to check reference integrity

        Returns:
            Integrity check result
        """
        start_time = datetime.utcnow()
        issues = []
        total_records = 0

        try:
            logger.info(f"Starting comprehensive integrity check for patient {patient_id or 'all'}")

            if check_flow_states:
                flow_issues, flow_count = await self.flow_state_checker.check_integrity(patient_id)
                issues.extend(flow_issues)
                total_records += flow_count

            if check_messages:
                message_issues, message_count = await self.message_checker.check_integrity(patient_id)
                issues.extend(message_issues)
                total_records += message_count

            if check_references:
                ref_issues, ref_count = await self.reference_checker.check_integrity(patient_id)
                issues.extend(ref_issues)
                total_records += ref_count

            corruption_score = self._calculate_corruption_score(issues, total_records)
            recommendations = self._generate_recommendations(issues)

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            result = IntegrityCheckResult(
                total_records_checked=total_records,
                issues_found=issues,
                corruption_score=corruption_score,
                recommendations=recommendations,
                check_duration_seconds=duration
            )

            logger.info(f"Integrity check completed: {len(issues)} issues found in {duration:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            raise

    async def fix_issue(self, issue_id: str, create_backup: bool = True) -> CorrectionResult:
        """
        Fix a specific data corruption issue.

        Args:
            issue_id: ID of the issue to fix
            create_backup: Whether to create backup before fixing

        Returns:
            Correction result
        """
        try:
            logger.info(f"Attempting to fix issue: {issue_id}")

            # Route to appropriate corrector based on issue ID
            if "invalid_flow_type_" in issue_id:
                return await self.flow_state_corrector.fix_invalid_flow_type(issue_id, create_backup)
            elif "invalid_step_" in issue_id:
                return await self.flow_state_corrector.fix_invalid_step(issue_id, create_backup)
            elif "corrupted_json_" in issue_id and "flow_state" in issue_id:
                return await self.flow_state_corrector.fix_corrupted_json(issue_id, create_backup)
            elif "corrupted_metadata_" in issue_id:
                return await self.message_corrector.fix_corrupted_metadata(issue_id, create_backup)
            elif "inconsistent_status_" in issue_id:
                return await self.message_corrector.fix_inconsistent_status(issue_id, create_backup)
            elif "invalid_message_dates_" in issue_id:
                return await self.message_corrector.fix_invalid_dates(issue_id, create_backup)
            elif "duplicate_active_flows_" in issue_id:
                return await self.flow_state_corrector.fix_duplicate_active_flows(issue_id, create_backup)
            elif "orphaned_flow_message_" in issue_id:
                return await self.flow_state_corrector.fix_orphaned_flow_message(issue_id, create_backup)
            else:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Unknown issue type - manual intervention required"
                )

        except Exception as e:
            logger.error(f"Failed to fix issue {issue_id}: {e}")
            return CorrectionResult(
                issue_id=issue_id,
                success=False,
                records_affected=0,
                backup_created=False,
                correction_details={},
                error_message=str(e)
            )

    def _calculate_corruption_score(self, issues: list[CorruptionIssue], total_records: int) -> float:
        """Calculate overall corruption score (0-100)."""
        if total_records == 0:
            return 0.0

        severity_weights = {
            CorruptionSeverity.LOW: 1,
            CorruptionSeverity.MEDIUM: 3,
            CorruptionSeverity.HIGH: 7,
            CorruptionSeverity.CRITICAL: 15
        }

        total_weight = sum(severity_weights[issue.severity] for issue in issues)
        score = min(100.0, (total_weight / total_records) * 100)

        return round(score, 2)

    def _generate_recommendations(self, issues: list[CorruptionIssue]) -> list[str]:
        """Generate recommendations based on found issues."""
        recommendations = []

        critical_count = len([i for i in issues if i.severity == CorruptionSeverity.CRITICAL])
        high_count = len([i for i in issues if i.severity == CorruptionSeverity.HIGH])
        auto_fixable_count = len([i for i in issues if i.auto_fixable])

        if critical_count > 0:
            recommendations.append(f"URGENT: {critical_count} critical issues require immediate attention")

        if high_count > 0:
            recommendations.append(f"{high_count} high-severity issues should be addressed soon")

        if auto_fixable_count > 0:
            recommendations.append(f"{auto_fixable_count} issues can be automatically fixed")

        corruption_types = set(issue.corruption_type for issue in issues)

        if CorruptionType.ORPHANED_DATA in corruption_types:
            recommendations.append("Clean up orphaned data to improve system performance")

        if CorruptionType.DUPLICATE_RECORDS in corruption_types:
            recommendations.append("Resolve duplicate records to prevent flow conflicts")

        if CorruptionType.CORRUPTED_JSON in corruption_types:
            recommendations.append("Fix corrupted JSON data to prevent processing errors")

        if not recommendations:
            recommendations.append("No significant issues found - system integrity is good")

        return recommendations

    async def get_correction_history(
        self,
        patient_id: Optional[UUID] = None,
        days_back: int = 30
    ) -> list[dict[str, Any]]:
        """Get history of data corrections."""
        try:
            # This would typically query a corrections log table
            corrections = []
            return corrections

        except Exception as e:
            logger.error(f"Failed to get correction history: {e}")
            return []


def get_flow_data_integrity_checker(db: Session) -> FlowDataIntegrityChecker:
    """Get flow data integrity checker instance."""
    return FlowDataIntegrityChecker(db)
