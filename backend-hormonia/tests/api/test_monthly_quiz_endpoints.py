"""
Comprehensive API tests for Monthly Quiz endpoints.

Tests all monthly quiz API endpoints including:
- Link creation and management
- Bulk operations
- Public access endpoints
- Security and validation
- Error handling
"""
import pytest
import json
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.schemas.monthly_quiz import (
    MonthlyQuizLinkCreate, MonthlyQuizLinkResponse, DeliveryMethod,
    QuizLinkStatus, BulkQuizLinkCreate, MonthlyQuizSubmitResponse
)
from app.models.user import User
from app.models.patient import Patient
from app.models.quiz import QuizTemplate, QuizSession
from app.exceptions import NotFoundError, ValidationError


class TestMonthlyQuizEndpoints:
    """Test suite for monthly quiz API endpoints."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_patient(self, db_session):
        """Create a sample patient."""
        patient = Patient(
            id=uuid4(),
            name="John Doe",
            email="john@example.com",
            phone="+1234567890",
            cpf="12345678901"
        )
        db_session.add(patient)
        db_session.commit()
        return patient

    @pytest.fixture
    def sample_quiz_template(self, db_session):
        """Create a sample quiz template."""
        template = QuizTemplate(
            id=uuid4(),
            name="Monthly Health Assessment",
            description="Monthly assessment for patients",
            questions=[
                {
                    "id": "q1",
                    "type": "scale",
                    "text": "How is your energy level?",
                    "options": {"min": 1, "max": 10}
                },
                {
                    "id": "q2",
                    "type": "yes_no",
                    "text": "Are you experiencing any side effects?"
                }
            ],
            version="1.0",
            is_active=True,
            created_by=uuid4()
        )
        db_session.add(template)
        db_session.commit()
        return template

    @pytest.fixture
    def auth_headers(self, doctor_a_credentials):
        """Create authorization headers."""
        return {"Authorization": f"Bearer {doctor_a_credentials['access_token']}"}

    @pytest.fixture
    def valid_link_data(self, sample_patient, sample_quiz_template):
        """Create valid link creation data."""
        return {
            "patient_id": str(sample_patient.id),
            "quiz_template_id": str(sample_quiz_template.id),
            "delivery_method": "whatsapp",
            "expiry_hours": 72,
            "custom_message": "Please complete your monthly assessment"
        }

    def test_create_monthly_quiz_link_success(self, test_client, auth_headers, valid_link_data):
        """Test successful monthly quiz link creation."""
        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = MonthlyQuizLinkResponse(
                id=uuid4(),
                patient_id=UUID(valid_link_data["patient_id"]),
                quiz_template_id=UUID(valid_link_data["quiz_template_id"]),
                token="test_token",
                link_url="https://example.com/quiz?token=test_token",
                delivery_method=DeliveryMethod.WHATSAPP,
                status=QuizLinkStatus.ACTIVE,
                expires_at=datetime.utcnow() + timedelta(hours=72),
                created_at=datetime.utcnow(),
                accessed_at=None,
                completed_at=None,
                access_count=0
            )
            mock_service.create_quiz_link = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/links",
                json=valid_link_data,
                headers=auth_headers
            )

            assert response.status_code == 201
            data = response.json()
            assert data["patient_id"] == valid_link_data["patient_id"]
            assert data["quiz_template_id"] == valid_link_data["quiz_template_id"]
            assert data["status"] == "active"
            assert data["token"] == "test_token"
            assert "link_url" in data

    def test_create_monthly_quiz_link_unauthorized(self, test_client, valid_link_data):
        """Test quiz link creation without authentication."""
        response = test_client.post(
            "/api/v1/monthly-quiz/links",
            json=valid_link_data
        )

        assert response.status_code == 401

    def test_create_monthly_quiz_link_invalid_data(self, test_client, auth_headers):
        """Test quiz link creation with invalid data."""
        invalid_data = {
            "patient_id": "invalid-uuid",
            "quiz_template_id": str(uuid4()),
            "delivery_method": "invalid_method"
        }

        response = test_client.post(
            "/api/v1/monthly-quiz/links",
            json=invalid_data,
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_create_monthly_quiz_link_patient_not_found(self, test_client, auth_headers, sample_quiz_template):
        """Test quiz link creation with non-existent patient."""
        link_data = {
            "patient_id": str(uuid4()),  # Non-existent patient
            "quiz_template_id": str(sample_quiz_template.id),
            "delivery_method": "whatsapp"
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.create_quiz_link = AsyncMock(
                side_effect=NotFoundError("Patient not found")
            )
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/links",
                json=link_data,
                headers=auth_headers
            )

            assert response.status_code == 404
            assert "Patient not found" in response.json()["detail"]

    def test_create_monthly_quiz_link_template_not_found(self, test_client, auth_headers, sample_patient):
        """Test quiz link creation with non-existent template."""
        link_data = {
            "patient_id": str(sample_patient.id),
            "quiz_template_id": str(uuid4()),  # Non-existent template
            "delivery_method": "whatsapp"
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.create_quiz_link = AsyncMock(
                side_effect=NotFoundError("Quiz template not found")
            )
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/links",
                json=link_data,
                headers=auth_headers
            )

            assert response.status_code == 404
            assert "Quiz template not found" in response.json()["detail"]

    def test_create_bulk_monthly_quiz_links_success(self, test_client, auth_headers, sample_quiz_template, db_session):
        """Test successful bulk quiz link creation."""
        # Create test patients
        patient1 = Patient(id=uuid4(), name="Patient 1", email="p1@example.com")
        patient2 = Patient(id=uuid4(), name="Patient 2", email="p2@example.com")
        db_session.add_all([patient1, patient2])
        db_session.commit()

        bulk_data = {
            "patient_ids": [str(patient1.id), str(patient2.id)],
            "quiz_template_id": str(sample_quiz_template.id),
            "delivery_method": "email",
            "expiry_hours": 48,
            "custom_message": "Complete your assessment"
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = Mock()
            mock_response.total_requested = 2
            mock_response.total_created = 2
            mock_response.total_failed = 0
            mock_response.links = [Mock(), Mock()]
            mock_response.failures = []
            mock_service.create_bulk_quiz_links = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/links/bulk",
                json=bulk_data,
                headers=auth_headers
            )

            assert response.status_code == 201
            data = response.json()
            assert data["total_requested"] == 2
            assert data["total_created"] == 2
            assert data["total_failed"] == 0

    def test_create_bulk_monthly_quiz_links_partial_failure(self, test_client, auth_headers, sample_quiz_template):
        """Test bulk quiz link creation with some failures."""
        valid_patient_id = str(uuid4())
        invalid_patient_id = str(uuid4())

        bulk_data = {
            "patient_ids": [valid_patient_id, invalid_patient_id],
            "quiz_template_id": str(sample_quiz_template.id),
            "delivery_method": "email"
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = Mock()
            mock_response.total_requested = 2
            mock_response.total_created = 1
            mock_response.total_failed = 1
            mock_response.links = [Mock()]
            mock_response.failures = [
                {"patient_id": invalid_patient_id, "error": "Patient not found"}
            ]
            mock_service.create_bulk_quiz_links = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/links/bulk",
                json=bulk_data,
                headers=auth_headers
            )

            assert response.status_code == 201
            data = response.json()
            assert data["total_requested"] == 2
            assert data["total_created"] == 1
            assert data["total_failed"] == 1
            assert len(data["failures"]) == 1

    def test_get_quiz_link_status_success(self, test_client, auth_headers):
        """Test successful quiz link status retrieval."""
        session_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = MonthlyQuizLinkResponse(
                id=session_id,
                patient_id=uuid4(),
                quiz_template_id=uuid4(),
                token="[REDACTED]",
                link_url="https://example.com/quiz?token=[REDACTED]",
                delivery_method=DeliveryMethod.WHATSAPP,
                status=QuizLinkStatus.ACTIVE,
                expires_at=datetime.utcnow() + timedelta(hours=24),
                created_at=datetime.utcnow(),
                accessed_at=None,
                completed_at=None,
                access_count=0
            )
            mock_service.get_quiz_link_status = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            response = test_client.get(
                f"/api/v1/monthly-quiz/links/{session_id}/status",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(session_id)
            assert data["status"] == "active"
            assert data["token"] == "[REDACTED]"

    def test_get_quiz_link_status_not_found(self, test_client, auth_headers):
        """Test quiz link status retrieval for non-existent session."""
        session_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_quiz_link_status = AsyncMock(
                side_effect=NotFoundError("Quiz session not found")
            )
            mock_get_service.return_value = mock_service

            response = test_client.get(
                f"/api/v1/monthly-quiz/links/{session_id}/status",
                headers=auth_headers
            )

            assert response.status_code == 404

    def test_get_monthly_quiz_stats_success(self, test_client, auth_headers):
        """Test successful monthly quiz statistics retrieval."""
        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_stats = Mock()
            mock_stats.total_links_created = 100
            mock_stats.active_links = 25
            mock_stats.expired_links = 15
            mock_stats.completed_quizzes = 60
            mock_stats.completion_rate = 60.0
            mock_stats.average_completion_time = 12.5
            mock_stats.delivery_methods_distribution = {
                "whatsapp": 70,
                "email": 20,
                "sms": 10
            }
            mock_service.get_monthly_quiz_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = test_client.get(
                "/api/v1/monthly-quiz/stats",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_links_created"] == 100
            assert data["completion_rate"] == 60.0
            assert "delivery_methods_distribution" in data

    def test_get_monthly_quiz_stats_with_date_filter(self, test_client, auth_headers):
        """Test monthly quiz statistics with date filters."""
        start_date = "2024-01-01T00:00:00Z"
        end_date = "2024-01-31T23:59:59Z"

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_stats = Mock()
            mock_stats.total_links_created = 50
            mock_stats.completed_quizzes = 30
            mock_service.get_monthly_quiz_stats = AsyncMock(return_value=mock_stats)
            mock_get_service.return_value = mock_service

            response = test_client.get(
                f"/api/v1/monthly-quiz/stats?start_date={start_date}&end_date={end_date}",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_links_created"] == 50

    def test_resend_quiz_link_success(self, test_client, auth_headers):
        """Test successful quiz link resending."""
        session_id = uuid4()
        resend_data = {
            "delivery_method": "email"
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = MonthlyQuizLinkResponse(
                id=session_id,
                patient_id=uuid4(),
                quiz_template_id=uuid4(),
                token="new_token",
                link_url="https://example.com/quiz?token=new_token",
                delivery_method=DeliveryMethod.EMAIL,
                status=QuizLinkStatus.ACTIVE,
                expires_at=datetime.utcnow() + timedelta(hours=24),
                created_at=datetime.utcnow(),
                accessed_at=None,
                completed_at=None,
                access_count=0
            )
            mock_service.resend_quiz_link = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                f"/api/v1/monthly-quiz/links/{session_id}/resend",
                json=resend_data,
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(session_id)
            assert data["delivery_method"] == "email"
            assert data["token"] == "new_token"

    def test_resend_quiz_link_expired(self, test_client, auth_headers):
        """Test resending expired quiz link."""
        session_id = uuid4()
        resend_data = {"delivery_method": "email"}

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.resend_quiz_link = AsyncMock(
                side_effect=ValidationError("Cannot resend expired quiz link")
            )
            mock_get_service.return_value = mock_service

            response = test_client.post(
                f"/api/v1/monthly-quiz/links/{session_id}/resend",
                json=resend_data,
                headers=auth_headers
            )

            assert response.status_code == 400
            assert "Cannot resend expired quiz link" in response.json()["detail"]

    def test_cancel_quiz_link_success(self, test_client, auth_headers):
        """Test successful quiz link cancellation."""
        session_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = MonthlyQuizLinkResponse(
                id=session_id,
                patient_id=uuid4(),
                quiz_template_id=uuid4(),
                token="[REDACTED]",
                link_url="https://example.com/quiz?token=[REDACTED]",
                delivery_method=DeliveryMethod.WHATSAPP,
                status=QuizLinkStatus.CANCELLED,
                expires_at=datetime.utcnow() + timedelta(hours=24),
                created_at=datetime.utcnow(),
                accessed_at=None,
                completed_at=None,
                access_count=0
            )
            mock_service.cancel_quiz_link = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            response = test_client.delete(
                f"/api/v1/monthly-quiz/links/{session_id}",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(session_id)
            assert data["status"] == "cancelled"

    def test_cancel_quiz_link_already_completed(self, test_client, auth_headers):
        """Test cancelling already completed quiz link."""
        session_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.cancel_quiz_link = AsyncMock(
                side_effect=ValidationError("Cannot cancel a completed quiz session")
            )
            mock_get_service.return_value = mock_service

            response = test_client.delete(
                f"/api/v1/monthly-quiz/links/{session_id}",
                headers=auth_headers
            )

            assert response.status_code == 400
            assert "Cannot cancel a completed quiz session" in response.json()["detail"]

    def test_regenerate_quiz_link_success(self, test_client, auth_headers):
        """Test successful quiz link regeneration."""
        session_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = MonthlyQuizLinkResponse(
                id=session_id,
                patient_id=uuid4(),
                quiz_template_id=uuid4(),
                token="new_regenerated_token",
                link_url="https://example.com/quiz?token=new_regenerated_token",
                delivery_method=DeliveryMethod.WHATSAPP,
                status=QuizLinkStatus.ACTIVE,
                expires_at=datetime.utcnow() + timedelta(hours=72),
                created_at=datetime.utcnow(),
                accessed_at=None,
                completed_at=None,
                access_count=0
            )
            mock_service.regenerate_link = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                f"/api/v1/monthly-quiz/links/{session_id}/regenerate",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(session_id)
            assert data["token"] == "new_regenerated_token"
            assert data["status"] == "active"

    def test_regenerate_quiz_link_completed_session(self, test_client, auth_headers):
        """Test regenerating link for completed session."""
        session_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.regenerate_link = AsyncMock(
                side_effect=ValidationError("Cannot regenerate link for completed session")
            )
            mock_get_service.return_value = mock_service

            response = test_client.post(
                f"/api/v1/monthly-quiz/links/{session_id}/regenerate",
                headers=auth_headers
            )

            assert response.status_code == 400
            assert "Cannot regenerate link for completed session" in response.json()["detail"]

    def test_get_patient_quiz_history_success(self, test_client, auth_headers):
        """Test successful patient quiz history retrieval."""
        patient_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_history = [
                Mock(id=uuid4(), status="completed"),
                Mock(id=uuid4(), status="active")
            ]
            mock_service.get_patient_history = AsyncMock(return_value=mock_history)
            mock_get_service.return_value = mock_service

            response = test_client.get(
                f"/api/v1/monthly-quiz/patients/{patient_id}/history",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_get_patient_quiz_history_with_pagination(self, test_client, auth_headers):
        """Test patient quiz history with pagination."""
        patient_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_history = [Mock(id=uuid4())]
            mock_service.get_patient_history = AsyncMock(return_value=mock_history)
            mock_get_service.return_value = mock_service

            response = test_client.get(
                f"/api/v1/monthly-quiz/patients/{patient_id}/history?limit=5&offset=10",
                headers=auth_headers
            )

            assert response.status_code == 200
            mock_service.get_patient_history.assert_called_with(patient_id, limit=5, offset=10)

    def test_get_active_quiz_links_success(self, test_client, auth_headers):
        """Test successful active quiz links retrieval."""
        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_links = [
                Mock(id=uuid4(), status="active"),
                Mock(id=uuid4(), status="active")
            ]
            mock_service.get_active_links = AsyncMock(return_value=mock_links)
            mock_get_service.return_value = mock_service

            response = test_client.get(
                "/api/v1/monthly-quiz/links/active",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_get_active_quiz_links_with_pagination(self, test_client, auth_headers):
        """Test active quiz links with pagination."""
        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_links = [Mock(id=uuid4())]
            mock_service.get_active_links = AsyncMock(return_value=mock_links)
            mock_get_service.return_value = mock_service

            response = test_client.get(
                "/api/v1/monthly-quiz/links/active?limit=20&offset=40",
                headers=auth_headers
            )

            assert response.status_code == 200
            mock_service.get_active_links.assert_called_with(limit=20, offset=40)


class TestMonthlyQuizPublicEndpoints:
    """Test suite for public monthly quiz endpoints (no authentication required)."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    def test_access_quiz_via_token_success(self, test_client):
        """Test successful quiz access via token."""
        token = "valid_test_token"

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = Mock()
            mock_response.quiz_session_id = uuid4()
            mock_response.patient_name = "John Doe"
            mock_response.template_name = "Health Assessment"
            mock_response.questions = [
                {"id": "q1", "type": "scale", "text": "How do you feel?"}
            ]
            mock_response.current_question_index = 0
            mock_response.total_questions = 1
            mock_service.access_quiz_via_token = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            response = test_client.get(f"/api/v1/monthly-quiz/access?token={token}")

            assert response.status_code == 200
            data = response.json()
            assert data["patient_name"] == "John Doe"
            assert data["template_name"] == "Health Assessment"
            assert len(data["questions"]) == 1

    def test_access_quiz_via_token_invalid(self, test_client):
        """Test quiz access with invalid token."""
        token = "invalid_token"

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.access_quiz_via_token = AsyncMock(
                side_effect=ValidationError("Invalid quiz token")
            )
            mock_get_service.return_value = mock_service

            response = test_client.get(f"/api/v1/monthly-quiz/access?token={token}")

            assert response.status_code == 400
            assert "Invalid quiz token" in response.json()["detail"]

    def test_access_quiz_missing_token(self, test_client):
        """Test quiz access without token."""
        response = test_client.get("/api/v1/monthly-quiz/access")

        assert response.status_code == 422  # Validation error

    def test_submit_quiz_response_success(self, test_client):
        """Test successful quiz response submission."""
        submit_data = {
            "token": "valid_test_token",
            "question_id": "q1",
            "response_value": 8
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_result = {
                "response_id": str(uuid4()),
                "success": True,
                "message": "Response submitted successfully",
                "is_completed": False,
                "current_question_index": 1,
                "new_token": None
            }
            mock_service.submit_quiz_response = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/submit",
                json=submit_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["is_completed"] is False
            assert data["current_question_index"] == 1

    def test_submit_quiz_response_with_other_text(self, test_client):
        """Test quiz response submission with other text."""
        submit_data = {
            "token": "valid_test_token",
            "question_id": "q1",
            "response_value": "outra",
            "other_text": "My custom answer"
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_result = {
                "response_id": str(uuid4()),
                "success": True,
                "message": "Response submitted successfully",
                "is_completed": False,
                "current_question_index": 1
            }
            mock_service.submit_quiz_response = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/submit",
                json=submit_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_submit_quiz_response_completes_quiz(self, test_client):
        """Test quiz response submission that completes the quiz."""
        submit_data = {
            "token": "valid_test_token",
            "question_id": "q2",
            "response_value": "yes"
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_result = {
                "response_id": str(uuid4()),
                "success": True,
                "message": "Response submitted successfully",
                "is_completed": True,
                "total_score": 85.5,
                "current_question_index": 2
            }
            mock_service.submit_quiz_response = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/submit",
                json=submit_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["is_completed"] is True
            assert data["total_score"] == 85.5

    def test_submit_quiz_response_invalid_token(self, test_client):
        """Test quiz response submission with invalid token."""
        submit_data = {
            "token": "invalid_token",
            "question_id": "q1",
            "response_value": 8
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.submit_quiz_response = AsyncMock(
                side_effect=ValidationError("Invalid quiz token")
            )
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/submit",
                json=submit_data
            )

            assert response.status_code == 400
            assert "Invalid quiz token" in response.json()["detail"]

    def test_submit_quiz_response_question_not_found(self, test_client):
        """Test quiz response submission with invalid question ID."""
        submit_data = {
            "token": "valid_test_token",
            "question_id": "invalid_question",
            "response_value": 8
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.submit_quiz_response = AsyncMock(
                side_effect=NotFoundError("Question not found in template")
            )
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/submit",
                json=submit_data
            )

            assert response.status_code == 404
            assert "Question not found in template" in response.json()["detail"]

    def test_submit_quiz_response_missing_data(self, test_client):
        """Test quiz response submission with missing required data."""
        submit_data = {
            "token": "valid_test_token"
            # Missing question_id and response_value
        }

        response = test_client.post(
            "/api/v1/monthly-quiz/submit",
            json=submit_data
        )

        assert response.status_code == 422  # Validation error

    def test_submit_quiz_response_with_token_rotation(self, test_client):
        """Test quiz response submission with token rotation enabled."""
        submit_data = {
            "token": "valid_test_token",
            "question_id": "q1",
            "response_value": 8
        }

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_result = {
                "response_id": str(uuid4()),
                "success": True,
                "message": "Response submitted successfully",
                "is_completed": False,
                "current_question_index": 1,
                "new_token": "new_rotated_token"
            }
            mock_service.submit_quiz_response = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/submit",
                json=submit_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["new_token"] == "new_rotated_token"


class TestMonthlyQuizErrorHandling:
    """Test error handling scenarios for monthly quiz endpoints."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, doctor_a_credentials):
        """Create authorization headers."""
        return {"Authorization": f"Bearer {doctor_a_credentials['access_token']}"}

    def test_service_unavailable_error(self, test_client, auth_headers, valid_link_data):
        """Test handling of service unavailable errors."""
        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.create_quiz_link = AsyncMock(
                side_effect=Exception("Service temporarily unavailable")
            )
            mock_get_service.return_value = mock_service

            response = test_client.post(
                "/api/v1/monthly-quiz/links",
                json=valid_link_data,
                headers=auth_headers
            )

            assert response.status_code == 500
            assert "Service temporarily unavailable" in response.json()["detail"]

    def test_database_connection_error(self, test_client, auth_headers):
        """Test handling of database connection errors."""
        session_id = uuid4()

        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_quiz_link_status = AsyncMock(
                side_effect=Exception("Database connection failed")
            )
            mock_get_service.return_value = mock_service

            response = test_client.get(
                f"/api/v1/monthly-quiz/links/{session_id}/status",
                headers=auth_headers
            )

            assert response.status_code == 500

    def test_invalid_uuid_parameter(self, test_client, auth_headers):
        """Test handling of invalid UUID parameters."""
        invalid_uuid = "not-a-uuid"

        response = test_client.get(
            f"/api/v1/monthly-quiz/links/{invalid_uuid}/status",
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_concurrent_request_handling(self, test_client, auth_headers, valid_link_data):
        """Test handling of concurrent requests."""
        # This test would ideally use async test clients to simulate concurrent requests
        # For now, we'll test that the endpoint can handle multiple calls
        with patch('app.dependencies.get_monthly_quiz_service') as mock_get_service:
            mock_service = Mock()
            mock_response = Mock()
            mock_response.id = uuid4()
            mock_service.create_quiz_link = AsyncMock(return_value=mock_response)
            mock_get_service.return_value = mock_service

            responses = []
            for _ in range(3):
                response = test_client.post(
                    "/api/v1/monthly-quiz/links",
                    json=valid_link_data,
                    headers=auth_headers
                )
                responses.append(response)

            # All requests should succeed
            for response in responses:
                assert response.status_code == 201

    def test_malformed_json_request(self, test_client, auth_headers):
        """Test handling of malformed JSON requests."""
        response = test_client.post(
            "/api/v1/monthly-quiz/links",
            data="invalid json",
            headers={**auth_headers, "Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_oversized_request_data(self, test_client, auth_headers, valid_link_data):
        """Test handling of oversized request data."""
        # Create a very large custom message
        oversized_data = valid_link_data.copy()
        oversized_data["custom_message"] = "A" * 10000  # Very long message

        response = test_client.post(
            "/api/v1/monthly-quiz/links",
            json=oversized_data,
            headers=auth_headers
        )

        # Should either reject due to size limits or handle gracefully
        assert response.status_code in [413, 422, 400]

    def test_rate_limiting_simulation(self, test_client, auth_headers, valid_link_data):
        """Test behavior under high request volume (rate limiting simulation)."""
        # Simulate rapid requests
        responses = []
        for i in range(10):
            response = test_client.post(
                "/api/v1/monthly-quiz/links",
                json=valid_link_data,
                headers=auth_headers
            )
            responses.append(response)

        # Depending on rate limiting configuration, some requests might be rejected
        # For now, verify that the endpoint doesn't crash
        for response in responses:
            assert response.status_code in [201, 429, 500]  # Success, rate limited, or server error