"""
Comprehensive unit tests for quiz service functionality.

Tests the core QuizService and its component services:
- QuizTemplateService - template CRUD and validation
- QuizResponseService - response handling and validation
- QuizSessionService - session management and flow control
- QuizAnalyticsService - analytics and reporting
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from typing import List, Dict, Any

from sqlalchemy.exc import IntegrityError

from app.services.quiz import (
    QuizTemplateService, QuizResponseService, QuizSessionService,
    QuizAnalyticsService, QuizService
)
from app.schemas.quiz import (
    QuizTemplateCreate, QuizTemplateUpdate, QuizTemplateResponse,
    QuizResponseCreate, QuizResponseResponse, QuizValidationResult,
    QuizSessionCreate, QuizSessionResponse, QuizAnalytics,
    QuizQuestion, QuestionType, ValidationRule, QuizOption,
    PatientQuizAnalytics
)
from app.exceptions import NotFoundError, ValidationError, ConflictError


class TestQuizTemplateService:
    """Test cases for QuizTemplateService."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session

    @pytest.fixture
    def mock_template_repository(self):
        """Mock quiz template repository."""
        repo = Mock()
        repo.create = Mock()
        repo.get = Mock()
        repo.update = Mock()
        repo.delete = Mock()
        repo.get_by_name_and_version = Mock()
        repo.get_by_name = Mock()
        repo.get_active_templates_with_count = Mock()
        repo.get_all_with_count = Mock()
        repo.get_all_versions = Mock()
        return repo

    @pytest.fixture
    def template_service(self, mock_db_session, mock_template_repository):
        """Create QuizTemplateService with mocked dependencies."""
        service = QuizTemplateService(mock_db_session)
        service.template_repository = mock_template_repository
        return service

    @pytest.fixture
    def sample_questions(self):
        """Sample quiz questions for testing."""
        return [
            QuizQuestion(
                id="mood_rating",
                text="How would you rate your mood today?",
                type=QuestionType.SCALE,
                validation_rules=[ValidationRule(type="range", min=1, max=10)],
                required=True
            ),
            QuizQuestion(
                id="symptoms",
                text="Which symptoms are you experiencing?",
                type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    QuizOption(id="nausea", value="Nausea"),
                    QuizOption(id="fatigue", value="Fatigue"),
                    QuizOption(id="none", value="None")
                ],
                required=False
            )
        ]

    def test_create_template_success(self, template_service, sample_questions):
        """Test successful template creation."""
        # Arrange
        template_data = QuizTemplateCreate(
            name="Patient Assessment",
            version="1.0",
            questions=sample_questions,
            is_active=True
        )

        mock_template = Mock()
        mock_template.id = uuid4()
        mock_template.name = template_data.name
        mock_template.version = template_data.version

        template_service.template_repository.get_by_name_and_version.return_value = None
        template_service.template_repository.create.return_value = mock_template

        # Act
        result = template_service.create_template(template_data)

        # Assert
        assert isinstance(result, QuizTemplateResponse)
        template_service.template_repository.create.assert_called_once()
        template_service.db.commit.assert_called_once()

    def test_create_template_validation_failure(self, template_service):
        """Test template creation with invalid questions."""
        # Arrange
        invalid_questions = [
            QuizQuestion(
                id="",  # Empty ID
                text="Invalid question",
                type=QuestionType.SCALE,
                required=True
            )
        ]

        template_data = QuizTemplateCreate(
            name="Invalid Template",
            version="1.0",
            questions=invalid_questions,
            is_active=True
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Template validation failed"):
            template_service.create_template(template_data)

    def test_create_template_duplicate_name_version(self, template_service, sample_questions):
        """Test template creation with duplicate name and version."""
        # Arrange
        template_data = QuizTemplateCreate(
            name="Existing Template",
            version="1.0",
            questions=sample_questions,
            is_active=True
        )

        existing_template = Mock()
        template_service.template_repository.get_by_name_and_version.return_value = existing_template

        # Act & Assert
        with pytest.raises(ConflictError, match="already exists"):
            template_service.create_template(template_data)

    def test_get_template_success(self, template_service):
        """Test successful template retrieval."""
        # Arrange
        template_id = uuid4()
        mock_template = Mock()
        mock_template.id = template_id
        mock_template.name = "Test Template"

        template_service.template_repository.get.return_value = mock_template

        # Act
        result = template_service.get_template(template_id)

        # Assert
        assert isinstance(result, QuizTemplateResponse)
        template_service.template_repository.get.assert_called_once_with(template_id)

    def test_get_template_not_found(self, template_service):
        """Test template retrieval when template doesn't exist."""
        # Arrange
        template_id = uuid4()
        template_service.template_repository.get.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError, match="not found"):
            template_service.get_template(template_id)

    def test_update_template_success(self, template_service, sample_questions):
        """Test successful template update."""
        # Arrange
        template_id = uuid4()
        update_data = QuizTemplateUpdate(
            name="Updated Template",
            questions=sample_questions
        )

        mock_template = Mock()
        mock_template.id = template_id
        template_service.template_repository.get.return_value = mock_template
        template_service.template_repository.update.return_value = mock_template

        # Act
        result = template_service.update_template(template_id, update_data)

        # Assert
        assert isinstance(result, QuizTemplateResponse)
        template_service.template_repository.update.assert_called_once()
        template_service.db.commit.assert_called_once()

    def test_delete_template_soft_delete(self, template_service):
        """Test template soft deletion."""
        # Arrange
        template_id = uuid4()
        mock_template = Mock()
        mock_template.id = template_id
        template_service.template_repository.get.return_value = mock_template
        template_service.template_repository.update.return_value = mock_template

        # Act
        result = template_service.delete_template(template_id)

        # Assert
        assert result is True
        template_service.template_repository.update.assert_called_once()
        # Verify it was called with is_active=False
        call_args = template_service.template_repository.update.call_args
        assert call_args[0][1]["is_active"] is False

    def test_validate_template_success(self, template_service, sample_questions):
        """Test successful template validation."""
        # Act
        result = template_service.validate_template(sample_questions)

        # Assert
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_template_no_questions(self, template_service):
        """Test template validation with no questions."""
        # Act
        result = template_service.validate_template([])

        # Assert
        assert result.is_valid is False
        assert "at least one question" in result.errors[0]

    def test_validate_template_duplicate_question_ids(self, template_service):
        """Test template validation with duplicate question IDs."""
        # Arrange
        duplicate_questions = [
            QuizQuestion(
                id="duplicate_id",
                text="Question 1",
                type=QuestionType.YES_NO,
                required=True
            ),
            QuizQuestion(
                id="duplicate_id",  # Same ID
                text="Question 2",
                type=QuestionType.YES_NO,
                required=True
            )
        ]

        # Act
        result = template_service.validate_template(duplicate_questions)

        # Assert
        assert result.is_valid is False
        assert "Duplicate question ID" in result.errors[0]

    def test_get_templates_with_pagination(self, template_service):
        """Test getting templates with pagination."""
        # Arrange
        mock_templates = [Mock(), Mock(), Mock()]
        template_service.template_repository.get_active_templates_with_count.return_value = (
            mock_templates, 3
        )

        # Act
        templates, total = template_service.get_templates(skip=0, limit=10, active_only=True)

        # Assert
        assert len(templates) == 3
        assert total == 3
        template_service.template_repository.get_active_templates_with_count.assert_called_once_with(
            skip=0, limit=10
        )

    def test_create_template_version_success(self, template_service):
        """Test creating a new version of existing template."""
        # Arrange
        template_id = uuid4()
        new_version = "2.0"

        original_template = Mock()
        original_template.name = "Original Template"
        original_template.questions = [{"id": "q1", "text": "Test"}]

        template_service.template_repository.get.return_value = original_template
        template_service.template_repository.get_by_name_and_version.return_value = None
        template_service.template_repository.create.return_value = Mock(id=uuid4())

        # Act
        result = template_service.create_template_version(template_id, new_version)

        # Assert
        assert isinstance(result, QuizTemplateResponse)
        template_service.template_repository.create.assert_called_once()


