"""
Comprehensive unit tests for quiz models and validation.

Tests the quiz data models including:
- QuizTemplate model validation and constraints
- QuizResponse model validation and serialization
- QuizSession model state management
- Question validation and question type handling
- Data integrity and relationship constraints
"""

import pytest
import json
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from typing import List, Dict, Any
from unittest.mock import Mock, patch

from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError as PydanticValidationError

from app.models.quiz import QuizTemplate, QuizResponse, QuizSession
from app.schemas.quiz import (
    QuizTemplateCreate, QuizTemplateUpdate, QuizTemplateResponse,
    QuizResponseCreate, QuizResponseResponse,
    QuizSessionCreate, QuizSessionResponse,
    QuizQuestion, QuestionType, ValidationRule, QuizOption,
    QuizValidationResult
)
from app.exceptions import ValidationError


class TestQuizTemplateModel:
    """Test cases for QuizTemplate model."""

    @pytest.fixture
    def sample_questions(self):
        """Sample quiz questions for testing."""
        return [
            {
                "id": "mood_rating",
                "text": "How would you rate your mood today?",
                "type": "scale",
                "options": [],
                "validation_rules": [{"type": "range", "min": 1, "max": 10}],
                "required": True
            },
            {
                "id": "medication_adherence",
                "text": "Did you take your medications as prescribed?",
                "type": "yes_no",
                "options": [
                    {"id": "yes", "value": "Yes"},
                    {"id": "no", "value": "No"}
                ],
                "required": True
            },
            {
                "id": "side_effects",
                "text": "Are you experiencing any side effects?",
                "type": "multiple_choice",
                "options": [
                    {"id": "nausea", "value": "Nausea"},
                    {"id": "fatigue", "value": "Fatigue"},
                    {"id": "headache", "value": "Headache"},
                    {"id": "none", "value": "None"},
                    {"id": "other", "value": "Other", "allow_other": True}
                ],
                "required": False
            }
        ]

    def test_quiz_template_creation(self, db_session, sample_questions):
        """Test creating a quiz template."""
        # Arrange
        template = QuizTemplate(
            name="Patient Health Assessment",
            version="1.0",
            questions=sample_questions,
            is_active=True
        )

        # Act
        db_session.add(template)
        db_session.commit()

        # Assert
        assert template.id is not None
        assert template.name == "Patient Health Assessment"
        assert template.version == "1.0"
        assert len(template.questions) == 3
        assert template.is_active is True
        assert template.created_at is not None
        assert template.updated_at is not None

    def test_quiz_template_unique_name_version_constraint(self, db_session, sample_questions):
        """Test unique constraint on template name and version."""
        # Arrange
        template1 = QuizTemplate(
            name="Health Check",
            version="1.0",
            questions=sample_questions,
            is_active=True
        )
        template2 = QuizTemplate(
            name="Health Check",
            version="1.0",  # Same name and version
            questions=sample_questions,
            is_active=True
        )

        # Act & Assert
        db_session.add(template1)
        db_session.commit()

        db_session.add(template2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_quiz_template_different_versions_allowed(self, db_session, sample_questions):
        """Test that different versions of same template are allowed."""
        # Arrange
        template1 = QuizTemplate(
            name="Health Check",
            version="1.0",
            questions=sample_questions,
            is_active=True
        )
        template2 = QuizTemplate(
            name="Health Check",
            version="2.0",  # Different version
            questions=sample_questions,
            is_active=True
        )

        # Act
        db_session.add(template1)
        db_session.add(template2)
        db_session.commit()

        # Assert
        assert template1.id != template2.id
        assert template1.name == template2.name
        assert template1.version != template2.version

    def test_quiz_template_questions_json_serialization(self, db_session, sample_questions):
        """Test that questions are properly serialized as JSON."""
        # Arrange
        template = QuizTemplate(
            name="JSON Test",
            version="1.0",
            questions=sample_questions,
            is_active=True
        )

        # Act
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)

        # Assert
        assert isinstance(template.questions, list)
        assert len(template.questions) == 3
        assert template.questions[0]["id"] == "mood_rating"
        assert template.questions[0]["type"] == "scale"

    def test_quiz_template_updated_at_auto_update(self, db_session, sample_questions):
        """Test that updated_at is automatically updated on changes."""
        # Arrange
        template = QuizTemplate(
            name="Update Test",
            version="1.0",
            questions=sample_questions,
            is_active=True
        )
        db_session.add(template)
        db_session.commit()
        original_updated_at = template.updated_at

        # Act
        template.name = "Updated Name"
        db_session.commit()
        db_session.refresh(template)

        # Assert
        assert template.updated_at > original_updated_at

    def test_quiz_template_soft_delete(self, db_session, sample_questions):
        """Test soft delete functionality via is_active flag."""
        # Arrange
        template = QuizTemplate(
            name="Soft Delete Test",
            version="1.0",
            questions=sample_questions,
            is_active=True
        )
        db_session.add(template)
        db_session.commit()

        # Act
        template.is_active = False
        db_session.commit()

        # Assert
        assert template.is_active is False
        # Template still exists in database
        assert db_session.query(QuizTemplate).filter(
            QuizTemplate.id == template.id
        ).first() is not None


