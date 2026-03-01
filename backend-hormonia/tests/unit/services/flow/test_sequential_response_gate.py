"""Unit tests for shared sequential response gate helpers."""

from __future__ import annotations

from app.services.flow.sequential_response_gate import (
    evaluate_sequential_gate,
    should_record_processed_response,
)


def test_should_record_processed_response_blocks_gate_failures() -> None:
    assert (
        should_record_processed_response(
            status="context_mismatch",
            reason="flow_day_mismatch",
        )
        is False
    )
    assert (
        should_record_processed_response(
            status="waiting",
            reason="ok",
        )
        is True
    )


def test_evaluate_sequential_gate_accepts_matching_context() -> None:
    step_data = {
        "current_flow_day": 3,
        "flow_kind": "onboarding",
        "current_day_message_index": 1,
        "awaiting_response": True,
        "pending_response_context": {"prompt_message_id": "prompt-123"},
    }
    response_context = {
        "flow_day": 3,
        "flow_kind": "onboarding",
        "message_index": 1,
        "awaiting_response": True,
        "prompt_message_id": "prompt-123",
        "response_message_id": "resp-1",
    }

    allowed, reason, normalized = evaluate_sequential_gate(step_data, response_context)

    assert allowed is True
    assert reason == "ok"
    assert normalized["response_message_id"] == "resp-1"


def test_evaluate_sequential_gate_detects_prompt_mismatch() -> None:
    step_data = {
        "current_flow_day": 2,
        "flow_kind": "onboarding",
        "current_day_message_index": 0,
        "awaiting_response": True,
        "pending_response_context": {"prompt_message_id": "prompt-expected"},
    }
    response_context = {
        "flow_day": 2,
        "flow_kind": "onboarding",
        "message_index": 0,
        "awaiting_response": True,
        "prompt_message_id": "prompt-other",
    }

    allowed, reason, _ = evaluate_sequential_gate(step_data, response_context)

    assert allowed is False
    assert reason == "prompt_message_id_mismatch"


def test_evaluate_sequential_gate_detects_duplicate_response_message() -> None:
    step_data = {
        "current_flow_day": 4,
        "flow_kind": "onboarding",
        "current_day_message_index": 2,
        "awaiting_response": True,
        "last_processed_response_message_id": "resp-dup",
    }
    response_context = {
        "flow_day": 4,
        "flow_kind": "onboarding",
        "message_index": 2,
        "response_message_id": "resp-dup",
    }

    allowed, reason, _ = evaluate_sequential_gate(step_data, response_context)

    assert allowed is False
    assert reason == "duplicate_response_message"