class TestQuizResponseService:
    """Test cases for QuizResponseService."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session

    @pytest.fixture
    def mock_repositories(self):
        """Mock repositories for response service."""
        response_repo = Mock()
        template_repo = Mock()
        session_repo = Mock()
        return response_repo, template_repo, session_repo

    @pytest.fixture
    def response_service(self, mock_db_session, mock_repositories):
        """Create QuizResponseService with mocked dependencies."""
        response_repo, template_repo, session_repo = mock_repositories
        service = QuizResponseService(mock_db_session)
        service.response_repository = response_repo
        service.template_repository = template_repo
        service.session_repository = session_repo
        return service

    @pytest.fixture
    def mock_template(self):
        """Mock quiz template."""
        template = Mock()
        template.id = uuid4()
        template.is_active = True
        template.questions = [
            {
                "id": "test_question",
                "text": "Test question?",
                "type": "single_choice",
                "options": [
                    {"id": "option1", "value": "Option 1"},
                    {"id": "option2", "value": "Option 2"}
                ],
                "validation_rules": []
            }
        ]
        return template

    @pytest.mark.asyncio
    async def test_create_response_success(self, response_service, mock_template):
        """Test successful response creation."""
        # Arrange
        response_data = QuizResponseCreate(
            patient_id=uuid4(),
            quiz_template_id=mock_template.id,
            question_id="test_question",
            response_type=QuestionType.SINGLE_CHOICE,
            response_value="option1"
        )

        response_service.template_repository.get.return_value = mock_template
        response_service.session_repository.get_active_session.return_value = None

        mock_response = Mock()
        mock_response.id = uuid4()
        response_service.response_repository.create.return_value = mock_response

        # Act
        result = await response_service.create_response(response_data)

        # Assert
        assert isinstance(result, QuizResponseResponse)
        response_service.response_repository.create.assert_called_once()
        response_service.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_response_template_not_found(self, response_service):
        """Test response creation with non-existent template."""
        # Arrange
        response_data = QuizResponseCreate(
            patient_id=uuid4(),
            quiz_template_id=uuid4(),
            question_id="test_question",
            response_type=QuestionType.SINGLE_CHOICE,
            response_value="option1"
        )

        response_service.template_repository.get.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError, match="template.*not found"):
            await response_service.create_response(response_data)

    @pytest.mark.asyncio
    async def test_create_response_inactive_template(self, response_service, mock_template):
        """Test response creation with inactive template."""
        # Arrange
        mock_template.is_active = False
        response_data = QuizResponseCreate(
            patient_id=uuid4(),
            quiz_template_id=mock_template.id,
            question_id="test_question",
            response_type=QuestionType.SINGLE_CHOICE,
            response_value="option1"
        )

        response_service.template_repository.get.return_value = mock_template

        # Act & Assert
        with pytest.raises(ValidationError, match="inactive template"):
            await response_service.create_response(response_data)

    @pytest.mark.asyncio
    async def test_create_response_question_not_found(self, response_service, mock_template):
        """Test response creation with non-existent question."""
        # Arrange
        response_data = QuizResponseCreate(
            patient_id=uuid4(),
            quiz_template_id=mock_template.id,
            question_id="nonexistent_question",
            response_type=QuestionType.SINGLE_CHOICE,
            response_value="option1"
        )

        response_service.template_repository.get.return_value = mock_template

        # Act & Assert
        with pytest.raises(ValidationError, match="Question.*not found"):
            await response_service.create_response(response_data)

    def test_validate_response_by_type_multiple_choice(self, response_service):
        """Test response validation for multiple choice questions."""
        # Arrange
        question_type = "multiple_choice"
        response_value = ["option1", "option2"]
        options = [
            {"id": "option1", "value": "Option 1"},
            {"id": "option2", "value": "Option 2"},
            {"id": "option3", "value": "Option 3"}
        ]
        validation_rules = []

        # Act
        errors = response_service._validate_response_by_type(
            question_type, response_value, options, validation_rules
        )

        # Assert
        assert len(errors) == 0

    def test_validate_response_by_type_invalid_option(self, response_service):
        """Test response validation with invalid option."""
        # Arrange
        question_type = "single_choice"
        response_value = "invalid_option"
        options = [
            {"id": "option1", "value": "Option 1"},
            {"id": "option2", "value": "Option 2"}
        ]
        validation_rules = []

        # Act
        errors = response_service._validate_response_by_type(
            question_type, response_value, options, validation_rules
        )

        # Assert
        assert len(errors) > 0
        assert "Invalid option" in errors[0]

    def test_validate_response_scale_out_of_range(self, response_service):
        """Test scale response validation with out of range value."""
        # Arrange
        question_type = "scale"
        response_value = "15"  # Out of range
        options = []
        validation_rules = [{"type": "range", "min": 1, "max": 10}]

        # Act
        errors = response_service._validate_response_by_type(
            question_type, response_value, options, validation_rules
        )

        # Assert
        assert len(errors) > 0
        assert "between 1 and 10" in errors[0]

    def test_get_patient_responses(self, response_service):
        """Test getting responses for a patient."""
        # Arrange
        patient_id = uuid4()
        mock_responses = [Mock(), Mock()]
        response_service.response_repository.get_by_patient_with_count.return_value = (
            mock_responses, 2
        )

        # Act
        responses, total = response_service.get_patient_responses(patient_id, skip=0, limit=10)

        # Assert
        assert len(responses) == 2
        assert total == 2
        response_service.response_repository.get_by_patient_with_count.assert_called_once_with(
            patient_id, skip=0, limit=10
        )


class TestQuizSessionService:
    """Test cases for QuizSessionService."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.begin = Mock()
        session.execute = Mock()
        session.flush = Mock()
        session.refresh = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def mock_repositories(self):
        """Mock repositories for session service."""
        session_repo = Mock()
        template_repo = Mock()
        response_repo = Mock()
        return session_repo, template_repo, response_repo

    @pytest.fixture
    def session_service(self, mock_db_session, mock_repositories):
        """Create QuizSessionService with mocked dependencies."""
        session_repo, template_repo, response_repo = mock_repositories
        service = QuizSessionService(mock_db_session)
        service.session_repository = session_repo
        service.template_repository = template_repo
        service.response_repository = response_repo
        return service

    @pytest.fixture
    def mock_template(self):
        """Mock quiz template."""
        template = Mock()
        template.id = uuid4()
        template.is_active = True
        template.questions = [
            {"id": "q1", "text": "Question 1"},
            {"id": "q2", "text": "Question 2"},
            {"id": "q3", "text": "Question 3"}
        ]
        return template

    @pytest.mark.asyncio
    async def test_start_quiz_session_success(self, session_service, mock_template):
        """Test successful quiz session start."""
        # Arrange
        session_data = QuizSessionCreate(
            patient_id=uuid4(),
            quiz_template_id=mock_template.id
        )

        session_service.template_repository.get.return_value = mock_template
        session_service.db.begin.return_value.__enter__ = Mock()
        session_service.db.begin.return_value.__exit__ = Mock(return_value=None)
        session_service.db.execute.return_value.fetchone.return_value = None

        mock_session = Mock()
        mock_session.id = uuid4()
        session_service.session_repository.create.return_value = mock_session

        # Act
        with patch('app.services.websocket_events.websocket_events', None):
            result = await session_service.start_quiz_session(session_data)

        # Assert
        assert isinstance(result, QuizSessionResponse)
        session_service.session_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_quiz_session_template_not_found(self, session_service):
        """Test session start with non-existent template."""
        # Arrange
        session_data = QuizSessionCreate(
            patient_id=uuid4(),
            quiz_template_id=uuid4()
        )

        session_service.db.begin.return_value.__enter__ = Mock()
        session_service.db.begin.return_value.__exit__ = Mock(return_value=None)
        session_service.template_repository.get.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError, match="template.*not found"):
            await session_service.start_quiz_session(session_data)

    @pytest.mark.asyncio
    async def test_start_quiz_session_inactive_template(self, session_service, mock_template):
        """Test session start with inactive template."""
        # Arrange
        mock_template.is_active = False
        session_data = QuizSessionCreate(
            patient_id=uuid4(),
            quiz_template_id=mock_template.id
        )

        session_service.db.begin.return_value.__enter__ = Mock()
        session_service.db.begin.return_value.__exit__ = Mock(return_value=None)
        session_service.template_repository.get.return_value = mock_template

        # Act & Assert
        with pytest.raises(ValidationError, match="inactive template"):
            await session_service.start_quiz_session(session_data)

    def test_get_active_session(self, session_service):
        """Test getting active session for a patient."""
        # Arrange
        patient_id = uuid4()
        mock_session = Mock()
        mock_session.id = uuid4()

        session_service.db.query.return_value.options.return_value.filter.return_value.order_by.return_value.first.return_value = mock_session

        # Act
        result = session_service.get_active_session(patient_id)

        # Assert
        assert isinstance(result, QuizSessionResponse)

    def test_advance_session_success(self, session_service, mock_template):
        """Test advancing session to next question."""
        # Arrange
        session_id = uuid4()
        mock_session = Mock()
        mock_session.id = session_id
        mock_session.status = "started"
        mock_session.current_question = 0
        mock_session.quiz_template = mock_template

        session_service.db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_session
        session_service.session_repository.update.return_value = mock_session

        # Act
        result = session_service.advance_session(session_id)

        # Assert
        assert isinstance(result, QuizSessionResponse)
        session_service.session_repository.update.assert_called_once()

    def test_advance_session_completed(self, session_service, mock_template):
        """Test advancing session when all questions are completed."""
        # Arrange
        session_id = uuid4()
        mock_session = Mock()
        mock_session.id = session_id
        mock_session.status = "started"
        mock_session.current_question = 2  # Last question (0-indexed)
        mock_session.quiz_template = mock_template

        session_service.db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_session
        session_service.session_repository.update.return_value = mock_session

        # Act
        result = session_service.advance_session(session_id)

        # Assert
        assert isinstance(result, QuizSessionResponse)
        # Should mark session as completed when advancing past last question

    @pytest.mark.asyncio
    async def test_complete_session_success(self, session_service):
        """Test completing a quiz session."""
        # Arrange
        session_id = uuid4()
        mock_session = Mock()
        mock_session.id = session_id
        mock_session.status = "started"
        mock_session.patient_id = uuid4()
        mock_session.quiz_template_id = uuid4()

        session_service.db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_session
        session_service.session_repository.update.return_value = mock_session

        # Act
        with patch('app.services.websocket_events.websocket_events', None):
            with patch('app.services.quiz_metrics.get_quiz_metrics_collector', AsyncMock()):
                result = await session_service.complete_session(session_id)

        # Assert
        assert isinstance(result, QuizSessionResponse)
        session_service.session_repository.update.assert_called_once()