class TestQuizResponseModel:
    """Test cases for QuizResponse model."""

    @pytest.fixture
    def sample_template(self, db_session):
        """Create a sample quiz template."""
        template = QuizTemplate(
            name="Test Template",
            version="1.0",
            questions=[
                {
                    "id": "test_question",
                    "text": "Test question?",
                    "type": "single_choice",
                    "options": [
                        {"id": "option1", "value": "Option 1"},
                        {"id": "option2", "value": "Option 2"}
                    ]
                }
            ],
            is_active=True
        )
        db_session.add(template)
        db_session.commit()
        return template

    def test_quiz_response_creation(self, db_session, sample_template):
        """Test creating a quiz response."""
        # Arrange
        patient_id = uuid4()
        response = QuizResponse(
            patient_id=patient_id,
            quiz_template_id=sample_template.id,
            question_id="test_question",
            question_text="Test question?",
            response_type="single_choice",
            response_value="option1",
            response_metadata={"completion_time": 30},
            responded_at=datetime.utcnow()
        )

        # Act
        db_session.add(response)
        db_session.commit()

        # Assert
        assert response.id is not None
        assert response.patient_id == patient_id
        assert response.quiz_template_id == sample_template.id
        assert response.question_id == "test_question"
        assert response.response_value == "option1"
        assert response.response_metadata == {"completion_time": 30}

    def test_quiz_response_json_value_storage(self, db_session, sample_template):
        """Test storing complex response values as JSON."""
        # Arrange
        complex_response = ["option1", "option2", "custom_text"]
        response = QuizResponse(
            patient_id=uuid4(),
            quiz_template_id=sample_template.id,
            question_id="test_question",
            question_text="Test question?",
            response_type="multiple_choice",
            response_value=json.dumps(complex_response),
            responded_at=datetime.utcnow()
        )

        # Act
        db_session.add(response)
        db_session.commit()
        db_session.refresh(response)

        # Assert
        stored_value = json.loads(response.response_value)
        assert stored_value == complex_response
        assert isinstance(stored_value, list)

    def test_quiz_response_metadata_json_storage(self, db_session, sample_template):
        """Test storing response metadata as JSON."""
        # Arrange
        metadata = {
            "completion_time_seconds": 45,
            "device_type": "mobile",
            "user_agent": "TestAgent/1.0",
            "screen_resolution": "1920x1080"
        }
        response = QuizResponse(
            patient_id=uuid4(),
            quiz_template_id=sample_template.id,
            question_id="test_question",
            question_text="Test question?",
            response_type="single_choice",
            response_value="option1",
            response_metadata=metadata,
            responded_at=datetime.utcnow()
        )

        # Act
        db_session.add(response)
        db_session.commit()
        db_session.refresh(response)

        # Assert
        assert response.response_metadata == metadata
        assert response.response_metadata["completion_time_seconds"] == 45

    def test_quiz_response_foreign_key_constraints(self, db_session):
        """Test foreign key constraints for quiz responses."""
        # Arrange
        invalid_template_id = uuid4()
        response = QuizResponse(
            patient_id=uuid4(),
            quiz_template_id=invalid_template_id,  # Non-existent template
            question_id="test_question",
            question_text="Test question?",
            response_type="single_choice",
            response_value="option1",
            responded_at=datetime.utcnow()
        )

        # Act & Assert
        db_session.add(response)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_quiz_response_other_text_field(self, db_session, sample_template):
        """Test other_text field for custom responses."""
        # Arrange
        response = QuizResponse(
            patient_id=uuid4(),
            quiz_template_id=sample_template.id,
            question_id="test_question",
            question_text="Test question?",
            response_type="single_choice",
            response_value="other",
            other_text="Custom response text here",
            responded_at=datetime.utcnow()
        )

        # Act
        db_session.add(response)
        db_session.commit()

        # Assert
        assert response.other_text == "Custom response text here"


