"""
Quiz Audit Mixin Module.

Contains all quiz-related audit logging methods.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.audit_log import AuditLog


class QuizAuditMixin:
    """
    Mixin providing quiz-related audit logging methods.

    Requires: log_event method from BaseAuditService
    """

    def log_link_created(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        delivery_method: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log quiz link creation."""
        return self.log_event(  # type: ignore[attr-defined]
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
                "expires_at": expires_at.isoformat(),
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
        )

    def log_link_accessed(
        self,
        patient_id: UUID,
        session_id: UUID,
        ip_address: str,
        user_agent: str,
        token_prefix: str,
    ) -> AuditLog:
        """Log quiz link access."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_link_accessed",
            event_category="access",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={"token_prefix": token_prefix},
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent",
        )

    def log_response_submitted(
        self,
        patient_id: UUID,
        session_id: UUID,
        question_id: str,
        response_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log quiz response submission."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_response_submitted",
            event_category="data_change",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={"question_id": question_id, "response_id": str(response_id)},
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent",
        )

    def log_invalid_access_attempt(
        self,
        ip_address: str,
        user_agent: str,
        reason: str,
        token_prefix: Optional[str] = None,
    ) -> AuditLog:
        """Log invalid access attempt."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_invalid_access",
            event_category="security",
            severity="warning",
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={"reason": reason, "token_prefix": token_prefix},
            result="blocked",
        )

    def log_token_expired(self, patient_id: UUID, session_id: UUID) -> AuditLog:
        """Log token expiration."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_token_expired",
            event_category="security",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            result="expired",
        )

    def log_link_resent(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        delivery_method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log quiz link resend action."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_link_resent",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={"delivery_method": delivery_method},
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
        )

    def log_link_regenerated(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        regeneration_count: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log quiz link regeneration action."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_link_regenerated",
            event_category="security",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={"regeneration_count": regeneration_count},
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
        )

    def log_link_cancelled(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log quiz link cancellation action."""
        return self.log_event(  # type: ignore[attr-defined]
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
            legal_basis="legitimate_interest",
        )

    def log_link_expired(
        self, patient_id: UUID, session_id: UUID, fallback_activated: bool = False
    ) -> AuditLog:
        """Log quiz link expiration."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_link_expired",
            event_category="security",
            severity="warning" if not fallback_activated else "info",
            subject_id=patient_id,
            session_id=session_id,
            event_data={"fallback_activated": fallback_activated},
            result="expired",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
        )

    def log_fallback_activated(
        self,
        patient_id: UUID,
        session_id: UUID,
        fallback_reason: str,
        fallback_method: str = "whatsapp_conversational",
    ) -> AuditLog:
        """Log fallback to WhatsApp conversational flow."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_fallback_activated",
            event_category="access",
            severity="warning",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "fallback_reason": fallback_reason,
                "fallback_method": fallback_method,
            },
            result="fallback",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
        )

    def log_reminder_sent(
        self,
        patient_id: UUID,
        session_id: UUID,
        delivery_channel: str,
        is_retry: bool = False,
        retry_count: int = 0,
    ) -> AuditLog:
        """Log quiz reminder sent."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_reminder_sent",
            event_category="access",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "delivery_channel": delivery_channel,
                "is_retry": is_retry,
                "retry_count": retry_count,
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
        )

    def log_reminder_failed(
        self,
        patient_id: UUID,
        session_id: UUID,
        delivery_channel: str,
        failure_reason: str,
        retry_count: int = 0,
    ) -> AuditLog:
        """Log quiz reminder failure."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="monthly_quiz_reminder_failed",
            event_category="access",
            severity="error",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "delivery_channel": delivery_channel,
                "failure_reason": failure_reason,
                "retry_count": retry_count,
            },
            result="failure",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
        )

    def log_consent_given(
        self, patient_id: UUID, consent_type: str, ip_address: Optional[str] = None
    ) -> AuditLog:
        """Log LGPD consent given."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="lgpd_consent_given",
            event_category="consent",
            severity="info",
            patient_id=patient_id,
            ip_address=ip_address,
            event_data={"consent_type": consent_type},
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent",
            retention_days=2555,  # 7 years for LGPD compliance
        )

    def log_data_deletion(
        self, patient_id: UUID, user_id: UUID, deletion_scope: str, reason: str
    ) -> AuditLog:
        """Log data deletion (right to be forgotten)."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="lgpd_data_deleted",
            event_category="data_change",
            severity="warning",
            actor_id=user_id,
            subject_id=patient_id,
            event_data={"deletion_scope": deletion_scope, "reason": reason},
            result="success",
            data_subject_id=patient_id,
            legal_basis="legal_obligation",
            retention_days=2555,  # 7 years retention
        )