class TestQuizAnalyticsService:
    """Test cases for QuizAnalyticsService."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def mock_repositories(self):
        """Mock repositories for analytics service."""
        template_repo = Mock()
        response_repo = Mock()
        session_repo = Mock()
        return template_repo, response_repo, session_repo

    @pytest.fixture
    def analytics_service(self, mock_db_session, mock_repositories):
        """Create QuizAnalyticsService with mocked dependencies."""
        template_repo, response_repo, session_repo = mock_repositories
        service = QuizAnalyticsService(mock_db_session)
        service.template_repository = template_repo
        service.response_repository = response_repo
        service.session_repository = session_repo
        return service

    def test_get_patient_analytics(self, analytics_service):
        """Test getting analytics for a patient."""
        # Arrange
        patient_id = uuid4()
        mock_responses = [Mock(), Mock(), Mock()]
        mock_sessions = [Mock(), Mock()]

        for session in mock_sessions:
            session.status = "completed"

        analytics_service.response_repository.get_by_patient.return_value = mock_responses
        analytics_service.session_repository.get_patient_sessions.return_value = mock_sessions

        # Act
        result = analytics_service.get_patient_analytics(patient_id)

        # Assert
        assert isinstance(result, PatientQuizAnalytics)
        assert result.patient_id == patient_id
        assert result.total_quizzes_completed == 2
        assert result.completion_rate == 100.0

    def test_get_template_analytics(self, analytics_service):
        """Test getting analytics for a quiz template."""
        # Arrange
        template_id = uuid4()

        mock_template = Mock()
        mock_template.id = template_id
        mock_template.questions = [
            {"id": "q1", "text": "Question 1"},
            {"id": "q2", "text": "Question 2"}
        ]

        mock_responses = [Mock(), Mock(), Mock()]
        mock_sessions = [Mock(), Mock()]

        # Set up sessions with completion data
        for i, session in enumerate(mock_sessions):
            session.status = "completed"
            session.started_at = datetime.utcnow() - timedelta(minutes=20)
            session.completed_at = datetime.utcnow() - timedelta(minutes=5)

        analytics_service.template_repository.get.return_value = mock_template
        analytics_service.response_repository.get_by_quiz_template.return_value = mock_responses
        analytics_service.session_repository.get_template_sessions.return_value = mock_sessions

        # Mock the SQL query for question stats
        analytics_service.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("q1", "answer1", 2),
            ("q1", "answer2", 1),
            ("q2", "answer1", 3)
        ]

        # Act
        result = analytics_service.get_template_analytics(template_id)

        # Assert
        assert isinstance(result, QuizAnalytics)
        assert result.quiz_template_id == template_id
        assert result.total_responses == 3
        assert result.completion_rate == 100.0
        assert result.average_completion_time == 15.0  # 15 minutes average

    def test_get_template_analytics_not_found(self, analytics_service):
        """Test analytics for non-existent template."""
        # Arrange
        template_id = uuid4()
        analytics_service.template_repository.get.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError, match="template.*not found"):
            analytics_service.get_template_analytics(template_id)


class TestUnifiedQuizService:
    """Test cases for the unified QuizService."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def unified_quiz_service(self, mock_db_session):
        """Create unified QuizService with mocked dependencies."""
        with patch('app.services.quiz.QuizTemplateService') as mock_template_service, \
             patch('app.services.quiz.QuizResponseService') as mock_response_service, \
             patch('app.services.quiz.QuizSessionService') as mock_session_service, \
             patch('app.services.quiz.QuizAnalyticsService') as mock_analytics_service:

            service = QuizService(mock_db_session)
            return service

    def test_unified_service_initialization(self, unified_quiz_service):
        """Test that unified service initializes all component services."""
        assert hasattr(unified_quiz_service, 'template_service')
        assert hasattr(unified_quiz_service, 'response_service')
        assert hasattr(unified_quiz_service, 'session_service')
        assert hasattr(unified_quiz_service, 'analytics_service')

    def test_unified_service_delegates_template_methods(self, unified_quiz_service):
        """Test that unified service delegates template methods."""
        # Test delegation of template methods
        template_id = uuid4()

        # Test get_template delegation
        unified_quiz_service.get_template(template_id)
        unified_quiz_service.template_service.get_template.assert_called_once_with(template_id)

        # Test create_template delegation
        template_data = Mock()
        unified_quiz_service.create_template(template_data)
        unified_quiz_service.template_service.create_template.assert_called_once_with(template_data)

    def test_unified_service_delegates_session_methods(self, unified_quiz_service):
        """Test that unified service delegates session methods."""
        # Test session method delegation
        session_id = uuid4()
        patient_id = uuid4()

        # Test get_session delegation
        unified_quiz_service.get_session(session_id)
        unified_quiz_service.session_service.get_session.assert_called_once_with(session_id)

        # Test get_patient_sessions delegation
        unified_quiz_service.get_patient_sessions(patient_id, skip=0, limit=10)
        unified_quiz_service.session_service.get_patient_sessions.assert_called_once_with(
            patient_id, skip=0, limit=10
        )

    def test_unified_service_delegates_analytics_methods(self, unified_quiz_service):
        """Test that unified service delegates analytics methods."""
        # Test analytics method delegation
        template_id = uuid4()
        patient_id = uuid4()

        # Test get_template_analytics delegation
        unified_quiz_service.get_template_analytics(template_id)
        unified_quiz_service.analytics_service.get_template_analytics.assert_called_once_with(
            template_id, start_date=None, end_date=None
        )

        # Test get_patient_analytics delegation
        unified_quiz_service.get_patient_analytics(patient_id)
        unified_quiz_service.analytics_service.get_patient_analytics.assert_called_once_with(
            patient_id, start_date=None, end_date=None
        )


