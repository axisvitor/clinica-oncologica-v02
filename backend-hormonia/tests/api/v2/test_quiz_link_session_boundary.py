"""Authenticated quiz link/session ownership boundary tests."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.middleware.csrf import get_csrf_token
from app.domain.quizzes.session import TokenManager
from app.models.quiz import QuizResponse, QuizSession, QuizTemplate
from app.utils.timezone import now_sao_paulo
from tests.api.v2.security_boundary_helpers import (
    assert_response_excludes_values,
    create_message_ownership_boundary,
    headers_for_user,
)


@pytest.fixture(autouse=True)
def ensure_quiz_boundary_tables(db_session):
    """Align legacy local Postgres quiz tables with the ORM fields this suite uses."""
    if db_session.bind.dialect.name != "postgresql":
        return

    statements = [
        "CREATE TABLE IF NOT EXISTS quiz_templates (id UUID PRIMARY KEY)",
        "ALTER TABLE quiz_templates ADD COLUMN IF NOT EXISTS name VARCHAR(255) NOT NULL DEFAULT 'Boundary Quiz'",
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
        "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS question_text TEXT NOT NULL DEFAULT 'Boundary question'",
        "ALTER TABLE quiz_responses ADD COLUMN IF NOT EXISTS response_type VARCHAR(50) NOT NULL DEFAULT 'scale'",
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


def _body(response) -> str:
    return json.dumps(response.json(), ensure_ascii=False, default=str)


def _create_quiz_template(db_session) -> QuizTemplate:
    template = QuizTemplate(
        name=f"Boundary Quiz {uuid4().hex}",
        version="1.0",
        description="Quiz link ownership boundary template",
        category="monthly_quiz",
        questions=[
            {
                "id": "q1",
                "text": "Boundary question",
                "type": "scale",
            }
        ],
        tags={"status": "published"},
        is_active=True,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


def _create_link(client, user, patient_id, template_id):
    return client.post(
        "/api/v2/quiz-extensions/links/",
        json={
            "patient_id": str(patient_id),
            "quiz_template_id": str(template_id),
            "delivery_method": "whatsapp",
            "expiry_hours": 24,
        },
        headers=headers_for_user(user),
    )


def _session_count(db_session, patient_id, template_id) -> int:
    db_session.expire_all()
    return (
        db_session.query(QuizSession)
        .filter(
            QuizSession.patient_id == patient_id,
            QuizSession.quiz_template_id == template_id,
        )
        .count()
    )


def test_authenticated_foreign_doctor_create_link_denied_without_session_side_effect(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    template = _create_quiz_template(db_session)
    before_count = _session_count(db_session, boundary.patient_b.id, template.id)

    response = _create_link(
        client,
        boundary.doctor_a,
        boundary.patient_b.id,
        template.id,
    )

    assert response.status_code == 403
    assert _session_count(db_session, boundary.patient_b.id, template.id) == before_count
    assert "token" not in _body(response)
    assert "quiz_session_id" not in _body(response)
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, str(template.id)],
    )


def test_patient_status_and_patient_history_foreign_doctor_denied_without_phi(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    template = _create_quiz_template(db_session)

    create_response = _create_link(
        client,
        boundary.doctor_b,
        boundary.patient_b.id,
        template.id,
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["quiz_session_id"]

    status_response = client.get(
        f"/api/v2/quiz-extensions/patients/{boundary.patient_b.id}/status",
        headers=headers_for_user(boundary.doctor_a),
    )
    history_response = client.get(
        f"/api/v2/quiz-extensions/patients/{boundary.patient_b.id}/history",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert status_response.status_code == 403
    assert history_response.status_code == 403
    for response in (status_response, history_response):
        assert_response_excludes_values(
            response,
            [boundary.patient_b.name, session_id, str(template.id)],
        )

    positive_response = client.get(
        f"/api/v2/quiz-extensions/patients/{boundary.patient_b.id}/status",
        headers=headers_for_user(boundary.doctor_b),
    )
    assert positive_response.status_code == 200
    assert session_id in _body(positive_response)


def test_active_links_scoped_to_assigned_doctor_and_admin_without_foreign_phi(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    template = _create_quiz_template(db_session)

    link_a = _create_link(
        client,
        boundary.doctor_a,
        boundary.patient_a.id,
        template.id,
    )
    link_b = _create_link(
        client,
        boundary.doctor_b,
        boundary.patient_b.id,
        template.id,
    )
    assert link_a.status_code == 200
    assert link_b.status_code == 200
    session_a = link_a.json()["quiz_session_id"]
    session_b = link_b.json()["quiz_session_id"]

    doctor_a_response = client.get(
        "/api/v2/quiz-extensions/links/active/",
        headers=headers_for_user(boundary.doctor_a),
    )
    assert doctor_a_response.status_code == 200
    doctor_a_body = _body(doctor_a_response)
    assert str(boundary.patient_a.id) in doctor_a_body
    assert boundary.patient_a.name in doctor_a_body
    assert session_a in doctor_a_body
    assert_response_excludes_values(
        doctor_a_response,
        [boundary.patient_b.id, boundary.patient_b.name, session_b],
    )

    admin_response = client.get(
        "/api/v2/quiz-extensions/links/active/",
        headers=headers_for_user(boundary.admin),
    )
    assert admin_response.status_code == 200
    admin_body = _body(admin_response)
    assert str(boundary.patient_a.id) in admin_body
    assert str(boundary.patient_b.id) in admin_body
    assert boundary.patient_b.name in admin_body
    assert session_a in admin_body
    assert session_b in admin_body


def _public_current(client, token: str):
    return client.get(
        "/api/v2/quiz-extensions/monthly/public/current",
        params={"token": token},
    )


def _public_submit(client, template_id, token: str, question_id: str = "q1"):
    return client.post(
        f"/api/v2/quiz-extensions/monthly/public/{template_id}/submit",
        json={
            "token": token,
            "question_id": question_id,
            "response_value": "7",
            "response_metadata": {"source": "boundary-test"},
        },
    )


def _create_public_link_fixture(client, db_session):
    boundary = create_message_ownership_boundary(db_session)
    template = _create_quiz_template(db_session)
    response = _create_link(
        client,
        boundary.doctor_a,
        boundary.patient_a.id,
        template.id,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    session = db_session.get(QuizSession, UUID(payload["quiz_session_id"]))
    assert session is not None
    assert session.status == "started"
    assert (session.session_metadata or {}).get("token_hash")
    assert (session.session_metadata or {}).get("link_status") == "active"
    assert session.expiration_date is not None
    return boundary, template, session, payload["token"]


def _response_count(db_session, session_id) -> int:
    db_session.expire_all()
    return (
        db_session.query(QuizResponse)
        .filter(QuizResponse.quiz_session_id == session_id)
        .count()
    )


def _session_count_for_link(db_session, patient_id, template_id) -> int:
    db_session.expire_all()
    return (
        db_session.query(QuizSession)
        .filter(
            QuizSession.patient_id == patient_id,
            QuizSession.quiz_template_id == template_id,
        )
        .count()
    )


def _replace_session_token(
    db_session,
    session: QuizSession,
    *,
    patient_id=None,
    quiz_template_id=None,
    session_id=None,
    expires_at=None,
    token_type: str = "quiz_access",
    include_session_id: bool = True,
) -> str:
    manager = TokenManager()
    expires_at = expires_at or (now_sao_paulo() + timedelta(hours=1))
    token = manager.generate_token(
        patient_id=patient_id or session.patient_id,
        quiz_template_id=quiz_template_id or session.quiz_template_id,
        expires_at=expires_at,
        session_id=(session.id if session_id is None else session_id)
        if include_session_id
        else None,
        token_type=token_type,
    )
    metadata = dict(session.session_metadata or {})
    metadata["token_hash"] = manager.hash_token(token)
    metadata["expires_at"] = expires_at.isoformat()
    metadata["link_status"] = "active"
    session.expiration_date = expires_at
    session.session_metadata = metadata
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return token


def _set_metadata(db_session, session: QuizSession, **updates):
    metadata = dict(session.session_metadata or {})
    metadata.update(updates)
    session.session_metadata = metadata
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)


def test_public_token_valid_current_and_submit_complete_existing_session(
    client, db_session
):
    _boundary, template, session, token = _create_public_link_fixture(client, db_session)

    current_response = _public_current(client, token)
    assert current_response.status_code == 200, current_response.text
    current_body = current_response.json()
    assert current_body["quiz_id"] == str(template.id)
    assert current_body["session_id"] == str(session.id)
    assert current_body["questions"] == [
        {
            "id": "q1",
            "text": "Boundary question",
            "type": "scale",
            "options": [],
        }
    ]

    assert _response_count(db_session, session.id) == 0
    submit_response = _public_submit(client, template.id, token)
    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["status"] == "completed"
    assert _response_count(db_session, session.id) == 1

    db_session.refresh(session)
    assert session.status == "completed"
    assert (session.session_metadata or {}).get("link_status") == "used"


def test_public_token_missing_session_id_does_not_create_session_or_return_quiz(
    client, db_session
):
    _boundary, template, session, _token = _create_public_link_fixture(client, db_session)
    token_without_session = _replace_session_token(
        db_session,
        session,
        include_session_id=False,
    )
    before_count = _session_count_for_link(db_session, session.patient_id, template.id)

    current_response = _public_current(client, token_without_session)
    submit_response = _public_submit(client, template.id, token_without_session)

    assert current_response.status_code == 401
    assert submit_response.status_code == 401
    assert _session_count_for_link(db_session, session.patient_id, template.id) == before_count
    assert _response_count(db_session, session.id) == 0
    assert "token" not in _body(current_response)
    assert "token" not in _body(submit_response)


@pytest.mark.parametrize(
    "case_name, mutate, expected_current_status, expected_submit_status",
    [
        (
            "patient_mismatch",
            lambda db_session, session, template: _replace_session_token(
                db_session,
                session,
                patient_id=uuid4(),
            ),
            403,
            403,
        ),
        (
            "template_mismatch",
            lambda db_session, session, template: _replace_session_token(
                db_session,
                session,
                quiz_template_id=uuid4(),
            ),
            403,
            401,
        ),
        (
            "session_missing",
            lambda db_session, session, template: _replace_session_token(
                db_session,
                session,
                session_id=uuid4(),
            ),
            404,
            404,
        ),
        (
            "wrong_token_type",
            lambda db_session, session, template: _replace_session_token(
                db_session,
                session,
                token_type="quiz_submission",
            ),
            401,
            401,
        ),
    ],
    ids=lambda case: case if isinstance(case, str) else None,
)
def test_public_token_mismatched_claims_fail_without_response_write(
    client,
    db_session,
    case_name,
    mutate,
    expected_current_status,
    expected_submit_status,
):
    _boundary, template, session, _token = _create_public_link_fixture(client, db_session)
    token = mutate(db_session, session, template)

    current_response = _public_current(client, token)
    submit_response = _public_submit(client, template.id, token)

    assert current_response.status_code == expected_current_status, case_name
    assert submit_response.status_code == expected_submit_status, case_name
    assert _response_count(db_session, session.id) == 0
    assert_response_excludes_values(
        submit_response,
        [token, token[:12], session.patient_id, template.id],
    )


def test_public_token_path_quiz_mismatch_fails_without_response_write(
    client, db_session
):
    _boundary, template, session, token = _create_public_link_fixture(client, db_session)

    response = _public_submit(client, uuid4(), token)

    assert response.status_code == 401
    assert _response_count(db_session, session.id) == 0
    assert_response_excludes_values(response, [token, token[:12], template.id])


def test_token_hash_mismatch_fails_without_response_write(client, db_session):
    _boundary, template, session, token = _create_public_link_fixture(client, db_session)
    _set_metadata(db_session, session, token_hash="not-the-current-token-hash")

    current_response = _public_current(client, token)
    submit_response = _public_submit(client, template.id, token)

    assert current_response.status_code == 403
    assert submit_response.status_code == 403
    assert _response_count(db_session, session.id) == 0
    assert_response_excludes_values(submit_response, [token, token[:12]])


@pytest.mark.parametrize("link_status", ["used", "cancelled", "expired"])
def test_link_state_terminal_values_fail_without_response_write(
    client, db_session, link_status
):
    _boundary, template, session, token = _create_public_link_fixture(client, db_session)
    _set_metadata(db_session, session, link_status=link_status)

    current_response = _public_current(client, token)
    submit_response = _public_submit(client, template.id, token)

    assert current_response.status_code == 410
    assert submit_response.status_code == 410
    assert _response_count(db_session, session.id) == 0
    assert_response_excludes_values(submit_response, [token, token[:12]])


@pytest.mark.parametrize("session_status", ["completed", "cancelled", "expired"])
def test_link_state_terminal_session_statuses_fail_without_response_write(
    client, db_session, session_status
):
    _boundary, template, session, token = _create_public_link_fixture(client, db_session)
    session.status = session_status
    if session_status == "completed":
        session.completed_at = now_sao_paulo()
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    current_response = _public_current(client, token)
    submit_response = _public_submit(client, template.id, token)

    assert current_response.status_code == 410
    assert submit_response.status_code == 410
    assert _response_count(db_session, session.id) == 0


@pytest.mark.parametrize(
    "case_name, mutate, expected_status",
    [
        (
            "metadata_expired",
            lambda db_session, session, token: _set_metadata(
                db_session,
                session,
                expires_at=(now_sao_paulo() - timedelta(minutes=1)).isoformat(),
            ),
            410,
        ),
        (
            "session_expired",
            lambda db_session, session, token: (
                setattr(session, "expiration_date", now_sao_paulo() - timedelta(minutes=1)),
                db_session.add(session),
                db_session.commit(),
                db_session.refresh(session),
            ),
            410,
        ),
        (
            "jwt_expired",
            lambda db_session, session, token: _replace_session_token(
                db_session,
                session,
                expires_at=now_sao_paulo() - timedelta(minutes=1),
            ),
            401,
        ),
    ],
    ids=lambda case: case if isinstance(case, str) else None,
)
def test_expired_public_token_boundaries_fail_without_response_write(
    client, db_session, case_name, mutate, expected_status
):
    _boundary, template, session, token = _create_public_link_fixture(client, db_session)
    mutated = mutate(db_session, session, token)
    if isinstance(mutated, str):
        token = mutated

    current_response = _public_current(client, token)
    submit_response = _public_submit(client, template.id, token)

    assert current_response.status_code == expected_status, case_name
    assert submit_response.status_code == expected_status, case_name
    assert _response_count(db_session, session.id) == 0
    assert_response_excludes_values(submit_response, [token, token[:12]])


def _compat_access(client, token: str):
    return client.post("/api/v2/quiz-extensions/access", json={"token": token})


def _compat_submit(client, question_id: str = "q1", value: str = "7", **kwargs):
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


def test_session_state_cookie_from_access_recovers_and_submits_bound_session(
    client, db_session
):
    _boundary, template, session, token = _create_public_link_fixture(client, db_session)

    access_response = _compat_access(client, token)
    assert access_response.status_code == 200, access_response.text
    assert access_response.cookies["quiz_session_id"] == str(session.id)
    assert "quiz_session_state" in access_response.cookies

    # The signed state is sufficient proof; the legacy raw cookie is only a
    # compatibility hint and is not required when state is present.
    state = access_response.cookies["quiz_session_state"]
    client.cookies.clear()
    client.cookies.set("quiz_session_state", state)

    active_response = client.get(
        "/api/v2/quiz-extensions/session/active",
        cookies={"quiz_session_state": state},
    )
    assert active_response.status_code == 200, active_response.text
    assert active_response.json()["id"] == str(session.id)
    assert active_response.json()["template_id"] == str(template.id)

    submit_response = _compat_submit(
        client,
        headers=_quiz_cookie_header(state=state),
    )
    assert submit_response.status_code == 200, submit_response.text
    assert _response_count(db_session, session.id) == 1
    db_session.refresh(session)
    assert session.status == "completed"


def test_raw_session_cookie_only_fails_compatibility_active_and_submit(
    client, db_session
):
    _boundary, _template, session, _token = _create_public_link_fixture(client, db_session)
    client.cookies.clear()
    client.cookies.set("quiz_session_id", str(session.id))

    active_response = client.get(
        "/api/v2/quiz-extensions/session/active",
        cookies={"quiz_session_id": str(session.id)},
    )
    submit_response = _compat_submit(
        client,
        headers=_quiz_cookie_header(session_id=session.id),
    )

    assert active_response.status_code == 401
    assert submit_response.status_code == 401
    assert _response_count(db_session, session.id) == 0
    assert_response_excludes_values(active_response, [session.id, session.patient_id])
    assert_response_excludes_values(submit_response, [session.id, session.patient_id])


def test_forged_state_cookie_fails_compatibility_without_response_write(
    client, db_session
):
    _boundary, _template, session, token = _create_public_link_fixture(client, db_session)
    access_response = _compat_access(client, token)
    assert access_response.status_code == 200, access_response.text

    client.cookies.clear()
    tampered_state = f"{access_response.cookies['quiz_session_state']}tampered"
    client.cookies.set("quiz_session_id", str(session.id))
    client.cookies.set("quiz_session_state", tampered_state)

    active_response = client.get(
        "/api/v2/quiz-extensions/session/active",
        cookies={
            "quiz_session_id": str(session.id),
            "quiz_session_state": tampered_state,
        },
    )
    submit_response = _compat_submit(
        client,
        headers=_quiz_cookie_header(session_id=session.id, state=tampered_state),
    )

    assert active_response.status_code == 401
    assert submit_response.status_code == 401
    assert _response_count(db_session, session.id) == 0
    assert_response_excludes_values(submit_response, [token, token[:12], session.id])


def test_session_state_raw_session_mismatch_fails_without_response_write(
    client, db_session
):
    _boundary, _template, session, token = _create_public_link_fixture(client, db_session)
    access_response = _compat_access(client, token)
    assert access_response.status_code == 200, access_response.text

    client.cookies.clear()
    raw_session_id = str(uuid4())
    state = access_response.cookies["quiz_session_state"]
    client.cookies.set("quiz_session_id", raw_session_id)
    client.cookies.set("quiz_session_state", state)

    active_response = client.get(
        "/api/v2/quiz-extensions/session/active",
        cookies={"quiz_session_id": raw_session_id, "quiz_session_state": state},
    )
    submit_response = _compat_submit(
        client,
        headers=_quiz_cookie_header(session_id=raw_session_id, state=state),
    )

    assert active_response.status_code == 401
    assert submit_response.status_code == 401
    assert _response_count(db_session, session.id) == 0
    assert_response_excludes_values(submit_response, [token, token[:12], session.id])


def test_logout_raw_session_only_does_not_cancel_foreign_session(client, db_session):
    _boundary, _template, session, _token = _create_public_link_fixture(client, db_session)
    client.cookies.clear()
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
    assert _response_count(db_session, session.id) == 0
