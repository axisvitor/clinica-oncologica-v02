"""
Comprehensive API tests for quiz endpoints.

Tests all quiz-related HTTP endpoints:
- Quiz template CRUD operations
- Quiz session management endpoints
- Quiz response submission endpoints
- Quiz analytics and reporting endpoints
- Error handling and validation
- Authentication and authorization
"""

import pytest
import json
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Dict, Any

from fastapi.testclient import TestClient
from fastapi import status

from app.schemas.quiz import (
    QuizTemplateCreate, QuizQuestion, QuestionType, ValidationRule, QuizOption,
    QuizResponseCreate, QuizSessionCreate
)


class TestQuizTemplateEndpoints:
    """Test cases for quiz template API endpoints."""

    @pytest.fixture
    def sample_quiz_questions(self):
        """Sample quiz questions for testing."""
        return [
            {
                "id": "mood_assessment",
                "text": "How would you rate your overall mood today?",
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
                "text": "Which side effects are you experiencing?",
                "type": "multiple_choice",
                "options": [
                    {"id": "nausea", "value": "Nausea"},
                    {"id": "fatigue", "value": "Fatigue"},
                    {"id": "headache", "value": "Headache"},
                    {"id": "none", "value": "None"}
                ],
                "required": False
            }
        ]

    @pytest.fixture
    def valid_template_data(self, sample_quiz_questions):
        """Valid quiz template data for testing."""
        return {
            "name": "Patient Health Assessment",
            "version": "1.0",
            "questions": sample_quiz_questions,
            "is_active": True
        }

    def test_create_quiz_template_success(self, test_client, auth_headers, doctor_a_credentials,
                                        valid_template_data):
        """Test successful quiz template creation."""
        # Act
        response = test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data,
            headers=auth_headers(doctor_a_credentials)
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == valid_template_data["name"]
        assert data["version"] == valid_template_data["version"]
        assert len(data["questions"]) == len(valid_template_data["questions"])
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_quiz_template_invalid_data(self, test_client, auth_headers, doctor_a_credentials):
        """Test quiz template creation with invalid data."""
        # Test empty name
        invalid_data = {
            "name": "",
            "version": "1.0",
            "questions": [],
            "is_active": True
        }

        response = test_client.post(
            "/api/v1/quiz/templates",
            json=invalid_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name cannot be empty" in response.json()["detail"]

    def test_create_quiz_template_no_questions(self, test_client, auth_headers, doctor_a_credentials):
        """Test quiz template creation with no questions."""
        invalid_data = {
            "name": "Empty Template",
            "version": "1.0",
            "questions": [],
            "is_active": True
        }

        response = test_client.post(
            "/api/v1/quiz/templates",
            json=invalid_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "at least one question" in response.json()["detail"]

    def test_create_quiz_template_duplicate(self, test_client, auth_headers, doctor_a_credentials,
                                          valid_template_data):
        """Test quiz template creation with duplicate name and version."""
        # Create first template
        response1 = test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to create duplicate
        response2 = test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response2.json()["detail"]

    def test_get_quiz_templates(self, test_client, auth_headers, doctor_a_credentials):
        """Test getting list of quiz templates."""
        response = test_client.get(
            "/api/v1/quiz/templates",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert isinstance(data["items"], list)

    def test_get_quiz_templates_with_pagination(self, test_client, auth_headers, doctor_a_credentials):
        """Test getting quiz templates with pagination parameters."""
        response = test_client.get(
            "/api/v1/quiz/templates?skip=0&limit=5",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["size"] == 5

    def test_get_quiz_template_by_id(self, test_client, auth_headers, doctor_a_credentials,
                                   valid_template_data):
        """Test getting a specific quiz template by ID."""
        # Create template first
        create_response = test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        template_id = create_response.json()["id"]

        # Get template by ID
        response = test_client.get(
            f"/api/v1/quiz/templates/{template_id}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == template_id
        assert data["name"] == valid_template_data["name"]

    def test_get_quiz_template_not_found(self, test_client, auth_headers, doctor_a_credentials):
        """Test getting non-existent quiz template."""
        fake_id = str(uuid4())
        response = test_client.get(
            f"/api/v1/quiz/templates/{fake_id}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_quiz_template(self, test_client, auth_headers, doctor_a_credentials,
                                valid_template_data):
        """Test updating a quiz template."""
        # Create template first
        create_response = test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        template_id = create_response.json()["id"]

        # Update template
        update_data = {
            "name": "Updated Assessment",
            "is_active": False
        }

        response = test_client.put(
            f"/api/v1/quiz/templates/{template_id}",
            json=update_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Assessment"
        assert data["is_active"] is False

    def test_delete_quiz_template(self, test_client, auth_headers, doctor_a_credentials,
                                valid_template_data):
        """Test deleting (deactivating) a quiz template."""
        # Create template first
        create_response = test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        template_id = create_response.json()["id"]

        # Delete template
        response = test_client.delete(
            f"/api/v1/quiz/templates/{template_id}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify template is deactivated
        get_response = test_client.get(
            f"/api/v1/quiz/templates/{template_id}",
            headers=auth_headers(doctor_a_credentials)
        )
        assert get_response.json()["is_active"] is False

    def test_get_template_by_name(self, test_client, auth_headers, doctor_a_credentials,
                                valid_template_data):
        """Test getting template by name."""
        # Create template first
        test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data,
            headers=auth_headers(doctor_a_credentials)
        )

        # Get by name
        template_name = valid_template_data["name"]
        response = test_client.get(
            f"/api/v1/quiz/templates/name/{template_name}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == template_name

    def test_validate_template_questions(self, test_client, auth_headers, doctor_a_credentials,
                                       sample_quiz_questions):
        """Test template validation endpoint."""
        response = test_client.post(
            "/api/v1/quiz/templates/validate",
            json=sample_quiz_questions,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "is_valid" in data
        assert "errors" in data
        assert "warnings" in data
        assert data["is_valid"] is True

    def test_create_template_version(self, test_client, auth_headers, doctor_a_credentials,
                                   valid_template_data):
        """Test creating a new version of existing template."""
        # Create original template
        create_response = test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        template_id = create_response.json()["id"]

        # Create new version
        response = test_client.post(
            f"/api/v1/quiz/templates/{template_id}/versions?new_version=2.0",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["version"] == "2.0"
        assert data["name"] == valid_template_data["name"]

    def test_unauthorized_template_access(self, test_client, valid_template_data):
        """Test accessing template endpoints without authentication."""
        response = test_client.post(
            "/api/v1/quiz/templates",
            json=valid_template_data
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestQuizSessionEndpoints:
    """Test cases for quiz session API endpoints."""

    @pytest.fixture
    def created_template_id(self, test_client, auth_headers, doctor_a_credentials):
        """Create a template and return its ID for session tests."""
        template_data = {
            "name": "Session Test Template",
            "version": "1.0",
            "questions": [
                {
                    "id": "test_question",
                    "text": "Test question?",
                    "type": "yes_no",
                    "options": [
                        {"id": "yes", "value": "Yes"},
                        {"id": "no", "value": "No"}
                    ],
                    "required": True
                }
            ],
            "is_active": True
        }

        response = test_client.post(
            "/api/v1/quiz/templates",
            json=template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        return response.json()["id"]

    def test_start_quiz_session_success(self, test_client, auth_headers, doctor_a_credentials,
                                      created_template_id):
        """Test successful quiz session start."""
        session_data = {
            "patient_id": str(uuid4()),
            "quiz_template_id": created_template_id
        }

        response = test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["patient_id"] == session_data["patient_id"]
        assert data["quiz_template_id"] == created_template_id
        assert data["status"] == "started"
        assert "id" in data
        assert "started_at" in data

    def test_start_quiz_session_invalid_data(self, test_client, auth_headers, doctor_a_credentials):
        """Test session start with invalid data."""
        invalid_data = {
            "patient_id": "",  # Empty patient ID
            "quiz_template_id": str(uuid4())
        }

        response = test_client.post(
            "/api/v1/quiz/sessions",
            json=invalid_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_start_quiz_session_nonexistent_template(self, test_client, auth_headers,
                                                   doctor_a_credentials):
        """Test session start with non-existent template."""
        session_data = {
            "patient_id": str(uuid4()),
            "quiz_template_id": str(uuid4())  # Non-existent template
        }

        response = test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_active_session(self, test_client, auth_headers, doctor_a_credentials,
                              created_template_id):
        """Test getting active session for a patient."""
        patient_id = str(uuid4())

        # Start session
        session_data = {
            "patient_id": patient_id,
            "quiz_template_id": created_template_id
        }

        start_response = test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )
        assert start_response.status_code == status.HTTP_201_CREATED

        # Get active session
        response = test_client.get(
            f"/api/v1/quiz/sessions/active/{patient_id}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["patient_id"] == patient_id
        assert data["status"] == "started"

    def test_get_session_by_id(self, test_client, auth_headers, doctor_a_credentials,
                             created_template_id):
        """Test getting session by ID."""
        # Start session
        session_data = {
            "patient_id": str(uuid4()),
            "quiz_template_id": created_template_id
        }

        start_response = test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )
        session_id = start_response.json()["id"]

        # Get session by ID
        response = test_client.get(
            f"/api/v1/quiz/sessions/{session_id}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == session_id

    def test_advance_session(self, test_client, auth_headers, doctor_a_credentials,
                           created_template_id):
        """Test advancing session to next question."""
        # Start session
        session_data = {
            "patient_id": str(uuid4()),
            "quiz_template_id": created_template_id
        }

        start_response = test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )
        session_id = start_response.json()["id"]

        # Advance session
        response = test_client.put(
            f"/api/v1/quiz/sessions/{session_id}/advance",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["current_question"] >= 0

    def test_complete_session(self, test_client, auth_headers, doctor_a_credentials,
                            created_template_id):
        """Test completing a quiz session."""
        # Start session
        session_data = {
            "patient_id": str(uuid4()),
            "quiz_template_id": created_template_id
        }

        start_response = test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )
        session_id = start_response.json()["id"]

        # Complete session
        response = test_client.put(
            f"/api/v1/quiz/sessions/{session_id}/complete",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "completed"
        assert "completed_at" in data

    def test_get_all_sessions(self, test_client, auth_headers, doctor_a_credentials):
        """Test getting all sessions with pagination."""
        response = test_client.get(
            "/api/v1/quiz/sessions?skip=0&limit=10",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_get_patient_sessions(self, test_client, auth_headers, doctor_a_credentials,
                                created_template_id):
        """Test getting sessions for a specific patient."""
        patient_id = str(uuid4())

        # Start session for patient
        session_data = {
            "patient_id": patient_id,
            "quiz_template_id": created_template_id
        }

        test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )

        # Get patient sessions
        response = test_client.get(
            f"/api/v1/quiz/sessions/patient/{patient_id}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1


class TestQuizResponseEndpoints:
    """Test cases for quiz response API endpoints."""

    @pytest.fixture
    def created_session_data(self, test_client, auth_headers, doctor_a_credentials):
        """Create a session and return session data for response tests."""
        # Create template
        template_data = {
            "name": "Response Test Template",
            "version": "1.0",
            "questions": [
                {
                    "id": "test_question",
                    "text": "How are you feeling?",
                    "type": "scale",
                    "options": [],
                    "validation_rules": [{"type": "range", "min": 1, "max": 10}],
                    "required": True
                }
            ],
            "is_active": True
        }

        template_response = test_client.post(
            "/api/v1/quiz/templates",
            json=template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        template_id = template_response.json()["id"]

        # Create session
        patient_id = str(uuid4())
        session_data = {
            "patient_id": patient_id,
            "quiz_template_id": template_id
        }

        session_response = test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )

        return {
            "template_id": template_id,
            "session_id": session_response.json()["id"],
            "patient_id": patient_id
        }

    def test_create_quiz_response_success(self, test_client, auth_headers, doctor_a_credentials,
                                        created_session_data):
        """Test successful quiz response creation."""
        response_data = {
            "patient_id": created_session_data["patient_id"],
            "quiz_template_id": created_session_data["template_id"],
            "question_id": "test_question",
            "response_type": "scale",
            "response_value": "8",
            "response_metadata": {"completion_time": 30}
        }

        response = test_client.post(
            "/api/v1/quiz/responses",
            json=response_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["patient_id"] == response_data["patient_id"]
        assert data["question_id"] == response_data["question_id"]
        assert data["response_value"] == response_data["response_value"]
        assert "id" in data
        assert "responded_at" in data

    def test_create_quiz_response_invalid_data(self, test_client, auth_headers,
                                             doctor_a_credentials):
        """Test quiz response creation with invalid data."""
        invalid_data = {
            "patient_id": "",  # Empty patient ID
            "quiz_template_id": str(uuid4()),
            "question_id": "test_question",
            "response_type": "scale",
            "response_value": "8"
        }

        response = test_client.post(
            "/api/v1/quiz/responses",
            json=invalid_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_quiz_response_invalid_value(self, test_client, auth_headers,
                                              doctor_a_credentials, created_session_data):
        """Test quiz response creation with invalid response value."""
        response_data = {
            "patient_id": created_session_data["patient_id"],
            "quiz_template_id": created_session_data["template_id"],
            "question_id": "test_question",
            "response_type": "scale",
            "response_value": "15",  # Out of range (1-10)
            "response_metadata": {}
        }

        response = test_client.post(
            "/api/v1/quiz/responses",
            json=response_data,
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "validation failed" in response.json()["detail"].lower()

    def test_get_patient_responses(self, test_client, auth_headers, doctor_a_credentials,
                                 created_session_data):
        """Test getting responses for a patient."""
        # Create a response first
        response_data = {
            "patient_id": created_session_data["patient_id"],
            "quiz_template_id": created_session_data["template_id"],
            "question_id": "test_question",
            "response_type": "scale",
            "response_value": "7"
        }

        test_client.post(
            "/api/v1/quiz/responses",
            json=response_data,
            headers=auth_headers(doctor_a_credentials)
        )

        # Get patient responses
        response = test_client.get(
            f"/api/v1/quiz/responses/patient/{created_session_data['patient_id']}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_get_template_responses(self, test_client, auth_headers, doctor_a_credentials,
                                  created_session_data):
        """Test getting responses for a template."""
        # Create a response first
        response_data = {
            "patient_id": created_session_data["patient_id"],
            "quiz_template_id": created_session_data["template_id"],
            "question_id": "test_question",
            "response_type": "scale",
            "response_value": "6"
        }

        test_client.post(
            "/api/v1/quiz/responses",
            json=response_data,
            headers=auth_headers(doctor_a_credentials)
        )

        # Get template responses
        response = test_client.get(
            f"/api/v1/quiz/responses/template/{created_session_data['template_id']}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_submit_response_via_session(self, test_client, auth_headers, doctor_a_credentials,
                                       created_session_data):
        """Test submitting response via session endpoint."""
        response = test_client.post(
            f"/api/v1/quiz/sessions/{created_session_data['session_id']}/submit",
            json={
                "question_id": "test_question",
                "answer": "9",
                "response_metadata": {"device": "mobile"}
            },
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["question_id"] == "test_question"
        assert data["response_value"] == "9"


class TestQuizAnalyticsEndpoints:
    """Test cases for quiz analytics API endpoints."""

    @pytest.fixture
    def analytics_test_data(self, test_client, auth_headers, doctor_a_credentials):
        """Create test data for analytics tests."""
        # Create template with multiple questions
        template_data = {
            "name": "Analytics Test Template",
            "version": "1.0",
            "questions": [
                {
                    "id": "mood",
                    "text": "Rate your mood",
                    "type": "scale",
                    "validation_rules": [{"type": "range", "min": 1, "max": 10}],
                    "required": True
                },
                {
                    "id": "energy",
                    "text": "Rate your energy level",
                    "type": "scale",
                    "validation_rules": [{"type": "range", "min": 1, "max": 10}],
                    "required": True
                }
            ],
            "is_active": True
        }

        template_response = test_client.post(
            "/api/v1/quiz/templates",
            json=template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        template_id = template_response.json()["id"]

        # Create sessions and responses
        patients = [str(uuid4()) for _ in range(3)]
        sessions = []

        for patient_id in patients:
            # Create session
            session_data = {
                "patient_id": patient_id,
                "quiz_template_id": template_id
            }

            session_response = test_client.post(
                "/api/v1/quiz/sessions",
                json=session_data,
                headers=auth_headers(doctor_a_credentials)
            )
            sessions.append(session_response.json()["id"])

            # Create responses
            for question_id in ["mood", "energy"]:
                response_data = {
                    "patient_id": patient_id,
                    "quiz_template_id": template_id,
                    "question_id": question_id,
                    "response_type": "scale",
                    "response_value": str(7)  # Fixed value for testing
                }

                test_client.post(
                    "/api/v1/quiz/responses",
                    json=response_data,
                    headers=auth_headers(doctor_a_credentials)
                )

        return {
            "template_id": template_id,
            "patient_ids": patients,
            "session_ids": sessions
        }

    def test_get_template_analytics(self, test_client, auth_headers, doctor_a_credentials,
                                  analytics_test_data):
        """Test getting analytics for a quiz template."""
        template_id = analytics_test_data["template_id"]

        response = test_client.get(
            f"/api/v1/quiz/analytics/template/{template_id}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "quiz_template_id" in data
        assert "total_responses" in data
        assert "completion_rate" in data
        assert "question_analytics" in data
        assert data["quiz_template_id"] == template_id

    def test_get_patient_analytics(self, test_client, auth_headers, doctor_a_credentials,
                                 analytics_test_data):
        """Test getting analytics for a patient."""
        patient_id = analytics_test_data["patient_ids"][0]

        response = test_client.get(
            f"/api/v1/quiz/analytics/patient/{patient_id}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "patient_id" in data
        assert "total_quizzes_completed" in data
        assert "completion_rate" in data
        assert "recent_activity" in data
        assert data["patient_id"] == patient_id

    def test_get_summary_analytics(self, test_client, auth_headers, doctor_a_credentials):
        """Test getting summary analytics."""
        response = test_client.get(
            "/api/v1/quiz/analytics/summary",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_templates" in data
        assert "total_responses" in data
        assert "total_sessions" in data
        assert "completion_rate" in data

    def test_get_summary_analytics_with_date_range(self, test_client, auth_headers,
                                                  doctor_a_credentials):
        """Test getting summary analytics with date range."""
        date_from = "2024-01-01T00:00:00Z"
        date_to = "2024-12-31T23:59:59Z"

        response = test_client.get(
            f"/api/v1/quiz/analytics/summary?date_from={date_from}&date_to={date_to}",
            headers=auth_headers(doctor_a_credentials)
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["date_from"] == date_from
        assert data["date_to"] == date_to


class TestQuizEndpointSecurity:
    """Test cases for quiz endpoint security and authorization."""

    def test_unauthorized_access(self, test_client):
        """Test accessing quiz endpoints without authentication."""
        endpoints = [
            "/api/v1/quiz/templates",
            "/api/v1/quiz/sessions",
            "/api/v1/quiz/responses",
            "/api/v1/quiz/analytics/summary"
        ]

        for endpoint in endpoints:
            response = test_client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_token_access(self, test_client, auth_headers, expired_token_credentials):
        """Test accessing quiz endpoints with expired token."""
        response = test_client.get(
            "/api/v1/quiz/templates",
            headers=auth_headers(expired_token_credentials)
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_malformed_token_access(self, test_client):
        """Test accessing quiz endpoints with malformed token."""
        headers = {"Authorization": "Bearer invalid_token"}

        response = test_client.get(
            "/api/v1/quiz/templates",
            headers=headers
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cross_patient_data_access(self, test_client, auth_headers,
                                     doctor_a_credentials, doctor_b_credentials):
        """Test that doctors cannot access other doctors' patient data."""
        # Doctor A creates a session for a patient
        patient_id = str(uuid4())

        # Create template as Doctor A
        template_data = {
            "name": "Security Test Template",
            "version": "1.0",
            "questions": [
                {
                    "id": "test_q",
                    "text": "Test?",
                    "type": "yes_no",
                    "options": [{"id": "yes", "value": "Yes"}],
                    "required": True
                }
            ],
            "is_active": True
        }

        template_response = test_client.post(
            "/api/v1/quiz/templates",
            json=template_data,
            headers=auth_headers(doctor_a_credentials)
        )
        template_id = template_response.json()["id"]

        # Create session as Doctor A
        session_data = {
            "patient_id": patient_id,
            "quiz_template_id": template_id
        }

        session_response = test_client.post(
            "/api/v1/quiz/sessions",
            json=session_data,
            headers=auth_headers(doctor_a_credentials)
        )
        assert session_response.status_code == status.HTTP_201_CREATED

        # Doctor B tries to access the patient's data
        response = test_client.get(
            f"/api/v1/quiz/responses/patient/{patient_id}",
            headers=auth_headers(doctor_b_credentials)
        )

        # Should be forbidden or return empty results based on RLS implementation
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK]
        if response.status_code == status.HTTP_200_OK:
            # If RLS is implemented, should return empty results
            data = response.json()
            assert len(data.get("items", [])) == 0


class TestQuizEndpointValidation:
    """Test cases for quiz endpoint input validation and error handling."""

    def test_invalid_uuid_parameters(self, test_client, auth_headers, doctor_a_credentials):
        """Test endpoints with invalid UUID parameters."""
        invalid_uuid = "not-a-uuid"

        endpoints = [
            f"/api/v1/quiz/templates/{invalid_uuid}",
            f"/api/v1/quiz/sessions/{invalid_uuid}",
            f"/api/v1/quiz/responses/patient/{invalid_uuid}",
            f"/api/v1/quiz/analytics/template/{invalid_uuid}"
        ]

        for endpoint in endpoints:
            response = test_client.get(
                endpoint,
                headers=auth_headers(doctor_a_credentials)
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_sql_injection_protection(self, test_client, auth_headers, doctor_a_credentials,
                                    security_test_payloads):
        """Test protection against SQL injection attempts."""
        for payload in security_test_payloads["sql_injection"]:
            # Test in template name search
            response = test_client.get(
                f"/api/v1/quiz/templates/name/{payload}",
                headers=auth_headers(doctor_a_credentials)
            )

            # Should return 404 or 400, not 500 (no SQL errors)
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]

    def test_xss_protection(self, test_client, auth_headers, doctor_a_credentials,
                          security_test_payloads):
        """Test protection against XSS attempts."""
        for payload in security_test_payloads["xss_payloads"]:
            template_data = {
                "name": payload,  # XSS payload in name
                "version": "1.0",
                "questions": [
                    {
                        "id": "test_q",
                        "text": "Test?",
                        "type": "yes_no",
                        "options": [{"id": "yes", "value": "Yes"}],
                        "required": True
                    }
                ],
                "is_active": True
            }

            response = test_client.post(
                "/api/v1/quiz/templates",
                json=template_data,
                headers=auth_headers(doctor_a_credentials)
            )

            # Should either reject the payload or sanitize it
            if response.status_code == status.HTTP_201_CREATED:
                # If accepted, verify XSS payload is sanitized
                data = response.json()
                assert_no_xss(data)

    def test_large_payload_handling(self, test_client, auth_headers, doctor_a_credentials):
        """Test handling of abnormally large payloads."""
        # Create template with very large question text
        large_text = "x" * 10000  # 10KB of text

        template_data = {
            "name": "Large Payload Test",
            "version": "1.0",
            "questions": [
                {
                    "id": "large_q",
                    "text": large_text,
                    "type": "open_text",
                    "required": True
                }
            ],
            "is_active": True
        }

        response = test_client.post(
            "/api/v1/quiz/templates",
            json=template_data,
            headers=auth_headers(doctor_a_credentials)
        )

        # Should handle large payloads gracefully
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        ]


def assert_no_xss(response_data: Any):
    """Assert response doesn't contain XSS indicators."""
    response_str = str(response_data)
    xss_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']
    for pattern in xss_patterns:
        assert pattern not in response_str, f"Potential XSS detected: {pattern}"