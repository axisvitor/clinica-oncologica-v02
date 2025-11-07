"""
Monthly Quiz Service - Refactored Modular Architecture.

This module provides a refactored version of the MonthlyQuizService,
split into focused, single-responsibility components.

Module Structure:
- session_manager: Quiz session lifecycle, token management, link operations
- question_renderer: Question formatting, context building, rendering
- answer_validator: Answer validation, normalization, encryption
- score_calculator: Score computation, result analysis, metrics
- report_generator: Report creation, statistics, analytics

Public API:
- MonthlyQuizService: Main service class (backward compatible)
- SessionManager: Direct access to session management
- QuestionRenderer: Direct access to question rendering
- AnswerValidator: Direct access to answer validation
- ScoreCalculator: Direct access to score calculation
- ReportGenerator: Direct access to report generation
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from .session_manager import SessionManager
from .question_renderer import QuestionRenderer
from .answer_validator import AnswerValidator
from .score_calculator import ScoreCalculator
from .report_generator import ReportGenerator

from app.models.quiz import QuizTemplate
from app.repositories.quiz import QuizResponseRepository
from app.services.quiz import QuizResponseService
from app.services.audit_service import AuditService
from app.core.monthly_quiz_config import get_monthly_quiz_config
from app.schemas.monthly_quiz import (
    MonthlyQuizLinkCreate, MonthlyQuizLinkResponse, MonthlyQuizAccessResponse,
    MonthlyQuizSubmitResponse, MonthlyQuizStats, QuizLinkStatus,
    DeliveryMethod, BulkQuizLinkCreate, BulkQuizLinkResponse
)
from app.schemas.quiz import QuizResponseCreate, QuestionType
from app.monitoring.business_metrics import BusinessMetricsCollector
import logging

logger = logging.getLogger(__name__)


class MonthlyQuizService:
    """
    Refactored Monthly Quiz Service with modular components.

    This service delegates responsibilities to specialized modules:
    - SessionManager: Handles session lifecycle and token management
    - QuestionRenderer: Formats and renders questions
    - AnswerValidator: Validates and normalizes responses
    - ScoreCalculator: Calculates scores and metrics
    - ReportGenerator: Generates reports and statistics

    Maintains backward compatibility with the original MonthlyQuizService API.
    """

    def __init__(self, db: Session):
        """
        Initialize the Monthly Quiz Service with all components.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.config = get_monthly_quiz_config()

        # Initialize modular components
        self.session_manager = SessionManager(db)
        self.question_renderer = QuestionRenderer()
        self.answer_validator = AnswerValidator()
        self.score_calculator = ScoreCalculator(db)
        self.report_generator = ReportGenerator(db)

        # Additional services
        self.response_repository = QuizResponseRepository(db)
        self.quiz_response_service = QuizResponseService(db)
        self.audit_service = AuditService(db)
        self.metrics_collector = BusinessMetricsCollector()

    # ========================================
    # Session Management Methods (Delegate to SessionManager)
    # ========================================

    async def create_quiz_link(
        self,
        link_data: MonthlyQuizLinkCreate,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Create a new monthly quiz link for a patient."""
        return await self.session_manager.create_quiz_link(
            link_data, actor_id, ip_address, user_agent
        )

    async def access_quiz_via_token(
        self,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizAccessResponse:
        """Access quiz using token."""
        # Verify token and get session
        payload = self.session_manager._verify_token(token)
        patient_id = UUID(payload["patient_id"])
        quiz_template_id = UUID(payload["quiz_template_id"])

        # Find session
        session = self.session_manager.find_session_by_token(token)
        metadata = session.session_metadata or {}

        # Enforce single-use token policy
        if (
            getattr(self.config, "MONTHLY_QUIZ_SINGLE_USE_TOKENS", False)
            and metadata.get("access_count", 0) > 0
        ):
            from app.exceptions import ValidationError
            raise ValidationError("This quiz link has already been used")

        # Enforce maximum access attempts per token
        max_attempts = getattr(self.config, "MONTHLY_QUIZ_MAX_ATTEMPTS", 0)
        if max_attempts and metadata.get("access_count", 0) >= max_attempts:
            from app.exceptions import ValidationError
            raise ValidationError("This quiz link is no longer available")

        # Check if already completed
        if session.status == 'completed':
            from app.exceptions import ValidationError
            raise ValidationError("This quiz has already been completed")

        # Update access count and timestamp
        metadata["access_count"] = metadata.get("access_count", 0) + 1
        if not metadata.get("accessed_at"):
            metadata["accessed_at"] = datetime.utcnow().isoformat()
        session.session_metadata = metadata
        self.db.commit()

        # Record metrics for successful access
        await self.metrics_collector.record_quiz_access_success(
            patient_id=str(patient_id),
            quiz_session_id=str(session.id),
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown",
            access_count=metadata.get("access_count", 0)
        )

        # Audit log access
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_accessed(
                patient_id=patient_id,
                session_id=session.id,
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                token_prefix=token[:10]
            )

        # Token rotation if enabled
        rotated_token = None
        if self.config.MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION:
            from app.repositories.quiz import QuizTemplateRepository
            template_repo = QuizTemplateRepository(self.db)
            template = template_repo.get(quiz_template_id)
            rotated_token = await self.session_manager.rotate_token(session, template)

            # Record token rotation metrics
            await self.metrics_collector.record_token_rotated(
                patient_id=str(patient_id),
                quiz_session_id=str(session.id),
                old_token_prefix=token[:10],
                new_token_prefix=rotated_token[:10],
                rotation_count=metadata.get("rotation_count", 0) + 1
            )

        # Get template and patient info
        from app.repositories.quiz import QuizTemplateRepository
        from app.models.patient import Patient
        template_repo = QuizTemplateRepository(self.db)
        template = template_repo.get(quiz_template_id)
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()

        # Build response using QuestionRenderer
        response = self.question_renderer.render_quiz_access_response(
            quiz_session_id=session.id,
            patient_name=patient.name,
            template=template,
            current_question_index=session.current_question,
            expires_at=datetime.fromisoformat(payload["expires_at"]),
            new_token=rotated_token
        )

        return response

    async def submit_quiz_response(
        self,
        submit_data: MonthlyQuizSubmitResponse,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a quiz response via token."""
        # Verify token and find session
        session = self.session_manager.find_session_by_token(submit_data.token)

        # Get template and validate question exists
        from app.repositories.quiz import QuizTemplateRepository
        template_repo = QuizTemplateRepository(self.db)
        template = template_repo.get(session.quiz_template_id)

        question = self.answer_validator.validate_question_exists(
            submit_data.question_id,
            template
        )

        # Validate and normalize response value
        response_value = self.answer_validator.validate_and_normalize_response(
            submit_data.response_value,
            question
        )

        # Encrypt sensitive response if enabled
        encrypted_response_value, is_encrypted = self.answer_validator.encrypt_response_if_needed(
            response_value,
            question
        )

        # Build response metadata
        response_metadata = self.answer_validator.build_response_metadata(
            is_encrypted=is_encrypted,
            other_text=submit_data.other_text,
            question_index=session.current_question,
            additional_metadata=submit_data.response_metadata
        )

        # Create response
        response_create = QuizResponseCreate(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            question_id=submit_data.question_id,
            question_text=question.get("text", ""),
            response_type=QuestionType(question.get("type", "open_text")),
            response_value=encrypted_response_value,
            response_metadata=response_metadata,
            responded_at=datetime.utcnow()
        )

        response = await self.quiz_response_service.create_response(response_create)

        # Update session progress
        session.current_question += 1

        # Check if quiz is completed
        total_questions = len(template.questions)
        if session.current_question >= total_questions:
            session.status = 'completed'
            session.completed_at = datetime.utcnow()
            # Calculate score using ScoreCalculator
            session.score = await self.score_calculator.calculate_score(session.id)

        self.db.commit()
        self.db.refresh(session)

        # Record metrics for successful submission
        await self.metrics_collector.record_quiz_submit_success(
            patient_id=str(session.patient_id),
            quiz_session_id=str(session.id),
            question_id=submit_data.question_id,
            response_id=str(response.id),
            is_encrypted=is_encrypted
        )

        # Audit log response submission
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_response_submitted(
                patient_id=session.patient_id,
                session_id=session.id,
                question_id=submit_data.question_id,
                response_id=response.id,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # Token rotation (if enabled)
        new_token = None
        if getattr(self.config, 'MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION', False):
            new_token = await self.session_manager.rotate_token(session, template)

        return {
            "response_id": str(response.id),
            "success": True,
            "message": "Response submitted successfully",
            "is_completed": session.status == 'completed',
            "total_score": session.score if session.status == 'completed' else None,
            "current_question_index": session.current_question,
            "new_token": new_token
        }

    async def get_quiz_link_status(self, session_id: UUID) -> MonthlyQuizLinkResponse:
        """Get status of a quiz link."""
        return await self.session_manager.get_quiz_link_status(session_id)

    async def create_bulk_quiz_links(
        self,
        bulk_data: BulkQuizLinkCreate,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> BulkQuizLinkResponse:
        """Create quiz links for multiple patients."""
        return await self.session_manager.create_bulk_quiz_links(
            bulk_data, actor_id, ip_address, user_agent
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
        return await self.session_manager.resend_quiz_link(
            session_id, delivery_method, actor_id, ip_address, user_agent
        )

    async def regenerate_link(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None
    ) -> MonthlyQuizLinkResponse:
        """Regenerate a new token and link for an expired session."""
        return await self.session_manager.regenerate_link(session_id, actor_id)

    async def handle_expired_token(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Handle expired token by checking regeneration limits."""
        return await self.session_manager.handle_expired_token(session_id, actor_id)

    async def cancel_quiz_link(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Cancel a quiz link."""
        return await self.session_manager.cancel_quiz_link(
            session_id, actor_id, ip_address, user_agent
        )

    async def get_patient_latest_status(self, patient_id: UUID) -> MonthlyQuizLinkResponse:
        """Get the latest quiz link status for a specific patient."""
        return await self.session_manager.get_patient_latest_status(patient_id)

    async def get_patient_history(
        self,
        patient_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> List[MonthlyQuizLinkResponse]:
        """Get quiz session history for a specific patient."""
        return await self.session_manager.get_patient_history(patient_id, limit, offset)

    async def get_active_links(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[MonthlyQuizLinkResponse]:
        """Get all active quiz links."""
        return await self.session_manager.get_active_links(limit, offset)

    async def get_active_links_with_details(
        self,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get active quiz links with patient and template details."""
        return await self.session_manager.get_active_links_with_details(user_id)

    def track_failure(
        self,
        session_id: UUID,
        failure_reason: str,
        failure_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track failure for monitoring repeated failures."""
        self.session_manager.track_failure(session_id, failure_reason, failure_details)

    # ========================================
    # Statistics and Report Methods (Delegate to ReportGenerator)
    # ========================================

    async def get_monthly_quiz_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> MonthlyQuizStats:
        """Get statistics for monthly quizzes."""
        return await self.report_generator.get_monthly_quiz_stats(start_date, end_date)

    async def get_quiz_stats(
        self,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get quiz statistics with backward-compatible field names."""
        return await self.report_generator.get_quiz_stats(user_id)

    # ========================================
    # Internal Helper Methods
    # ========================================

    async def _calculate_score(self, session_id: UUID) -> float:
        """Calculate score for a completed quiz session."""
        return await self.score_calculator.calculate_score(session_id)

    async def _rotate_token(self, session, template) -> str:
        """Generate new rotated token for quiz session."""
        return await self.session_manager.rotate_token(session, template)


__all__ = [
    "MonthlyQuizService",
    "SessionManager",
    "QuestionRenderer",
    "AnswerValidator",
    "ScoreCalculator",
    "ReportGenerator"
]
