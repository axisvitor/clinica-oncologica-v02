"""
Quiz Service - Consolidated Quiz Management Core (QW-023).

Consolidates:
    - quiz.py (QuizTemplateService, QuizSessionService, QuizResponseService)
    - monthly_quiz_service.py (MonthlyQuizService)
    - optimized_monthly_quiz_service.py

Total: 3 files → 1 file
"""

from __future__ import annotations

# Standard library imports
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

# Third-party imports
# FIX P1-007: Changed from AsyncSession to Session as code uses sync patterns
from sqlalchemy.orm import Session
from typing import Union

# Local application imports
from app.core.exceptions import NotFoundError
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.repositories.quiz import (
    QuizResponseRepository,
    QuizSessionRepository,
    QuizTemplateRepository,
)
from app.schemas.quiz import (
    QuizResponseCreate,
    QuizResponseResponse,
    QuizSessionCreate,
    QuizSessionResponse,
    QuizTemplateCreate,
    QuizTemplateResponse,
)
from app.utils.db_retry import with_db_retry


class QuizService:
    """
    Unified quiz service for all quiz operations.

    Provides a facade for template, session, and response
    management operations.

    Attributes:
        db: Database session.
        template_service: Template management service.
        session_service: Session management service.
        response_service: Response management service.
    """

    # FIX P1-007: Accept both sync and async sessions for backwards compatibility
    def __init__(self, db: Union[Session, "AsyncSession"]):  # type: ignore[name-defined]
        self.db = db
        self.template_service = QuizTemplateService(db)
        self.session_service = QuizSessionService(db)
        self.response_service = QuizResponseService(db)
        self._logger = logging.getLogger(__name__)


class QuizTemplateService:
    """
    Service for managing quiz templates.

    Handles CRUD operations for quiz templates including
    creation, retrieval, and pagination.

    Attributes:
        db: Database session.
        repository: Quiz template repository.
    """

    # FIX P1-007: Accept both sync and async sessions for backwards compatibility
    def __init__(
        self,
        db: Union[Session, "AsyncSession"],  # type: ignore[name-defined]
        repository: Optional[QuizTemplateRepository] = None,
    ):
        self.db = db
        self.repository = repository or QuizTemplateRepository(db)
        self._logger = logging.getLogger(__name__)

    @with_db_retry(max_retries=3)
    def create_template(self, data: QuizTemplateCreate) -> QuizTemplateResponse:
        """Create quiz template."""
        template = QuizTemplate(
            name=data.name,
            version=data.version,
            questions=[q.dict() for q in data.questions],
            is_active=data.is_active,
        )
        created = self.repository.create(template)
        self.db.commit()
        return QuizTemplateResponse.from_orm(created)

    @with_db_retry(max_retries=3)
    async def get_template(self, template_id: UUID) -> QuizTemplateResponse:
        """
        Get template by ID.

        Args:
            template_id: Template identifier.

        Returns:
            Quiz template response.

        Raises:
            NotFoundError: If template not found.
        """
        template = await self.repository.get(template_id)
        if not template:
            raise NotFoundError(f"Template {template_id} not found")
        return QuizTemplateResponse.from_orm(template)

    @with_db_retry(max_retries=3)
    def get_templates(
        self, skip: int = 0, limit: int = 100, active_only: bool = True
    ) -> tuple[list[QuizTemplateResponse], int]:
        """Get quiz templates with pagination."""

        query = self.db.query(QuizTemplate)

        if active_only:
            query = query.filter(QuizTemplate.is_active)

        total = query.count()
        templates = query.offset(skip).limit(limit).all()

        template_responses = [
            QuizTemplateResponse.from_orm(template) for template in templates
        ]
        return template_responses, total


