from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from app.agents.analytics.alert_analyzer import AlertAnalyzerAgent
from app.agents.patient.flow_coordinator.consensus_manager import ConsensusManager
from app.agents.patient.flow_coordinator.coordinator import FlowCoordinatorAgent
from app.agents.patient.patient_monitor import PatientMonitorAgent
from app.agents.registry import ALERT_ANALYZER_ID, PATIENT_MONITOR_ID


@pytest.mark.asyncio
async def test_alert_analyzer_registers_consensus_and_escalation_handlers():
    agent = AlertAnalyzerAgent(db_session=MagicMock())

    assert "consensus_request" in agent.message_handlers
    assert "analyze_escalation" in agent.message_handlers
    assert "escalation_alert" in agent.message_handlers


@pytest.mark.asyncio
async def test_alert_analyzer_consensus_request_votes_approve_for_high_risk_escalation():
    agent = AlertAnalyzerAgent(db_session=MagicMock())

    result = await agent.message_handlers["consensus_request"](
        {
            "decision_topic": "intervention_decision",
            "decision_data": {
                "priority": "high",
                "risk_factors": ["critical mood decline"],
            },
        }
    )

    assert result["agent_id"] == ALERT_ANALYZER_ID
    assert result["vote"] == "approve"
    assert result["confidence"] > 0.8


@pytest.mark.asyncio
async def test_alert_analyzer_analyze_escalation_uses_alert_analysis_path():
    agent = AlertAnalyzerAgent(db_session=MagicMock())

    result = await agent.message_handlers["analyze_escalation"](
        {
            "patient_id": "patient-1",
            "reason": "critical symptom report",
            "structured_response": {"mood": "very bad"},
        }
    )

    assert result["success"] is True
    assert result["patient_id"] == "patient-1"
    assert result["analysis"]["severity"] == "high"
    assert result["needs_medical_review"] is True


@pytest.mark.asyncio
async def test_patient_monitor_registers_consensus_handler_and_votes():
    agent = PatientMonitorAgent(db_session=MagicMock())

    assert "consensus_request" in agent.message_handlers

    result = await agent.message_handlers["consensus_request"](
        {
            "decision_topic": "escalate_intervention",
            "decision_data": {"risk_factors": ["adherence_drop"]},
        }
    )

    assert result["agent_id"] == PATIENT_MONITOR_ID
    assert result["vote"] == "approve"
    assert result["risk_factor_count"] == 1


@pytest.mark.asyncio
async def test_flow_coordinator_captures_and_consumes_consensus_request_response():
    agent = FlowCoordinatorAgent(
        db_session=MagicMock(),
        template_loader=MagicMock(),
    )

    captured = await agent.message_handlers["consensus_request_response"](
        {"agent_id": ALERT_ANALYZER_ID, "vote": "approve", "confidence": 0.9}
    )
    assert captured["captured"] is True

    votes = agent._consume_consensus_votes({ALERT_ANALYZER_ID: "cid-1"})
    assert votes[ALERT_ANALYZER_ID]["vote"] == "approve"
    assert agent._consume_consensus_votes({ALERT_ANALYZER_ID: "cid-1"}) == {}


@pytest.mark.asyncio
async def test_consensus_manager_uses_configured_prepare_and_fetch_hooks(monkeypatch):
    class _FakeGraph:
        def __init__(self):
            self.state = None

        async def ainvoke(self, state, config=None):
            self.state = state
            return {"result": {"consensus_reached": True, "votes": {}}}

    fake_graph = _FakeGraph()
    prepare_calls = []

    def prepare_vote_collection(agent_ids):
        prepare_calls.append(list(agent_ids))

    def fetch_votes(correlation_ids):
        return {key: {"vote": "approve"} for key in correlation_ids}

    async def send_message_fn(*_args, **_kwargs):
        return "cid"

    import app.ai.langgraph.consensus as consensus_module

    monkeypatch.setattr(consensus_module, "get_consensus_graph", lambda: fake_graph)

    manager = ConsensusManager(
        agent_id="flow_coordinator",
        logger=logging.getLogger("test_consensus_manager"),
        send_message_fn=send_message_fn,
        fetch_votes_fn=fetch_votes,
        prepare_vote_collection_fn=prepare_vote_collection,
    )

    result = await manager.seek_agent_consensus(
        decision_topic="intervention_decision",
        decision_data={"patient_id": "p-1"},
    )

    assert result["consensus_reached"] is True
    assert prepare_calls
    assert set(prepare_calls[0]) == {ALERT_ANALYZER_ID, PATIENT_MONITOR_ID}
    assert fake_graph.state["fetch_votes_fn"] is fetch_votes
