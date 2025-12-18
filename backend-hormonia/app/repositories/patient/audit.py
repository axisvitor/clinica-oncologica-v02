"""
Hard delete operations with LGPD compliance audit trail.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete

from app.models.patient import Patient

logger = logging.getLogger(__name__)


class PatientAuditMixin:
    """
    Hard delete operations with audit trail for LGPD compliance.
    """

    async def hard_delete(self, patient_id: UUID, *, audit_reason: str = None) -> bool:
        """
        Permanently delete patient data for LGPD Art. 16 compliance.

        LGPD Art. 16: Right to deletion - right to request deletion of personal data.
        LGPD Art. 18, II: Right to request correction or deletion of data.

        ⚠️  WARNING: This is IRREVERSIBLE. Use only for:
        - Right to be forgotten requests (LGPD Art. 16)
        - Data retention policy expiration
        - Legal compliance requirements

        This method performs a HARD DELETE, permanently removing all patient data
        from the database. Unlike soft delete (deleted_at timestamp), this cannot
        be undone.

        Security Considerations:
        1. Audit logging: All deletions are logged for compliance
        2. Authorization: Caller must verify user permissions before calling
        3. Related data: Handles cascade deletion of related records
        4. Backup: Consider database backups before executing

        Args:
            patient_id: UUID of patient to permanently delete
            audit_reason: Required reason for deletion (for audit trail)
                         Examples:
                         - "LGPD Art. 16 - Patient requested data deletion"
                         - "Data retention policy - 7 years expired"
                         - "Legal compliance - Court order #12345"

        Returns:
            True if patient was deleted, False if not found

        Raises:
            ValueError: If audit_reason is not provided
            IntegrityError: If related data prevents deletion

        Example:
            >>> deleted = await repository.hard_delete(
            ...     patient_id=uuid.UUID("123..."),
            ...     audit_reason="LGPD Art. 16 - Patient data deletion request"
            ... )
            >>> if deleted:
            ...     logger.info("Patient data permanently deleted")

        Note:
            For normal patient deactivation, use soft delete (set deleted_at timestamp).
            Hard delete should ONLY be used for legal compliance requirements.
        """
        # Validate audit reason is provided
        if not audit_reason:
            raise ValueError(
                "LGPD Compliance: audit_reason is required for hard delete operations. "
                "Provide legal justification (e.g., 'LGPD Art. 16 - Data deletion request')."
            )

        # Log deletion for audit trail (BEFORE deletion)
        logger.warning(
            "LGPD: Hard delete requested - IRREVERSIBLE OPERATION",
            extra={
                "event": "patient_hard_delete",
                "patient_id": str(patient_id),
                "reason": audit_reason,
                "timestamp": datetime.utcnow().isoformat(),
                "compliance_article": "LGPD Art. 16 (Right to deletion)",
            },
        )

        # Create audit record before deletion
        if audit_reason:
            await self._create_deletion_audit(patient_id, audit_reason)

        # Delete related data first (if cascade not configured)
        # Note: Most relationships in Patient model have cascade="all, delete-orphan"
        # so this is mainly a safety measure for any non-cascading relationships

        # The following relationships have passive_deletes=True and should cascade:
        # - messages
        # - flow_states
        # - quiz_sessions
        # - quiz_responses (if configured)
        # - medical_reports
        # - reports
        # - alerts
        # - onboarding_sagas
        # - treatments
        # - appointments
        # - medications
        # - notifications
        # - consents
        # - analytics
        # - summaries

        # Delete patient record (cascades to related records)
        result = await self.db.execute(delete(Patient).where(Patient.id == patient_id))
        await self.db.commit()

        deleted = result.rowcount > 0

        if deleted:
            logger.warning(
                "LGPD: Patient data permanently deleted",
                extra={
                    "event": "patient_hard_delete_complete",
                    "patient_id": str(patient_id),
                    "reason": audit_reason,
                },
            )
        else:
            logger.info(
                "LGPD: Hard delete requested but patient not found",
                extra={
                    "event": "patient_hard_delete_not_found",
                    "patient_id": str(patient_id),
                },
            )

        return deleted

    async def _create_deletion_audit(self, patient_id: UUID, reason: str) -> None:
        """
        Create audit record for patient deletion.

        This creates a permanent audit trail for LGPD compliance,
        recording the deletion event before the patient data is removed.

        Args:
            patient_id: UUID of patient being deleted
            reason: Reason for deletion

        Note:
            This audit record should be stored in a separate audit table
            that is NOT deleted with the patient data.
        """
        # TODO: Implement proper audit table storage
        # For now, we log to application logs which should be persisted
        # In production, create a dedicated audit_logs table

        logger.warning(
            "LGPD: Deletion audit record created",
            extra={
                "event": "patient_deletion_audit",
                "patient_id": str(patient_id),
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "compliance": "LGPD Art. 16, 18",
            },
        )

        # Future implementation:
        # audit_record = DeletionAudit(
        #     patient_id=patient_id,
        #     reason=reason,
        #     deleted_at=datetime.utcnow(),
        #     deleted_by=current_user_id  # from request context
        # )
        # self.db.add(audit_record)
        # await self.db.commit()
