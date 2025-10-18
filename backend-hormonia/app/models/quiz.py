"""
Quiz and assessment models.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, Numeric, Index, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates

from app.models.base import BaseModel


class QuizTemplate(BaseModel):
    """Quiz template for medical assessments."""
    __tablename__ = "quiz_templates"

    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    questions = Column(JSONB, nullable=False)  # Array of questions
    is_active = Column(Boolean, default=True, nullable=False)
    # Align to DB extras
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    passing_score = Column(Integer, nullable=True)
    time_limit_minutes = Column(Integer, nullable=True)
    randomize_questions = Column(Boolean, nullable=True)
    tags = Column(JSONB, nullable=True)  # stored as array in DB

    # Relationships
    responses = relationship("QuizResponse", back_populates="quiz_template")
    sessions = relationship("QuizSession", back_populates="quiz_template")

    # Database constraints
    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_quiz_template_name_version'),
        CheckConstraint('LENGTH(name) >= 1', name='ck_quiz_template_name_not_empty'),
        CheckConstraint('LENGTH(version) >= 1', name='ck_quiz_template_version_not_empty'),
        CheckConstraint('questions IS NOT NULL', name='ck_quiz_template_questions_not_null'),
        Index('idx_quiz_templates_category', 'category'),
        Index('idx_quiz_templates_is_active', 'is_active'),
    )

    @validates('name')
    def validate_name(self, key, name):
        if not name or len(name.strip()) < 1:
            raise ValueError("Template name cannot be empty")
        return name.strip()

    @validates('version')
    def validate_version(self, key, version):
        if not version or len(version.strip()) < 1:
            raise ValueError("Template version cannot be empty")
        return version.strip()

    @validates('questions')
    def validate_questions(self, key, questions):
        if not questions or not isinstance(questions, (list, dict)):
            raise ValueError("Questions must be a valid JSON structure")
        return questions
    
    def __repr__(self):
        return f"<QuizTemplate(name='{self.name}', version='{self.version}')>"


class QuizSession(BaseModel):
    """Quiz session tracking for patients."""
    __tablename__ = "quiz_sessions"

    # References
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    quiz_template_id = Column(UUID(as_uuid=True), ForeignKey("quiz_templates.id", ondelete="RESTRICT"), nullable=False)

    # Session state - FIX: Match actual database schema
    status = Column(String(50), nullable=False, default="started")  # started, completed, cancelled
    current_question = Column(Integer, nullable=True, default=0)  # FIX: Renamed from current_question_index
    total_questions = Column(Integer, nullable=True)
    answered_questions = Column(Integer, nullable=True, default=0)

    # Scores - DECIMAL (align with DB)
    score = Column(Numeric(5, 2), nullable=True)
    max_score = Column(Numeric(5, 2), nullable=True)
    passed = Column(Boolean, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)

    # Session metadata for tracking additional info
    session_metadata = Column(JSONB, nullable=True, default=dict)

    # Relationships
    patient = relationship("Patient", back_populates="quiz_sessions")
    quiz_template = relationship("QuizTemplate", back_populates="sessions")
    responses = relationship("QuizResponse", back_populates="quiz_session")
    # Note: alerts relationship removed since quiz_session_id is stored in Alert.data JSONB field

    # Database constraints and indexes - FIX: Match actual database schema
    __table_args__ = (
        # Check constraints for data integrity
        CheckConstraint('current_question >= 0', name='ck_quiz_session_question_positive'),
        CheckConstraint('score >= 0', name='ck_quiz_session_score_positive'),
        CheckConstraint(
            "status IN ('started', 'completed', 'cancelled')",
            name='ck_quiz_session_status_valid'
        ),
        # NOTE: Removed NOW() constraint for SQLite compatibility
        # PostgreSQL version: 'started_at <= COALESCE(completed_at, NOW())'
        # This constraint is enforced in PostgreSQL production database only
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR (status != 'completed')",
            name='ck_quiz_session_completed_timing'
        ),
        # Performance indexes
        Index('idx_quiz_sessions_patient_id_v2', 'patient_id'),
        Index('idx_quiz_sessions_quiz_template_id_v2', 'quiz_template_id'),
        Index('idx_quiz_sessions_status_v2', 'status'),
        Index('idx_quiz_sessions_patient_status_v2', 'patient_id', 'status'),
        Index('idx_quiz_sessions_template_status_v2', 'quiz_template_id', 'status'),
        Index('idx_quiz_sessions_created_at_v2', 'created_at'),
        Index('idx_quiz_sessions_completed_at_v2', 'completed_at'),
    )

    @validates('status')
    def validate_status(self, key, status):
        # FIX: Match actual database status values
        valid_statuses = ['started', 'completed', 'cancelled']
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return status

    @validates('current_question')
    def validate_question_index(self, key, index):
        if index < 0:
            raise ValueError("Question index must be non-negative")
        return index

    @validates('score')
    def validate_score(self, key, score):
        if score is not None and score < 0:
            raise ValueError("Score must be non-negative")
        return score
    
    def __repr__(self):
        return f"<QuizSession(patient_id='{self.patient_id}', template_id='{self.quiz_template_id}')>"

    @property
    def current_question_index(self) -> int:
        """Backward-compatible alias for current question pointer."""
        return self.current_question or 0

    @current_question_index.setter
    def current_question_index(self, value: int) -> None:
        self.current_question = value

    @property
    def is_completed(self) -> bool:
        """Compatibility flag mapping to status column."""
        return self.status == "completed"

    @is_completed.setter
    def is_completed(self, value: bool) -> None:
        if value:
            self.status = "completed"
        elif self.status == "completed":
            self.status = "started"



# Partial unique index ensures at most one started session per patient and template.
Index(
    'idx_quiz_session_unique_active',
    QuizSession.patient_id,
    QuizSession.quiz_template_id,
    unique=True,
    postgresql_where=QuizSession.status == 'started'
)
class QuizResponse(BaseModel):
    """Patient responses to quiz questions."""
    __tablename__ = "quiz_responses"

    # References
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    quiz_template_id = Column(UUID(as_uuid=True), ForeignKey("quiz_templates.id", ondelete="RESTRICT"), nullable=False)
    quiz_session_id = Column(UUID(as_uuid=True), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=True)

    # Question details
    question_id = Column(String(100), nullable=False)
    question_text = Column(Text, nullable=False)

    # Response details
    response_type = Column(String(50), nullable=False)  # 'multiple_choice', 'open_text', 'scale'
    response_value = Column(Text, nullable=False)
    response_metadata = Column(JSONB, nullable=True, default=dict)  # Sentiment analysis, entities, etc.
    other_text = Column(Text, nullable=True)  # Custom text for 'other' option

    # Timing
    responded_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="quiz_responses")
    quiz_template = relationship("QuizTemplate", back_populates="responses")
    quiz_session = relationship("QuizSession", back_populates="responses")

    # Database constraints and indexes
    __table_args__ = (
        # Unique constraint: one response per question per session
        UniqueConstraint(
            'quiz_session_id', 'question_id',
            name='uq_quiz_response_per_question_session'
        ),
        # Check constraints
        CheckConstraint('LENGTH(question_id) >= 1', name='ck_quiz_response_question_id_not_empty'),
        CheckConstraint('LENGTH(question_text) >= 1', name='ck_quiz_response_question_text_not_empty'),
        CheckConstraint('LENGTH(response_value) >= 1', name='ck_quiz_response_value_not_empty'),
        CheckConstraint(
            "response_type IN ('multiple_choice', 'open_text', 'scale', 'boolean', 'rating', 'yes_no', 'number', 'date', 'single_choice')",
            name='ck_quiz_response_type_valid'
        ),
        # Performance indexes
        Index('idx_quiz_responses_patient_id', 'patient_id'),
        Index('idx_quiz_responses_quiz_template_id', 'quiz_template_id'),
        Index('idx_quiz_response_session_id', 'quiz_session_id'),
        Index('idx_quiz_responses_responded_at', 'responded_at'),
        Index('idx_quiz_response_analytics_covering_index', 'quiz_template_id', 'question_id', 'response_value', 'responded_at'),
        Index('idx_quiz_response_patient_template_index', 'patient_id', 'quiz_template_id', 'responded_at'),
    )

    @validates('response_type')
    def validate_response_type(self, key, response_type):
        valid_types = ['multiple_choice', 'open_text', 'scale', 'boolean', 'rating', 'yes_no', 'number', 'date', 'single_choice']
        if response_type not in valid_types:
            raise ValueError(f"Response type must be one of: {valid_types}")
        return response_type

    @validates('question_id')
    def validate_question_id(self, key, question_id):
        if not question_id or len(question_id.strip()) < 1:
            raise ValueError("Question ID cannot be empty")
        return question_id.strip()

    @validates('question_text')
    def validate_question_text(self, key, question_text):
        if not question_text or len(question_text.strip()) < 1:
            raise ValueError("Question text cannot be empty")
        return question_text.strip()

    @validates('response_value')
    def validate_response_value(self, key, response_value):
        if not response_value or len(str(response_value).strip()) < 1:
            raise ValueError("Response value cannot be empty")
        return str(response_value).strip()
    
    def __repr__(self):
        return f"<QuizResponse(patient_id='{self.patient_id}', question_id='{self.question_id}')>"
