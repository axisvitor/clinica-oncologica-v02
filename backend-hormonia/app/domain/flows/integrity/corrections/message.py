"""
Message corrections.
"""
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.message import MessageStatus
from app.repositories.message import MessageRepository
from .backup_manager import BackupManager
from ..types import CorrectionResult

logger = logging.getLogger(__name__)


class MessageCorrector:
    """Corrector for message issues."""

    def __init__(self, db: Session):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.backup_manager = BackupManager()

    async def fix_inconsistent_status(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix inconsistent message status."""
        try:
            message_id = UUID(issue_id.split("_")[-1])
            message = self.message_repo.get(message_id)

            if not message:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Message not found"
                )

            backup_data = None
            if create_backup:
                backup_data = {
                    "original_status": message.status.value,
                    "original_sent_at": message.sent_at.isoformat() if message.sent_at else None,
                    "backup_timestamp": datetime.utcnow().isoformat()
                }

            # Add sent_at timestamp if marked as sent but missing
            if message.status == MessageStatus.SENT and not message.sent_at:
                message.sent_at = message.created_at or datetime.utcnow()

                if backup_data:
                    self.backup_manager.store_backup_in_state_data(message, backup_data)

            self.db.commit()

            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "action": "added_sent_timestamp",
                    "new_sent_at": message.sent_at.isoformat(),
                    "backup_data": backup_data
                }
            )

        except Exception as e:
            self.db.rollback()
            raise

    async def fix_invalid_dates(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix invalid message dates."""
        try:
            message_id = UUID(issue_id.split("_")[-1])
            message = self.message_repo.get(message_id)

            if not message:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Message not found"
                )

            backup_data = None
            if create_backup:
                backup_data = self.backup_manager.create_message_backup(
                    message, "sent_at", message.sent_at.isoformat() if message.sent_at else None
                )

            # Correct sent_at to be after created_at
            if message.sent_at and message.created_at and message.sent_at < message.created_at:
                message.sent_at = message.created_at

                if backup_data:
                    self.backup_manager.store_backup_in_state_data(message, backup_data)

            self.db.commit()

            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "action": "corrected_sent_at",
                    "new_sent_at": message.sent_at.isoformat(),
                    "backup_data": backup_data
                }
            )

        except Exception as e:
            self.db.rollback()
            raise

    async def fix_corrupted_metadata(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix corrupted message metadata."""
        try:
            message_id = UUID(issue_id.split("_")[-1])
            message = self.message_repo.get(message_id)

            if not message:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Message not found"
                )

            backup_data = None
            if create_backup:
                backup_data = {
                    "original_metadata": str(message.message_metadata),
                    "backup_timestamp": datetime.utcnow().isoformat()
                }

            # Reset metadata to empty dict
            message.message_metadata = {"reset_due_to_corruption": True}
            if backup_data:
                message.message_metadata["corruption_backup"] = backup_data

            self.db.commit()

            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "action": "reset_metadata",
                    "backup_data": backup_data
                }
            )

        except Exception as e:
            self.db.rollback()
            raise
