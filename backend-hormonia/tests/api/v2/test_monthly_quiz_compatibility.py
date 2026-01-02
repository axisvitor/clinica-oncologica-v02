
import pytest
from uuid import uuid4
from datetime import datetime
import json
import base64
from fastapi.testclient import TestClient
from app.main import app
from app.models.quiz_template import QuizTemplate
from app.models.quiz_session import QuizSession
from app.api.v2.routers.monthly_quiz_operations.public import PUBLIC_PATIENT_ID

client = TestClient(app)

@pytest.fixture
def mock_quiz(db_session):
    # Create a mock quiz template
    quiz = QuizTemplate(
        id=uuid4(),
        name="Compatibility Test Quiz",
        category="monthly_quiz",
        version="1.0",
        questions=[
            {"id": "q1", "text": "Question 1", "type": "single_choice", "options": ["A", "B"]},
            {"id": "q2", "text": "Question 2", "type": "scale"}
        ],
        tags={"status": "published"}
    )
    db_session.add(quiz)
    db_session.commit()
    return quiz

def test_access_quiz_compatibility(db_session, mock_quiz):
    # Generate token
    token_data = {
        "quiz_id": str(mock_quiz.id),
        "exp": (datetime.now().timestamp() + 3600),
        "type": "quiz_access"
    }
    token = base64.b64encode(json.dumps(token_data).encode()).decode()

    # Call /access endpoint
    response = client.post(
        "/api/v2/monthly-quiz-public/access",
        json={"token": token}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify structure matches QuizSession
    assert "id" in data
    assert "quiz_session_id" in data
    assert data["quiz_session_id"] == data["id"]
    assert data["template_id"] == str(mock_quiz.id)
    assert data["patient_name"] == "Paciente"
    assert "questions" in data
    assert len(data["questions"]) == 2
    assert data["questions"][0]["text"] == "Question 1"

    # Verify Cookie
    assert "quiz_session_id" in response.cookies
    assert response.cookies["quiz_session_id"] == data["id"]

def test_recover_session_compatibility(db_session, mock_quiz):
    # Create session manually
    session = QuizSession(
        id=uuid4(),
        quiz_template_id=mock_quiz.id,
        patient_id=PUBLIC_PATIENT_ID,
        status="in_progress",
        started_at=datetime.now()
    )
    db_session.add(session)
    db_session.commit()

    # Call /session/active endpoint with cookie
    client.cookies.set("quiz_session_id", str(session.id))
    response = client.get("/api/v2/monthly-quiz-public/session/active")

    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(session.id)
    assert data["status"] == "in_progress"
    assert "questions" in data
    assert len(data["questions"]) == 2