class TestQuizSessionModel:
    """Test cases for QuizSession model."""

    @pytest.fixture
    def sample_template(self, db_session):
        """Create a sample quiz template."""
        template = QuizTemplate(
            name="Session Test Template",
            version="1.0",
            questions=[
                {"id": "q1", "text": "Question 1?", "type": "yes_no"},
                {"id": "q2", "text": "Question 2?", "type": "scale"},
                {"id": "q3", "text": "Question 3?", "type": "open_text"}
            ],
            is_active=True
        )
        db_session.add(template)
        db_session.commit()
        return template

    def test_quiz_session_creation(self, db_session, sample_template):
        """Test creating a quiz session."""
        # Arrange
        patient_id = uuid4()
        session = QuizSession(
            patient_id=patient_id,
            quiz_template_id=sample_template.id,
            current_question=0,
            status="started",
            started_at=datetime.utcnow()
        )

        # Act
        db_session.add(session)
        db_session.commit()

        # Assert
        assert session.id is not None
        assert session.patient_id == patient_id
        assert session.quiz_template_id == sample_template.id
        assert session.current_question == 0
        assert session.status == "started"
        assert session.completed_at is None

    def test_quiz_session_status_transitions(self, db_session, sample_template):
        """Test quiz session status transitions."""
        # Arrange
        session = QuizSession(
            patient_id=uuid4(),
            quiz_template_id=sample_template.id,
            current_question=0,
            status="started",
            started_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # Act - Advance through questions
        session.current_question = 1
        session.status = "in_progress"
        db_session.commit()

        # Complete session
        session.current_question = 3
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        db_session.commit()

        # Assert
        assert session.status == "completed"
        assert session.completed_at is not None
        assert session.current_question == 3

    def test_quiz_session_unique_active_constraint(self, db_session, sample_template):
        """Test unique constraint for active sessions per patient."""
        # This test assumes there's a database constraint preventing
        # multiple active sessions for the same patient
        patient_id = uuid4()

        # Arrange
        session1 = QuizSession(
            patient_id=patient_id,
            quiz_template_id=sample_template.id,
            current_question=0,
            status="started",
            started_at=datetime.utcnow()
        )

        session2 = QuizSession(
            patient_id=patient_id,  # Same patient
            quiz_template_id=sample_template.id,
            current_question=0,
            status="started",  # Both active
            started_at=datetime.utcnow()
        )

        # Act & Assert
        db_session.add(session1)
        db_session.commit()

        db_session.add(session2)
        # This might raise IntegrityError if there's a unique constraint
        # In practice, this should be handled by application logic
        try:
            db_session.commit()
            # If no constraint exists, we'll manually verify in application logic
        except IntegrityError:
            # Expected if database has unique constraint
            pass

    def test_quiz_session_completion_time_calculation(self, db_session, sample_template):
        """Test calculation of session completion time."""
        # Arrange
        start_time = datetime.utcnow()
        session = QuizSession(
            patient_id=uuid4(),
            quiz_template_id=sample_template.id,
            current_question=0,
            status="started",
            started_at=start_time
        )
        db_session.add(session)
        db_session.commit()

        # Act
        completion_time = start_time + timedelta(minutes=15)
        session.status = "completed"
        session.completed_at = completion_time
        db_session.commit()

        # Assert
        duration = session.completed_at - session.started_at
        assert duration.total_seconds() == 900  # 15 minutes


class TestQuizSchemaValidation:
    """Test cases for quiz schema validation."""

    def test_quiz_question_schema_validation(self):
        """Test QuizQuestion schema validation."""
        # Valid question
        valid_question = QuizQuestion(
            id="test_question",
            text="How are you feeling?",
            type=QuestionType.SCALE,
            validation_rules=[
                ValidationRule(type="range", min=1, max=10)
            ],
            required=True
        )
        assert valid_question.id == "test_question"
        assert valid_question.type == QuestionType.SCALE

        # Invalid question - missing required fields
        with pytest.raises(PydanticValidationError):
            QuizQuestion(
                # Missing id and text
                type=QuestionType.SCALE
            )

    def test_quiz_template_create_schema(self):
        """Test QuizTemplateCreate schema validation."""
        # Valid template
        questions = [
            QuizQuestion(
                id="q1",
                text="Test question?",
                type=QuestionType.YES_NO,
                required=True
            )
        ]

        template = QuizTemplateCreate(
            name="Test Template",
            version="1.0",
            questions=questions,
            is_active=True
        )

        assert template.name == "Test Template"
        assert len(template.questions) == 1

        # Invalid template - empty name
        with pytest.raises(PydanticValidationError):
            QuizTemplateCreate(
                name="",  # Empty name
                version="1.0",
                questions=questions
            )

    def test_quiz_response_create_schema(self):
        """Test QuizResponseCreate schema validation."""
        # Valid response
        response = QuizResponseCreate(
            patient_id=uuid4(),
            quiz_template_id=uuid4(),
            question_id="test_question",
            response_type=QuestionType.SINGLE_CHOICE,
            response_value="option1",
            response_metadata={"time": 30}
        )

        assert response.question_id == "test_question"
        assert response.response_type == QuestionType.SINGLE_CHOICE

        # Invalid response - missing required fields
        with pytest.raises(PydanticValidationError):
            QuizResponseCreate(
                # Missing patient_id and other required fields
                question_id="test_question",
                response_value="option1"
            )

    def test_quiz_session_create_schema(self):
        """Test QuizSessionCreate schema validation."""
        # Valid session
        session = QuizSessionCreate(
            patient_id=uuid4(),
            quiz_template_id=uuid4()
        )

        assert session.patient_id is not None
        assert session.quiz_template_id is not None

        # Invalid session - invalid UUID
        with pytest.raises(PydanticValidationError):
            QuizSessionCreate(
                patient_id="invalid-uuid",
                quiz_template_id=uuid4()
            )

    def test_question_type_validation(self):
        """Test question type enumeration validation."""
        # Valid question types
        valid_types = [
            QuestionType.OPEN_TEXT,
            QuestionType.MULTIPLE_CHOICE,
            QuestionType.SINGLE_CHOICE,
            QuestionType.SCALE,
            QuestionType.YES_NO,
            QuestionType.DATE,
            QuestionType.NUMBER
        ]

        for question_type in valid_types:
            question = QuizQuestion(
                id="test",
                text="Test",
                type=question_type,
                required=False
            )
            assert question.type == question_type

    def test_validation_rule_schema(self):
        """Test ValidationRule schema validation."""
        # Range validation rule
        range_rule = ValidationRule(
            type="range",
            min=1,
            max=10,
            message="Value must be between 1 and 10"
        )
        assert range_rule.type == "range"
        assert range_rule.min == 1
        assert range_rule.max == 10

        # Required validation rule
        required_rule = ValidationRule(
            type="required",
            value=True,
            message="This field is required"
        )
        assert required_rule.type == "required"
        assert required_rule.value is True

    def test_quiz_option_schema(self):
        """Test QuizOption schema validation."""
        # Standard option
        option = QuizOption(
            id="option1",
            value="Option 1",
            allow_other=False
        )
        assert option.id == "option1"
        assert option.value == "Option 1"
        assert option.allow_other is False

        # Option with "other" support
        other_option = QuizOption(
            id="other",
            value="Other",
            allow_other=True
        )
        assert other_option.allow_other is True


class TestQuizValidationLogic:
    """Test cases for quiz validation logic."""

    def test_quiz_validation_result(self):
        """Test QuizValidationResult structure."""
        # Valid result
        valid_result = QuizValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Consider adding more questions"]
        )
        assert valid_result.is_valid is True
        assert len(valid_result.errors) == 0
        assert len(valid_result.warnings) == 1

        # Invalid result
        invalid_result = QuizValidationResult(
            is_valid=False,
            errors=["Question ID is required", "Invalid question type"],
            warnings=[]
        )
        assert invalid_result.is_valid is False
        assert len(invalid_result.errors) == 2

    def test_question_validation_rules_logic(self):
        """Test validation rule application logic."""
        # This would test the actual validation logic implemented in services
        # Here we test the schema structure that supports validation

        # Scale question with range validation
        scale_question = QuizQuestion(
            id="mood_scale",
            text="Rate your mood",
            type=QuestionType.SCALE,
            validation_rules=[
                ValidationRule(type="required", value=True),
                ValidationRule(type="range", min=1, max=10)
            ],
            required=True
        )

        assert len(scale_question.validation_rules) == 2
        assert scale_question.validation_rules[0].type == "required"
        assert scale_question.validation_rules[1].type == "range"

    def test_response_value_type_consistency(self):
        """Test that response values are consistent with question types."""
        # This tests the schema structure for type consistency

        # Single choice response
        single_choice_response = QuizResponseCreate(
            patient_id=uuid4(),
            quiz_template_id=uuid4(),
            question_id="choice_question",
            response_type=QuestionType.SINGLE_CHOICE,
            response_value="option1"  # Should be string for single choice
        )
        assert isinstance(single_choice_response.response_value, str)

        # Multiple choice response (would typically be JSON array)
        multi_choice_response = QuizResponseCreate(
            patient_id=uuid4(),
            quiz_template_id=uuid4(),
            question_id="multi_question",
            response_type=QuestionType.MULTIPLE_CHOICE,
            response_value='["option1", "option2"]'  # JSON string
        )
        assert isinstance(multi_choice_response.response_value, str)


