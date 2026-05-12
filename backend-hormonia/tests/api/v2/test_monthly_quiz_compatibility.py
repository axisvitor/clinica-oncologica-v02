import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.middleware.csrf import get_csrf_token
from app.domain.quizzes.session import TokenManager
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.utils.timezone import now_sao_paulo
from tests.api.v2.security_boundary_helpers import create_message_ownership_boundary

sqlite3.register_adapter(uuid.UUID, lambda value: str(value))


@pytest.fixture(autouse=True)
def ensure_quiz_tables(db_session):
    if db_session.bind.dialect.name == "postgresql":
        statements = [
            "CREATE TABLE IF NOT EXISTS quiz_templates (id UUID PRIMARY KEY)",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS name VARCHAR(255) NOT NULL DEFAULT 'Compatibility Test Quiz'",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS version VARCHAR(50) NOT NULL DEFAULT '1.0'",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS questions JSONB NOT NULL DEFAULT '[]'::jsonb",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS category VARCHAR(100)",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS passing_score INTEGER",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS time_limit_minutes INTEGER",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS randomize_questions BOOLEAN",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS tags JSONB",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
            "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
            "CREATE TABLE IF NOT EXISTS quiz_sessions (id UUID PRIMARY KEY)",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS patient_id UUID",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS quiz_template_id UUID",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'started'",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS current_question INTEGER DEFAULT 0",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS total_questions INTEGER",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS answered_questions INTEGER DEFAULT 0",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS score NUMERIC(5, 2)",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS max_score NUMERIC(5, 2)",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS passed BOOLEAN",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT now()",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS expiration_date TIMESTAMPTZ",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS time_spent_seconds INTEGER",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS session_metadata JSONB DEFAULT '{}'::jsonb",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
            "ALTER TABLE quiz_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
            "CREATE TABLE IF NOT EXISTS quiz_responses (id UUID PRIMARY KEY)",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS patient_id UUID",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS quiz_template_id UUID",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS quiz_session_id UUID",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS question_id VARCHAR(100) NOT NULL DEFAULT 'q1'",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS question_text TEXT NOT NULL DEFAULT 'Compatibility question'",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS response_type VARCHAR(50) NOT NULL DEFAULT 'single_choice'",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS response_value JSONB",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS response_value_text_backup TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS response_metadata JSONB DEFAULT '{}'::jsonb",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS other_text TEXT",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS responded_at TIMESTAMPTZ NOT NULL DEFAULT now()",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
            "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ]
        for statement in statements:
            db_session.execute(text(statement))
        db_session.execute(text("DELETE FROM quiz_responses"))
        db_session.execute(text("DELETE FROM quiz_sessions"))
        db_session.execute(
            text("DELETE FROM quiz_templates WHERE name LIKE 'Compatibility Test Quiz%'")
        )
        db_session.commit()
        return

    QuizResponse.__table__.drop(bind=db_session.bind, checkfirst=True)
    QuizSession.__table__.drop(bind=db_session.bind, checkfirst=True)
    QuizTemplate.__table__.create(bind=db_session.bind, checkfirst=True)
    QuizSession.__table__.create(bind=db_session.bind, checkfirst=True)
    QuizResponse.__table__.create(bind=db_session.bind, checkfirst=True)


@pytest.fixture
def mock_quiz(db_session):
    quiz = QuizTemplate(
        id=uuid4(),
        name=f"Compatibility Test Quiz {uuid4().hex}",
        category="monthly_quiz",
        version="1.0",
        questions=[
            {"id": "q1", "text": "Question 1", "type": "single_choice", "options": ["A", "B"]},
            {"id": "q2", "text": "Question 2", "type": "scale"},
        ],
        tags={"status": "published"},
    )
    db_session.add(quiz)
    db_session.commit()
    db_session.refresh(quiz)
    return quiz


def _create_started_link_session(db_session, mock_quiz, *, patient_id=None, expires_at=None):
    if patient_id is None:
        patient_id = create_message_ownership_boundary(db_session).patient_a.id
    expires_at = expires_at or (now_sao_paulo() + timedelta(hours=1))
    session = QuizSession(
        id=uuid4(),
        quiz_template_id=mock_quiz.id,
        patient_id=patient_id,
        status="started",
        started_at=now_sao_paulo(),
        expiration_date=expires_at,
        session_metadata={},
    )
    db_session.add(session)
    db_session.flush()

    token_manager = TokenManager()
    token = token_manager.generate_token(
        patient_id=patient_id,
        quiz_template_id=mock_quiz.id,
        expires_at=expires_at,
        session_id=session.id,
        token_type="quiz_access",
    )
    session.session_metadata = {
        "token_hash": token_manager.hash_token(token),
        "expires_at": expires_at.isoformat(),
        "link_status": "active",
    }
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session, token


def _response_count(db_session, session_id) -> int:
    db_session.expire_all()
    return (
        db_session.query(QuizResponse)
        .filter(QuizResponse.quiz_session_id == session_id)
        .count()
    )


def _get_response(db_session, session_id, question_id="q1"):
    db_session.expire_all()
    return (
        db_session.query(QuizResponse)
        .filter(
            QuizResponse.quiz_session_id == session_id,
            QuizResponse.question_id == question_id,
        )
        .one()
    )


def _access(client, token):
    return client.post("/api/v2/quiz-extensions/access", json={"token": token})


def _submit(client, question_id="q1", value="A", **kwargs):
    return client.post(
        "/api/v2/quiz-extensions/submit",
        json={"question_id": question_id, "response_value": value},
        **kwargs,
    )


def _quiz_cookie_header(*, session_id=None, state=None):
    csrf_token = get_csrf_token()
    cookies = [f"csrf_token={csrf_token}"]
    if session_id is not None:
        cookies.append(f"quiz_session_id={session_id}")
    if state is not None:
        cookies.append(f"quiz_session_state={state}")
    return {"cookie": "; ".join(cookies), "X-CSRF-Token": csrf_token}


def test_access_quiz_compatibility_sets_legacy_and_signed_state_cookies(
    client, db_session, mock_quiz
):
    session, token = _create_started_link_session(db_session, mock_quiz)

    response = _access(client, token)

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["id"] == str(session.id)
    assert data["quiz_session_id"] == data["id"]
    assert data["template_id"] == str(mock_quiz.id)
    assert data["patient_name"] == "Paciente"
    assert "questions" in data
    assert len(data["questions"]) == 2
    assert data["questions"][0]["text"] == "Question 1"

    assert response.cookies["quiz_session_id"] == data["id"]
    assert "quiz_session_state" in response.cookies
    assert response.cookies["quiz_session_state"] != response.cookies["quiz_session_id"]
    set_cookie = "; ".join(response.headers.get_list("set-cookie"))
    assert "quiz_session_id=" in set_cookie
    assert "quiz_session_state=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Max-Age=" in set_cookie


def test_access_quiz_canonical_quiz_extensions_path(client, db_session, mock_quiz):
    _session, token = _create_started_link_session(db_session, mock_quiz)

    response = _access(client, token)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["template_id"] == str(mock_quiz.id)
    assert data["quiz_session_id"] == data["id"]
    assert "quiz_session_state" in response.cookies


def test_monthly_quiz_alias_removed(client, db_session, mock_quiz):
    session, token = _create_started_link_session(db_session, mock_quiz)

    response = client.post("/api/v2/monthly-quiz-public/access", json={"token": token})
    assert response.status_code == 404

    client.cookies.set("quiz_session_id", str(session.id))
    session_response = client.get("/api/v2/monthly-quiz-public/session/active")
    assert session_response.status_code == 404


def test_recover_session_compatibility_requires_signed_state_after_access(
    client, db_session, mock_quiz
):
    session, token = _create_started_link_session(db_session, mock_quiz)
    access_response = _access(client, token)
    assert access_response.status_code == 200, access_response.text

    response = client.get("/api/v2/quiz-extensions/session/active")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == str(session.id)
    assert data["quiz_session_id"] == data["id"]
    assert data["status"] == "started"
    returned_expiry = datetime.fromisoformat(data["expires_at"])
    session_expiry = session.expiration_date
    assert abs(
        (
            returned_expiry.astimezone(timezone.utc)
            - session_expiry.astimezone(timezone.utc)
        ).total_seconds()
    ) < 1
    assert "questions" in data
    assert len(data["questions"]) == 2


def test_signed_state_submit_writes_and_updates_expected_response(
    client, db_session, mock_quiz
):
    session, token = _create_started_link_session(db_session, mock_quiz)
    access_response = _access(client, token)
    assert access_response.status_code == 200, access_response.text

    post_cookie_header = _quiz_cookie_header(
        session_id=access_response.cookies["quiz_session_id"],
        state=access_response.cookies["quiz_session_state"],
    )
    first_submit = _submit(client, value="A", headers=post_cookie_header)
    assert first_submit.status_code == 200, first_submit.text
    assert first_submit.json()["success"] is True
    assert _response_count(db_session, session.id) == 1
    saved = _get_response(db_session, session.id)
    assert saved.response_value == {"text": "A"}
    assert saved.response_value_text_backup == "A"

    second_submit = _submit(client, value="B", headers=post_cookie_header)
    assert second_submit.status_code == 200, second_submit.text
    assert _response_count(db_session, session.id) == 1
    updated = _get_response(db_session, session.id)
    assert updated.response_value == {"text": "B"}
    assert updated.response_value_text_backup == "B"


def test_raw_session_cookie_only_fails_recovery_and_submit_without_response_write(
    client, db_session, mock_quiz
):
    session, _token = _create_started_link_session(db_session, mock_quiz)
    client.cookies.set("quiz_session_id", str(session.id))

    active_response = client.get("/api/v2/quiz-extensions/session/active")
    submit_response = _submit(
        client,
        headers=_quiz_cookie_header(session_id=session.id),
    )

    assert active_response.status_code == 401
    assert submit_response.status_code == 401
    assert _response_count(db_session, session.id) == 0


def test_forged_state_cookie_fails_without_response_write(client, db_session, mock_quiz):
    session, token = _create_started_link_session(db_session, mock_quiz)
    access_response = _access(client, token)
    assert access_response.status_code == 200, access_response.text

    tampered_state = f"{access_response.cookies['quiz_session_state']}tampered"
    client.cookies.clear()
    client.cookies.set("quiz_session_id", str(session.id))
    client.cookies.set("quiz_session_state", tampered_state)

    active_response = client.get("/api/v2/quiz-extensions/session/active")
    submit_response = _submit(
        client,
        headers=_quiz_cookie_header(session_id=session.id, state=tampered_state),
    )

    assert active_response.status_code == 401
    assert submit_response.status_code == 401
    assert _response_count(db_session, session.id) == 0


def test_session_state_raw_cookie_mismatch_fails_closed(client, db_session, mock_quiz):
    session, token = _create_started_link_session(db_session, mock_quiz)
    access_response = _access(client, token)
    assert access_response.status_code == 200, access_response.text

    state = access_response.cookies["quiz_session_state"]
    mismatched_session_id = uuid4()
    client.cookies.clear()
    client.cookies.set("quiz_session_id", str(mismatched_session_id))
    client.cookies.set("quiz_session_state", state)

    active_response = client.get("/api/v2/quiz-extensions/session/active")
    submit_response = _submit(
        client,
        headers=_quiz_cookie_header(session_id=mismatched_session_id, state=state),
    )

    assert active_response.status_code == 401
    assert submit_response.status_code == 401
    assert _response_count(db_session, session.id) == 0


def test_logout_clears_both_cookies_and_raw_cookie_only_does_not_cancel_session(
    client, db_session, mock_quiz
):
    session, _token = _create_started_link_session(db_session, mock_quiz)
    client.cookies.set("quiz_session_id", str(session.id))

    response = client.post(
        "/api/v2/quiz-extensions/logout",
        headers=_quiz_cookie_header(session_id=session.id),
    )

    assert response.status_code == 200, response.text
    set_cookie = "; ".join(response.headers.get_list("set-cookie"))
    assert "quiz_session_id=" in set_cookie
    assert "quiz_session_state=" in set_cookie
    db_session.refresh(session)
    assert session.status == "started"
    assert (session.session_metadata or {}).get("link_status") == "active"


def test_logout_with_valid_signed_state_cancels_started_session(
    client, db_session, mock_quiz
):
    session, token = _create_started_link_session(db_session, mock_quiz)
    access_response = _access(client, token)
    assert access_response.status_code == 200, access_response.text

    response = client.post(
        "/api/v2/quiz-extensions/logout",
        headers=_quiz_cookie_header(
            session_id=access_response.cookies["quiz_session_id"],
            state=access_response.cookies["quiz_session_state"],
        ),
    )

    assert response.status_code == 200, response.text
    set_cookie = "; ".join(response.headers.get_list("set-cookie"))
    assert "quiz_session_id=" in set_cookie
    assert "quiz_session_state=" in set_cookie
    db_session.refresh(session)
    assert session.status == "cancelled"
    assert (session.session_metadata or {}).get("link_status") == "cancelled"
