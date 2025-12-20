"""
Test suite for Quiz API endpoints.

Tests cover:
- Quiz session initialization (POST /api/v2/quiz/initialize)
- Quiz session status (GET /api/v2/quiz/session/{id})
- Submit quiz answer (POST /api/v2/quiz/submit-answer)
- Complete quiz session (POST /api/v2/quiz/complete/{id})
- Resume quiz session (GET /api/v2/quiz/resume/{patient_id})
- Quiz templates (GET /api/v2/quiz/templates)
- Authentication and authorization
- Session state management
- Answer validation
"""

import pytest
from uuid import uuid4
from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.quiz import QuizSession, QuizTemplate, QuizResponse
from app.models.patient import Patient


class TestQuizSessionEndpoints:
    """Test quiz session lifecycle endpoints."""

    @pytest.fixture
    def quiz_template(self, db: Session):
        """Create a test quiz template."""
        template = QuizTemplate(
            name="Monthly Assessment",
            version="1.0",
            is_active=True,
            questions={
                "questions": [
                    {
                        "id": "q1",
                        "type": "single_choice",
                        "text": "How are you feeling?",
                        "options": ["Good", "Fair", "Poor"]
                    },
                    {
                        "id": "q2",
                        "type": "scale",
                        "text": "Rate your pain level",
                        "min": 0,
                        "max": 10
                    }
                ]
            }
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    @pytest.fixture
    def patient(self, db: Session):
        """Create a test patient."""
        patient = Patient(
            name="Test Patient",
            email="quiz.patient@example.com",
            phone="+5511999999998",
            birth_date=datetime(1990, 1, 1)
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient

    @pytest.mark.api
    def test_initialize_quiz_session_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient: Patient,
        quiz_template: QuizTemplate
    ):
        """Test successful quiz session initialization."""
        response = client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": str(patient.id),
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert "session_id" in data
        assert data["patient_id"] == str(patient.id)
        assert data["template_id"] == str(quiz_template.id)
        assert data["status"] == "in_progress"
        assert data["current_question"] == 0

        # Verify in database
        session = db.query(QuizSession).filter(
            QuizSession.id == data["session_id"]
        ).first()
        assert session is not None
        assert session.status == "in_progress"

    @pytest.mark.api
    def test_initialize_quiz_session_patient_not_found(
        self,
        client: TestClient,
        authenticated_headers: dict,
        quiz_template: QuizTemplate
    ):
        """Test quiz initialization with non-existent patient."""
        fake_patient_id = str(uuid4())

        response = client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": fake_patient_id,
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.api
    def test_initialize_quiz_session_already_active(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient: Patient,
        quiz_template: QuizTemplate
    ):
        """Test that only one active session is allowed per patient."""
        # Create first session
        client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": str(patient.id),
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )

        # Try to create another session
        response = client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": str(patient.id),
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.api
    def test_get_session_status_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient: Patient,
        quiz_template: QuizTemplate
    ):
        """Test getting quiz session status."""
        # Initialize session
        init_response = client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": str(patient.id),
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )
        session_id = init_response.json()["session_id"]

        # Get status
        response = client.get(
            f"/api/v2/quiz/session/{session_id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["session_id"] == session_id
        assert data["status"] == "in_progress"
        assert data["current_question"] == 0
        assert "questions" in data

    @pytest.mark.api
    def test_submit_answer_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient: Patient,
        quiz_template: QuizTemplate
    ):
        """Test successful answer submission."""
        # Initialize session
        init_response = client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": str(patient.id),
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )
        session_id = init_response.json()["session_id"]

        # Submit answer
        response = client.post(
            "/api/v2/quiz/submit-answer",
            json={
                "session_id": session_id,
                "question_id": "q1",
                "answer": "Good"
            },
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["current_question"] == 1
        assert data["answers_count"] == 1

        # Verify in database
        responses = db.query(QuizResponse).filter(
            QuizResponse.quiz_session_id == session_id
        ).all()
        assert len(responses) == 1
        assert responses[0].question_id == "q1"

    @pytest.mark.api
    def test_submit_answer_invalid_question(
        self,
        client: TestClient,
        authenticated_headers: dict,
        patient: Patient,
        quiz_template: QuizTemplate
    ):
        """Test answer submission with invalid question ID."""
        # Initialize session
        init_response = client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": str(patient.id),
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )
        session_id = init_response.json()["session_id"]

        # Submit with invalid question
        response = client.post(
            "/api/v2/quiz/submit-answer",
            json={
                "session_id": session_id,
                "question_id": "invalid_question",
                "answer": "Test"
            },
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.api
    def test_complete_quiz_session_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict,
        patient: Patient,
        quiz_template: QuizTemplate
    ):
        """Test successful quiz session completion."""
        # Initialize session
        init_response = client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": str(patient.id),
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )
        session_id = init_response.json()["session_id"]

        # Submit all answers
        client.post(
            "/api/v2/quiz/submit-answer",
            json={
                "session_id": session_id,
                "question_id": "q1",
                "answer": "Good"
            },
            headers=authenticated_headers
        )

        client.post(
            "/api/v2/quiz/submit-answer",
            json={
                "session_id": session_id,
                "question_id": "q2",
                "answer": "7"
            },
            headers=authenticated_headers
        )

        # Complete session
        response = client.post(
            f"/api/v2/quiz/complete/{session_id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "completed"
        assert data["completed_at"] is not None

        # Verify in database
        session = db.query(QuizSession).filter(
            QuizSession.id == session_id
        ).first()
        assert session.status == "completed"
        assert session.completed_at is not None

    @pytest.mark.api
    def test_resume_quiz_session_success(
        self,
        client: TestClient,
        authenticated_headers: dict,
        patient: Patient,
        quiz_template: QuizTemplate
    ):
        """Test resuming an in-progress quiz session."""
        # Initialize session and submit one answer
        init_response = client.post(
            "/api/v2/quiz/initialize",
            json={
                "patient_id": str(patient.id),
                "template_id": str(quiz_template.id)
            },
            headers=authenticated_headers
        )

        session_id = init_response.json()["session_id"]

        client.post(
            "/api/v2/quiz/submit-answer",
            json={
                "session_id": session_id,
                "question_id": "q1",
                "answer": "Good"
            },
            headers=authenticated_headers
        )

        # Resume session
        response = client.get(
            f"/api/v2/quiz/resume/{patient.id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["session_id"] == session_id
        assert data["current_question"] == 1
        assert data["answers_count"] == 1

    @pytest.mark.api
    def test_resume_quiz_session_no_active_session(
        self,
        client: TestClient,
        authenticated_headers: dict,
        patient: Patient
    ):
        """Test resume with no active session."""
        response = client.get(
            f"/api/v2/quiz/resume/{patient.id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestQuizTemplateEndpoints:
    """Test quiz template endpoints."""

    @pytest.mark.api
    def test_list_quiz_templates_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict
    ):
        """Test listing active quiz templates."""
        # Create templates
        for i in range(3):
            template = QuizTemplate(
                name=f"Template {i}",
                version="1.0",
                is_active=True,
                questions={"questions": []}
            )
            db.add(template)
        db.commit()

        # Get templates
        response = client.get(
            "/api/v2/quiz/templates",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) >= 3
        assert all(t["is_active"] for t in data)

    @pytest.mark.api
    def test_get_quiz_template_by_id_success(
        self,
        client: TestClient,
        db: Session,
        authenticated_headers: dict
    ):
        """Test getting specific quiz template."""
        template = QuizTemplate(
            name="Specific Template",
            version="1.0",
            is_active=True,
            questions={"questions": [{"id": "q1", "text": "Test"}]}
        )
        db.add(template)
        db.commit()
        db.refresh(template)

        response = client.get(
            f"/api/v2/quiz/templates/{template.id}",
            headers=authenticated_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(template.id)
        assert data["name"] == "Specific Template"
        assert "questions" in data


@pytest.fixture
def authenticated_headers(client: TestClient, db: Session):
    """Create authenticated headers for testing."""
    return {
        "Authorization": "Bearer test-token",
        "X-Session-ID": "test-session-id"
    }