class QuizSessionService:
    """
    Service for managing quiz sessions.

    Handles quiz session lifecycle including creation,
    retrieval, and response enrichment.

    Attributes:
        db: Database session.
        repository: Quiz session repository.
    """

    # FIX P1-007: Accept both sync and async sessions for backwards compatibility
    def __init__(
        self,
        db: Union[Session, "AsyncSession"],  # type: ignore[name-defined]
        repository: Optional[QuizSessionRepository] = None,
    ):
        self.db = db
        self.repository = repository or QuizSessionRepository(db)
        self._logger = logging.getLogger(__name__)

    @with_db_retry(max_retries=3)
    def create_session(self, data: QuizSessionCreate) -> QuizSessionResponse:
        """Create quiz session."""
        session = QuizSession(**data.dict())
        created = self.repository.create(session)
        self.db.flush()
        return QuizSessionResponse.from_orm(created)

    def get_session(self, session_id: UUID) -> Optional[QuizSession]:
        """
        Get quiz session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            QuizSession if found, None otherwise.
        """
        return self.repository.get(session_id)

    def get_active_session(self, patient_id: UUID) -> Optional[QuizSession]:
        """
        Get active (non-completed, non-expired) quiz session for patient.

        Args:
            patient_id: Patient identifier.

        Returns:
            Active QuizSession if found, None otherwise.
        """
        now = datetime.now(timezone.utc)
        session = (
            self.db.query(QuizSession)
            .filter(
                QuizSession.patient_id == patient_id,
                QuizSession.is_completed == False,
                QuizSession.expires_at > now,
            )
            .order_by(QuizSession.created_at.desc())
            .first()
        )
        return session

    def get_patient_sessions(
        self, patient_id: UUID, limit: int = 100, skip: int = 0
    ) -> tuple[list[QuizSession], int]:
        """
        Get all quiz sessions for a patient with pagination.

        Args:
            patient_id: Patient identifier.
            limit: Maximum number of sessions to return.
            skip: Number of sessions to skip.

        Returns:
            Tuple of (list of sessions, total count).
        """
        query = self.db.query(QuizSession).filter(
            QuizSession.patient_id == patient_id
        )
        total = query.count()
        sessions = (
            query.order_by(QuizSession.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return sessions, total

    def complete_session(
        self, session_id: UUID, final_score: Optional[float] = None
    ) -> Optional[QuizSession]:
        """
        Mark a quiz session as completed.

        Args:
            session_id: Session identifier.
            final_score: Optional final score to set.

        Returns:
            Updated QuizSession if found, None otherwise.
        """
        session = self.repository.get(session_id)
        if not session:
            self._logger.warning(f"Session {session_id} not found for completion")
            return None

        session.is_completed = True
        session.completed_at = datetime.now(timezone.utc)
        if final_score is not None:
            session.final_score = final_score

        self.db.flush()
        self._logger.info(f"Session {session_id} marked as completed")
        return session

    def start_quiz_session(
        self, session_data: dict[str, Any]
    ) -> QuizSession:
        """
        Start a new quiz session from dictionary data.

        Args:
            session_data: Dictionary with session data.

        Returns:
            Created QuizSession.
        """
        session = QuizSession(
            patient_id=session_data.get("patient_id"),
            template_id=session_data.get("template_id"),
            session_type=session_data.get("session_type", "monthly"),
            expires_at=session_data.get(
                "expires_at",
                datetime.now(timezone.utc) + timedelta(days=7)
            ),
            session_metadata=session_data.get("session_metadata", {}),
        )
        self.db.add(session)
        self.db.flush()
        self._logger.info(f"Started quiz session {session.id} for patient {session.patient_id}")
        return session

    def _enrich_session_response(self, session: QuizSession) -> QuizSessionResponse:
        """
        Enrich session response with additional data.
        This method can be patched by quiz_question_humanizer_integration.
        """
        return QuizSessionResponse.from_orm(session)


class QuizResponseService:
    """
    Service for managing quiz responses.

    Handles quiz response creation and processing.

    Attributes:
        db: Database session.
        repository: Quiz response repository.
    """

    # FIX P1-007: Accept both sync and async sessions for backwards compatibility
    def __init__(
        self,
        db: Union[Session, "AsyncSession"],  # type: ignore[name-defined]
        repository: Optional[QuizResponseRepository] = None,
    ):
        self.db = db
        self.repository = repository or QuizResponseRepository(db)
        self._logger = logging.getLogger(__name__)

    @with_db_retry(max_retries=3)
    def create_response(self, data: QuizResponseCreate) -> QuizResponseResponse:
        """Create quiz response."""
        response = QuizResponse(**data.dict())
        created = self.repository.create(response)
        self.db.flush()
        return QuizResponseResponse.from_orm(created)

    def get_session_responses(
        self, session_id: UUID
    ) -> list[QuizResponse]:
        """
        Get all responses for a quiz session.

        Args:
            session_id: Session identifier.

        Returns:
            List of quiz responses for the session.
        """
        responses = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.session_id == session_id)
            .order_by(QuizResponse.question_order)
            .all()
        )
        return responses

    def get_patient_responses(
        self, patient_id: UUID, limit: int = 100
    ) -> list[QuizResponse]:
        """
        Get recent responses for a patient across all sessions.

        Args:
            patient_id: Patient identifier.
            limit: Maximum number of responses to return.

        Returns:
            List of quiz responses.
        """
        responses = (
            self.db.query(QuizResponse)
            .join(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .order_by(QuizResponse.answered_at.desc())
            .limit(limit)
            .all()
        )
        return responses


class MonthlyQuizService:
    """
    Service for monthly quiz management.

    Handles creation and management of monthly quiz sessions
    with automatic expiration.

    Attributes:
        db: Database session.
        quiz_service: Core quiz service.
    """

    # FIX P1-007: Accept both sync and async sessions for backwards compatibility
    def __init__(
        self,
        db: Union[Session, "AsyncSession"],  # type: ignore[name-defined]
        quiz_service: Optional[QuizService] = None,
    ):
        self.db = db
        self.quiz_service = quiz_service or QuizService(db)
        self._logger = logging.getLogger(__name__)

    def create_monthly_quiz(
        self, patient_id: UUID, template_id: UUID
    ) -> QuizSessionResponse:
        """Create monthly quiz session for patient."""
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            template_id=template_id,
            session_type="monthly",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        return self.quiz_service.session_service.create_session(session_data)


def get_quiz_service(db: Any) -> QuizService:
    """Get QuizService instance."""
    return QuizService(db)


def get_monthly_quiz_service(db: Any) -> MonthlyQuizService:
    """Get MonthlyQuizService instance."""
    return MonthlyQuizService(db)
