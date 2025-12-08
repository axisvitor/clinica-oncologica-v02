"""Main orchestrator for quiz session management (refactored from quiz_session_manager.py)."""

import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient
from app.repositories.quiz import QuizTemplateRepository, QuizSessionRepository
from app.schemas.monthly_quiz import (
    MonthlyQuizLinkCreate, MonthlyQuizLinkResponse,
    QuizLinkStatus, DeliveryMethod, BulkQuizLinkCreate, BulkQuizLinkResponse
)
from app.exceptions import NotFoundError, ValidationError
from app.services.audit import AuditService
from app.monitoring.business_metrics import BusinessMetricsCollector
from app.core.monthly_quiz_config import get_monthly_quiz_config

from .session import TokenManager, SessionFactory
from .delivery import LinkBuilder, DeliveryService
from .operations import LinkOperations, ExpiryHandler, BulkManager
from .queries import StatusQuery, HistoryQuery

import logging

logger = logging.getLogger(__name__)


class QuizSessionManager:
    """Manages quiz session lifecycle, tokens, and link operations.

    This is a refactored orchestrator that delegates to specialized modules:
    - session/: Token and session creation
    - delivery/: Link building and message delivery
    - operations/: Link operations (regenerate, cancel, resend, bulk)
    - queries/: Status and history queries
    """

    def __init__(self, db: Session):
        self.db = db
        self.config = get_monthly_quiz_config()

        # Repositories
        self.template_repository = QuizTemplateRepository(db)
        self.session_repository = QuizSessionRepository(db)

        # Services
        self.audit_service = AuditService(db)
        self.metrics_collector = BusinessMetricsCollector()

        # Specialized modules
        self.token_manager = TokenManager()
        self.session_factory = SessionFactory(db)
        self.link_builder = LinkBuilder()
        self.delivery_service = DeliveryService(db)
        self.link_operations = LinkOperations(db)
        self.expiry_handler = ExpiryHandler(db, max_regenerations=getattr(self.config, 'MAX_LINK_REGENERATIONS', 2))
        self.bulk_manager = BulkManager(db)
        self.status_query = StatusQuery(db)
        self.history_query = HistoryQuery(db, self.status_query)

    # ========== PRIVATE HELPERS (for backward compatibility) ==========

    def _generate_token(
        self,
        patient_id: UUID,
        quiz_template_id: UUID,
        expires_at: datetime,
        rotation_count: int = 0
    ) -> str:
        """Generate JWT token (delegates to TokenManager)."""
        return self.token_manager.generate_token(patient_id, quiz_template_id, expires_at, rotation_count)

    def _verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token (delegates to TokenManager)."""
        return self.token_manager.verify_token(token)

    def _record_delivery_attempt(
        self,
        session: QuizSession,
        delivery_method: DeliveryMethod,
        status: str,
        message_id: Optional[str] = None,
        error: Optional[str] = None,
        action: str = "send"
    ) -> None:
        """Record delivery attempt (delegates to DeliveryService)."""
        self.delivery_service.record_delivery_attempt(
            session, delivery_method, status, message_id, error, action
        )

    async def _send_quiz_link_notification(
        self,
        patient: Patient,
        template: QuizTemplate,
        session: QuizSession,
        link_url: str,
        delivery_method: DeliveryMethod,
        expiry_hours: int,
        custom_message: Optional[str]
    ) -> Dict[str, Any]:
        """Send quiz link notification (delegates to DeliveryService)."""
        return await self.delivery_service.send_quiz_link_notification(
            patient, template, session, link_url, delivery_method, expiry_hours, custom_message
        )

    # ========== PUBLIC API ==========

    async def create_quiz_link(
        self,
        link_data: MonthlyQuizLinkCreate,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Create a new monthly quiz link for a patient."""
        # Validate patient exists
        patient = self.db.query(Patient).filter(Patient.id == link_data.patient_id).first()
        if not patient:
            raise NotFoundError(f"Patient with ID {link_data.patient_id} not found")

        # Validate template exists and is active
        template = self.template_repository.get(link_data.quiz_template_id)
        if not template:
            raise NotFoundError(f"Quiz template with ID {link_data.quiz_template_id} not found")

        if not template.is_active:
            raise ValidationError("Cannot create link for inactive template")

        # Calculate expiration
        expiry_hours = link_data.expiry_hours or self.config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS
        expires_at = self.token_manager.generate_expiry(expiry_hours)

        # Create session with link
        session, token = await self.session_factory.create_session_with_link(
            patient_id=link_data.patient_id,
            quiz_template_id=link_data.quiz_template_id,
            delivery_method=link_data.delivery_method,
            expires_at=expires_at,
            custom_message=link_data.custom_message
        )

        # Build link URL
        link_url = self.link_builder.build_link(token)

        delivery_record: Optional[Dict[str, Any]] = None
        last_status = "pending"
        last_error: Optional[str] = None

        if link_data.send_immediately:
            try:
                delivery_record = await self._send_quiz_link_notification(
                    patient=patient,
                    template=template,
                    session=session,
                    link_url=link_url,
                    delivery_method=link_data.delivery_method,
                    expiry_hours=expiry_hours,
                    custom_message=link_data.custom_message
                )
                last_status = "sent" if delivery_record.get("sent") else "pending"
            except Exception as exc:
                last_status = "failed"
                last_error = str(exc)
            finally:
                self._record_delivery_attempt(
                    session=session,
                    delivery_method=link_data.delivery_method,
                    status=last_status,
                    message_id=delivery_record.get("message_id") if delivery_record else None,
                    error=last_error,
                    action="send"
                )
                self.db.commit()
                self.db.refresh(session)

        # Audit log link creation
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_created(
                actor_id=actor_id or UUID('00000000-0000-0000-0000-000000000000'),
                patient_id=link_data.patient_id,
                session_id=session.id,
                delivery_method=link_data.delivery_method.value,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # Record metrics for link generation
        await self.metrics_collector.record_quiz_link_generated(
            patient_id=str(link_data.patient_id),
            quiz_template_id=str(link_data.quiz_template_id),
            token_prefix=token[:10],
            delivery_method=link_data.delivery_method.value,
            expires_at=expires_at
        )

        # Build response
        metadata = session.session_metadata or {}

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=link_data.patient_id,
            quiz_template_id=link_data.quiz_template_id,
            token=token,
            link_url=link_url,
            delivery_method=link_data.delivery_method,
            status=QuizLinkStatus.ACTIVE,
            expires_at=expires_at,
            created_at=session.started_at,
            accessed_at=None,
            completed_at=None,
            access_count=metadata.get("access_count", 0),
            delivery_attempts=metadata.get("delivery_attempts"),
            last_delivery_status=metadata.get("last_delivery_status"),
            last_delivery_method=metadata.get("last_delivery_method")
        )

    def find_session_by_token(self, token: str) -> QuizSession:
        """Find quiz session by token hash."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        payload = self._verify_token(token)
        patient_id = UUID(payload["patient_id"])
        quiz_template_id = UUID(payload["quiz_template_id"])

        sessions = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_id,
                QuizSession.quiz_template_id == quiz_template_id,
                QuizSession.session_metadata["token_hash"].astext == token_hash
            )
        ).all()

        if not sessions:
            raise NotFoundError("Quiz session not found for this token")

        return sessions[0]

    async def get_quiz_link_status(self, session_id: UUID) -> MonthlyQuizLinkResponse:
        """Get status of a quiz link (delegates to StatusQuery)."""
        return await self.status_query.get_link_status(session_id)

    async def create_bulk_quiz_links(
        self,
        bulk_data: BulkQuizLinkCreate,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> BulkQuizLinkResponse:
        """Create quiz links for multiple patients (delegates to BulkManager)."""
        return await self.bulk_manager.create_bulk_links(
            bulk_data,
            create_link_callback=self.create_quiz_link,
            actor_id=actor_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

    async def resend_quiz_link(
        self,
        session_id: UUID,
        delivery_method: DeliveryMethod,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Resend an existing quiz link (delegates to LinkOperations)."""
        token, expires_at = await self.link_operations.resend_link(
            session_id, delivery_method, actor_id, ip_address, user_agent
        )

        session = self.session_repository.get(session_id)
        updated_metadata = session.session_metadata or {}
        link_url = self.link_builder.build_link(token)

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            token=token,
            link_url=link_url,
            delivery_method=delivery_method,
            status=QuizLinkStatus.ACTIVE,
            expires_at=expires_at,
            created_at=session.started_at,
            accessed_at=datetime.fromisoformat(updated_metadata["accessed_at"]) if updated_metadata.get("accessed_at") else None,
            completed_at=session.completed_at,
            access_count=updated_metadata.get("access_count", 0),
            delivery_attempts=updated_metadata.get("delivery_attempts"),
            last_delivery_status=updated_metadata.get("last_delivery_status"),
            last_delivery_method=updated_metadata.get("last_delivery_method")
        )

    async def regenerate_link(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None
    ) -> MonthlyQuizLinkResponse:
        """Regenerate a new token and link (delegates to LinkOperations)."""
        new_token, new_expires_at = await self.link_operations.regenerate_link(session_id, actor_id)

        session = self.session_repository.get(session_id)
        metadata = session.session_metadata or {}
        link_url = self.link_builder.build_link(new_token)

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            token=new_token,
            link_url=link_url,
            delivery_method=DeliveryMethod(metadata.get("delivery_method", "whatsapp")),
            status=QuizLinkStatus.ACTIVE,
            expires_at=new_expires_at,
            created_at=session.started_at,
            accessed_at=datetime.fromisoformat(metadata["accessed_at"]) if metadata.get("accessed_at") else None,
            completed_at=session.completed_at,
            access_count=metadata.get("access_count", 0)
        )

    async def handle_expired_token(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Handle expired token (delegates to ExpiryHandler)."""
        return await self.expiry_handler.handle_expired_token(
            session_id,
            regenerate_callback=self.link_operations.regenerate_link,
            actor_id=actor_id
        )

    async def cancel_quiz_link(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Cancel a quiz link (delegates to LinkOperations)."""
        await self.link_operations.cancel_link(session_id, actor_id, ip_address, user_agent)
        return await self.get_quiz_link_status(session_id)

    async def get_patient_latest_status(self, patient_id: UUID) -> MonthlyQuizLinkResponse:
        """Get latest quiz link status for patient (delegates to StatusQuery)."""
        return await self.status_query.get_patient_latest_status(patient_id)

    async def get_patient_history(
        self,
        patient_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> List[MonthlyQuizLinkResponse]:
        """Get patient quiz session history (delegates to HistoryQuery)."""
        return await self.history_query.get_patient_history(patient_id, limit, offset)

    async def get_active_links(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[MonthlyQuizLinkResponse]:
        """Get all active quiz links (delegates to StatusQuery)."""
        return await self.status_query.get_active_links(limit, offset)

    async def get_active_links_with_details(
        self,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get active links with details (delegates to StatusQuery)."""
        return await self.status_query.get_active_links_with_details(user_id)

    def track_failure(
        self,
        session_id: UUID,
        failure_reason: str,
        failure_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track failure (delegates to ExpiryHandler)."""
        self.expiry_handler.track_failure(session_id, failure_reason, failure_details)

    async def rotate_token(
        self,
        session: QuizSession,
        template: QuizTemplate
    ) -> str:
        """Generate new rotated token for quiz session."""
        expires_at_dt = datetime.fromisoformat(
            session.session_metadata.get("expires_at", datetime.utcnow().isoformat())
        )

        new_token = self.token_manager.generate_token(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            expires_at=expires_at_dt
        )

        # Update session metadata with new token hash
        new_token_hash = self.token_manager.hash_token(new_token)

        metadata = session.session_metadata or {}
        metadata["previous_token_hash"] = metadata.get("token_hash")
        metadata["token_rotated_at"] = datetime.utcnow().isoformat()
        metadata["token_hash"] = new_token_hash

        session.session_metadata = metadata
        self.db.commit()

        return new_token
