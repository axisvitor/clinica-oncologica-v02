"""Authenticated quiz link/session ownership boundary tests."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models.quiz import QuizSession, QuizTemplate
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
