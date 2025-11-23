"""
Quiz Session Manager Module for Monthly Quiz Service.

Handles quiz session lifecycle, token management, and link operations.
Responsibilities: Session creation, token generation/verification, link status,
session state tracking, and patient session queries.

NOTE: Renamed from SessionManager to QuizSessionManager to avoid name collision
with core.session_manager.SessionManager (database session management).
"""
import secrets
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
import jwt
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text

from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient
from app.repositories.quiz import QuizTemplateRepository, QuizSessionRepository
from app.services.quiz import QuizSessionService
from app.domain.messaging.core import MessageFactory
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.core.monthly_quiz_config import get_monthly_quiz_config
from app.exceptions import NotFoundError, ValidationError, ConflictError
from app.schemas.monthly_quiz import (
    MonthlyQuizLinkCreate, MonthlyQuizLinkResponse,
    QuizLinkStatus, DeliveryMethod, BulkQuizLinkCreate, BulkQuizLinkResponse
)
from app.schemas.quiz import QuizSessionCreate
from app.services.audit_service import AuditService
from app.monitoring.business_metrics import BusinessMetricsCollector
import logging

logger = logging.getLogger(__name__)


class QuizSessionManager:
    """Manages quiz session lifecycle, tokens, and link operations.

    Renamed from SessionManager to QuizSessionManager to eliminate name
    collision with core database SessionManager.
    """

    def __init__(self, db: Session):
        self.db = db
        self.config = get_monthly_quiz_config()
        self.template_repository = QuizTemplateRepository(db)
        self.session_repository = QuizSessionRepository(db)
        self.quiz_session_service = QuizSessionService(db)
        self.audit_service = AuditService(db)
        self.metrics_collector = BusinessMetricsCollector()

        # Initialize Redis for fast patient checking
        try:
            from app.core.redis_manager import get_redis_manager
            self.redis_manager = get_redis_manager()
            self.redis_client = self.redis_manager.get_compatible_client('sync')
        except Exception as e:
            logger.warning(f"Redis not available for fast patient checking: {e}")
        # Warn if using localhost in production-like environment
        if "localhost" in self.config.MONTHLY_QUIZ_BASE_URL and self.config.ENVIRONMENT != "development":
            logger.warning(
                f"MONTHLY_QUIZ_BASE_URL is set to localhost ({self.config.MONTHLY_QUIZ_BASE_URL}) "
                "in non-development environment. Quiz links will be invalid for external users."
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
        """Send the monthly quiz link to the patient via WhatsApp with retries."""
        max_retries = 3
        retry_delay = 2  # seconds
        last_error = None

        message_factory = MessageFactory(self.db)
        message = message_factory.create_monthly_quiz_link_message(
            patient_id=patient.id,
            patient_name=patient.name,
            link_url=link_url,
            quiz_session_id=str(session.id),
            expiry_hours=expiry_hours,
            delivery_method=delivery_method.value,
            custom_message=custom_message
        )

        whatsapp_service = UnifiedWhatsAppService(
            db=self.db,
            messaging_mode=MessagingMode.HYBRID
        )

        for attempt in range(max_retries):
            try:
                sent = await whatsapp_service.send_message(message)
                
                if sent:
                    return {
                        "sent": True,
                        "message_id": str(message.id),
                        "attempts": attempt + 1
                    }
                else:
                    # If send_message returns False without raising, treat as failure and retry
                    logger.warning(
                        f"WhatsApp send returned False (attempt {attempt + 1}/{max_retries})",
                        extra={"patient_id": str(patient.id)}
                    )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"Failed to send monthly quiz link (attempt {attempt + 1}/{max_retries}): {exc}",
                    extra={
                        "patient_id": str(patient.id),
                        "quiz_session_id": str(session.id),
                        "error": str(exc)
                    }
                )
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff

        # If we get here, all retries failed
        error_msg = str(last_error) if last_error else "Unknown error (send returned False)"
        logger.error(
            "All retries failed for monthly quiz link delivery",
            extra={
                "patient_id": str(patient.id),
                "quiz_session_id": str(session.id),
                "delivery_method": delivery_method.value,
                "error": error_msg
            }
        )
        raise Exception(f"Failed to send after {max_retries} attempts: {error_msg}")

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
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

        # Generate token
        token = self._generate_token(link_data.patient_id, link_data.quiz_template_id, expires_at)

        # Build link URL
        link_url = f"{self.config.MONTHLY_QUIZ_BASE_URL}?token={token}"

        # Create quiz session with metadata containing link info
        session_data = QuizSessionCreate(
            patient_id=link_data.patient_id,
            quiz_template_id=link_data.quiz_template_id
        )

        session = await self.quiz_session_service.start_quiz_session(session_data)

        # Update session metadata with link information
        session_model = self.session_repository.get(session.id)
        session_model.session_metadata = {
            "delivery_method": link_data.delivery_method.value,
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "expires_at": expires_at.isoformat(),
            "link_status": QuizLinkStatus.ACTIVE.value,
            "access_count": 0,
            "custom_message": link_data.custom_message
        }
        self.db.commit()
        self.db.refresh(session_model)

        delivery_record: Optional[Dict[str, Any]] = None
        last_status = "pending"
        last_error: Optional[str] = None

        if link_data.send_immediately:
            try:
                delivery_record = await self._send_quiz_link_notification(
                    patient=patient,
                    template=template,
                    session=session_model,
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
                    session=session_model,
                    delivery_method=link_data.delivery_method,
                    status=last_status,
                    message_id=delivery_record.get("message_id") if delivery_record else None,
                    error=last_error,
                    action="send"
                )
                self.db.commit()
                self.db.refresh(session_model)

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
        metadata = session_model.session_metadata or {}

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
        """Get status of a quiz link."""
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}

        # Determine status
        status = QuizLinkStatus(metadata.get("link_status", QuizLinkStatus.ACTIVE.value))
        if session.status == 'completed':
            status = QuizLinkStatus.USED
        elif datetime.utcnow() > datetime.fromisoformat(metadata.get("expires_at", datetime.utcnow().isoformat())):
            status = QuizLinkStatus.EXPIRED

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            token="[REDACTED]",
            link_url=f"{self.config.MONTHLY_QUIZ_BASE_URL}?token=[REDACTED]",
            delivery_method=DeliveryMethod(metadata.get("delivery_method", "whatsapp")),
            status=status,
            expires_at=datetime.fromisoformat(metadata.get("expires_at", datetime.utcnow().isoformat())),
            created_at=session.started_at,
            accessed_at=datetime.fromisoformat(metadata["accessed_at"]) if metadata.get("accessed_at") else None,
            completed_at=session.completed_at,
            access_count=metadata.get("access_count", 0),
            delivery_attempts=metadata.get("delivery_attempts"),
            last_delivery_status=metadata.get("last_delivery_status"),
            last_delivery_method=metadata.get("last_delivery_method")
        )

    async def create_bulk_quiz_links(
        self,
        bulk_data: BulkQuizLinkCreate,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> BulkQuizLinkResponse:
        """Create quiz links for multiple patients."""
        links: List[MonthlyQuizLinkResponse] = []
        failures: List[Dict[str, Any]] = []

        for patient_id in bulk_data.patient_ids:
            try:
                link_data = MonthlyQuizLinkCreate(
                    patient_id=patient_id,
                    quiz_template_id=bulk_data.quiz_template_id,
                    delivery_method=bulk_data.delivery_method,
                    expiry_hours=bulk_data.expiry_hours,
                    custom_message=bulk_data.custom_message,
                    send_immediately=bulk_data.send_immediately
                )

                link = await self.create_quiz_link(
                    link_data,
                    actor_id=actor_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                links.append(link)

            except Exception as e:
                failures.append({
                    "patient_id": str(patient_id),
                    "error": str(e)
                })

        return BulkQuizLinkResponse(
            total_requested=len(bulk_data.patient_ids),
            total_created=len(links),
            total_failed=len(failures),
            links=links,
            failures=failures
        )

    async def resend_quiz_link(
        self,
        session_id: UUID,
        delivery_method: DeliveryMethod,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Resend an existing quiz link via a new delivery method."""
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}

        # Check if session is still valid
        expires_at = datetime.fromisoformat(metadata.get("expires_at", datetime.utcnow().isoformat()))
        if datetime.utcnow() > expires_at:
            raise ValidationError("Cannot resend expired quiz link")

        if session.status == 'completed':
            raise ValidationError("Cannot resend completed quiz link")

        # Audit log link resend
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_resent(
                actor_id=actor_id or UUID('00000000-0000-0000-0000-000000000000'),
                patient_id=session.patient_id,
                session_id=session.id,
                delivery_method=delivery_method.value,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # Regenerate token for security
        token = self._generate_token(
            session.patient_id,
            session.quiz_template_id,
            expires_at
        )

        # Update metadata
        metadata["token_hash"] = hashlib.sha256(token.encode()).hexdigest()
        metadata["delivery_method"] = delivery_method.value
        metadata["resent_at"] = datetime.utcnow().isoformat()
        session.session_metadata = metadata
        self.db.commit()

        patient = self.db.query(Patient).filter(Patient.id == session.patient_id).first()
        if not patient:
            raise NotFoundError(f"Patient with ID {session.patient_id} not found")

        template = self.template_repository.get(session.quiz_template_id)
        if not template:
            raise NotFoundError(f"Quiz template with ID {session.quiz_template_id} not found")

        remaining_hours = max(
            int((expires_at - datetime.utcnow()).total_seconds() // 3600),
            0
        ) if expires_at else self.config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS

        link_url = f"{self.config.MONTHLY_QUIZ_BASE_URL}?token={token}"

        delivery_record: Optional[Dict[str, Any]] = None
        last_status = "pending"
        last_error: Optional[str] = None

        try:
            delivery_record = await self._send_quiz_link_notification(
                patient=patient,
                template=template,
                session=session,
                link_url=link_url,
                delivery_method=delivery_method,
                expiry_hours=remaining_hours,
                custom_message=metadata.get("custom_message")
            )
            last_status = "sent" if delivery_record.get("sent") else "pending"
        except Exception as exc:
            last_status = "failed"
            last_error = str(exc)
        finally:
            self._record_delivery_attempt(
                session=session,
                delivery_method=delivery_method,
                status=last_status,
                message_id=delivery_record.get("message_id") if delivery_record else None,
                error=last_error,
                action="resend"
            )
            self.db.commit()
            self.db.refresh(session)

        # Build response
        status = QuizLinkStatus.ACTIVE
        updated_metadata = session.session_metadata or {}

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            token=token,
            link_url=link_url,
            delivery_method=delivery_method,
            status=status,
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
        """Regenerate a new token and link for an expired session."""
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        if session.status == 'completed':
            raise ValidationError("Cannot regenerate link for completed session")

        metadata = session.session_metadata or {}
        regeneration_count = metadata.get("regeneration_count", 0)

        # Generate new expiry time
        new_expires_at = datetime.utcnow() + timedelta(
            hours=self.config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS
        )

        # Generate new token
        new_token = self._generate_token(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            expires_at=new_expires_at,
            rotation_count=regeneration_count + 1
        )

        # Update metadata
        metadata["token_hash"] = hashlib.sha256(new_token.encode()).hexdigest()
        metadata["expires_at"] = new_expires_at.isoformat()
        metadata["regeneration_count"] = regeneration_count + 1
        metadata["regenerated_at"] = datetime.utcnow().isoformat()
        metadata["link_status"] = QuizLinkStatus.ACTIVE.value

        session.session_metadata = metadata
        self.db.commit()

        # Audit log
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_regenerated(
                actor_id=actor_id or UUID('00000000-0000-0000-0000-000000000000'),
                patient_id=session.patient_id,
                session_id=session.id,
                regeneration_count=regeneration_count + 1
            )

        # Build link URL
        link_url = f"{self.config.MONTHLY_QUIZ_BASE_URL}?token={new_token}"

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
        """Handle expired token by checking regeneration limits."""
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}
        regeneration_count = metadata.get("regeneration_count", 0)

        # Maximum regenerations from config or default to 2
        max_regenerations = getattr(self.config, 'MAX_LINK_REGENERATIONS', 2)

        if regeneration_count >= max_regenerations:
            # Max regenerations exceeded - mark for fallback
            metadata["fallback_required"] = True
            metadata["fallback_reason"] = "max_regenerations_exceeded"
            session.session_metadata = metadata
            self.db.commit()

            return {
                "action": "fallback_required",
                "session_id": str(session_id),
                "reason": "max_regenerations_exceeded",
                "regeneration_count": regeneration_count
            }

        # Regenerate token
        result = await self.regenerate_link(
            session_id=session_id,
            actor_id=actor_id
        )

        return {
            "action": "regenerated",
            "session_id": str(session_id),
            "new_token": result.token,
            "new_expires_at": result.expires_at.isoformat(),
            "regeneration_count": regeneration_count + 1
        }

    async def cancel_quiz_link(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Cancel a quiz link (update status to cancelled)."""
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        if session.status == 'completed':
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
                actor_id=actor_id or UUID('00000000-0000-0000-0000-000000000000'),
                patient_id=session.patient_id,
                session_id=session.id,
                ip_address=ip_address,
                user_agent=user_agent
            )

        return await self.get_quiz_link_status(session_id)

    async def get_patient_latest_status(self, patient_id: UUID) -> MonthlyQuizLinkResponse:
        """Get the latest quiz link status for a specific patient."""
        start_time = time.time()

        # FAST 404 CHECK: Verify patient exists before heavy queries
        if not self._check_patient_exists_fast(str(patient_id)):
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Fast 404 for patient {str(patient_id)[:8]}... ({elapsed:.1f}ms)")
            raise NotFoundError(f"Patient {patient_id} not found")

        # Get the most recent session for the patient
        session = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_id,
                QuizSession.session_metadata.isnot(None)
            )
        ).order_by(QuizSession.started_at.desc()).first()

        if not session:
            raise NotFoundError(f"No quiz sessions found for patient {patient_id}")

        return await self.get_quiz_link_status(session.id)

    async def get_patient_history(
        self,
        patient_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> List[MonthlyQuizLinkResponse]:
        """Get quiz session history for a specific patient."""
        # FAST 404 CHECK: Verify patient exists before querying sessions
        if not self._check_patient_exists_fast(str(patient_id)):
            logger.info(f"Fast 404 for patient history {str(patient_id)[:8]}...")
            return []

        sessions = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_id,
                QuizSession.session_metadata.isnot(None)
            )
        ).order_by(QuizSession.started_at.desc()).offset(offset).limit(limit).all()

        results = []
        for session in sessions:
            try:
                link_response = await self.get_quiz_link_status(session.id)
                results.append(link_response)
            except Exception as e:
                logger.error(f"Error getting status for session {session.id}: {str(e)}")
                continue

        return results

    async def get_active_links(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[MonthlyQuizLinkResponse]:
        """Get all active (non-expired, uncompleted) quiz links."""
        sessions = self.db.query(QuizSession).filter(
            and_(
                QuizSession.status != 'completed',
                QuizSession.session_metadata.isnot(None),
                or_(
                    QuizSession.session_metadata["link_status"].astext == "active",
                    QuizSession.session_metadata["link_status"].astext.is_(None)
                )
            )
        ).order_by(QuizSession.started_at.desc()).offset(offset).limit(limit).all()

        active_links = []
        current_time = datetime.utcnow()

        for session in sessions:
            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")

            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if (current_time <= expires_at and
                        metadata.get("link_status") != "cancelled" and
                        session.status != 'completed'):

                        try:
                            link_response = await self.get_quiz_link_status(session.id)
                            active_links.append(link_response)
                        except Exception as e:
                            logger.error(f"Error getting status for session {session.id}: {str(e)}")
                            continue
                except ValueError:
                    continue

        return active_links

    async def get_active_links_with_details(
        self,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get active quiz links with patient and template details."""
        query = self.db.query(QuizSession).join(
            Patient,
            QuizSession.patient_id == Patient.id
        ).join(
            QuizTemplate,
            QuizSession.quiz_template_id == QuizTemplate.id
        ).filter(
            QuizSession.status != 'completed',
            QuizSession.session_metadata.isnot(None)
        )

        sessions = query.all()
        results = []
        current_time = datetime.utcnow()

        for session in sessions:
            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")

            if not expires_at_str:
                continue

            try:
                expires_at = datetime.fromisoformat(expires_at_str)

                if current_time <= expires_at:
                    access_url = f"{self.config.MONTHLY_QUIZ_BASE_URL}?token=[REDACTED]"

                    results.append({
                        "id": str(session.id),
                        "session_id": str(session.id),
                        "patient_id": str(session.patient_id),
                        "patient_name": session.patient.name if session.patient else "Unknown",
                        "patient_phone": session.patient.phone if hasattr(session.patient, 'phone') and session.patient.phone else None,
                        "template_id": str(session.quiz_template_id),
                        "template_name": session.quiz_template.name if session.quiz_template else "Unknown",
                        "template_version": session.quiz_template.version if session.quiz_template else "1.0",
                        "access_url": access_url,
                        "created_at": session.started_at.isoformat(),
                        "sent_at": session.started_at.isoformat(),
                        "expires_at": expires_at.isoformat(),
                        "is_active": expires_at > current_time,
                        "status": session.status,
                        "access_count": metadata.get("access_count", 0),
                        "delivery_method": metadata.get("delivery_method", "whatsapp")
                    })
            except (ValueError, AttributeError):
                continue

        return results

    def track_failure(
        self,
        session_id: UUID,
        failure_reason: str,
        failure_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track failure for monitoring repeated failures."""
        session = self.session_repository.get(session_id)
        if not session:
            return

        metadata = session.session_metadata or {}

        # Initialize failures tracking
        if "failures" not in metadata:
            metadata["failures"] = []

        failure_count = metadata.get("failure_count", 0)
        metadata["failure_count"] = failure_count + 1

        # Add failure record
        failure_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "reason": failure_reason,
            "details": failure_details or {}
        }
        metadata["failures"].append(failure_record)

        session.session_metadata = metadata
        self.db.commit()

    async def rotate_token(
        self,
        session: QuizSession,
        template: QuizTemplate
    ) -> str:
        """Generate new rotated token for quiz session."""
        expires_at_dt = datetime.fromisoformat(
            session.session_metadata.get("expires_at", datetime.utcnow().isoformat())
        )

        token_payload = {
            "patient_id": str(session.patient_id),
            "quiz_template_id": str(session.quiz_template_id),
            "session_id": str(session.id),
            "exp": expires_at_dt
        }

        # Generate new JWT token
        new_token = jwt.encode(
            token_payload,
            self.config.MONTHLY_QUIZ_TOKEN_SECRET,
            algorithm="HS256"
        )

        # Update session metadata with new token hash
        new_token_hash = hashlib.sha256(new_token.encode()).hexdigest()

        metadata = session.session_metadata or {}
        metadata["previous_token_hash"] = metadata.get("token_hash")
        metadata["token_rotated_at"] = datetime.utcnow().isoformat()
        metadata["token_hash"] = new_token_hash

        session.session_metadata = metadata
        self.db.commit()

        return new_token
