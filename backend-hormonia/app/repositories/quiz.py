
from __future__ import annotations
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.quiz import QuizTemplate, QuizResponse, QuizSession
from app.repositories.base import BaseRepository
from app.utils.query_cache import cached_query


class QuizRepository(BaseRepository[QuizSession]):
    """Repository for QuizSession model (main quiz repository)"""

    def __init__(self, db: Session):
        super().__init__(db, QuizSession)

    @cached_query("quiz_sessions_by_patient", ttl=300, tags=["quizzes"])
    def get_by_patient(
        self, patient_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[QuizSession]:
        """
        Get quiz sessions by patient with eager loading and caching (5min TTL).

        PERFORMANCE OPTIMIZATION:
        - Eager loading prevents N+1 queries
        - Redis caching reduces DB load
        - Cache invalidated on quiz mutations

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - quiz_template: Quiz template used (joinedload - 1:1)

        Args:
            patient_id: UUID of the patient
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of quiz sessions with relationships pre-loaded
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .order_by(QuizSession.created_at.desc())
        )

        if eager_load:
            query = query.options(
                joinedload(QuizSession.patient), joinedload(QuizSession.quiz_template)
            )

        return query.offset(skip).limit(limit).all()

    def get_active_sessions(self, eager_load: bool = True) -> List[QuizSession]:
        """
        Get active quiz sessions with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - quiz_template: Quiz template used (joinedload - 1:1)
        - responses: Quiz responses in session (selectinload - 1:many)

        Args:
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of active quiz sessions with relationships pre-loaded
        """
        from sqlalchemy.orm import joinedload, selectinload

        query = self.db.query(QuizSession).filter(QuizSession.status == "in_progress")

        if eager_load:
            # PERFORMANCE: Load patient, template, and responses to prevent N+1 queries
            query = query.options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template),
                selectinload(QuizSession.responses),
            )

        return query.all()


class QuizTemplateRepository(BaseRepository[QuizTemplate]):
    """Repository for QuizTemplate model"""

    def __init__(self, db: Session):
        super().__init__(db, QuizTemplate)

    @cached_query("active_quiz_templates", ttl=600)
    def get_active_templates(
        self, skip: int = 0, limit: int = 100
    ) -> List[QuizTemplate]:
        """
        Get active quiz templates with caching (10min TTL).

        PERFORMANCE: Cached for 10 minutes as templates change infrequently.
        """
        return (
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.is_active)
            .order_by(QuizTemplate.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_templates_with_count(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[List[QuizTemplate], int]:
        """Get active quiz templates with total count"""
        query = (
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.is_active)
            .order_by(QuizTemplate.created_at.desc())
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def get_by_name(self, name: str) -> Optional[QuizTemplate]:
        """Get quiz template by name (latest version)"""
        return (
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.name == name)
            .filter(QuizTemplate.is_active)
            .order_by(QuizTemplate.created_at.desc())
            .first()
        )

    def get_by_name_and_version(
        self, name: str, version: str
    ) -> Optional[QuizTemplate]:
        """Get quiz template by name and version"""
        return (
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.name == name)
            .filter(QuizTemplate.version == version)
            .first()
        )

    def get_all_versions(self, name: str) -> List[QuizTemplate]:
        """Get all versions of a template by name"""
        return (
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.name == name)
            .order_by(QuizTemplate.created_at.desc())
            .all()
        )


class QuizResponseRepository(BaseRepository[QuizResponse]):
    """Repository for QuizResponse model"""

    def __init__(self, db: Session):
        super().__init__(db, QuizResponse)

    def get_by_patient(
        self, patient_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[QuizResponse]:
        """
        Get quiz responses by patient with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - quiz_template: Quiz template used (joinedload - 1:1)

        Args:
            patient_id: UUID of the patient
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of quiz responses with relationships pre-loaded
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .order_by(QuizResponse.responded_at.desc())
        )

        if eager_load:
            query = query.options(
                joinedload(QuizResponse.patient), joinedload(QuizResponse.quiz_template)
            )

        return query.offset(skip).limit(limit).all()

    def get_by_patient_with_count(
        self, patient_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[QuizResponse], int]:
        """Get quiz responses by patient with total count"""
        query = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .order_by(QuizResponse.responded_at.desc())
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def get_by_quiz_template(
        self, quiz_template_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[QuizResponse]:
        """Get responses by quiz template"""
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.quiz_template_id == quiz_template_id)
            .order_by(QuizResponse.responded_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_quiz_template_with_count(
        self, quiz_template_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[QuizResponse], int]:
        """Get responses by quiz template with total count"""
        query = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.quiz_template_id == quiz_template_id)
            .order_by(QuizResponse.responded_at.desc())
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def get_patient_quiz_responses(
        self, patient_id: UUID, quiz_template_id: UUID
    ) -> List[QuizResponse]:
        """Get all responses from a patient for a specific quiz"""
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .filter(QuizResponse.quiz_template_id == quiz_template_id)
            .order_by(QuizResponse.responded_at.asc())
            .all()
        )

    def get_by_patient_since(
        self, patient_id: UUID, since_date: datetime
    ) -> List[QuizResponse]:
        """Get quiz responses by patient since a specific date"""
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .filter(QuizResponse.responded_at >= since_date)
            .order_by(QuizResponse.responded_at.desc())
            .all()
        )

    def get_by_session(
        self, session_id: UUID, eager_load: bool = False
    ) -> List[QuizResponse]:
        """
        Get all responses for a specific quiz session.

        Note: Eager loading is disabled by default since the session is usually
        already loaded. Enable if you need related entities.

        Args:
            session_id: UUID of the quiz session
            eager_load: Enable eager loading of related entities

        Returns:
            List of quiz responses for the session, ordered by response time
        """
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.quiz_session_id == session_id)
            .order_by(QuizResponse.responded_at.asc())
        )

        if eager_load:
            query = query.options(
                joinedload(QuizResponse.patient),
                joinedload(QuizResponse.quiz_template),
            )

        return query.all()


