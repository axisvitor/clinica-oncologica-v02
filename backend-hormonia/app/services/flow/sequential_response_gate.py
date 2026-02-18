"""
Shared helpers for sequential flow response-gating.

This module centralizes continuation gate logic used by both webhook and
response-processor paths to avoid divergence in patient-response validation.
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.flow.context_parsing import (
    parse_optional_bool,
    parse_optional_int,
    parse_optional_str,
)


def should_record_processed_response(
    *,
    status: Optional[str],
    reason: Optional[str],
) -> bool:
    """
    Return whether an inbound response should be marked as consumed.

    Responses blocked by progression-gate mismatches must not be recorded
    as processed, otherwise valid future retries could be ignored.
    """
    if status in {None, "error", "no_active_flow", "not_awaiting", "context_mismatch"}:
        return False

    blocked_reasons = {
        "not_awaiting_response",
        "context_not_awaiting_response",
        "flow_day_mismatch",
        "flow_kind_mismatch",
        "message_index_mismatch",
        "missing_flow_day",
        "missing_flow_kind",
        "missing_message_index",
        "missing_prompt_message_id",
        "prompt_message_id_mismatch",
        "duplicate_response_message",
        "context_mismatch",
    }
    return reason not in blocked_reasons


def evaluate_sequential_gate(
    step_data: dict[str, Any],
    response_context: Optional[dict[str, Any]],
) -> tuple[bool, str, dict[str, Any]]:
    """
    Validate that an inbound response matches the pending flow prompt context.

    Returns:
        (allowed, reason, normalized_context)
    """
    context = dict(response_context or {})
    pending_context_raw = step_data.get("pending_response_context")
    pending_context = pending_context_raw if isinstance(pending_context_raw, dict) else {}

    pending = {
        "flow_day": parse_optional_int(step_data.get("current_flow_day")),
        "flow_kind": parse_optional_str(step_data.get("flow_kind")),
        "message_index": parse_optional_int(step_data.get("current_day_message_index")),
        "awaiting_response": bool(parse_optional_bool(step_data.get("awaiting_response"))),
        "prompt_message_id": parse_optional_str(pending_context.get("prompt_message_id")),
    }

    prompt_message_id = parse_optional_str(context.get("prompt_message_id"))
    normalized_context = {
        "prompt_message_id": prompt_message_id,
        "response_message_id": parse_optional_str(context.get("response_message_id")),
        "flow_day": parse_optional_int(
            context.get("flow_day", context.get("current_flow_day"))
        ),
        "flow_kind": parse_optional_str(context.get("flow_kind")),
        "message_index": parse_optional_int(
            context.get(
                "message_index",
                context.get("current_message_index", context.get("current_day_message_index")),
            )
        ),
        "awaiting_response": parse_optional_bool(context.get("awaiting_response")),
    }

    if not pending["awaiting_response"]:
        return False, "not_awaiting_response", normalized_context

    if normalized_context["awaiting_response"] is False:
        return False, "context_not_awaiting_response", normalized_context

    required_fields = ("flow_day", "flow_kind", "message_index")
    for field in required_fields:
        if pending[field] is None or normalized_context[field] is None:
            return False, f"missing_{field}", normalized_context

    comparisons = (
        ("flow_day", "flow_day_mismatch"),
        ("flow_kind", "flow_kind_mismatch"),
        ("message_index", "message_index_mismatch"),
    )
    for key, reason in comparisons:
        if pending[key] != normalized_context[key]:
            return False, reason, normalized_context

    if pending["prompt_message_id"]:
        if normalized_context["prompt_message_id"] is None:
            return False, "missing_prompt_message_id", normalized_context
        if pending["prompt_message_id"] != normalized_context["prompt_message_id"]:
            return False, "prompt_message_id_mismatch", normalized_context

    last_processed = parse_optional_str(step_data.get("last_processed_response_message_id"))
    response_message_id = normalized_context.get("response_message_id")
    if response_message_id and last_processed and response_message_id == last_processed:
        return False, "duplicate_response_message", normalized_context

    return True, "ok", normalized_context
