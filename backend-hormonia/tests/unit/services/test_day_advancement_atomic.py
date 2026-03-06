from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.exceptions import FlowStateConflictError
from app.services.flow.management.advancement import advance_day_atomic
from app.services.flow.sequential_message_handler_pkg.sequencing import SequencingMixin


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _DummySequencingHandler(SequencingMixin):
    pass


@pytest.mark.asyncio
async def test_advance_day_atomic_sets_verified_after_successful_commits():
    flow_state = SimpleNamespace(
        id=uuid4(),
        step_data={"pending_response_context": {"flow_day": 1}},
        version=4,
        last_interaction_at=None,
    )
    db = MagicMock()
    db.execute = AsyncMock(return_value=_ScalarResult(4))
    db.commit = AsyncMock(side_effect=[None, None])

    step_data = await advance_day_atomic(
        db=db,
        flow_state=flow_state,
        patient_id=uuid4(),
        day_number=3,
        flow_kind="onboarding",
        message_index=2,
        sent_count=3,
        mark_last_message_sent=lambda data: data.__setitem__(
            "last_message_sent", "2026-03-06T16:00:00-03:00"
        ),
    )

    assert step_data["day_complete"] is True
    assert step_data["day_advance_verified"] is True
    assert "pending_response_context" not in step_data
    assert flow_state.version == 6
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_advance_day_atomic_leaves_verification_false_when_commit_fails():
    flow_state = SimpleNamespace(id=uuid4(), step_data={}, version=2, last_interaction_at=None)
    db = MagicMock()
    db.execute = AsyncMock(return_value=_ScalarResult(2))
    db.commit = AsyncMock(side_effect=RuntimeError("db down"))

    with pytest.raises(RuntimeError, match="db down"):
        await advance_day_atomic(
            db=db,
            flow_state=flow_state,
            patient_id=uuid4(),
            day_number=2,
            flow_kind="onboarding",
            message_index=1,
        )

    assert flow_state.step_data["day_advance_verified"] is False
    assert "day_advance_verified_at" not in flow_state.step_data


@pytest.mark.asyncio
async def test_advance_day_atomic_detects_version_conflict():
    flow_state = SimpleNamespace(id=uuid4(), step_data={}, version=1, last_interaction_at=None)
    db = MagicMock()
    db.execute = AsyncMock(return_value=_ScalarResult(2))
    db.commit = AsyncMock()

    with pytest.raises(FlowStateConflictError):
        await advance_day_atomic(
            db=db,
            flow_state=flow_state,
            patient_id=uuid4(),
            day_number=2,
            flow_kind="onboarding",
            message_index=1,
        )


@pytest.mark.asyncio
async def test_send_all_sequential_uses_advance_day_atomic():
    handler = _DummySequencingHandler()
    handler.db = MagicMock()
    handler._personalize_message_ai = AsyncMock(side_effect=lambda msg, *_args, **_kwargs: msg["content"])
    handler._send_flow_message = AsyncMock(return_value=True)
    handler._await_inter_message_delay = AsyncMock()
    handler._mark_last_message_sent = MagicMock()

    patient = SimpleNamespace(id=uuid4())
    flow_state = SimpleNamespace(id=uuid4(), step_data={}, version=1, last_interaction_at=None)
    messages = [{"content": "Hello", "expects_response": False}]

    with patch(
        "app.services.flow.sequential_message_handler_pkg.sequencing.advance_day_atomic",
        new=AsyncMock(return_value={"day_advance_verified": True}),
    ) as atomic_mock:
        result = await handler._send_all_sequential(
            patient=patient,
            messages=messages,
            flow_state=flow_state,
            day_number=1,
            flow_kind="onboarding",
        )

    assert result["status"] == "ok"
    atomic_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_remaining_after_response_uses_advance_day_atomic():
    handler = _DummySequencingHandler()
    handler.db = MagicMock()
    handler._personalize_message_ai = AsyncMock(side_effect=lambda msg, *_args, **_kwargs: msg["content"])
    handler._send_flow_message = AsyncMock(return_value=True)
    handler._await_inter_message_delay = AsyncMock()
    handler._set_flow_progress = AsyncMock()
    handler._mark_last_message_sent = MagicMock()

    patient = SimpleNamespace(id=uuid4())
    flow_state = SimpleNamespace(id=uuid4(), step_data={}, version=1, last_interaction_at=None)
    messages = [{"content": "Done", "expects_response": False}]

    with patch(
        "app.services.flow.sequential_message_handler_pkg.sequencing.advance_day_atomic",
        new=AsyncMock(return_value={"day_advance_verified": True}),
    ) as atomic_mock:
        result = await handler._send_remaining_after_response(
            patient=patient,
            messages=messages,
            start_index=0,
            flow_state=flow_state,
            day_number=1,
            flow_kind="onboarding",
        )

    assert result["status"] == "complete"
    atomic_mock.assert_awaited_once()