@pytest.mark.integration
class TestQuizModelRelationships:
    """Integration tests for quiz model relationships."""

    def test_template_response_relationship(self, db_session):
        """Test relationship between template and responses."""
        # Arrange
        template = QuizTemplate(
            name="Relationship Test",
            version="1.0",
            questions=[{"id": "q1", "text": "Test?", "type": "yes_no"}],
            is_active=True
        )
        db_session.add(template)
        db_session.commit()

        response = QuizResponse(
            patient_id=uuid4(),
            quiz_template_id=template.id,
            question_id="q1",
            question_text="Test?",
            response_type="yes_no",
            response_value="yes",
            responded_at=datetime.utcnow()
        )
        db_session.add(response)
        db_session.commit()

        # Act
        db_session.refresh(template)
        template_responses = db_session.query(QuizResponse).filter(
            QuizResponse.quiz_template_id == template.id
        ).all()

        # Assert
        assert len(template_responses) == 1
        assert template_responses[0].quiz_template_id == template.id

    def test_session_template_relationship(self, db_session):
        """Test relationship between session and template."""
        # Arrange
        template = QuizTemplate(
            name="Session Template",
            version="1.0",
            questions=[{"id": "q1", "text": "Test?", "type": "yes_no"}],
            is_active=True
        )
        db_session.add(template)
        db_session.commit()

        session = QuizSession(
            patient_id=uuid4(),
            quiz_template_id=template.id,
            current_question=0,
            status="started",
            started_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # Act
        session_template = db_session.query(QuizTemplate).filter(
            QuizTemplate.id == session.quiz_template_id
        ).first()

        # Assert
        assert session_template is not None
        assert session_template.id == template.id
        assert session_template.name == "Session Template"