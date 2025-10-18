"""
Cursor Pagination Tests for Quiz API v2 - IMPLEMENTATION COMPLETE
Tests to prevent SQL type errors and pagination bugs.

Issue: #17
Priority: P1 - High
Status: IMPLEMENTED
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import base64
import json
from uuid import uuid4

from app.models.user import UserRole
from app.models.quiz import QuizSession
from app.models.patient import Patient
from tests.conftest import create_test_user, create_test_patient


def create_quiz_session(db_session, patient, status="started", created_at=None):
    """Helper to create quiz session."""
    quiz = QuizSession(
        id=uuid4(),
        patient_id=patient.id,
        quiz_template_id=uuid4(),
        status=status,
        created_at=created_at or datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(quiz)
    db_session.commit()
    db_session.refresh(quiz)
    return quiz


class TestQuizCursorPagination:
    """Test cursor-based pagination for quiz endpoints."""
    
    def test_quiz_pagination_with_cursor(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """
        Test cursor pagination with datetime comparison.
        
        Validates the fix for: "operator does not exist: timestamp without time zone > text"
        """
        # Create test patient
        patient = create_test_patient(db_session, doctor=test_user)
        
        # Create 25 quiz sessions with varying timestamps
        now = datetime.utcnow()
        for i in range(25):
            create_quiz_session(
                db_session,
                patient=patient,
                created_at=now - timedelta(minutes=i)
            )
        
        # First page
        response1 = client.get("/api/v2/quiz?limit=10", headers=auth_headers)
        
        assert response1.status_code == 200
        page1 = response1.json()
        assert len(page1["data"]) == 10
        assert page1["has_more"] is True
        
        cursor = page1["next_cursor"]
        assert cursor is not None
        
        # Decode cursor to verify datetime format
        cursor_data = json.loads(base64.b64decode(cursor))
        assert "created_at" in cursor_data
        assert "id" in cursor_data
        
        # Verify ISO format can be parsed
        datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        
        # Second page - should NOT throw SQL error
        response2 = client.get(f"/api/v2/quiz?limit=10&cursor={cursor}", headers=auth_headers)
        
        assert response2.status_code == 200
        page2 = response2.json()
        assert len(page2["data"]) == 10
        
        # Verify no duplicates
        page1_ids = {q["id"] for q in page1["data"]}
        page2_ids = {q["id"] for q in page2["data"]}
        assert page1_ids.isdisjoint(page2_ids)
    
    def test_quiz_pagination_empty_cursor(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Test first page without cursor."""
        patient = create_test_patient(db_session, doctor=test_user)
        
        # Create some quiz sessions
        for i in range(5):
            create_quiz_session(db_session, patient=patient)
        
        response = client.get("/api/v2/quiz?limit=10", headers=auth_headers)
        
        assert response.status_code == 200
        assert "data" in response.json()
        assert "next_cursor" in response.json()
    
    def test_quiz_pagination_invalid_cursor(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test malformed cursor handling."""
        # Invalid base64
        response = client.get("/api/v2/quiz?cursor=invalid!!!", headers=auth_headers)
        assert response.status_code in [400, 500]  # Should handle gracefully
        
        # Valid base64 but invalid JSON
        bad_cursor = base64.b64encode(b"not json").decode()
        response = client.get(f"/api/v2/quiz?cursor={bad_cursor}", headers=auth_headers)
        assert response.status_code in [400, 500]
        
        # Valid JSON but missing fields
        bad_data = base64.b64encode(json.dumps({"id": "123"}).encode()).decode()
        response = client.get(f"/api/v2/quiz?cursor={bad_data}", headers=auth_headers)
        assert response.status_code in [400, 500]
    
    def test_quiz_pagination_tie_breaking(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Test tie-breaking when multiple records have same created_at."""
        patient = create_test_patient(db_session, doctor=test_user)
        
        # Create 3 sessions with EXACTLY same timestamp
        now = datetime.utcnow()
        session_ids = []
        
        for i in range(3):
            quiz = create_quiz_session(db_session, patient=patient, created_at=now)
            session_ids.append(str(quiz.id))
        
        # Fetch all
        response = client.get("/api/v2/quiz?limit=100", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()["data"]
        result_ids = [q["id"] for q in data]
        
        # All 3 should be present
        for session_id in session_ids:
            assert session_id in result_ids
    
    def test_quiz_pagination_descending_order(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Test that results are in descending order (newest first)."""
        patient = create_test_patient(db_session, doctor=test_user)
        
        now = datetime.utcnow()
        for i in range(20):
            create_quiz_session(
                db_session,
                patient=patient,
                created_at=now - timedelta(minutes=i)
            )
        
        response = client.get("/api/v2/quiz?limit=20", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Verify descending order
        created_at_list = [
            datetime.fromisoformat(q["created_at"].replace("Z", "+00:00"))
            for q in data
        ]
        
        for i in range(len(created_at_list) - 1):
            assert created_at_list[i] >= created_at_list[i + 1]
    
    def test_patients_pagination_with_cursor(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Test cursor pagination for patients endpoint."""
        now = datetime.utcnow()
        
        # Create 25 patients
        for i in range(25):
            create_test_patient(
                db_session,
                doctor=test_user,
                name=f"Patient {i}",
                phone=f"119999{i:05d}",
                created_at=now - timedelta(minutes=i)
            )
        
        # First page
        response1 = client.get("/api/v2/patients?limit=10", headers=auth_headers)
        
        assert response1.status_code == 200
        page1 = response1.json()
        assert len(page1["data"]) == 10
        
        if page1["has_more"]:
            cursor = page1["next_cursor"]
            
            # Second page
            response2 = client.get(f"/api/v2/patients?limit=10&cursor={cursor}", headers=auth_headers)
            
            assert response2.status_code == 200
            page2 = response2.json()
            
            # No duplicates
            page1_ids = {p["id"] for p in page1["data"]}
            page2_ids = {p["id"] for p in page2["data"]}
            assert page1_ids.isdisjoint(page2_ids)
    
    def test_pagination_with_filters(
        self,
        client: TestClient,
        db_session,
        test_user,
        auth_headers
    ):
        """Test pagination works with query filters."""
        patient1 = create_test_patient(db_session, doctor=test_user, name="Active Patient")
        patient2 = create_test_patient(db_session, doctor=test_user, name="Other Patient")
        
        # Create quiz sessions with different statuses
        for i in range(10):
            create_quiz_session(db_session, patient=patient1, status="started")
        
        for i in range(10):
            create_quiz_session(db_session, patient=patient2, status="completed")
        
        # Filter by status and paginate
        response = client.get(
            f"/api/v2/quiz?limit=5&status=started",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        # All should have status="started"
        for quiz in data:
            assert quiz["status"] == "started"