@pytest.mark.performance
class TestQuizServicePerformance:
    """Performance tests for quiz services."""

    def test_template_validation_performance(self, performance_timer):
        """Test performance of template validation with many questions."""
        # Arrange
        large_question_list = []
        for i in range(100):
            large_question_list.append(
                QuizQuestion(
                    id=f"question_{i}",
                    text=f"Question {i}?",
                    type=QuestionType.SCALE,
                    validation_rules=[ValidationRule(type="range", min=1, max=10)],
                    required=True
                )
            )

        template_service = QuizTemplateService(Mock())

        # Act
        performance_timer.start()
        result = template_service.validate_template(large_question_list)
        execution_time = performance_timer.stop()

        # Assert
        assert execution_time < 1.0  # Should validate 100 questions in under 1 second
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_bulk_response_creation_performance(self, performance_timer):
        """Test performance of creating many responses."""
        # This would test bulk response creation performance
        # For now, we'll test the structure for such a test

        response_service = QuizResponseService(Mock())
        response_service.template_repository.get.return_value = Mock(
            is_active=True,
            questions=[{"id": "q1", "type": "yes_no", "options": [], "validation_rules": []}]
        )
        response_service.session_repository.get_active_session.return_value = None
        response_service.response_repository.create.return_value = Mock(id=uuid4())
        response_service.db.commit = Mock()

        # Simulate creating many responses
        performance_timer.start()

        for _ in range(50):  # Create 50 responses
            response_data = QuizResponseCreate(
                patient_id=uuid4(),
                quiz_template_id=uuid4(),
                question_id="q1",
                response_type=QuestionType.YES_NO,
                response_value="yes"
            )
            await response_service.create_response(response_data)

        execution_time = performance_timer.stop()

        # Assert
        assert execution_time < 5.0  # Should create 50 responses in under 5 seconds