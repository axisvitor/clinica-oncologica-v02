from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.quiz import QuizTemplate, QuizResponse, QuizSession
from app.repositories.base import BaseRepository


class QuizRepository(BaseRepository[QuizSession]):
    """Repository for QuizSession model (main quiz repository)"""

    def __init__(self, db: Session):
        super().__init__(db, QuizSession)

    def get_by_patient(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> List[QuizSession]:
        """Get quiz sessions by patient"""
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .order_by(QuizSession.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_sessions(self) -> List[QuizSession]:
        """Get active quiz sessions"""
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.status == 'in_progress')
            .all()
        )


class QuizTemplateRepository(BaseRepository[QuizTemplate]):
    """Repository for QuizTemplate model"""
    
    def __init__(self, db: Session):
        super().__init__(db, QuizTemplate)
    
    def get_active_templates(self, skip: int = 0, limit: int = 100) -> List[QuizTemplate]:
        """Get active quiz templates"""
        return (
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.is_active == True)
            .order_by(QuizTemplate.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_active_templates_with_count(self, skip: int = 0, limit: int = 100) -> tuple[List[QuizTemplate], int]:
        """Get active quiz templates with total count"""
        query = (
            self.db.query(QuizTemplate)
            .filter(QuizTemplate.is_active == True)
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
            .filter(QuizTemplate.is_active == True)
            .order_by(QuizTemplate.created_at.desc())
            .first()
        )
    
    def get_by_name_and_version(self, name: str, version: str) -> Optional[QuizTemplate]:
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
    
    def get_by_patient(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> List[QuizResponse]:
        """Get quiz responses by patient"""
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .order_by(QuizResponse.responded_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_patient_with_count(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> tuple[List[QuizResponse], int]:
        """Get quiz responses by patient with total count"""
        query = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .order_by(QuizResponse.responded_at.desc())
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total
    
    def get_by_quiz_template(self, quiz_template_id: UUID, skip: int = 0, limit: int = 100) -> List[QuizResponse]:
        """Get responses by quiz template"""
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.quiz_template_id == quiz_template_id)
            .order_by(QuizResponse.responded_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_by_quiz_template_with_count(self, quiz_template_id: UUID, skip: int = 0, limit: int = 100) -> tuple[List[QuizResponse], int]:
        """Get responses by quiz template with total count"""
        query = (
            self.db.query(QuizResponse)
            .filter(QuizResponse.quiz_template_id == quiz_template_id)
            .order_by(QuizResponse.responded_at.desc())
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total
    
    def get_patient_quiz_responses(self, patient_id: UUID, quiz_template_id: UUID) -> List[QuizResponse]:
        """Get all responses from a patient for a specific quiz"""
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .filter(QuizResponse.quiz_template_id == quiz_template_id)
            .order_by(QuizResponse.responded_at.asc())
            .all()
        )
    
    def get_by_patient_since(self, patient_id: UUID, since_date: datetime) -> List[QuizResponse]:
        """Get quiz responses by patient since a specific date"""
        return (
            self.db.query(QuizResponse)
            .filter(QuizResponse.patient_id == patient_id)
            .filter(QuizResponse.responded_at >= since_date)
            .order_by(QuizResponse.responded_at.desc())
            .all()
        )


class QuizSessionRepository(BaseRepository[QuizSession]):
    """Repository for QuizSession model"""
    
    def __init__(self, db: Session):
        super().__init__(db, QuizSession)
    
    def get_active_session(self, patient_id: UUID) -> Optional[QuizSession]:
        """Get active quiz session for a patient"""
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .filter(QuizSession.status == 'in_progress')  # FIX: Use status field instead of is_completed
            .order_by(QuizSession.started_at.desc())
            .first()
        )
    
    def get_patient_sessions(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> List[QuizSession]:
        """Get quiz sessions for a patient"""
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .order_by(QuizSession.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_patient_sessions_with_count(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> tuple[List[QuizSession], int]:
        """Get quiz sessions for a patient with total count"""
        query = (
            self.db.query(QuizSession)
            .filter(QuizSession.patient_id == patient_id)
            .order_by(QuizSession.started_at.desc())
        )
        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, total
    
    def get_template_sessions(self, template_id: UUID, skip: int = 0, limit: int = 100) -> List[QuizSession]:
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
        if session and session.status != 'completed':  # FIX: Check status instead of is_completed
            session.status = 'completed'  # FIX: Set status to completed
            session.completed_at = datetime.utcnow()
            self.db.commit()
        return session
    
    def get_expired_incomplete_sessions(self, cutoff_time: datetime) -> List[QuizSession]:
        """Get incomplete sessions older than cutoff time"""
        return (
            self.db.query(QuizSession)
            .filter(QuizSession.status == 'in_progress')  # FIX: Use status field
            .filter(QuizSession.started_at < cutoff_time)
            .all()
        )


class QuizRepository:
    """Unified repository for all quiz-related operations"""

    def __init__(self, db: Session):
        self.db = db
        self.templates = QuizTemplateRepository(db)
        self.responses = QuizResponseRepository(db)
        self.sessions = QuizSessionRepository(db)