"""Unit tests for sequential gate mismatch recovery."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import app.services.flow.sequential_response_gate as sequential_gate
from app.services.flow._flow_response_flow import load_response_context
from app.services.flow.sequential_response_gate import (
    MAX_CONTEXT_MISMATCH_RETRIES,
    reset_awaiting_on_mismatch_limit,
    should_record_processed_response,
)


def _build_handler(step_data: dict, *, messages: list[dict] | None = None) -> tuple[SimpleNamespace, SimpleNamespace, MagicMock]:
    flow_state = SimpleNamespace(id=uuid4(), step_data=dict(step_data))
    commit = MagicMock()
    handler = SimpleNamespace(
        db=SimpleNamespace(commit=commit),
        flow_state_repo=SimpleNamespace(get_active_flow=MagicMock(return_value=flow_state)),
        _get_day_config=AsyncMock(
            return_value={
                "send_mode": "wait_response",
                "messages": messages or [{"content": "Question 1"}, {"content": "Question 2"}],
            }
        ),
    )
    return handler, flow_state, commit


async def _load_context(
    step_data: dict,
    *,
    response_context: dict | None = None,
    messages: list[dict] | None = None,
) -> tuple[dict, SimpleNamespace, MagicMock, str]:
    patient_id = uuid4()
    handler, flow_state, commit = _build_handler(step_data, messages=messages)
    state = {"patient_id": patient_id}
    if response_context is not None:
        state["response_context"] = response_context

    result = await load_response_context(
        state,
        config={
            "configurable": {
                "thread_id": "test-thread",
                "handler": handler,
            }
        },
    )
    return result, flow_state, commit, str(patient_id)


@pytest.mark.asyncio
async def test_load_response_context_increments_mismatch_counter_until_limit() -> None:
    result, flow_state, commit, _ = await _load_context(
        {
            "current_flow_day": 2,
            "flow_kind": "onboarding",
            "current_day_message_index": 0,
            "awaiting_response": True,
        },
        response_context={
            "flow_day": 2,
            "flow_kind": "onboarding",
            "message_index": 4,
        },
    )

    assert result["result"]["status"] == "waiting"
    assert result["result"]["reason"] == "context_mismatch"
    assert result["result"]["mismatch_count"] == 1
    assert flow_state.step_data["context_mismatch_count"] == 1
    commit.assert_called_once()


@pytest.mark.asyncio
async def test_load_response_context_resets_waiting_after_retry_limit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("WARNING", logger="app.services.flow._flow_response_flow")

    result, flow_state, commit, patient_id = await _load_context(
        {
            "current_flow_day": 2,
            "flow_kind": "onboarding",
            "current_day_message_index": 0,
            "awaiting_response": True,
            "context_mismatch_count": MAX_CONTEXT_MISMATCH_RETRIES - 1,
            "pending_response_context": {"prompt_message_id": str(uuid4())},
        },
        response_context={
            "flow_day": 99,
            "flow_kind": "onboarding",
            "message_index": 0,
        },
    )

    assert result["result"]["status"] == "context_mismatch_reset"
    assert result["result"]["reset_after"] == MAX_CONTEXT_MISMATCH_RETRIES
    assert result["result"]["reason"] == "context_mismatch"
    assert flow_state.step_data["awaiting_response"] is False
    assert "pending_response_context" not in flow_state.step_data
    assert flow_state.step_data["context_mismatch_count"] == 0
    assert datetime.fromisoformat(flow_state.step_data["last_mismatch_reset_at"])
    assert any(
        record.levelname == "WARNING" and getattr(record, "patient_id", None) == patient_id
        for record in caplog.records
    )
    commit.assert_called_once()


@pytest.mark.asyncio
async def test_load_response_context_resets_counter_after_successful_match() -> None:
    result, flow_state, commit, _ = await _load_context(
        {
            "current_flow_day": 2,
            "flow_kind": "onboarding",
            "current_day_message_index": 0,
            "awaiting_response": True,
            "context_mismatch_count": 2,
        },
        response_context={
            "flow_day": 2,
            "flow_kind": "onboarding",
            "message_index": 0,
        },
    )

    assert result["current_index"] == 1
    assert result["flow_state_step_data"]["context_mismatch_count"] == 0
    assert flow_state.step_data["context_mismatch_count"] == 0
    commit.assert_called_once()


@pytest.mark.asyncio
async def test_load_response_context_preserves_default_behavior_when_context_missing() -> None:
    result, flow_state, commit, _ = await _load_context(
        {
            "current_flow_day": 2,
            "flow_kind": "onboarding",
            "current_day_message_index": 0,
            "awaiting_response": True,
        }
    )

    assert result["current_index"] == 1
    assert "result" not in result
    assert "context_mismatch_count" not in flow_state.step_data
    commit.assert_not_called()


def test_reset_awaiting_on_mismatch_limit_uses_configurable_max(monkeypatch: pytest.MonkeyPatch) -> None:
    assert MAX_CONTEXT_MISMATCH_RETRIES == 3
    monkeypatch.setattr(sequential_gate, "MAX_CONTEXT_MISMATCH_RETRIES", 1)
    step_data = {
        "awaiting_response": True,
        "pending_response_context": {"message_index": 0},
    }

    reset_triggered, payload = reset_awaiting_on_mismatch_limit(
        step_data,
        {"message_index": {"expected": 0, "received": 1}},
        lambda: None,
    )

    assert reset_triggered is True
    assert payload["status"] == "context_mismatch_reset"
    assert payload["reset_after"] == 1
    assert step_data["context_mismatch_count"] == 0


def test_context_mismatch_reset_is_not_recorded_as_processed_response() -> None:
    assert (
        should_record_processed_response(
            status="context_mismatch_reset",
            reason="context_mismatch",
        )
        is False
    )
