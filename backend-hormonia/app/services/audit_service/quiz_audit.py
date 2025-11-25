"""
Quiz Audit Mixin for Monthly Quiz System.

Provides audit logging methods specific to quiz link management,
access control, and LGPD compliance.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.audit_log import AuditLog


class QuizAuditMixin:
    """Mixin class for quiz-related audit logging methods."""

    def log_link_created(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        delivery_method: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Log quiz link creation.

        Args:
            actor_id: User who created the link
            patient_id: Patient the link is for
            session_id: Quiz session identifier
            delivery_method: How the link will be delivered (email, whatsapp, etc.)
            expires_at: When the link expires
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_link_created",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "delivery_method": delivery_method,
                "expires_at": expires_at.isoformat()
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_accessed(
        self,
        patient_id: UUID,
        session_id: UUID,
        ip_address: str,
        user_agent: str,
        token_prefix: str
    ) -> AuditLog:
        """
        Log quiz link access.

        Args:
            patient_id: Patient accessing the link
            session_id: Quiz session identifier
            ip_address: IP address of the access
            user_agent: User agent string
            token_prefix: Prefix of the access token (for tracking)

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_link_accessed",
            event_category="access",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "token_prefix": token_prefix
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent"
        )

    def log_response_submitted(
        self,
        patient_id: UUID,
        session_id: UUID,
        question_id: str,
        response_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Log quiz response submission.

        Args:
            patient_id: Patient submitting the response
            session_id: Quiz session identifier
            question_id: Identifier of the question answered
            response_id: ID of the response record
            ip_address: IP address of the submission
            user_agent: User agent string

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_response_submitted",
            event_category="data_change",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "question_id": question_id,
                "response_id": str(response_id)
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent"
        )

    def log_invalid_access_attempt(
        self,
        ip_address: str,
        user_agent: str,
        reason: str,
        token_prefix: Optional[str] = None
    ) -> AuditLog:
        """
        Log invalid access attempt (security event).

        Args:
            ip_address: IP address of the attempt
            user_agent: User agent string
            reason: Reason for denial (expired, invalid, etc.)
            token_prefix: Prefix of attempted token (if available)

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_invalid_access",
            event_category="security",
            severity="warning",
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "reason": reason,
                "token_prefix": token_prefix
            },
            result="blocked"
        )

    def log_token_expired(
        self,
        patient_id: UUID,
        session_id: UUID
    ) -> AuditLog:
        """
        Log token expiration event.

        Args:
            patient_id: Patient whose token expired
            session_id: Quiz session identifier

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_token_expired",
            event_category="security",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            result="expired"
        )

    def log_link_resent(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        delivery_method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Log quiz link resend action.

        Args:
            actor_id: User who resent the link
            patient_id: Patient the link is for
            session_id: Quiz session identifier
            delivery_method: Delivery method used
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_link_resent",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "delivery_method": delivery_method
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_regenerated(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        regeneration_count: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Log quiz link regeneration action.

        Args:
            actor_id: User who regenerated the link
            patient_id: Patient the link is for
            session_id: Quiz session identifier
            regeneration_count: Number of times link has been regenerated
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_link_regenerated",
            event_category="security",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "regeneration_count": regeneration_count
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_cancelled(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Log quiz link cancellation action.

        Args:
            actor_id: User who cancelled the link
            patient_id: Patient the link was for
            session_id: Quiz session identifier
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_link_cancelled",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={},
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_expired(
        self,
        patient_id: UUID,
        session_id: UUID,
        fallback_activated: bool = False
    ) -> AuditLog:
        """
        Log quiz link expiration.

        Args:
            patient_id: Patient whose link expired
            session_id: Quiz session identifier
            fallback_activated: Whether fallback mechanism was activated

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_link_expired",
            event_category="security",
            severity="warning" if not fallback_activated else "info",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "fallback_activated": fallback_activated
            },
            result="expired",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_fallback_activated(
        self,
        patient_id: UUID,
        session_id: UUID,
        fallback_reason: str,
        fallback_method: str = "whatsapp_conversational"
    ) -> AuditLog:
        """
        Log fallback to WhatsApp conversational flow.

        Args:
            patient_id: Patient for whom fallback was activated
            session_id: Quiz session identifier
            fallback_reason: Reason for fallback activation
            fallback_method: Method used for fallback

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_fallback_activated",
            event_category="access",
            severity="warning",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "fallback_reason": fallback_reason,
                "fallback_method": fallback_method
            },
            result="fallback",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_reminder_sent(
        self,
        patient_id: UUID,
        session_id: UUID,
        delivery_channel: str,
        is_retry: bool = False,
        retry_count: int = 0
    ) -> AuditLog:
        """
        Log quiz reminder sent.

        Args:
            patient_id: Patient to whom reminder was sent
            session_id: Quiz session identifier
            delivery_channel: Channel used (email, whatsapp, etc.)
            is_retry: Whether this is a retry attempt
            retry_count: Number of retry attempts

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_reminder_sent",
            event_category="access",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "delivery_channel": delivery_channel,
                "is_retry": is_retry,
                "retry_count": retry_count
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_reminder_failed(
        self,
        patient_id: UUID,
        session_id: UUID,
        delivery_channel: str,
        failure_reason: str,
        retry_count: int = 0
    ) -> AuditLog:
        """
        Log quiz reminder failure.

        Args:
            patient_id: Patient for whom reminder failed
            session_id: Quiz session identifier
            delivery_channel: Channel that failed
            failure_reason: Reason for failure
            retry_count: Number of retry attempts made

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="monthly_quiz_reminder_failed",
            event_category="access",
            severity="error",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "delivery_channel": delivery_channel,
                "failure_reason": failure_reason,
                "retry_count": retry_count
            },
            result="failure",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_consent_given(
        self,
        patient_id: UUID,
        consent_type: str,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Log LGPD consent given.

        Args:
            patient_id: Patient who gave consent
            consent_type: Type of consent given
            ip_address: IP address of consent

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="lgpd_consent_given",
            event_category="consent",
            severity="info",
            patient_id=patient_id,
            ip_address=ip_address,
            event_data={
                "consent_type": consent_type
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent",
            retention_days=2555  # 7 years for LGPD compliance
        )

    def log_data_deletion(
        self,
        patient_id: UUID,
        user_id: UUID,
        deletion_scope: str,
        reason: str
    ) -> AuditLog:
        """
        Log data deletion (right to be forgotten).

        Args:
            patient_id: Patient whose data was deleted
            user_id: User who performed the deletion
            deletion_scope: Scope of deletion (partial, full, etc.)
            reason: Reason for deletion

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_event(
            event_type="lgpd_data_deleted",
            event_category="data_change",
            severity="warning",
            actor_id=user_id,
            subject_id=patient_id,
            event_data={
                "deletion_scope": deletion_scope,
                "reason": reason
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legal_obligation",
            retention_days=2555  # 7 years retention
        )

    def get_patient_audit_trail(
        self,
        patient_id: UUID,
        limit: int = 100
    ) -> list:
        """
        Get audit trail for a specific patient (for LGPD export).

        Args:
            patient_id: Patient to get audit trail for
            limit: Maximum number of records to return

        Returns:
            list[AuditLog]: List of audit log entries
        """
        from app.models.audit_log import AuditLog

        # Query by metadata subject_id since it's not a top-level column
        return self.db.query(AuditLog).filter(
            AuditLog.event_metadata['subject_id'].astext == str(patient_id)
        ).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()

    def cleanup_expired_logs(self) -> int:
        """
        Clean up logs past retention period.

        Note: This is a placeholder that defers to system retention policy
        to avoid accidental deletion with the new schema.

        Returns:
            int: Number of logs cleaned up (always 0 in legacy adapter)
        """
        self.logger.info("Cleanup called on legacy adapter - deferring to system retention policy")
        return 0
