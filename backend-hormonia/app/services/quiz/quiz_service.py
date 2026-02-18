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
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

# Third-party imports
# FIX P1-007: Changed from AsyncSession to Session as code uses sync patterns
from sqlalchemy import or_
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
from app.utils.timezone import now_sao_paulo

if TYPE_CHECKING:
    from app.schemas.monthly_quiz import MonthlyQuizLinkCreate, MonthlyQuizLinkResponse


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
    async def get_template(self, template_id: UUID) -> QuizTemplate:
        """
        Get template by ID.

        Args:
            template_id: Template identifier.

        Returns:
            Quiz template response.

        Raises:
            NotFoundError: If template not found.
        """
        template = self.repository.get(template_id)
        if not template:
            raise NotFoundError(f"Template {template_id} not found")
        return template

    @with_db_retry(max_retries=3)
    def get_template_by_name(self, name: str) -> Optional[QuizTemplate]:
        """Get active template by name."""
        return self.repository.get_by_name(name)

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

    def _normalize_session_payload(
        self, session_data: Union[QuizSessionCreate, dict[str, Any], Any]
    ) -> dict[str, Any]:
        """
        Normalize legacy/new session payloads to QuizSession model fields.

        This removes compatibility drift between callers that still send
        `template_id`/`expires_at` and the current model fields.
        """
        if isinstance(session_data, QuizSessionCreate):
            raw_data = session_data.model_dump(exclude_none=True)
        elif isinstance(session_data, dict):
            raw_data = {k: v for k, v in session_data.items() if v is not None}
        elif hasattr(session_data, "model_dump"):
            raw_data = {
                k: v for k, v in session_data.model_dump(exclude_none=True).items()
            }
        else:
            raise TypeError("session_data must be dict-like or QuizSessionCreate")

        quiz_template_id = raw_data.get("quiz_template_id") or raw_data.get("template_id")
        if quiz_template_id is None:
            raise ValueError("quiz_template_id/template_id is required")

        now = now_sao_paulo()
        started_at = raw_data.get("started_at") or now
        expiration_date = (
            raw_data.get("expiration_date")
            or raw_data.get("expires_at")
            or (started_at + timedelta(days=7))
        )

        session_metadata = raw_data.get("session_metadata") or {}
        if not isinstance(session_metadata, dict):
            session_metadata = {}

        current_question = raw_data.get("current_question")
        if current_question is None:
            current_question = raw_data.get("current_question_index", 0)

        return {
            "patient_id": raw_data.get("patient_id"),
            "quiz_template_id": quiz_template_id,
            "status": raw_data.get("status", "started"),
            "current_question": current_question,
            "answered_questions": raw_data.get("answered_questions", 0),
            "total_questions": raw_data.get("total_questions"),
            "started_at": started_at,
            "expiration_date": expiration_date,
            "session_metadata": session_metadata,
        }

    @with_db_retry(max_retries=3)
    def create_session(self, data: QuizSessionCreate) -> QuizSessionResponse:
        """Create quiz session."""
        payload = self._normalize_session_payload(data)
        session = QuizSession(**payload)
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
        now = now_sao_paulo()
        session = (
            self.db.query(QuizSession)
            .filter(
                QuizSession.patient_id == patient_id,
                QuizSession.status == "started",
                or_(
                    QuizSession.expiration_date.is_(None),
                    QuizSession.expiration_date > now,
                ),
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
        session.completed_at = now_sao_paulo()
        if final_score is not None:
            session.final_score = final_score

        self.db.flush()
        self._logger.info(f"Session {session_id} marked as completed")
        return session

    def advance_session(self, session_id: UUID) -> Optional[QuizSession]:
        """
        Advance session to the next question in a single, consistent place.

        Args:
            session_id: Session identifier.

        Returns:
            Updated QuizSession if found, None otherwise.
        """
        session = self.repository.get(session_id)
        if not session:
            self._logger.warning(f"Session {session_id} not found for advancement")
            return None

        current_question = session.current_question or 0
        answered_questions = session.answered_questions or 0

        session.current_question = current_question + 1
        session.answered_questions = answered_questions + 1
        self.db.flush()
        return session

    def start_quiz_session(
        self, session_data: Union[QuizSessionCreate, dict[str, Any], Any]
    ) -> QuizSession:
        """
        Start a new quiz session from dictionary data.

        Args:
            session_data: Dictionary with session data.

        Returns:
            Created QuizSession.
        """
        payload = self._normalize_session_payload(session_data)
        session = QuizSession(**payload)
        self.repository.create(session)
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
            .filter(QuizResponse.quiz_session_id == session_id)
            .order_by(QuizResponse.responded_at.asc())
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
            .order_by(QuizResponse.responded_at.desc())
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
            expires_at=now_sao_paulo() + timedelta(days=7),
        )
        return self.quiz_service.session_service.create_session(session_data)

    async def create_quiz_link(self, link_data: "MonthlyQuizLinkCreate") -> "MonthlyQuizLinkResponse":
        """Create a monthly quiz link via QuizSessionManager."""
        from app.domain.quizzes.manager import QuizSessionManager

        manager = QuizSessionManager(self.db)
        return await manager.create_quiz_link(link_data)

    async def get_quiz_link_status(self, session_id: UUID) -> "MonthlyQuizLinkResponse":
        """Get quiz link status via QuizSessionManager."""
        from app.domain.quizzes.manager import QuizSessionManager

        manager = QuizSessionManager(self.db)
        return await manager.get_quiz_link_status(session_id)

    async def regenerate_link(self, session_id: UUID) -> "MonthlyQuizLinkResponse":
        """Regenerate quiz link via QuizSessionManager."""
        from app.domain.quizzes.manager import QuizSessionManager

        manager = QuizSessionManager(self.db)
        return await manager.regenerate_link(session_id)


def get_quiz_service(db: Any) -> QuizService:
    """Get QuizService instance."""
    return QuizService(db)


def get_monthly_quiz_service(db: Any) -> MonthlyQuizService:
    """Get MonthlyQuizService instance."""
    return MonthlyQuizService(db)
