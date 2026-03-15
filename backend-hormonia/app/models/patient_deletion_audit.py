"""
PatientDeletionAudit model — LGPD Art. 16/18 compliance.

Records every patient deletion event permanently.  The row is written
inside the same DB transaction as the soft-delete so there is no window
for data loss, and PostgreSQL rules block any subsequent UPDATE or DELETE
on this table so the record is truly immutable once committed.

NOTE: No foreign key to patients.id by design.  The audit record must
survive even when the patient row is later hard-deleted or when the
patients table is truncated in a disaster-recovery scenario.
"""

import hashlib
import uuid

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PatientDeletionAudit(Base):
    """
    Append-only audit log for patient deletion events.

    Columns
    -------
    id                  Primary key (UUID v4).
    patient_id          UUID of the patient that was deleted.  Indexed for
                        fast look-ups by compliance officers.  No FK —
                        survives even after hard-deletion of the patient row.
    deleted_by_user_id  UUID of the admin/doctor who triggered the deletion.
                        Nullable so callers that don't have the user in scope
                        (e.g., bulk maintenance jobs) can still write a record.
    deleted_by_email    Email of the executor at deletion time, stored in plain
                        text for human-readable audit reports.
    deletion_reason     Free-text reason provided by the caller.  Defaults to a
                        system message when the caller omits it.
    patient_name_hash   SHA-256 hex digest of the patient's name at deletion
                        time.  Allows cross-referencing without re-exposing PII
                        in the audit table.
    deleted_at          Timezone-aware timestamp of the deletion event.
                        NOT NULL — every record must be anchored in time.
    """

    __tablename__ = "patient_deletion_audit"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary key",
    )

    # The deleted patient — no FK so the audit row outlives the patient row
    patient_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="UUID of the deleted patient (no FK — intentional)",
    )

    # Who performed the deletion
    deleted_by_user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="UUID of the user who triggered the deletion",
    )
    deleted_by_email = Column(
        String(255),
        nullable=True,
        comment="Email of the executor at deletion time",
    )

    # Why the deletion happened
    deletion_reason = Column(
        Text,
        nullable=True,
        comment="Human-readable reason for the deletion",
    )

    # Privacy-safe patient name reference
    patient_name_hash = Column(
        String(64),
        nullable=True,
        comment="SHA-256 hex digest of the patient name — NOT plaintext",
    )

    # When the deletion happened
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timezone-aware timestamp of the deletion event",
    )

    # Composite indexes for common compliance queries
    __table_args__ = (
        Index("idx_pda_patient_deleted_at", "patient_id", "deleted_at"),
        Index("idx_pda_deleted_at", "deleted_at"),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def hash_name(name: str) -> str:
        """Return SHA-256 hex digest of *name* for privacy-safe storage."""
        return hashlib.sha256((name or "").encode()).hexdigest()

    def __repr__(self) -> str:
        return (
            f"<PatientDeletionAudit("
            f"patient_id='{self.patient_id}', "
            f"deleted_by_email='{self.deleted_by_email}', "
            f"deleted_at='{self.deleted_at}'"
            f")>"
        )
