"""Unit tests for pure consensus node logic."""

from __future__ import annotations

import pytest

from app.agents.base import MessagePriority
from app.ai.langgraph import consensus as consensus_module


@pytest.mark.asyncio
async def test_prepare_consensus_applies_defaults(monkeypatch):
    monkeypatch.setattr(
        consensus_module,
        "_load_default_agents",
        lambda: ["alert_analyzer", "patient_monitor"],
    )

    result = await consensus_module.prepare_consensus({})

    assert result["agents"] == ["alert_analyzer", "patient_monitor"]
    assert result["min_participants"] == 2
    assert result["consensus_threshold"] == 0.7
    assert result["max_poll_attempts"] == 1
    assert result["poll_delay_seconds"] == 0.0
    assert result["poll_attempts"] == 0


@pytest.mark.asyncio
async def test_prepare_consensus_clamps_min_participants_and_normalizes_polling():
    result = await consensus_module.prepare_consensus(
        {
            "agents": ["agent_a", "agent_b"],
            "min_participants": 99,
            "consensus_threshold": 0.8,
            "max_poll_attempts": 4,
            "poll_delay_seconds": -5,
            "poll_attempts": -3,
        }
    )

    assert result["min_participants"] == 2
    assert result["consensus_threshold"] == 0.8
    assert result["max_poll_attempts"] == 4
    assert result["poll_delay_seconds"] == 0.0
    assert result["poll_attempts"] == 0


@pytest.mark.asyncio
async def test_dispatch_consensus_requests_without_send_message_fn_sets_error_result():
    result = await consensus_module.dispatch_consensus_requests({"agents": ["agent_a"]})

    assert result["result"]["consensus_reached"] is False
    assert result["result"]["error"] == "send_message_fn not provided"


@pytest.mark.asyncio
async def test_dispatch_consensus_requests_handles_partial_send_failures():
    calls = []

    async def send_message_fn(agent_id, message_type, payload, priority, requires_response):
        calls.append((agent_id, message_type, payload, priority, requires_response))
        if agent_id == "agent_b":
            raise RuntimeError("send failed")
        return f"cid-{agent_id}"

    result = await consensus_module.dispatch_consensus_requests(
        {
            "agents": ["agent_a", "agent_b"],
            "decision_topic": "escalate_intervention",
            "decision_data": {"risk": "high"},
            "send_message_fn": send_message_fn,
        }
    )

    assert result["correlation_ids"]["agent_a"] == "cid-agent_a"
    assert result["correlation_ids"]["agent_b"] is None
    assert len(calls) == 2
    assert calls[0][1] == "consensus_request"
    assert calls[0][2]["decision_topic"] == "escalate_intervention"
    assert calls[0][2]["decision_data"] == {"risk": "high"}
    assert calls[0][3] == MessagePriority.HIGH
    assert calls[0][4] is True


@pytest.mark.asyncio
async def test_collect_votes_sync_filters_disallowed_agents_and_increments_poll_attempts():
    def fetch_votes_fn(_correlation_ids):
        return {
            "agent_a": {"vote": "approve"},
            "agent_b": {"vote": "reject"},
            "unknown_agent": {"vote": "approve"},
        }

    result = await consensus_module.collect_votes(
        {
            "agents": ["agent_a"],
            "correlation_ids": {"agent_a": "cid-a", "agent_b": "cid-b"},
            "votes": {"existing_agent": {"vote": "approve"}},
            "poll_attempts": 1,
            "fetch_votes_fn": fetch_votes_fn,
        }
    )

    assert result["poll_attempts"] == 2
    assert result["votes"] == {
        "existing_agent": {"vote": "approve"},
        "agent_a": {"vote": "approve"},
    }


@pytest.mark.asyncio
async def test_collect_votes_supports_async_fetch_function():
    async def fetch_votes_fn(_correlation_ids):
        return {"agent_b": {"vote": "approve"}}

    result = await consensus_module.collect_votes(
        {
            "correlation_ids": {"agent_a": "cid-a", "agent_b": "cid-b"},
            "fetch_votes_fn": fetch_votes_fn,
        }
    )

    assert result["poll_attempts"] == 1
    assert result["votes"] == {"agent_b": {"vote": "approve"}}


@pytest.mark.asyncio
async def test_collect_votes_exception_only_increments_poll_attempts():
    def fetch_votes_fn(_correlation_ids):
        raise RuntimeError("backend unavailable")

    result = await consensus_module.collect_votes(
        {
            "correlation_ids": {"agent_a": "cid-a"},
            "votes": {"agent_a": {"vote": "approve"}},
            "poll_attempts": 3,
            "fetch_votes_fn": fetch_votes_fn,
        }
    )

    assert result["poll_attempts"] == 4
    assert result["votes"] == {"agent_a": {"vote": "approve"}}


@pytest.mark.asyncio
async def test_evaluate_consensus_no_responses_when_all_correlation_ids_missing():
    result = await consensus_module.evaluate_consensus(
        {
            "correlation_ids": {"agent_a": None, "agent_b": None},
        }
    )

    assert result["result"]["consensus_reached"] is False
    assert result["result"]["error"] == "No agent responses"
    assert result["result"]["votes"] == {}


@pytest.mark.asyncio
async def test_evaluate_consensus_pending_when_votes_not_collected_yet():
    result = await consensus_module.evaluate_consensus(
        {
            "correlation_ids": {"agent_a": "cid-a"},
        }
    )

    assert result["result"]["consensus_reached"] is False
    assert result["result"]["error"] == "Consensus pending: no votes collected"
    assert result["result"]["votes"] == {}


@pytest.mark.asyncio
async def test_evaluate_consensus_reached_when_threshold_and_participants_met():
    result = await consensus_module.evaluate_consensus(
        {
            "votes": {
                "agent_a": {"vote": "approve"},
                "agent_b": {"vote": "approve"},
            },
            "min_participants": 2,
            "consensus_threshold": 0.7,
        }
    )

    assert result["result"]["consensus_reached"] is True
    assert result["result"]["approval_rate"] == 1.0


@pytest.mark.asyncio
async def test_evaluate_consensus_not_reached_when_approval_rate_below_threshold():
    result = await consensus_module.evaluate_consensus(
        {
            "votes": {
                "agent_a": {"vote": "approve"},
                "agent_b": {"vote": "reject"},
            },
            "min_participants": 2,
            "consensus_threshold": 0.8,
        }
    )

    assert result["result"]["consensus_reached"] is False
    assert result["result"]["approval_rate"] == 0.5
