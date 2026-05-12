"""Patient ownership boundary tests for message and flow patient-bound routes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.models.flow import (
    FlowKind,
    FlowTemplateVersion,
    PatientFlowOverride,
    PatientFlowState,
)
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient_flow_response import PatientFlowResponse
from tests.api.v2.security_boundary_helpers import (
    assert_response_excludes_values,
    create_message_ownership_boundary,
    headers_for_user,
)


def _body(response) -> str:
    return json.dumps(response.json(), ensure_ascii=False, default=str)


def _message_snapshot(db_session, message_id):
    db_session.expire_all()
    message = db_session.get(Message, message_id)
    assert message is not None
    return {
        "id": message.id,
        "patient_id": message.patient_id,
        "content": message.content,
        "status": message.status,
        "read_at": message.read_at,
        "updated_at": message.updated_at,
    }


def _patient_message_count(db_session, patient_id):
    db_session.expire_all()
    return db_session.query(Message).filter(Message.patient_id == patient_id).count()


@dataclass(frozen=True)
class FlowOwnershipRecords:
    flow_state_a: PatientFlowState
    flow_state_b: PatientFlowState
    response_a: PatientFlowResponse
    response_b: PatientFlowResponse
    override_b: PatientFlowOverride


def _create_flow_ownership_records(db_session, boundary) -> FlowOwnershipRecords:
    """Create minimal flow response/state/override rows for both boundary patients."""
    flow_kind = FlowKind(
        kind_key=f"boundary-flow-{uuid4().hex}",
        display_name="Boundary Flow",
        description="Patient ownership boundary flow fixture",
        is_active=True,
    )
    db_session.add(flow_kind)
    db_session.flush()

    template_version = FlowTemplateVersion(
        flow_kind_id=flow_kind.id,
        version_number=1,
        template_name="Boundary Template",
        description="Minimal template for flow override boundary tests",
        is_active=True,
        is_draft=False,
        steps=[
            {
                "day": 1,
                "message_type": "question",
                "messages": [
                    {
                        "content": "Boundary global day one",
                        "expects_response": True,
                    }
                ],
            },
            {
                "day": 2,
                "message_type": "motivation",
                "messages": [
                    {
                        "content": "Boundary global day two",
                        "expects_response": False,
                    }
                ],
            },
        ],
        created_by=boundary.admin.id,
    )
    db_session.add(template_version)
    db_session.flush()

    flow_state_a = PatientFlowState(
        patient_id=boundary.patient_a.id,
        flow_template_version_id=template_version.id,
        status="active",
        current_step=1,
        step_data={"current_flow_day": 1},
    )
    flow_state_b = PatientFlowState(
        patient_id=boundary.patient_b.id,
        flow_template_version_id=template_version.id,
        status="active",
        current_step=1,
        step_data={"current_flow_day": 1},
    )
    db_session.add_all([flow_state_a, flow_state_b])
    db_session.flush()

    response_a = PatientFlowResponse(
        patient_id=boundary.patient_a.id,
        flow_state_id=flow_state_a.id,
        day_number=1,
        message_index=0,
        response_text="Doctor A owned flow response",
        responded_at=datetime.now(timezone.utc),
        prompt_message_id="prompt-a",
        response_message_id="response-a",
    )
    response_b = PatientFlowResponse(
        patient_id=boundary.patient_b.id,
        flow_state_id=flow_state_b.id,
        day_number=1,
        message_index=0,
        response_text="Doctor B secret free-text flow response",
        responded_at=datetime.now(timezone.utc),
        prompt_message_id="prompt-b",
        response_message_id="response-b",
    )
    override_b = PatientFlowOverride(
        patient_flow_state_id=flow_state_b.id,
        day_number=2,
        content="Doctor B private override day",
        message_type="question",
        expects_response=True,
        skip=False,
        created_by=boundary.doctor_b.id,
    )
    db_session.add_all([response_a, response_b, override_b])
    db_session.commit()
    for row in [flow_state_a, flow_state_b, response_a, response_b, override_b]:
        db_session.refresh(row)

    return FlowOwnershipRecords(
        flow_state_a=flow_state_a,
        flow_state_b=flow_state_b,
        response_a=response_a,
        response_b=response_b,
        override_b=override_b,
    )


def _override_snapshot(db_session, flow_state_id):
    db_session.expire_all()
    rows = (
        db_session.query(PatientFlowOverride)
        .filter(PatientFlowOverride.patient_flow_state_id == flow_state_id)
        .order_by(PatientFlowOverride.day_number)
        .all()
    )
    return [
        {
            "day_number": row.day_number,
            "content": row.content,
            "message_type": row.message_type,
            "expects_response": row.expects_response,
            "skip": row.skip,
            "created_by": row.created_by,
        }
        for row in rows
    ]


def _override_content_count(db_session, content):
    db_session.expire_all()
    return (
        db_session.query(PatientFlowOverride)
        .filter(PatientFlowOverride.content == content)
        .count()
    )


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


def test_message_mutation_send_foreign_patient_denied_without_creating_row(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    before_count = _patient_message_count(db_session, boundary.patient_b.id)
    forbidden_content = "Doctor A should not send this to Patient B"

    response = client.post(
        "/api/v2/messages",
        json={
            "patient_id": str(boundary.patient_b.id),
            "content": forbidden_content,
            "type": "text",
        },
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content, forbidden_content],
    )
    assert _patient_message_count(db_session, boundary.patient_b.id) == before_count
    assert (
        db_session.query(Message)
        .filter(
            Message.patient_id == boundary.patient_b.id,
            Message.content == forbidden_content,
        )
        .count()
        == 0
    )


def test_message_mutation_bulk_mixed_owned_foreign_denied_without_side_effects(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    before_total = db_session.query(Message).count()
    forbidden_content = "Doctor A bulk message must not reach Patient B"

    response = client.post(
        "/api/v2/messages/bulk/send",
        json={
            "patient_ids": [str(boundary.patient_a.id), str(boundary.patient_b.id)],
            "content": forbidden_content,
            "type": "text",
        },
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content, forbidden_content],
    )
    db_session.expire_all()
    assert db_session.query(Message).count() == before_total


def test_read_state_foreign_message_mark_read_denied_before_mutation(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    before = _message_snapshot(db_session, boundary.message_b.id)

    response = client.patch(
        f"/api/v2/messages/{boundary.message_b.id}/read",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content],
    )
    assert _message_snapshot(db_session, boundary.message_b.id) == before


def test_message_mutation_foreign_pending_delete_denied_before_cancel(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    pending_message = Message(
        patient_id=boundary.patient_b.id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Doctor B pending deletion boundary message",
        status=MessageStatus.PENDING,
    )
    db_session.add(pending_message)
    db_session.commit()
    db_session.refresh(pending_message)
    before = _message_snapshot(db_session, pending_message.id)

    response = client.delete(
        f"/api/v2/messages/{pending_message.id}",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, pending_message.content],
    )
    assert _message_snapshot(db_session, pending_message.id) == before


def test_read_state_foreign_conversation_mark_read_denied_without_mutation(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    before = _message_snapshot(db_session, boundary.message_b.id)

    response = client.post(
        f"/api/v2/messages/conversations/{boundary.patient_b.id}/mark-read",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content, "\"count\""],
    )
    assert _message_snapshot(db_session, boundary.message_b.id) == before


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


def test_flow_response_foreign_patient_denied_without_free_text_leak(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    records = _create_flow_ownership_records(db_session, boundary)

    warm_response = client.get(
        f"/api/v2/patients/{boundary.patient_b.id}/flow-responses",
        headers=headers_for_user(boundary.doctor_b),
    )
    assert warm_response.status_code == 200
    assert records.response_b.response_text in _body(warm_response)

    response = client.get(
        f"/api/v2/patients/{boundary.patient_b.id}/flow-responses",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [
            boundary.patient_b.name,
            boundary.message_b.content,
            records.response_b.response_text,
        ],
    )


def test_flow_overrides_foreign_get_denied_without_override_disclosure(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    records = _create_flow_ownership_records(db_session, boundary)

    warm_response = client.get(
        f"/api/v2/patients/{boundary.patient_b.id}/flow-overrides",
        headers=headers_for_user(boundary.doctor_b),
    )
    assert warm_response.status_code == 200
    assert records.override_b.content in _body(warm_response)

    response = client.get(
        f"/api/v2/patients/{boundary.patient_b.id}/flow-overrides",
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [boundary.patient_b.name, boundary.message_b.content, records.override_b.content],
    )


def test_flow_overrides_foreign_put_denied_without_mutating_rows(client, db_session):
    boundary = create_message_ownership_boundary(db_session)
    records = _create_flow_ownership_records(db_session, boundary)
    before = _override_snapshot(db_session, records.flow_state_b.id)
    forbidden_content = "Doctor A must not replace Doctor B override"

    response = client.put(
        f"/api/v2/patients/{boundary.patient_b.id}/flow-overrides",
        json={
            "days": [
                {
                    "day_number": 2,
                    "content": forbidden_content,
                    "message_type": "question",
                    "expects_response": True,
                    "skip": False,
                }
            ]
        },
        headers=headers_for_user(boundary.doctor_a),
    )

    assert response.status_code == 403
    assert_response_excludes_values(
        response,
        [
            boundary.patient_b.name,
            boundary.message_b.content,
            records.override_b.content,
            forbidden_content,
        ],
    )
    assert _override_snapshot(db_session, records.flow_state_b.id) == before
    assert _override_content_count(db_session, forbidden_content) == 0


def test_flow_response_and_override_assigned_doctor_succeeds_with_dict_session(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    records = _create_flow_ownership_records(db_session, boundary)
    headers = headers_for_user(boundary.doctor_a)
    replacement_content = "Doctor A owned replacement override"

    flow_responses = client.get(
        f"/api/v2/patients/{boundary.patient_a.id}/flow-responses",
        headers=headers,
    )
    assert flow_responses.status_code == 200
    assert records.response_a.response_text in _body(flow_responses)

    initial_overrides = client.get(
        f"/api/v2/patients/{boundary.patient_a.id}/flow-overrides",
        headers=headers,
    )
    assert initial_overrides.status_code == 200
    assert initial_overrides.json()["patient_id"] == str(boundary.patient_a.id)

    saved = client.put(
        f"/api/v2/patients/{boundary.patient_a.id}/flow-overrides",
        json={
            "days": [
                {
                    "day_number": 2,
                    "content": replacement_content,
                    "message_type": "motivation",
                    "expects_response": False,
                    "skip": False,
                }
            ]
        },
        headers=headers,
    )
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["patient_id"] == str(boundary.patient_a.id)
    assert saved_body["current_flow_day"] == 1
    assert any(
        day["day_number"] == 2
        and day["content"] == replacement_content
        and day["source"] == "override"
        and day["editable"] is True
        for day in saved_body["days"]
    )

    overrides = _override_snapshot(db_session, records.flow_state_a.id)
    assert overrides == [
        {
            "day_number": 2,
            "content": replacement_content,
            "message_type": "motivation",
            "expects_response": False,
            "skip": False,
            "created_by": boundary.doctor_a.id,
        }
    ]


def test_flow_response_and_override_admin_can_access_foreign_patient(
    client, db_session
):
    boundary = create_message_ownership_boundary(db_session)
    records = _create_flow_ownership_records(db_session, boundary)
    headers = headers_for_user(boundary.admin)

    flow_responses = client.get(
        f"/api/v2/patients/{boundary.patient_b.id}/flow-responses",
        headers=headers,
    )
    assert flow_responses.status_code == 200
    assert records.response_b.response_text in _body(flow_responses)

    flow_overrides = client.get(
        f"/api/v2/patients/{boundary.patient_b.id}/flow-overrides",
        headers=headers,
    )
    assert flow_overrides.status_code == 200
    body = _body(flow_overrides)
    assert str(records.flow_state_b.id) in body
    assert records.override_b.content in body
