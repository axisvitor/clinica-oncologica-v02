from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.flow.recovery import (
    attempt_recovery,
    determine_recovery_action,
    find_stuck_flows,
)


def _flow_state(
    *,
    step_data: dict | None = None,
    current_step: int = 2,
    version: int = 4,
):
    return SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        current_step=current_step,
        version=version,
        step_data=step_data or {},
        last_interaction_at=None,
    )


def _query_chain(db: MagicMock, result):
    query = db.query.return_value
    query.join.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = result
    query.first.return_value = result
    return query


def _async_to_sync_return(value):
    def _factory(fn):
        def _call(*args, **kwargs):
            coro = fn(*args, **kwargs)
            coro.close()
            return value

        return _call

    return _factory


def test_find_stuck_flows_returns_matching_results_with_safety_limit():
    db = MagicMock()
    flows = [_flow_state(), _flow_state()]
    query = _query_chain(db, flows)

    result = find_stuck_flows(db, threshold_hours=6)

    assert result == flows
    db.query.assert_called_once()
    query.join.assert_called_once()
    query.limit.assert_called_once_with(100)


def test_find_stuck_flows_returns_empty_list_when_nothing_is_stuck():
    db = MagicMock()
    _query_chain(db, [])

    result = find_stuck_flows(db)

    assert result == []


def test_determine_recovery_action_returns_advance_day_for_unverified_day_completion():
    action = determine_recovery_action(
        {"day_complete": True, "day_advance_verified": False}
    )

    assert action == "advance_day"


def test_determine_recovery_action_returns_resend_prompt_for_normal_waiting_state():
    action = determine_recovery_action({"day_complete": False})

    assert action == "resend_prompt"


def test_determine_recovery_action_returns_resend_prompt_when_day_already_verified():
    action = determine_recovery_action(
        {"day_complete": True, "day_advance_verified": True}
    )

    assert action == "resend_prompt"


def test_attempt_recovery_skips_when_max_attempts_exceeded():
    db = MagicMock()
    flow = _flow_state(
        step_data={"awaiting_response": True, "recovery_attempts": 3},
    )
    redis_client = MagicMock()

    result = attempt_recovery(db, flow, redis_client)

    assert result == {
        "status": "max_attempts_exceeded",
        "flow_state_id": str(flow.id),
    }
    redis_client.get.assert_not_called()
    assert flow.step_data["manual_intervention_required"] is True
    assert flow.step_data["manual_intervention_reason"] == "stuck_flow_recovery_exhausted"
    db.commit.assert_called_once()


def test_attempt_recovery_skips_when_idempotency_key_is_already_present():
    db = MagicMock()
    flow = _flow_state(step_data={"awaiting_response": True, "recovery_attempts": 1})
    redis_client = MagicMock()
    redis_client.get.return_value = "1"

    result = attempt_recovery(db, flow, redis_client)

    assert result == {
        "status": "already_recovering",
        "flow_state_id": str(flow.id),
    }
    redis_client.set.assert_not_called()


def test_attempt_recovery_returns_no_longer_stuck_when_waiting_flag_cleared():
    db = MagicMock()
    flow = _flow_state(step_data={"awaiting_response": True})
    latest_flow = _flow_state(step_data={"awaiting_response": False}, version=flow.version)
    _query_chain(db, latest_flow)
    redis_client = MagicMock()
    redis_client.get.return_value = None
    redis_client.set.return_value = True

    result = attempt_recovery(db, flow, redis_client)

    assert result == {
        "status": "no_longer_stuck",
        "flow_state_id": str(flow.id),
    }


def test_attempt_recovery_resends_prompt_and_updates_recovery_metadata():
    db = MagicMock()
    flow = _flow_state(
        step_data={
            "awaiting_response": True,
            "recovery_attempts": 1,
            "flow_kind": "onboarding",
            "current_flow_day": 2,
            "current_day_message_index": 1,
            "pending_response_context": {"prompt_message_id": str(uuid4())},
        }
    )
    latest_flow = _flow_state(step_data=dict(flow.step_data), version=flow.version)
    latest_flow.id = flow.id
    latest_flow.patient_id = flow.patient_id
    latest_flow.current_step = flow.current_step
    query = _query_chain(db, latest_flow)
    query.first.side_effect = [latest_flow]
    redis_client = MagicMock()
    redis_client.get.return_value = None
    redis_client.set.return_value = True

    with patch(
        "app.tasks.flows.send_retry.retry_failed_flow_send.delay"
    ) as retry_task, patch(
        "app.services.flow.recovery.now_sao_paulo"
    ) as now_mock:
        now_mock.return_value.isoformat.return_value = "2026-03-06T12:00:00-03:00"

        result = attempt_recovery(db, flow, redis_client)

    assert result == {
        "status": "recovered",
        "action": "resend_prompt",
        "flow_state_id": str(flow.id),
    }
    assert latest_flow.step_data["recovery_attempts"] == 2
    assert latest_flow.step_data["last_recovery_at"] == "2026-03-06T12:00:00-03:00"
    retry_task.assert_called_once()
    db.commit.assert_called()


def test_attempt_recovery_advances_day_when_completion_is_unverified():
    db = MagicMock()
    flow = _flow_state(
        step_data={
            "awaiting_response": True,
            "day_complete": True,
            "day_advance_verified": False,
            "current_flow_day": 3,
        },
        current_step=3,
    )
    latest_flow = _flow_state(step_data=dict(flow.step_data), version=flow.version, current_step=3)
    latest_flow.id = flow.id
    latest_flow.patient_id = flow.patient_id
    query = _query_chain(db, latest_flow)
    query.first.side_effect = [latest_flow]
    redis_client = MagicMock()
    redis_client.get.return_value = None
    redis_client.set.return_value = True
    flow_repo = MagicMock()
    manager = MagicMock()
    manager.advance_patient_flow = MagicMock()

    with patch(
        "app.services.flow.recovery.FlowStateRepository",
        return_value=flow_repo,
    ), patch(
        "app.services.flow.recovery.FlowManagementService",
        return_value=manager,
    ), patch(
        "app.services.flow.recovery.async_to_sync",
        side_effect=_async_to_sync_return({"success": True}),
    ), patch(
        "app.services.flow.recovery.now_sao_paulo"
    ) as now_mock:
        now_mock.return_value.isoformat.return_value = "2026-03-06T12:00:00-03:00"

        result = attempt_recovery(db, flow, redis_client)

    assert result == {
        "status": "recovered",
        "action": "advance_day",
        "flow_state_id": str(flow.id),
    }
    manager.advance_patient_flow.assert_called_once_with(flow.patient_id, force_day=4)
