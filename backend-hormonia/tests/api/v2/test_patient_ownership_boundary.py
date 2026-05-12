"""Patient ownership boundary tests for message read/conversation routes."""

from __future__ import annotations

import json

from tests.api.v2.security_boundary_helpers import (
    assert_response_excludes_values,
    create_message_ownership_boundary,
    headers_for_user,
)


def _body(response) -> str:
    return json.dumps(response.json(), ensure_ascii=False, default=str)


def test_message_read_direct_idor_denied_after_foreign_cache_is_warmed(client, db_session):
    boundary = create_message_ownership_boundary(db_session)

    warm_response = client.get(
        f"/api/v2/messages/{boundary.message_b.id}?include=patient",
        headers=headers_for_user(boundary.doctor_b),
    )
    assert warm_response.status_code == 200
    assert boundary.message_b.content in _body(warm_response)

    response = client.get(
        f"/api/v2/messages/{boundary.message_b.id}?include=patient",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content],
    )


def test_message_read_patient_id_filter_idor_denied_after_list_cache_is_warmed(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)

    warm_response = client.get(
        f"/api/v2/messages?patient_id={boundary.patient_b.id}&include=patient",
        headers=headers_for_user(boundary.doctor_b),
    )
    assert warm_response.status_code == 200
    assert boundary.message_b.content in _body(warm_response)

    response = client.get(
        f"/api/v2/messages?patient_id={boundary.patient_b.id}&include=patient",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content],
    )


def test_conversation_global_list_scopes_doctor_to_own_patient(client, db_session):
    boundary = create_message_ownership_boundary(db_session)

    response = client.get(
        "/api/v2/messages/conversations?limit=20",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 200
    body = _body(response)
    assert str(boundary.patient_a.id) in body
    assert boundary.message_a.content in body
    assert str(boundary.patient_b.id) not in body
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content],
    )


def test_conversation_history_idor_denied_after_foreign_cache_is_warmed(client, db_session):
    boundary = create_message_ownership_boundary(db_session)

    warm_response = client.get(
        f"/api/v2/messages/conversations/{boundary.patient_b.id}",
        headers=headers_for_user(boundary.doctor_b),
    )
    assert warm_response.status_code == 200
    assert boundary.message_b.content in _body(warm_response)

    response = client.get(
        f"/api/v2/messages/conversations/{boundary.patient_b.id}",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content],
    )


def test_conversation_unread_count_idor_denied_without_side_channel(client, db_session):
    boundary = create_message_ownership_boundary(db_session)

    response = client.get(
        f"/api/v2/messages/conversations/{boundary.patient_b.id}/unread",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content, "\"count\": 1"],
    )


def test_message_read_patient_stats_idor_denied_without_patient_phi(client, db_session):
    boundary = create_message_ownership_boundary(db_session)

    response = client.get(
        f"/api/v2/messages/patient/{boundary.patient_b.id}/stats",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content],
    )


def test_message_read_assigned_doctor_can_read_own_message_and_conversation(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    headers = headers_for_user(boundary.doctor_a)

    direct = client.get(
        f"/api/v2/messages/{boundary.message_a.id}?include=patient",
        headers=headers,
    )
    assert direct.status_code == 200
    direct_body = _body(direct)
    assert boundary.message_a.content in direct_body
    assert boundary.patient_a.name in direct_body

    listed = client.get(
        f"/api/v2/messages?patient_id={boundary.patient_a.id}&include=patient",
        headers=headers,
    )
    assert listed.status_code == 200
    assert boundary.message_a.content in _body(listed)

    conversation = client.get(
        f"/api/v2/messages/conversations/{boundary.patient_a.id}",
        headers=headers,
    )
    assert conversation.status_code == 200
    assert boundary.message_a.content in _body(conversation)

    unread = client.get(
        f"/api/v2/messages/conversations/{boundary.patient_a.id}/unread",
        headers=headers,
    )
    assert unread.status_code == 200
    assert unread.json()["count"] == 1


def test_conversation_admin_can_read_both_doctors_conversations(client, db_session):
    boundary = create_message_ownership_boundary(db_session)
    headers = headers_for_user(boundary.admin)

    message_a = client.get(f"/api/v2/messages/{boundary.message_a.id}", headers=headers)
    message_b = client.get(f"/api/v2/messages/{boundary.message_b.id}", headers=headers)
    assert message_a.status_code == 200
    assert message_b.status_code == 200

    listed_b = client.get(
        f"/api/v2/messages?patient_id={boundary.patient_b.id}&include=patient",
        headers=headers,
    )
    assert listed_b.status_code == 200
    assert boundary.message_b.content in _body(listed_b)

    conversations = client.get("/api/v2/messages/conversations?limit=20", headers=headers)
    assert conversations.status_code == 200
    body = _body(conversations)
    assert str(boundary.patient_a.id) in body
    assert str(boundary.patient_b.id) in body
    assert boundary.message_a.content in body
    assert boundary.message_b.content in body
