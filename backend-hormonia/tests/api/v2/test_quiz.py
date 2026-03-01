"""
Tests for Quiz API v2
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient


class TestQuizV2:
    """Test suite for quiz v2 endpoints"""
    
    def test_list_quizzes_basic(self, client: TestClient, db: Session, auth_headers: dict):
        """Test basic quiz listing"""
        response = client.get("/api/v2/quiz/sessions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data
        assert isinstance(data["data"], list)
    
    def test_list_quizzes_with_pagination(self, client: TestClient, db: Session, auth_headers: dict):
        """Test quiz listing with pagination"""
        response = client.get(
            "/api/v2/quiz/sessions?limit=5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) <= 5
    
    def test_list_quizzes_filter_by_patient(self, client: TestClient, db: Session, auth_headers: dict):
        """Test quiz listing filtered by patient"""
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patient available for test")
        
        response = client.get(
            f"/api/v2/quiz/sessions?patient_id={patient.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for quiz in data["data"]:
            assert quiz["patient_id"] == str(patient.id)
    
    def test_list_quizzes_filter_by_status(self, client: TestClient, db: Session, auth_headers: dict):
        """Test quiz listing filtered by status"""
        response = client.get(
            "/api/v2/quiz/sessions?status=completed",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for quiz in data["data"]:
            assert quiz["status"] == "completed"
    
    def test_list_quizzes_with_eager_loading(self, client: TestClient, db: Session, auth_headers: dict):
        """Test quiz listing with eager loading"""
        response = client.get(
            "/api/v2/quiz/sessions?include=patient",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["data"]:
            quiz = data["data"][0]
            if quiz.get("patient"):
                assert "id" in quiz["patient"]
                assert "name" in quiz["patient"]
    
    def test_get_quiz_by_id(self, client: TestClient, db: Session, auth_headers: dict):
        """Test getting a single quiz"""
        quiz = db.query(QuizSession).first()
        if not quiz:
            pytest.skip("No quiz available for test")
        
        response = client.get(
            f"/api/v2/quiz/{quiz.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(quiz.id)
    
    def test_get_quiz_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting a non-existent quiz"""
        missing_quiz_id = uuid4()
        response = client.get(
            f"/api/v2/quiz/{missing_quiz_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_create_quiz(self, client: TestClient, db: Session, auth_headers: dict):
        """Test creating a new quiz"""
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patient available for test")
        
        # Criar template primeiro
        template = QuizTemplate(
            name="Test Template",
            version="1.0",
            questions=[{"id": "q1", "text": "Test question"}]
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        
        quiz_data = {
            "patient_id": str(patient.id),
            "quiz_template_id": str(template.id),
            "status": "started"
        }
        
        response = client.post(
            "/api/v2/quiz",
            json=quiz_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["patient_id"] == quiz_data["patient_id"]
        assert data["quiz_template_id"] == quiz_data["quiz_template_id"]
        assert data["status"] == quiz_data["status"]
    
    def test_create_quiz_duplicate(self, client: TestClient, db: Session, auth_headers: dict):
        """Test creating a duplicate quiz"""
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patient available for test")
        
        # Create first quiz
        quiz = QuizSession(
            patient_id=patient.id,
            month=2,
            year=2025,
            status="pending"
        )
        db.add(quiz)
        db.commit()
        
        # Try to create duplicate
        quiz_data = {
            "patient_id": patient.id,
            "month": 2,
            "year": 2025,
            "status": "pending"
        }
        
        response = client.post(
            "/api/v2/quiz",
            json=quiz_data,
            headers=auth_headers
        )
        
        assert response.status_code == 409
    
    def test_update_quiz(self, client: TestClient, db: Session, auth_headers: dict):
        """Test updating a quiz"""
        quiz = db.query(QuizSession).first()
        if not quiz:
            pytest.skip("No quiz available for test")
        
        update_data = {
            "status": "completed",
            "responses": {"q1": "answer1"}
        }
        
        response = client.patch(
            f"/api/v2/quiz/{quiz.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == update_data["status"]
    
    def test_delete_quiz(self, client: TestClient, db: Session, auth_headers: dict):
        """Test deleting a quiz"""
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patient available for test")
        
        # Create quiz
        quiz = QuizSession(
            patient_id=patient.id,
            month=3,
            year=2025,
            status="pending"
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        
        # Delete quiz
        response = client.delete(
            f"/api/v2/quiz/{quiz.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # Verify deletion
        deleted_quiz = db.query(QuizSession).filter(QuizSession.id == quiz.id).first()
        assert deleted_quiz is None
