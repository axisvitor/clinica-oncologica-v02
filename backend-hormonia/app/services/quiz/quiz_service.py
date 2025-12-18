"""
Quiz Service - Consolidated Quiz Management Core (QW-023).

Consolidates:
    - quiz.py (QuizTemplateService, QuizSessionService, QuizResponseService)
    - monthly_quiz_service.py (MonthlyQuizService)
    - optimized_monthly_quiz_service.py

Total: 3 files → 1 file
"""

from typing import Any
from uuid import UUID
from datetime import datetime, timedelta

from app.models.quiz import QuizTemplate, QuizSession, QuizResponse
from app.repositories.quiz import (
    QuizTemplateRepository,
    QuizSessionRepository,
    QuizResponseRepository,
)
from app.schemas.quiz import (
    QuizTemplateCreate,
    QuizTemplateResponse,
    QuizSessionCreate,
    QuizSessionResponse,
    QuizResponseCreate,
    QuizResponseResponse,
)
from app.exceptions import NotFoundError
from app.utils.db_retry import with_db_retry


class QuizService:
    """Unified quiz service for all quiz operations."""

    def __init__(self, db: Any):
        self.db = db
        self.template_service = QuizTemplateService(db)
        self.session_service = QuizSessionService(db)
        self.response_service = QuizResponseService(db)


class QuizTemplateService:
    """Service for managing quiz templates."""

    def __init__(self, db: Any):
        self.db = db
        self.repository = QuizTemplateRepository(db)

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
    def get_template(self, template_id: UUID) -> QuizTemplateResponse:
        """Get template by ID."""
        template = self.repository.get(template_id)
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
    """Service for managing quiz sessions."""

    def __init__(self, db: Any):
        self.db = db
        self.repository = QuizSessionRepository(db)

    @with_db_retry(max_retries=3)
    def create_session(self, data: QuizSessionCreate) -> QuizSessionResponse:
        """Create quiz session."""
        session = QuizSession(**data.dict())
        created = self.repository.create(session)
        self.db.commit()
        return QuizSessionResponse.from_orm(created)


class QuizResponseService:
    """Service for managing quiz responses."""

    def __init__(self, db: Any):
        self.db = db
        self.repository = QuizResponseRepository(db)

    @with_db_retry(max_retries=3)
    def create_response(self, data: QuizResponseCreate) -> QuizResponseResponse:
        """Create quiz response."""
        response = QuizResponse(**data.dict())
        created = self.repository.create(response)
        self.db.commit()
        return QuizResponseResponse.from_orm(created)


class MonthlyQuizService:
    """Service for monthly quiz management."""

    def __init__(self, db: Any):
        self.db = db
        self.quiz_service = QuizService(db)

    def create_monthly_quiz(
        self, patient_id: UUID, template_id: UUID
    ) -> QuizSessionResponse:
        """Create monthly quiz session for patient."""
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            template_id=template_id,
            session_type="monthly",
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        return self.quiz_service.session_service.create_session(session_data)


def get_quiz_service(db: Any) -> QuizService:
    """Get QuizService instance."""
    return QuizService(db)


def get_monthly_quiz_service(db: Any) -> MonthlyQuizService:
    """Get MonthlyQuizService instance."""
    return MonthlyQuizService(db)
