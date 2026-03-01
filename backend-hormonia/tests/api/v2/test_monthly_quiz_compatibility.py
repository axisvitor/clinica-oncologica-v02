
import pytest
import sqlite3
import uuid
from datetime import timedelta
from uuid import uuid4
from datetime import datetime

from app.models.quiz import QuizTemplate, QuizSession
from app.domain.quizzes.session import TokenManager

from app.utils.timezone import now_sao_paulo
sqlite3.register_adapter(uuid.UUID, lambda value: str(value))

@pytest.fixture(autouse=True)
def ensure_quiz_tables(db_session):
    QuizSession.__table__.drop(bind=db_session.bind, checkfirst=True)
    QuizTemplate.__table__.create(bind=db_session.bind, checkfirst=True)
    QuizSession.__table__.create(bind=db_session.bind, checkfirst=True)

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

def test_access_quiz_compatibility(client, db_session, mock_quiz):
    patient_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    session = QuizSession(
        id=uuid4(),
        quiz_template_id=mock_quiz.id,
        patient_id=patient_id,
        status="started",
        started_at=datetime.now(),
    )
    db_session.add(session)
    db_session.flush()
    session_id = session.id
    db_session.commit()

    # Generate token
    token_manager = TokenManager()
    token = token_manager.generate_token(
        patient_id=patient_id,
        quiz_template_id=mock_quiz.id,
        expires_at=now_sao_paulo() + timedelta(hours=1),
        session_id=session_id,
        token_type="quiz_access",
    )

    # Call canonical /access endpoint
    response = client.post(
        "/api/v2/quiz-extensions/access",
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


def test_access_quiz_canonical_quiz_extensions_path(client, db_session, mock_quiz):
    patient_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    session = QuizSession(
        id=uuid4(),
        quiz_template_id=mock_quiz.id,
        patient_id=patient_id,
        status="started",
        started_at=datetime.now(),
    )
    db_session.add(session)
    db_session.flush()
    session_id = session.id
    db_session.commit()

    token_manager = TokenManager()
    token = token_manager.generate_token(
        patient_id=patient_id,
        quiz_template_id=mock_quiz.id,
        expires_at=now_sao_paulo() + timedelta(hours=1),
        session_id=session_id,
        token_type="quiz_access",
    )

    response = client.post(
        "/api/v2/quiz-extensions/access",
        json={"token": token}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["template_id"] == str(mock_quiz.id)
    assert data["quiz_session_id"] == data["id"]


def test_monthly_quiz_alias_removed(client, db_session, mock_quiz):
    patient_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    session = QuizSession(
        id=uuid4(),
        quiz_template_id=mock_quiz.id,
        patient_id=patient_id,
        status="started",
        started_at=datetime.now(),
    )
    db_session.add(session)
    db_session.flush()
    session_id = session.id
    db_session.commit()

    token_manager = TokenManager()
    token = token_manager.generate_token(
        patient_id=patient_id,
        quiz_template_id=mock_quiz.id,
        expires_at=now_sao_paulo() + timedelta(hours=1),
        session_id=session_id,
        token_type="quiz_access",
    )

    response = client.post(
        "/api/v2/monthly-quiz-public/access",
        json={"token": token}
    )
    assert response.status_code == 404

    client.cookies.set("quiz_session_id", str(session_id))
    session_response = client.get("/api/v2/monthly-quiz-public/session/active")
    assert session_response.status_code == 404


def test_recover_session_compatibility(client, db_session, mock_quiz):
    patient_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    # Create session manually
    session = QuizSession(
        id=uuid4(),
        quiz_template_id=mock_quiz.id,
        patient_id=patient_id,
        status="started",
        started_at=datetime.now()
    )
    db_session.add(session)
    db_session.flush()
    session_id = session.id
    db_session.commit()

    # Call /session/active endpoint with cookie
    client.cookies.set("quiz_session_id", str(session_id))
    response = client.get("/api/v2/quiz-extensions/session/active")

    assert response.status_code == 200
    data = response.json()
    
    assert data["id"]
    assert data["quiz_session_id"] == data["id"]
    assert data["status"] == "started"
    assert "questions" in data
    assert len(data["questions"]) == 2
