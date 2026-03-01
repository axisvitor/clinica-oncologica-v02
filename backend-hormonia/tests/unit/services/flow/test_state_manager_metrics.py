from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.agents.patient.flow_coordinator.models import FlowContext
from app.agents.patient.flow_coordinator.state_manager import StateManager


class _FakeQuery:
    def __init__(self, *, all_result=None, scalar_result=None):
        self._all_result = all_result if all_result is not None else []
        self._scalar_result = scalar_result

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all_result

    def scalar(self):
        return self._scalar_result


class _FakeDB:
    def __init__(self, queries):
        self._queries = list(queries)

    def query(self, *_args, **_kwargs):
        if not self._queries:
            raise AssertionError("Unexpected extra query")
        return self._queries.pop(0)


@pytest.mark.asyncio
async def test_calculate_adherence_metrics_uses_real_query_data():
    fake_db = _FakeDB(
        queries=[
            _FakeQuery(all_result=[("completed",), ("started",)]),
            _FakeQuery(scalar_result=3),
        ]
    )
    manager = StateManager(db_session=fake_db, agent_id="agent-1", logger=Mock())

    context = FlowContext(
        patient_id=uuid4(),
        current_day=10,
        recent_interactions=[{"answer": "ok"}, {"answer": ""}],
    )

    metrics = await manager._calculate_adherence_metrics(context)

    assert metrics["message_response_rate"] == 0.5
    assert metrics["quiz_completion_rate"] == 0.5
    assert metrics["scheduled_engagement_rate"] == 0.3
