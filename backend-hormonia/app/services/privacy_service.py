"""
Privacy Service for LGPD Compliance.

This service handles all LGPD (Brazilian Data Protection Law) requirements:
- Consent management
- Right to be forgotten
- Data portability
- Data anonymization
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Text

from app.database import Base
from app.models.patient import Patient
from app.models.quiz import QuizSession, QuizResponse
from app.services.audit import AuditService
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class ConsentRecord(Base):
    """Model for storing LGPD consent records."""

    __tablename__ = "consent_records"

    id = Column(String, primary_key=True)
    patient_id = Column(String, nullable=False, index=True)
    consent_type = Column(
        String, nullable=False
    )  # data_collection, data_processing, marketing
    consent_given = Column(Boolean, nullable=False, default=False)
    consent_text = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    given_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)


class PrivacyService:
    """Service for LGPD compliance and privacy management."""

    def __init__(self, db: Any, audit_service: AuditService):
        self.db = db
        self.audit_service = audit_service
        self.logger = logging.getLogger(__name__)

    def record_consent(
        self,
        patient_id: UUID,
        consent_type: str,
        consent_given: bool,
        consent_text: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConsentRecord:
        """
        Record LGPD consent from patient.

        Args:
            patient_id: Patient identifier
            consent_type: Type of consent (data_collection, data_processing, marketing)
            consent_given: Whether consent was given
            consent_text: The consent text shown to the patient
            ip_address: IP address of the patient
            user_agent: User agent string
            metadata: Additional metadata
        """
        consent = ConsentRecord(
            id=str(UUID()),
            patient_id=str(patient_id),
            consent_type=consent_type,
            consent_given=consent_given,
            consent_text=consent_text,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            given_at=datetime.utcnow() if consent_given else None,
            metadata=metadata or {},
        )

        self.db.add(consent)
        self.db.commit()

        # Audit log
        if consent_given:
            self.audit_service.log_consent_given(
                patient_id=patient_id, consent_type=consent_type, ip_address=ip_address
            )

        self.logger.info(
            f"Consent recorded: {consent_type} - {'given' if consent_given else 'denied'}",
            extra={"patient_id": str(patient_id)},
        )

        return consent

    def revoke_consent(self, patient_id: UUID, consent_type: str) -> ConsentRecord:
        """Revoke previously given consent."""
        consent = (
            self.db.query(ConsentRecord)
            .filter(
                ConsentRecord.patient_id == str(patient_id),
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.consent_given,
            )
            .first()
        )

        if not consent:
            raise NotFoundError(f"No active consent found for type {consent_type}")

        consent.consent_given = False
        consent.revoked_at = datetime.utcnow()

        self.db.commit()

        self.logger.info(
            f"Consent revoked: {consent_type}", extra={"patient_id": str(patient_id)}
        )

        return consent

    def check_consent(self, patient_id: UUID, consent_type: str) -> bool:
        """Check if patient has given consent for a specific type."""
        consent = (
            self.db.query(ConsentRecord)
            .filter(
                ConsentRecord.patient_id == str(patient_id),
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.consent_given,
                ConsentRecord.revoked_at.is_(None),
            )
            .first()
        )

        return consent is not None

    def export_patient_data(self, patient_id: UUID) -> Dict[str, Any]:
        """
        Export all patient data for LGPD compliance (data portability).

        Returns a complete export of all patient data in JSON format.
        """
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()

        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        # Get all quiz sessions
        sessions = (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .all()
        )

        # Get all responses
        responses = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .all()
        )

        # Get consents
        consents = (
            self.db.query(ConsentRecord)
            .filter(ConsentRecord.patient_id == str(patient_id))
            .all()
        )

        # Get audit trail
        audit_logs = self.audit_service.get_patient_audit_trail(patient_id)

        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "patient": {
                "id": str(patient.id),
                "name": patient.name,
                "email": patient.email,
                "phone": patient.phone,
                "created_at": patient.created_at.isoformat()
                if patient.created_at
                else None,
            },
            "quiz_sessions": [
                {
                    "id": str(s.id),
                    "quiz_template_id": str(s.quiz_template_id),
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat()
                    if s.completed_at
                    else None,
                    "is_completed": s.status == "completed",
                }
                for s in sessions
            ],
            "quiz_responses": [
                {
                    "id": str(r.id),
                    "question_id": r.question_id,
                    "question_text": r.question_text,
                    "response_value": r.response_value,
                    "responded_at": r.responded_at.isoformat()
                    if r.responded_at
                    else None,
                }
                for r in responses
            ],
            "consents": [
                {
                    "type": c.consent_type,
                    "given": c.consent_given,
                    "given_at": c.given_at.isoformat() if c.given_at else None,
                    "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
                }
                for c in consents
            ],
            "audit_trail": [
                {
                    "event_type": log.event_type,
                    "timestamp": log.timestamp.isoformat(),
                    "result": log.result,
                }
                for log in audit_logs
            ],
        }

        self.logger.info(
            "Data export generated for patient", extra={"patient_id": str(patient_id)}
        )

        return export_data

    def delete_patient_data(
        self, patient_id: UUID, user_id: UUID, reason: str, scope: str = "all"
    ) -> Dict[str, int]:
        """
        Delete patient data (right to be forgotten).

        Args:
            patient_id: Patient to delete data for
            user_id: User performing the deletion
            reason: Reason for deletion
            scope: Scope of deletion (all, quiz_only, consents_only)

        Returns:
            Dictionary with counts of deleted records
        """
        deleted_counts = {"sessions": 0, "responses": 0, "consents": 0}

        if scope in ["all", "quiz_only"]:
            # Delete quiz responses
            deleted_counts["responses"] = (
                self.db.query(QuizResponse)
                .filter(QuizResponse.patient_id == patient_id)
                .delete()
            )

            # Delete quiz sessions
            deleted_counts["sessions"] = (
                self.db.query(QuizSession)
                .filter(QuizSession.patient_id == patient_id)
                .delete()
            )

        if scope in ["all", "consents_only"]:
            # Delete consents (but keep audit trail for legal compliance)
            deleted_counts["consents"] = (
                self.db.query(ConsentRecord)
                .filter(ConsentRecord.patient_id == str(patient_id))
                .delete()
            )

        self.db.commit()

        # Audit log
        self.audit_service.log_data_deletion(
            patient_id=patient_id, user_id=user_id, deletion_scope=scope, reason=reason
        )

        self.logger.warning(
            f"Patient data deleted: {scope}",
            extra={"patient_id": str(patient_id), "deleted_counts": deleted_counts},
        )

        return deleted_counts

    def anonymize_patient_data(
        self, patient_id: UUID, retention_cutoff_days: int = 730
    ) -> Dict[str, int]:
        """
        Anonymize old patient data while retaining statistical value.

        Data older than cutoff_days will be anonymized.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_cutoff_days)

        # Anonymize old quiz responses
        old_responses = (
            self.db.query(QuizResponse)
            .filter(
                QuizResponse.patient_id == patient_id,
                QuizResponse.responded_at < cutoff_date,
            )
            .all()
        )

        anonymized_count = 0
        for response in old_responses:
            # Keep statistical data but remove identifying info
            response.response_metadata = response.response_metadata or {}
            response.response_metadata["anonymized"] = True
            response.response_metadata["anonymized_at"] = datetime.utcnow().isoformat()
            anonymized_count += 1

        self.db.commit()

        self.logger.info(
            f"Anonymized {anonymized_count} old responses",
            extra={"patient_id": str(patient_id)},
        )

        return {"anonymized_responses": anonymized_count}

    def get_consent_status(self, patient_id: UUID) -> Dict[str, Any]:
        """Get complete consent status for a patient."""
        consents = (
            self.db.query(ConsentRecord)
            .filter(ConsentRecord.patient_id == str(patient_id))
            .all()
        )

        consent_status = {}
        for consent in consents:
            consent_status[consent.consent_type] = {
                "given": consent.consent_given,
                "given_at": consent.given_at.isoformat() if consent.given_at else None,
                "revoked_at": consent.revoked_at.isoformat()
                if consent.revoked_at
                else None,
            }

        return consent_status
