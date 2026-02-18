"""Real LangGraph flow smoke tests (patient flow, response, AI question optimization)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

# LangGraph is an optional dependency in some environments.
pytest.importorskip("langgraph")

from app.ai.langgraph.graphs import (
    build_flow_message_graph,
    build_flow_response_graph,
    build_humanization_graph,
)
from app.ai.langgraph import nodes_ai as langgraph_nodes
from app.models.patient import Patient


class _StubHandler:
    def __init__(self, db, flow_state, day_config):
        self.db = db
        self.flow_state = flow_state
        self.flow_state_repo = SimpleNamespace(get_active_flow=lambda _pid: flow_state)
        self._day_config = day_config

        self._get_day_config = AsyncMock(return_value=day_config)
        self._get_or_create_flow_state = AsyncMock(return_value=flow_state)

        self._send_all_sequential = AsyncMock(return_value={"status": "ok"})
        self._send_message_and_wait = AsyncMock(return_value={"status": "waiting"})
        self._send_wait_each_with_auto_advance = AsyncMock(return_value={"status": "waiting_each"})
        self._send_remaining_after_response = AsyncMock(return_value={"status": "continued"})


@pytest.fixture
def patient():
    patient = MagicMock(spec=Patient)
    patient.id = uuid4()
    patient.name = "Paciente Teste"
    return patient


@pytest.fixture
def db(patient):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = patient
    db.commit = MagicMock()
    return db


@pytest.mark.asyncio
async def test_flow_message_graph_patient_flow(db, patient):
    """Run real LangGraph flow for a patient day message."""
    flow_state = SimpleNamespace(step_data={})
    day_config = {
        "day": 1,
        "send_mode": "single",
        "messages": [{"content": "Olá", "expects_response": False}],
    }
    handler = _StubHandler(db, flow_state, day_config)

    graph = build_flow_message_graph()
    result = await graph.ainvoke(
        {
            "patient_id": patient.id,
            "day_number": 1,
            "flow_kind": "onboarding",
        },
        config={
            "configurable": {
                "thread_id": f"test:flow_message:{patient.id}",
                "handler": handler,
            }
        },
    )

    assert result["result"]["status"] == "ok"
    assert handler._send_all_sequential.await_count == 1
    assert flow_state.step_data.get("current_flow_day") == 1


@pytest.mark.asyncio
async def test_flow_response_graph_response_reception(db, patient):
    """Run real LangGraph flow for response continuation."""
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
    day_config = {
        "day": 2,
        "send_mode": "wait_response",
        "messages": [
            {"content": "Pergunta", "expects_response": True},
            {"content": "Obrigado", "expects_response": False},
        ],
    }
    handler = _StubHandler(db, flow_state, day_config)

    graph = build_flow_response_graph()
    result = await graph.ainvoke(
        {
            "patient_id": patient.id,
            "response_context": {
                "flow_day": 2,
                "flow_kind": "onboarding",
                "message_index": 0,
                "prompt_message_id": pending_message_id,
                "response_message_id": str(uuid4()),
            },
        },
        config={
            "configurable": {
                "thread_id": f"test:flow_response:{patient.id}",
                "handler": handler,
            }
        },
    )

    assert result["result"]["status"] == "continued"
    assert handler._send_remaining_after_response.await_count == 1
    assert db.commit.called
    assert "last_response_at" in flow_state.step_data


@pytest.mark.asyncio
async def test_flow_response_graph_blocks_on_context_mismatch(db, patient):
    """Flow response graph should not continue if correlation context does not match."""
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
    day_config = {
        "day": 2,
        "send_mode": "wait_response",
        "messages": [
            {"content": "Pergunta", "expects_response": True},
            {"content": "Obrigado", "expects_response": False},
        ],
    }
    handler = _StubHandler(db, flow_state, day_config)

    graph = build_flow_response_graph()
    result = await graph.ainvoke(
        {
            "patient_id": patient.id,
            "response_context": {
                "flow_day": 3,
                "flow_kind": "onboarding",
                "message_index": 0,
                "prompt_message_id": pending_message_id,
                "response_message_id": str(uuid4()),
            },
        },
        config={
            "configurable": {
                "thread_id": f"test:flow_response:{patient.id}",
                "handler": handler,
            }
        },
    )

    assert result["result"]["status"] == "waiting"
    assert result["result"]["reason"] == "context_mismatch"
    assert handler._send_remaining_after_response.await_count == 0


@pytest.mark.asyncio
async def test_flow_response_graph_accepts_matching_context(db, patient):
    """Flow response graph should continue when correlation context matches pending state."""
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
    day_config = {
        "day": 2,
        "send_mode": "wait_response",
        "messages": [
            {"content": "Pergunta", "expects_response": True},
            {"content": "Obrigado", "expects_response": False},
        ],
    }
    handler = _StubHandler(db, flow_state, day_config)

    graph = build_flow_response_graph()
    result = await graph.ainvoke(
        {
            "patient_id": patient.id,
            "response_context": {
                "flow_day": 2,
                "flow_kind": "onboarding",
                "message_index": 0,
                "prompt_message_id": pending_message_id,
                "response_message_id": str(uuid4()),
            },
        },
        config={
            "configurable": {
                "thread_id": f"test:flow_response:{patient.id}",
                "handler": handler,
            }
        },
    )

    assert result["result"]["status"] == "continued"
    assert handler._send_remaining_after_response.await_count == 1


@pytest.mark.asyncio
async def test_humanization_graph_ai_question_optimization(monkeypatch):
    """Run real LangGraph humanization graph with stubbed Gemini client."""

    class _GeminiStub:
        async def generate_content(self, *_args, **_kwargs):
            return "Como você está se sentindo hoje?"

    monkeypatch.setattr(langgraph_nodes, "_get_gemini_client", lambda: _GeminiStub())

    graph = build_humanization_graph()
    result = await graph.ainvoke(
        {
            "template": "Como você está?",
            "context": {"patient_name": "Ana"},
            "history": ["Oi"],
            "hints": ["gentil"],
            "output_kind": "message",
        },
        config={"configurable": {"thread_id": "test:humanization:ana"}},
    )

    assert result["output"] == "Como você está se sentindo hoje?"
    assert result.get("confidence") is not None
