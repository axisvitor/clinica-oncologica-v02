"""
Comprehensive unit tests for monthly quiz service automation.

Tests the MonthlyQuizService responsible for:
- Automated quiz scheduling and deployment
- Monthly quiz template management
- Recurring quiz automation logic
- Quiz notification and reminder systems
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from typing import List, Dict, Any

from app.services.monthly_quiz_service import MonthlyQuizService
from app.schemas.quiz import (
    QuizTemplateCreate, QuizTemplateResponse, QuizQuestion, QuestionType,
    QuizSessionCreate, QuizSessionResponse, QuizResponseCreate
)
from app.exceptions import NotFoundError, ValidationError, ConflictError


class TestMonthlyQuizService:
    """Test cases for MonthlyQuizService."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock()
        session.query = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.add = Mock()
        session.flush = Mock()
        return session

    @pytest.fixture
    def mock_quiz_service(self):
        """Mock quiz service dependency."""
        service = Mock()
        service.create_template = Mock()
        service.get_templates = Mock()
        service.create_session = AsyncMock()
        service.get_template_analytics = Mock()
        return service

    @pytest.fixture
    def mock_patient_service(self):
        """Mock patient service dependency."""
        service = Mock()
        service.get_all_active_patients = Mock()
        service.get_patient = Mock()
        return service

    @pytest.fixture
    def mock_notification_service(self):
        """Mock notification service."""
        service = AsyncMock()
        service.send_quiz_notification = AsyncMock()
        service.send_quiz_reminder = AsyncMock()
        return service

    @pytest.fixture
    def monthly_quiz_service(self, mock_db_session, mock_quiz_service,
                           mock_patient_service, mock_notification_service):
        """Create MonthlyQuizService instance with mocked dependencies."""
        with patch('app.services.monthly_quiz_service.get_db_session', return_value=mock_db_session):
            service = MonthlyQuizService(
                db=mock_db_session,
                quiz_service=mock_quiz_service,
                patient_service=mock_patient_service,
                notification_service=mock_notification_service
            )
            return service

    @pytest.fixture
    def sample_quiz_template(self):
        """Sample quiz template for testing."""
        return QuizTemplateResponse(
            id=uuid4(),
            name="Monthly Assessment",
            version="1.0",
            questions=[
                {
                    "id": "mood_assessment",
                    "text": "How would you rate your overall mood this month?",
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
                }
            ],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    @pytest.fixture
    def sample_patients(self):
        """Sample patient list for testing."""
        return [
            {"id": uuid4(), "name": "Patient A", "email": "patient.a@test.com"},
            {"id": uuid4(), "name": "Patient B", "email": "patient.b@test.com"},
            {"id": uuid4(), "name": "Patient C", "email": "patient.c@test.com"}
        ]

    def test_schedule_monthly_quiz_success(self, monthly_quiz_service,
                                         sample_quiz_template, sample_patients):
        """Test successful monthly quiz scheduling."""
        # Arrange
        monthly_quiz_service.quiz_service.get_template_by_name.return_value = sample_quiz_template
        monthly_quiz_service.patient_service.get_all_active_patients.return_value = sample_patients
        monthly_quiz_service.quiz_service.create_session.return_value = Mock(
            id=uuid4(), status="started"
        )

        # Act
        result = monthly_quiz_service.schedule_monthly_quiz(
            template_name="Monthly Assessment",
            month=datetime.now().month,
            year=datetime.now().year
        )

        # Assert
        assert result["status"] == "success"
        assert result["quiz_template_id"] == str(sample_quiz_template.id)
        assert result["scheduled_sessions"] == len(sample_patients)

        # Verify sessions were created for each patient
        assert monthly_quiz_service.quiz_service.create_session.call_count == len(sample_patients)

    def test_schedule_monthly_quiz_template_not_found(self, monthly_quiz_service):
        """Test scheduling with non-existent template."""
        # Arrange
        monthly_quiz_service.quiz_service.get_template_by_name.side_effect = NotFoundError("Template not found")

        # Act & Assert
        with pytest.raises(NotFoundError, match="Template not found"):
            monthly_quiz_service.schedule_monthly_quiz(
                template_name="NonExistent Template",
                month=12,
                year=2024
            )

    def test_schedule_monthly_quiz_no_active_patients(self, monthly_quiz_service, sample_quiz_template):
        """Test scheduling when no active patients exist."""
        # Arrange
        monthly_quiz_service.quiz_service.get_template_by_name.return_value = sample_quiz_template
        monthly_quiz_service.patient_service.get_all_active_patients.return_value = []

        # Act
        result = monthly_quiz_service.schedule_monthly_quiz(
            template_name="Monthly Assessment",
            month=12,
            year=2024
        )

        # Assert
        assert result["status"] == "success"
        assert result["scheduled_sessions"] == 0
        assert "message" in result
        assert "no active patients" in result["message"].lower()

    def test_schedule_monthly_quiz_session_creation_failure(self, monthly_quiz_service,
                                                          sample_quiz_template, sample_patients):
        """Test handling of session creation failures."""
        # Arrange
        monthly_quiz_service.quiz_service.get_template_by_name.return_value = sample_quiz_template
        monthly_quiz_service.patient_service.get_all_active_patients.return_value = sample_patients
        monthly_quiz_service.quiz_service.create_session.side_effect = [
            Mock(id=uuid4(), status="started"),  # First succeeds
            ConflictError("Session already exists"),  # Second fails
            Mock(id=uuid4(), status="started")   # Third succeeds
        ]

        # Act
        result = monthly_quiz_service.schedule_monthly_quiz(
            template_name="Monthly Assessment",
            month=12,
            year=2024
        )

        # Assert
        assert result["status"] == "partial_success"
        assert result["scheduled_sessions"] == 2  # 2 out of 3 succeeded
        assert result["failed_sessions"] == 1
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_send_quiz_notifications_success(self, monthly_quiz_service, sample_patients):
        """Test successful quiz notification sending."""
        # Arrange
        quiz_template_id = uuid4()
        monthly_quiz_service.notification_service.send_quiz_notification.return_value = True

        # Act
        result = await monthly_quiz_service.send_quiz_notifications(
            quiz_template_id=quiz_template_id,
            patients=sample_patients,
            notification_type="monthly_quiz_available"
        )

        # Assert
        assert result["status"] == "success"
        assert result["notifications_sent"] == len(sample_patients)
        assert monthly_quiz_service.notification_service.send_quiz_notification.call_count == len(sample_patients)

    @pytest.mark.asyncio
    async def test_send_quiz_notifications_partial_failure(self, monthly_quiz_service, sample_patients):
        """Test quiz notification sending with some failures."""
        # Arrange
        quiz_template_id = uuid4()
        monthly_quiz_service.notification_service.send_quiz_notification.side_effect = [
            True,   # First succeeds
            False,  # Second fails
            True    # Third succeeds
        ]

        # Act
        result = await monthly_quiz_service.send_quiz_notifications(
            quiz_template_id=quiz_template_id,
            patients=sample_patients,
            notification_type="monthly_quiz_available"
        )

        # Assert
        assert result["status"] == "partial_success"
        assert result["notifications_sent"] == 2
        assert result["failed_notifications"] == 1

    def test_get_monthly_quiz_schedule(self, monthly_quiz_service):
        """Test retrieving monthly quiz schedule."""
        # Arrange
        mock_schedule = [
            {
                "template_id": str(uuid4()),
                "template_name": "Monthly Assessment",
                "month": 12,
                "year": 2024,
                "scheduled_date": datetime(2024, 12, 1),
                "status": "scheduled"
            }
        ]
        monthly_quiz_service._get_schedule_from_db = Mock(return_value=mock_schedule)

        # Act
        result = monthly_quiz_service.get_monthly_quiz_schedule(year=2024, month=12)

        # Assert
        assert len(result) == 1
        assert result[0]["template_name"] == "Monthly Assessment"
        assert result[0]["month"] == 12
        assert result[0]["year"] == 2024

    def test_validate_quiz_schedule_parameters(self, monthly_quiz_service):
        """Test validation of quiz scheduling parameters."""
        # Test invalid month
        with pytest.raises(ValidationError, match="Month must be between 1 and 12"):
            monthly_quiz_service.schedule_monthly_quiz(
                template_name="Test Template",
                month=13,
                year=2024
            )

        # Test invalid year
        with pytest.raises(ValidationError, match="Year must be current year or future"):
            monthly_quiz_service.schedule_monthly_quiz(
                template_name="Test Template",
                month=12,
                year=2020
            )

    def test_cancel_monthly_quiz_schedule(self, monthly_quiz_service):
        """Test cancelling a scheduled monthly quiz."""
        # Arrange
        schedule_id = uuid4()
        monthly_quiz_service._get_schedule_by_id = Mock(return_value={
            "id": schedule_id,
            "status": "scheduled",
            "sessions": []
        })

        # Act
        result = monthly_quiz_service.cancel_monthly_quiz_schedule(schedule_id)

        # Assert
        assert result["status"] == "success"
        assert result["cancelled_schedule_id"] == str(schedule_id)

    def test_update_quiz_template_monthly_settings(self, monthly_quiz_service, sample_quiz_template):
        """Test updating monthly quiz template settings."""
        # Arrange
        monthly_quiz_service.quiz_service.get_template.return_value = sample_quiz_template
        monthly_quiz_service.quiz_service.update_template.return_value = sample_quiz_template

        # Act
        result = monthly_quiz_service.update_quiz_template_monthly_settings(
            template_id=sample_quiz_template.id,
            auto_schedule=True,
            schedule_day=1,
            notification_days_before=3
        )

        # Assert
        assert result["status"] == "success"
        assert result["template_id"] == str(sample_quiz_template.id)

        # Verify update was called with correct settings
        monthly_quiz_service.quiz_service.update_template.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_monthly_quiz_automation(self, monthly_quiz_service):
        """Test the main monthly quiz automation process."""
        # Arrange
        monthly_quiz_service._get_templates_for_automation = Mock(return_value=[
            {"id": uuid4(), "name": "Monthly Mood Assessment", "schedule_day": 1},
            {"id": uuid4(), "name": "Weekly Symptom Check", "schedule_day": 15}
        ])
        monthly_quiz_service.schedule_monthly_quiz = Mock(return_value={
            "status": "success", "scheduled_sessions": 5
        })
        monthly_quiz_service.send_quiz_notifications = AsyncMock(return_value={
            "status": "success", "notifications_sent": 5
        })

        # Act
        result = await monthly_quiz_service.process_monthly_quiz_automation(
            month=12, year=2024
        )

        # Assert
        assert result["status"] == "success"
        assert result["processed_templates"] == 2
        assert "template_results" in result

    def test_get_quiz_completion_analytics(self, monthly_quiz_service):
        """Test quiz completion analytics retrieval."""
        # Arrange
        mock_analytics = {
            "total_scheduled": 100,
            "total_completed": 85,
            "completion_rate": 85.0,
            "average_completion_time": 15.5,
            "pending_quizzes": 15
        }
        monthly_quiz_service.quiz_service.get_monthly_completion_analytics = Mock(
            return_value=mock_analytics
        )

        # Act
        result = monthly_quiz_service.get_quiz_completion_analytics(
            month=12, year=2024
        )

        # Assert
        assert result["completion_rate"] == 85.0
        assert result["total_scheduled"] == 100
        assert result["total_completed"] == 85

    @pytest.mark.asyncio
    async def test_send_quiz_reminders(self, monthly_quiz_service):
        """Test sending quiz reminders to patients."""
        # Arrange
        overdue_sessions = [
            {"session_id": uuid4(), "patient_id": uuid4(), "days_overdue": 3},
            {"session_id": uuid4(), "patient_id": uuid4(), "days_overdue": 5}
        ]
        monthly_quiz_service._get_overdue_sessions = Mock(return_value=overdue_sessions)
        monthly_quiz_service.notification_service.send_quiz_reminder.return_value = True

        # Act
        result = await monthly_quiz_service.send_quiz_reminders(days_overdue=2)

        # Assert
        assert result["status"] == "success"
        assert result["reminders_sent"] == 2
        assert monthly_quiz_service.notification_service.send_quiz_reminder.call_count == 2

    def test_validate_monthly_quiz_template(self, monthly_quiz_service):
        """Test validation of monthly quiz templates."""
        # Valid template
        valid_questions = [
            QuizQuestion(
                id="mood",
                text="Rate your mood",
                type=QuestionType.SCALE,
                validation_rules=[{"type": "range", "min": 1, "max": 10}],
                required=True
            )
        ]

        result = monthly_quiz_service.validate_monthly_quiz_template(valid_questions)
        assert result.is_valid is True

        # Invalid template - no questions
        result = monthly_quiz_service.validate_monthly_quiz_template([])
        assert result.is_valid is False
        assert "at least one question" in result.errors[0]

    @pytest.mark.asyncio
    async def test_monthly_quiz_automation_error_handling(self, monthly_quiz_service):
        """Test error handling in monthly quiz automation."""
        # Arrange
        monthly_quiz_service._get_templates_for_automation.side_effect = Exception("Database error")

        # Act
        result = await monthly_quiz_service.process_monthly_quiz_automation(
            month=12, year=2024
        )

        # Assert
        assert result["status"] == "error"
        assert "Database error" in result["error_message"]

    def test_get_monthly_quiz_metrics(self, monthly_quiz_service):
        """Test retrieval of monthly quiz metrics."""
        # Arrange
        mock_metrics = {
            "templates_scheduled": 5,
            "sessions_created": 150,
            "responses_received": 125,
            "completion_rate": 83.3,
            "avg_response_time": 12.5,
            "patient_engagement_score": 78.5
        }
        monthly_quiz_service._calculate_monthly_metrics = Mock(return_value=mock_metrics)

        # Act
        result = monthly_quiz_service.get_monthly_quiz_metrics(month=12, year=2024)

        # Assert
        assert result["completion_rate"] == 83.3
        assert result["patient_engagement_score"] == 78.5
        assert result["sessions_created"] == 150

    @pytest.mark.asyncio
    async def test_automated_quiz_deployment_workflow(self, monthly_quiz_service,
                                                     sample_quiz_template, sample_patients):
        """Test the complete automated quiz deployment workflow."""
        # Arrange
        monthly_quiz_service.quiz_service.get_template_by_name.return_value = sample_quiz_template
        monthly_quiz_service.patient_service.get_all_active_patients.return_value = sample_patients
        monthly_quiz_service.quiz_service.create_session.return_value = Mock(id=uuid4(), status="started")
        monthly_quiz_service.notification_service.send_quiz_notification.return_value = True

        # Act
        deployment_result = await monthly_quiz_service.deploy_monthly_quiz_workflow(
            template_name="Monthly Assessment",
            target_date=datetime.now().date(),
            send_notifications=True
        )

        # Assert
        assert deployment_result["status"] == "success"
        assert deployment_result["sessions_created"] == len(sample_patients)
        assert deployment_result["notifications_sent"] == len(sample_patients)

        # Verify workflow steps were executed
        monthly_quiz_service.quiz_service.get_template_by_name.assert_called_once()
        monthly_quiz_service.patient_service.get_all_active_patients.assert_called_once()
        assert monthly_quiz_service.quiz_service.create_session.call_count == len(sample_patients)


class TestMonthlyQuizServiceIntegration:
    """Integration tests for MonthlyQuizService with real dependencies."""

    @pytest.fixture
    def integration_service(self, db_session):
        """Create service with real database session."""
        from app.services.quiz import QuizService
        from app.services.patient import PatientService

        quiz_service = QuizService(db_session)
        patient_service = PatientService(db_session)
        notification_service = Mock()

        return MonthlyQuizService(
            db=db_session,
            quiz_service=quiz_service,
            patient_service=patient_service,
            notification_service=notification_service
        )

    def test_monthly_quiz_service_initialization(self, integration_service):
        """Test service initialization with real dependencies."""
        assert integration_service is not None
        assert hasattr(integration_service, 'quiz_service')
        assert hasattr(integration_service, 'patient_service')
        assert hasattr(integration_service, 'notification_service')

    def test_service_dependencies_injection(self, integration_service):
        """Test that all required dependencies are properly injected."""
        # Verify service has all required methods
        required_methods = [
            'schedule_monthly_quiz',
            'send_quiz_notifications',
            'get_monthly_quiz_schedule',
            'cancel_monthly_quiz_schedule',
            'process_monthly_quiz_automation'
        ]

        for method in required_methods:
            assert hasattr(integration_service, method)
            assert callable(getattr(integration_service, method))


@pytest.mark.performance
class TestMonthlyQuizServicePerformance:
    """Performance tests for MonthlyQuizService."""

    def test_bulk_quiz_scheduling_performance(self, monthly_quiz_service, performance_timer):
        """Test performance of scheduling quizzes for large patient populations."""
        # Arrange
        large_patient_list = [
            {"id": uuid4(), "name": f"Patient {i}", "email": f"patient{i}@test.com"}
            for i in range(1000)
        ]

        sample_template = QuizTemplateResponse(
            id=uuid4(),
            name="Performance Test Quiz",
            version="1.0",
            questions=[],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        monthly_quiz_service.quiz_service.get_template_by_name.return_value = sample_template
        monthly_quiz_service.patient_service.get_all_active_patients.return_value = large_patient_list
        monthly_quiz_service.quiz_service.create_session.return_value = Mock(id=uuid4(), status="started")

        # Act
        performance_timer.start()
        result = monthly_quiz_service.schedule_monthly_quiz(
            template_name="Performance Test Quiz",
            month=12,
            year=2024
        )
        execution_time = performance_timer.stop()

        # Assert
        assert execution_time < 5.0  # Should complete within 5 seconds
        assert result["scheduled_sessions"] == 1000
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_notification_sending_performance(self, monthly_quiz_service, performance_timer):
        """Test performance of sending notifications to large patient groups."""
        # Arrange
        large_patient_list = [
            {"id": uuid4(), "name": f"Patient {i}", "email": f"patient{i}@test.com"}
            for i in range(500)
        ]

        monthly_quiz_service.notification_service.send_quiz_notification.return_value = True

        # Act
        performance_timer.start()
        result = await monthly_quiz_service.send_quiz_notifications(
            quiz_template_id=uuid4(),
            patients=large_patient_list,
            notification_type="monthly_quiz_available"
        )
        execution_time = performance_timer.stop()

        # Assert
        assert execution_time < 10.0  # Should complete within 10 seconds
        assert result["notifications_sent"] == 500
        assert result["status"] == "success"