class QuizSessionRepository(BaseRepository[QuizSession]):
    """Repository for QuizSession model"""

    def __init__(self, db: Session):
        super().__init__(db, QuizSession)

    def get_active_session(
        self, patient_id: UUID, eager_load: bool = True
    ) -> Optional[QuizSession]:
        """
        Get active quiz session for a patient with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - quiz_template: Quiz template used (joinedload - 1:1)
        - responses: Quiz responses in session (selectinload - 1:many)

        Args:
            patient_id: UUID of the patient
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            Active quiz session or None
        """
        from sqlalchemy.orm import joinedload, selectinload

        query = (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .filter(
                QuizSession.status == "in_progress"
            )  # FIX: Use status field instead of is_completed
            .order_by(QuizSession.started_at.desc())
        )

        if eager_load:
            # PERFORMANCE: Load all related entities to prevent N+1 queries
            query = query.options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template),
                selectinload(QuizSession.responses),
            )

        return query.first()

    def get_patient_sessions(
        self, patient_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[QuizSession]:
        """
        Get quiz sessions for a patient with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)
        - quiz_template: Quiz template used (joinedload - 1:1)
        - responses: Quiz responses in session (selectinload - 1:many)

        Args:
            patient_id: UUID of the patient
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of quiz sessions with relationships pre-loaded
        """
        from sqlalchemy.orm import joinedload, selectinload

        query = (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .order_by(QuizSession.started_at.desc())
        )

        if eager_load:
            # PERFORMANCE: Load all related entities to prevent N+1 queries
            query = query.options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template),
                selectinload(QuizSession.responses),
            )

        return query.offset(skip).limit(limit).all()

    def get_patient_sessions_with_count(
        self, patient_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[List[QuizSession], int]:
        """Get quiz sessions for a patient with total count"""
        query = (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .order_by(QuizSession.started_at.desc())
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total

    def get_template_sessions(
        self, template_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[QuizSession]:
        """Get sessions for a quiz template"""
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.quiz_template_id == template_id)
            .order_by(QuizSession.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def complete_session(self, session_id: UUID) -> Optional[QuizSession]:
        """Mark a session as completed"""
        session = self.get(session_id)
        if (
            session and session.status != "completed"
        ):  # FIX: Check status instead of is_completed
            session.status = "completed"  # FIX: Set status to completed
            session.completed_at = datetime.now(timezone.utc)
            self.db.commit()
        return session

    def get_expired_incomplete_sessions(
        self, cutoff_time: datetime
    ) -> List[QuizSession]:
        """Get incomplete sessions older than cutoff time"""
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.status == "in_progress")  # FIX: Use status field
            .filter(QuizSession.started_at < cutoff_time)
            .all()
        )

    def get_patient_template_sessions(
        self, patient_id: UUID, template_id: UUID, limit: int = 5, eager_load: bool = True
    ) -> List[QuizSession]:
        """
        Get completed sessions for a patient and specific template with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default to prevent N+1 queries.

        Relationships loaded when eager_load=True:
        - responses: Quiz responses in session (selectinload - 1:many)
        - quiz_template: Quiz template used (joinedload - 1:1)

        This is used for trend analysis and comparison across historical sessions.

        Args:
            patient_id: UUID of the patient
            template_id: UUID of the quiz template
            limit: Maximum sessions to return (default: 5 for trend analysis)
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of completed quiz sessions with responses pre-loaded
        """
        from sqlalchemy.orm import joinedload, selectinload

        query = (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .filter(QuizSession.quiz_template_id == template_id)
            .filter(QuizSession.status == "completed")
            .order_by(QuizSession.completed_at.desc())
        )

        if eager_load:
            # PERFORMANCE: Eager load responses to prevent N+1 queries in trend analysis
            query = query.options(
                selectinload(QuizSession.responses),
                joinedload(QuizSession.quiz_template),
            )

        return query.limit(limit).all()


class UnifiedQuizRepository:
    """Unified repository for all quiz-related operations"""

    def __init__(self, db: Session):
        self.db = db
        self.templates = QuizTemplateRepository(db)
        self.responses = QuizResponseRepository(db)
        self.sessions = QuizSessionRepository(db)
