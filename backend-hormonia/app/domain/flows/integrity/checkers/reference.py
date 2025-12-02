"""
Reference integrity checker.
"""
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flow_analytics import FlowMessage
from app.repositories.flow import FlowStateRepository
from ..types import CorruptionIssue, CorruptionType, CorruptionSeverity

logger = logging.getLogger(__name__)


class ReferenceChecker:
    """Checker for reference integrity between related records."""

    def __init__(self, db: Session):
        self.db = db
        self.flow_repo = FlowStateRepository(db)

    async def check_integrity(self, patient_id: Optional[UUID]) -> tuple[list[CorruptionIssue], int]:
        """
        Check reference integrity between related records.

        Args:
            patient_id: Optional specific patient to check

        Returns:
            Tuple of (issues_found, total_records_checked)
        """
        issues = []
        total_count = 0

        try:
            # Check flow messages without valid flow states
            flow_messages = self.db.query(FlowMessage).all()
            total_count += len(flow_messages)

            for flow_message in flow_messages:
                if not self.flow_repo.get(flow_message.flow_state_id):
                    issues.append(CorruptionIssue(
                        id=f"orphaned_flow_message_{flow_message.id}",
                        corruption_type=CorruptionType.ORPHANED_DATA,
                        severity=CorruptionSeverity.MEDIUM,
                        description=f"Flow message references non-existent flow state {flow_message.flow_state_id}",
                        affected_records=[{"flow_message_id": str(flow_message.id)}],
                        suggested_fix="Delete orphaned flow message",
                        auto_fixable=True
                    ))

            return issues, total_count

        except Exception as e:
            logger.error(f"Reference integrity check failed: {e}")
            return [], 0
