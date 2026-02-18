"""Validation-focused tests for LangGraph-compatible state and node entry points.

These tests intentionally avoid graph builders and real LangGraph runtime usage.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.langgraph.ai_state import validate_ai_state
from app.ai.langgraph.nodes import (
    dispatch_response_continuation,
    generate_node,
    humanize_node,
    load_flow_context,
    load_response_context,
)
from app.ai.langgraph.state import validate_flow_message_state


def test_validate_flow_message_state_required_keys_missing() -> None:
    with pytest.raises(ValueError, match="Missing required FlowMessageState keys: day_number."):
        validate_flow_message_state(
            {"patient_id": str(uuid4()), "flow_kind": "onboarding"},
            required_keys=("patient_id", "day_number", "flow_kind"),
        )


def test_validate_flow_message_state_wrong_types() -> None:
    with pytest.raises(TypeError, match="Field 'day_number' must be an integer."):
        validate_flow_message_state(
            {"patient_id": str(uuid4()), "day_number": True, "flow_kind": "onboarding"},
            required_keys=("patient_id", "day_number", "flow_kind"),
        )


def test_validate_flow_message_state_success_normalizes_uuid() -> None:
    patient_id = str(uuid4())
    flow_state_id = str(uuid4())

    validated = validate_flow_message_state(
        {
            "patient_id": patient_id,
            "day_number": 3,
            "flow_kind": "onboarding",
            "flow_state_id": flow_state_id,
            "messages": [{"content": "Oi"}],
            "send_mode": "single",
            "current_index": 0,
        },
        required_keys=("patient_id", "day_number", "flow_kind"),
    )

    assert isinstance(validated["patient_id"], UUID)
    assert validated["patient_id"] == UUID(patient_id)
    assert isinstance(validated["flow_state_id"], UUID)
    assert validated["flow_state_id"] == UUID(flow_state_id)
    assert validated["day_number"] == 3


def test_validate_flow_message_state_normalizes_response_context() -> None:
    patient_id = str(uuid4())
    prompt_message_id = str(uuid4())
    response_message_id = str(uuid4())

    validated = validate_flow_message_state(
        {
            "patient_id": patient_id,
            "response_context": {
                "flow_day": 2,
                "flow_kind": "onboarding",
                "message_index": 1,
                "prompt_message_id": prompt_message_id,
                "response_message_id": response_message_id,
            },
        },
        required_keys=("patient_id",),
    )

    response_context = validated["response_context"]
    assert isinstance(response_context, dict)
    assert response_context["flow_day"] == 2
    assert response_context["flow_kind"] == "onboarding"
    assert response_context["message_index"] == 1
    assert response_context["prompt_message_id"] == UUID(prompt_message_id)
    assert response_context["response_message_id"] == UUID(response_message_id)


def test_validate_ai_state_required_keys_missing() -> None:
    with pytest.raises(ValueError, match="Missing required AIState keys: input_text."):
        validate_ai_state({"template": "oi"}, required_keys=("input_text",))


def test_validate_ai_state_wrong_types() -> None:
    with pytest.raises(TypeError, match="Field 'context' must be a dict."):
        validate_ai_state(
            {"input_text": "hello", "context": []},
            required_keys=("input_text",),
        )


def test_validate_ai_state_success_normalizes_confidence() -> None:
    validated = validate_ai_state(
        {
            "input_text": "texto",
            "template": None,
            "context": {"patient_name": "Ana"},
            "history": ["h1"],
            "hints": ["h2"],
            "confidence": 1,
            "metadata": {"source": "test"},
        },
        required_keys=("input_text",),
    )

    assert validated["input_text"] == "texto"
    assert validated["template"] is None
    assert validated["confidence"] == 1.0


@pytest.mark.asyncio
async def test_load_flow_context_invalid_state_returns_error_payload() -> None:
    updates = await load_flow_context(
        {"patient_id": str(uuid4()), "flow_kind": "onboarding"},
        config=None,
    )

    assert updates["result"]["status"] == "error"
    assert "Missing required FlowMessageState keys" in updates["result"]["message"]


@pytest.mark.asyncio
async def test_load_response_context_invalid_state_returns_error_payload() -> None:
    updates = await load_response_context({"patient_id": 123}, config=None)

    assert updates["result"]["status"] == "error"
    assert "Field 'patient_id' must be a UUID or UUID string." in updates["result"]["message"]


@pytest.mark.asyncio
async def test_load_flow_context_requires_thread_id_in_config() -> None:
    updates = await load_flow_context(
        {
            "patient_id": str(uuid4()),
            "day_number": 1,
            "flow_kind": "onboarding",
        },
        config={"configurable": {"handler": object()}},
    )

    assert updates["result"]["status"] == "error"
    assert "thread_id missing" in updates["result"]["message"]


@pytest.mark.asyncio
async def test_load_response_context_requires_thread_id_in_config() -> None:
    updates = await load_response_context(
        {"patient_id": str(uuid4())},
        config={"configurable": {"handler": object()}},
    )

    assert updates["result"]["status"] == "error"
    assert "thread_id missing" in updates["result"]["message"]


@pytest.mark.asyncio
async def test_load_flow_context_rejects_legacy_send_mode_alias() -> None:
    patient = object()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = patient

    handler = SimpleNamespace(
        db=db,
        _get_day_config=AsyncMock(
            return_value={
                "send_mode": "sequential_wait",
                "messages": [{"content": "Oi"}],
            }
        ),
        _get_or_create_flow_state=AsyncMock(return_value=SimpleNamespace(step_data={})),
    )

    updates = await load_flow_context(
        {
            "patient_id": str(uuid4()),
            "day_number": 1,
            "flow_kind": "onboarding",
        },
        config={"configurable": {"handler": handler, "thread_id": "test-thread"}},
    )

    assert updates["result"]["status"] == "error"
    assert "Invalid send_mode" in updates["result"]["message"]


@pytest.mark.asyncio
async def test_load_flow_context_day_change_preserves_waiting_state() -> None:
    patient = object()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = patient

    flow_state = SimpleNamespace(
        step_data={
            "current_flow_day": 2,
            "flow_kind": "onboarding",
            "awaiting_response": True,
            "day_complete": False,
            "current_day_message_index": 1,
        }
    )

    handler = SimpleNamespace(
        db=db,
        _get_day_config=AsyncMock(
            return_value={
                "send_mode": "wait_response",
                "messages": [{"content": "Mensagem do dia 3", "expects_response": True}],
            }
        ),
        _get_or_create_flow_state=AsyncMock(return_value=flow_state),
    )

    updates = await load_flow_context(
        {
            "patient_id": str(uuid4()),
            "day_number": 3,
            "flow_kind": "onboarding",
        },
        config={"configurable": {"handler": handler, "thread_id": "test-thread"}},
    )

    assert updates["result"] == {"status": "waiting", "day": 2, "message_index": 1}
    assert flow_state.step_data["current_flow_day"] == 2
    assert flow_state.step_data["awaiting_response"] is True
    assert flow_state.step_data["current_day_message_index"] == 1


@pytest.mark.asyncio
async def test_load_response_context_blocks_continuation_on_context_mismatch() -> None:
    db = MagicMock()
    db.commit = MagicMock()

    pending_message_id = str(uuid4())
    flow_state = SimpleNamespace(
        step_data={
            "current_flow_day": 2,
            "flow_kind": "onboarding",
            "awaiting_response": True,
            "day_complete": False,
            "current_day_message_index": 0,
            "pending_response_context": {
                "flow_day": 2,
                "flow_kind": "onboarding",
                "message_index": 0,
                "prompt_message_id": pending_message_id,
            },
        }
    )

    handler = SimpleNamespace(
        db=db,
        flow_state_repo=SimpleNamespace(get_active_flow=lambda _pid: flow_state),
        _get_day_config=AsyncMock(
            return_value={
                "send_mode": "wait_response",
                "messages": [
                    {"content": "Pergunta", "expects_response": True},
                    {"content": "Próxima", "expects_response": False},
                ],
            }
        ),
    )

    updates = await load_response_context(
        {
            "patient_id": str(uuid4()),
            "response_context": {
                "flow_day": 3,
                "flow_kind": "onboarding",
                "message_index": 0,
                "prompt_message_id": pending_message_id,
                "response_message_id": str(uuid4()),
            },
        },
        config={"configurable": {"handler": handler, "thread_id": "test-thread"}},
    )

    assert updates["result"]["status"] == "waiting"
    assert updates["result"]["reason"] == "context_mismatch"
    assert "flow_day" in updates["result"]["mismatches"]
    assert db.commit.call_count == 0


@pytest.mark.asyncio
async def test_load_response_context_accepts_matching_correlation_context() -> None:
    db = MagicMock()
    db.commit = MagicMock()

    pending_message_id = str(uuid4())
    flow_state = SimpleNamespace(
        id=uuid4(),
        step_data={
            "current_flow_day": 2,
            "flow_kind": "onboarding",
            "awaiting_response": True,
            "day_complete": False,
            "current_day_message_index": 0,
            "pending_response_context": {
                "flow_day": 2,
                "flow_kind": "onboarding",
                "message_index": 0,
                "prompt_message_id": pending_message_id,
            },
        },
    )

    handler = SimpleNamespace(
        db=db,
        flow_state_repo=SimpleNamespace(get_active_flow=lambda _pid: flow_state),
        _get_day_config=AsyncMock(
            return_value={
                "send_mode": "wait_response",
                "messages": [
                    {"content": "Pergunta", "expects_response": True},
                    {"content": "Próxima", "expects_response": False},
                ],
            }
        ),
    )

    updates = await load_response_context(
        {
            "patient_id": str(uuid4()),
            "response_context": {
                "flow_day": 2,
                "flow_kind": "onboarding",
                "message_index": 0,
                "prompt_message_id": pending_message_id,
                "response_message_id": str(uuid4()),
            },
        },
        config={"configurable": {"handler": handler, "thread_id": "test-thread"}},
    )

    assert updates["day_number"] == 2
    assert updates["flow_kind"] == "onboarding"
    assert updates["current_index"] == 1
    assert "result" not in updates


@pytest.mark.asyncio
async def test_dispatch_response_continuation_uses_handler_from_dispatch_context() -> None:
    patient = object()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = patient
    db.commit = MagicMock()

    flow_state = SimpleNamespace(step_data={})
    handler = SimpleNamespace(
        db=db,
        flow_state_repo=SimpleNamespace(get_active_flow=lambda _pid: flow_state),
        _send_remaining_after_response=AsyncMock(return_value={"status": "continued"}),
        _send_wait_each_with_auto_advance=AsyncMock(return_value={"status": "waiting"}),
    )

    updates = await dispatch_response_continuation(
        {
            "patient_id": str(uuid4()),
            "day_number": 2,
            "flow_kind": "onboarding",
            "day_config": {"day": 2},
            "messages": [{"content": "Pergunta", "expects_response": True}],
            "send_mode": "wait_response",
            "current_index": 1,
        },
        config={"configurable": {"handler": handler, "thread_id": "test-thread"}},
    )

    assert updates["result"]["status"] == "continued"
    assert handler._send_remaining_after_response.await_count == 1
    assert db.commit.call_count == 1


@pytest.mark.asyncio
async def test_humanize_node_missing_template_fails_before_client_call(monkeypatch) -> None:
    called = False

    def _unexpected_client_call():
        nonlocal called
        called = True
        raise AssertionError("Gemini client should not be called on invalid AI state.")

    monkeypatch.setattr("app.ai.langgraph.nodes_ai._get_gemini_client", _unexpected_client_call)

    with pytest.raises(ValueError, match="Missing required AIState keys: template."):
        await humanize_node({"context": {"patient_name": "Ana"}})

    assert called is False


@pytest.mark.asyncio
async def test_generate_node_missing_input_text_fails_before_client_call(monkeypatch) -> None:
    called = False

    def _unexpected_client_call():
        nonlocal called
        called = True
        raise AssertionError("Gemini client should not be called on invalid AI state.")

    monkeypatch.setattr("app.ai.langgraph.nodes_ai._get_gemini_client", _unexpected_client_call)

    with pytest.raises(ValueError, match="Missing required AIState keys: input_text."):
        await generate_node({"output_kind": "message"})

    assert called is False
