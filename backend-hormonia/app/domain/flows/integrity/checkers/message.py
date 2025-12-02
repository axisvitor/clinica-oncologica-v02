"""
Message integrity checker.
"""
import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.message import MessageStatus
from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from ..types import CorruptionIssue, CorruptionType, CorruptionSeverity

logger = logging.getLogger(__name__)


class MessageChecker:
    """Checker for message data integrity."""

    def __init__(self, db: Session):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.patient_repo = PatientRepository(db)

    async def check_integrity(self, patient_id: Optional[UUID]) -> tuple[list[CorruptionIssue], int]:
        """
        Check message data integrity.

        Args:
            patient_id: Optional specific patient to check

        Returns:
            Tuple of (issues_found, total_records_checked)
        """
        issues = []

        try:
            # Get messages to check
            if patient_id:
                messages = self.message_repo.get_by_patient(patient_id, limit=1000)
            else:
                messages = self.message_repo.get_recent_messages(limit=1000)

            total_count = len(messages)

            for message in messages:
                issues.extend(self._check_patient_reference(message))
                issues.extend(self._check_date_consistency(message))
                issues.extend(self._check_status_consistency(message))
                issues.extend(self._check_metadata_json(message))

            return issues, total_count

        except Exception as e:
            logger.error(f"Message integrity check failed: {e}")
            return [], 0

    def _check_patient_reference(self, message) -> list[CorruptionIssue]:
        """Check patient reference validity."""
        if not self.patient_repo.get(message.patient_id):
            return [CorruptionIssue(
                id=f"orphaned_message_{message.id}",
                corruption_type=CorruptionType.ORPHANED_DATA,
                severity=CorruptionSeverity.HIGH,
                description=f"Message references non-existent patient {message.patient_id}",
                affected_records=[{"message_id": str(message.id)}],
                suggested_fix="Delete orphaned message or restore patient record",
                auto_fixable=False
            )]
        return []

    def _check_date_consistency(self, message) -> list[CorruptionIssue]:
        """Check date consistency."""
        if message.sent_at and message.created_at and message.sent_at < message.created_at:
            return [CorruptionIssue(
                id=f"invalid_message_dates_{message.id}",
                corruption_type=CorruptionType.INCONSISTENT_DATES,
                severity=CorruptionSeverity.MEDIUM,
                description="Message sent before creation",
                affected_records=[{"message_id": str(message.id)}],
                suggested_fix="Correct sent_at timestamp",
                auto_fixable=True
            )]
        return []

    def _check_status_consistency(self, message) -> list[CorruptionIssue]:
        """Check status consistency."""
        if message.status == MessageStatus.SENT and not message.sent_at:
            return [CorruptionIssue(
                id=f"inconsistent_status_{message.id}",
                corruption_type=CorruptionType.INVALID_STATE,
                severity=CorruptionSeverity.MEDIUM,
                description="Message marked as sent but no sent_at timestamp",
                affected_records=[{"message_id": str(message.id)}],
                suggested_fix="Update sent_at timestamp or correct status",
                auto_fixable=True
            )]
        return []

    def _check_metadata_json(self, message) -> list[CorruptionIssue]:
        """Check metadata JSON validity."""
        if message.message_metadata:
            try:
                json.dumps(message.message_metadata)
            except (TypeError, ValueError) as e:
                return [CorruptionIssue(
                    id=f"corrupted_metadata_{message.id}",
                    corruption_type=CorruptionType.CORRUPTED_JSON,
                    severity=CorruptionSeverity.MEDIUM,
                    description=f"Corrupted message metadata: {str(e)}",
                    affected_records=[{"message_id": str(message.id)}],
                    suggested_fix="Reset message_metadata to empty dict",
                    auto_fixable=True
                )]
        return []
