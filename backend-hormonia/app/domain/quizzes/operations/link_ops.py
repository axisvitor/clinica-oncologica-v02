"""Link operations: regenerate, cancel, resend."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.repositories.quiz import QuizSessionRepository, QuizTemplateRepository
from app.schemas.monthly_quiz import DeliveryMethod, QuizLinkStatus
from app.exceptions import NotFoundError, ValidationError
from app.services.audit import AuditService
from app.core.monthly_quiz_config import get_monthly_quiz_config

from ..session.token_manager import TokenManager
from ..delivery.link_builder import LinkBuilder
from ..delivery.service import DeliveryService

import logging

logger = logging.getLogger(__name__)


class LinkOperations:
    """Handles regeneration, cancellation, and resending of quiz links."""

    def __init__(self, db: Session):
        self.db = db
        self.config = get_monthly_quiz_config()
        self.session_repository = QuizSessionRepository(db)
        self.template_repository = QuizTemplateRepository(db)
        self.token_manager = TokenManager()
        self.link_builder = LinkBuilder()
        self.delivery_service = DeliveryService(db)
        self.audit_service = AuditService(db)

    async def regenerate_link(
        self, session_id: UUID, actor_id: Optional[UUID] = None
    ) -> tuple[str, datetime]:
        """Regenerate a new token and link for an expired session.

        Args:
            session_id: Session identifier
            actor_id: User performing the regeneration

        Returns:
            Tuple of (new_token, new_expires_at)

        Raises:
            NotFoundError: Session not found
            ValidationError: Session completed or invalid
        """
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        if session.status == "completed":
            raise ValidationError("Cannot regenerate link for completed session")

        metadata = session.session_metadata or {}
        regeneration_count = metadata.get("regeneration_count", 0)

        # Generate new expiry time
        new_expires_at = self.token_manager.generate_expiry()

        # Generate new token
        new_token = self.token_manager.generate_token(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            expires_at=new_expires_at,
            rotation_count=regeneration_count + 1,
        )

        # Update metadata
        metadata["token_hash"] = self.token_manager.hash_token(new_token)
        metadata["expires_at"] = new_expires_at.isoformat()
        metadata["regeneration_count"] = regeneration_count + 1
        metadata["regenerated_at"] = datetime.utcnow().isoformat()
        metadata["link_status"] = QuizLinkStatus.ACTIVE.value

        session.session_metadata = metadata
        self.db.commit()

        # Audit log
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_regenerated(
                actor_id=actor_id or UUID("00000000-0000-0000-0000-000000000000"),
                patient_id=session.patient_id,
                session_id=session.id,
                regeneration_count=regeneration_count + 1,
            )

        return new_token, new_expires_at

    async def cancel_link(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Cancel a quiz link (update status to cancelled).

        Args:
            session_id: Session identifier
            actor_id: User performing the cancellation
            ip_address: IP address of request
            user_agent: User agent of request

        Raises:
            NotFoundError: Session not found
            ValidationError: Session already completed
        """
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        if session.status == "completed":
            raise ValidationError("Cannot cancel a completed quiz session")

        # Update metadata to cancelled status
        metadata = session.session_metadata or {}
        metadata["link_status"] = QuizLinkStatus.CANCELLED.value
        metadata["cancelled_at"] = datetime.utcnow().isoformat()
        metadata["cancelled_by"] = str(actor_id) if actor_id else None

        session.session_metadata = metadata
        self.db.commit()

        # Audit log cancellation
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_cancelled(
                actor_id=actor_id or UUID("00000000-0000-0000-0000-000000000000"),
                patient_id=session.patient_id,
                session_id=session.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

    async def resend_link(
        self,
        session_id: UUID,
        delivery_method: DeliveryMethod,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[str, datetime]:
        """Resend an existing quiz link via a new delivery method.

        Args:
            session_id: Session identifier
            delivery_method: New delivery method
            actor_id: User performing the resend
            ip_address: IP address of request
            user_agent: User agent of request

        Returns:
            Tuple of (new_token, expires_at)

        Raises:
            NotFoundError: Session or patient/template not found
            ValidationError: Link expired or completed
        """
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}

        # Check if session is still valid
        expires_at = datetime.fromisoformat(
            metadata.get("expires_at", datetime.utcnow().isoformat())
        )
        if datetime.utcnow() > expires_at:
            raise ValidationError("Cannot resend expired quiz link")

        if session.status == "completed":
            raise ValidationError("Cannot resend completed quiz link")

        # Audit log link resend
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_resent(
                actor_id=actor_id or UUID("00000000-0000-0000-0000-000000000000"),
                patient_id=session.patient_id,
                session_id=session.id,
                delivery_method=delivery_method.value,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        # Regenerate token for security
        token = self.token_manager.generate_token(
            session.patient_id, session.quiz_template_id, expires_at
        )

        # Update metadata
        metadata["token_hash"] = self.token_manager.hash_token(token)
        metadata["delivery_method"] = delivery_method.value
        metadata["resent_at"] = datetime.utcnow().isoformat()
        session.session_metadata = metadata
        self.db.commit()

        patient = (
            self.db.query(Patient).filter(Patient.id == session.patient_id).first()
        )
        if not patient:
            raise NotFoundError(f"Patient with ID {session.patient_id} not found")

        template = self.template_repository.get(session.quiz_template_id)
        if not template:
            raise NotFoundError(
                f"Quiz template with ID {session.quiz_template_id} not found"
            )

        remaining_hours = (
            max(int((expires_at - datetime.utcnow()).total_seconds() // 3600), 0)
            if expires_at
            else self.config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS
        )

        link_url = self.link_builder.build_link(token)

        delivery_record = None
        last_status = "pending"
        last_error = None

        try:
            delivery_record = await self.delivery_service.send_quiz_link_notification(
                patient=patient,
                template=template,
                session=session,
                link_url=link_url,
                delivery_method=delivery_method,
                expiry_hours=remaining_hours,
                custom_message=metadata.get("custom_message"),
            )
            last_status = "sent" if delivery_record.get("sent") else "pending"
        except Exception as exc:
            last_status = "failed"
            last_error = str(exc)
        finally:
            self.delivery_service.record_delivery_attempt(
                session=session,
                delivery_method=delivery_method,
                status=last_status,
                message_id=delivery_record.get("message_id")
                if delivery_record
                else None,
                error=last_error,
                action="resend",
            )
            self.db.commit()
            self.db.refresh(session)

        return token, expires_at
