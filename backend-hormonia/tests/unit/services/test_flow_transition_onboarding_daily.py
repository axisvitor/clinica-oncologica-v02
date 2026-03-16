"""
Tests for onboarding → daily_follow_up flow transition (S05/T02).

Verifies:
- determine_flow_type returns correct FlowType for boundary days
- _transition_flow_type records transition in step_data.transitions
- advance_patient_flow(force_day=16) triggers transition from onboarding to daily_follow_up
- step_data.transitions contains from/to/timestamp/at_day
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch, PropertyMock
from uuid import uuid4

import pytest

from app.services.flow.types import FlowType
from app.services.flow_core import FlowCore
from app.utils.timezone import now_sao_paulo


class _QueryResult:
    """Simulate SQLAlchemy result proxy."""

    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class _AsyncLikeSession:
    """Session that handles both sync and async call patterns."""

    def __init__(self, execute_results=None):
        self._execute_results = list(execute_results or [])
        self.execute = AsyncMock(side_effect=self._pop_execute_result)
        self.add = Mock()
        self.commit = AsyncMock()
        self.flush = AsyncMock()
        self.refresh = AsyncMock()
        self.rollback = AsyncMock()
        self.query = Mock()

    async def _pop_execute_result(self, _statement):
        if not self._execute_results:
            return _QueryResult(None)
        return _QueryResult(self._execute_results.pop(0))


def _make_flow_state(
    patient_id=None,
    flow_type_value="onboarding",
    current_step=1,
    status="active",
    step_data=None,
    version=0,
):
    """Create a mock PatientFlowState-like object."""
    fs = SimpleNamespace(
        id=uuid4(),
        patient_id=patient_id or uuid4(),
        flow_type=flow_type_value,
        current_step=current_step,
        status=status,
        step_data=step_data if step_data is not None else {},
        state_data=step_data if step_data is not None else {},
        version=version,
        started_at=now_sao_paulo(),
        flow_template_version_id=uuid4(),
    )
    return fs


def _make_service(db=None, active_flow=None) -> FlowCore:
    """Create FlowCore with mocked dependencies.
    
    When active_flow is provided, patches flow_state_repo.get_active_flow
    to return it directly — bypassing the Mock chain issue where db.query()
    returns Mock objects that confuse _is_awaiting_response().
    """
    if db is None:
        db = _AsyncLikeSession()
    service = FlowCore(
        db,
        platform_sync=Mock(),
        template_loader=Mock(),
        template_cache=Mock(),
    )
    if active_flow is not None:
        service.flow_state_repo = Mock()
        service.flow_state_repo.get_active_flow = Mock(return_value=active_flow)
    return service


# ============================================================================
# determine_flow_type tests
# ============================================================================


class TestDetermineFlowType:
    """Test flow type determination based on patient day number."""

    @pytest.mark.asyncio
    async def test_day_1_returns_onboarding(self):
        service = _make_service()
        result = await service.determine_flow_type(uuid4(), current_day=1)
        assert result == FlowType.ONBOARDING

    @pytest.mark.asyncio
    async def test_day_15_returns_onboarding(self):
        """Day 15 is the last onboarding day."""
        service = _make_service()
        result = await service.determine_flow_type(uuid4(), current_day=15)
        assert result == FlowType.ONBOARDING

    @pytest.mark.asyncio
    async def test_day_16_returns_daily_follow_up(self):
        """Day 16 is the first daily_follow_up day — the transition boundary."""
        service = _make_service()
        result = await service.determine_flow_type(uuid4(), current_day=16)
        assert result == FlowType.DAILY_FOLLOW_UP

    @pytest.mark.asyncio
    async def test_day_30_returns_daily_follow_up(self):
        service = _make_service()
        result = await service.determine_flow_type(uuid4(), current_day=30)
        assert result == FlowType.DAILY_FOLLOW_UP

    @pytest.mark.asyncio
    async def test_day_45_returns_daily_follow_up(self):
        """Day 45 is the last daily_follow_up day."""
        service = _make_service()
        result = await service.determine_flow_type(uuid4(), current_day=45)
        assert result == FlowType.DAILY_FOLLOW_UP

    @pytest.mark.asyncio
    async def test_day_46_returns_quiz_mensal(self):
        """Day 46 transitions to quiz_mensal."""
        service = _make_service()
        result = await service.determine_flow_type(uuid4(), current_day=46)
        assert result == FlowType.QUIZ_MENSAL

    @pytest.mark.asyncio
    async def test_day_100_returns_quiz_mensal(self):
        service = _make_service()
        result = await service.determine_flow_type(uuid4(), current_day=100)
        assert result == FlowType.QUIZ_MENSAL


# ============================================================================
# _transition_flow_type tests
# ============================================================================


class TestTransitionFlowType:
    """Test step_data.transitions recording during flow type transition."""

    @pytest.mark.asyncio
    async def test_records_transition_in_step_data(self):
        service = _make_service()
        flow_state = _make_flow_state(flow_type_value="onboarding", step_data={})

        await service._transition_flow_type(
            flow_state, FlowType.DAILY_FOLLOW_UP, current_day=16
        )

        assert "transitions" in flow_state.step_data
        transitions = flow_state.step_data["transitions"]
        assert len(transitions) == 1

        t = transitions[0]
        assert t["from_flow"] == "onboarding"
        assert t["to_flow"] == "daily_follow_up"
        assert t["at_day"] == 16
        assert "timestamp" in t

    @pytest.mark.asyncio
    async def test_updates_flow_type(self):
        service = _make_service()
        flow_state = _make_flow_state(flow_type_value="onboarding")

        await service._transition_flow_type(
            flow_state, FlowType.DAILY_FOLLOW_UP, current_day=16
        )

        # flow_type should be updated to new value
        assert flow_state.flow_type == FlowType.DAILY_FOLLOW_UP.value

    @pytest.mark.asyncio
    async def test_appends_to_existing_transitions(self):
        """Multiple transitions should accumulate."""
        service = _make_service()
        existing_transition = {
            "timestamp": "2025-01-01T00:00:00",
            "from_flow": "custom",
            "to_flow": "onboarding",
            "at_day": 1,
        }
        flow_state = _make_flow_state(
            flow_type_value="onboarding",
            step_data={"transitions": [existing_transition]},
        )

        await service._transition_flow_type(
            flow_state, FlowType.DAILY_FOLLOW_UP, current_day=16
        )

        transitions = flow_state.step_data["transitions"]
        assert len(transitions) == 2
        assert transitions[0] == existing_transition
        assert transitions[1]["from_flow"] == "onboarding"
        assert transitions[1]["to_flow"] == "daily_follow_up"

    @pytest.mark.asyncio
    async def test_initializes_step_data_if_none(self):
        service = _make_service()
        flow_state = _make_flow_state(flow_type_value="onboarding", step_data=None)
        flow_state.step_data = None  # Force None

        await service._transition_flow_type(
            flow_state, FlowType.DAILY_FOLLOW_UP, current_day=16
        )

        assert flow_state.step_data is not None
        assert len(flow_state.step_data["transitions"]) == 1

    @pytest.mark.asyncio
    async def test_daily_to_quiz_transition(self):
        service = _make_service()
        flow_state = _make_flow_state(flow_type_value="daily_follow_up")

        await service._transition_flow_type(
            flow_state, FlowType.QUIZ_MENSAL, current_day=46
        )

        t = flow_state.step_data["transitions"][0]
        assert t["from_flow"] == "daily_follow_up"
        assert t["to_flow"] == "quiz_mensal"
        assert t["at_day"] == 46


# ============================================================================
# advance_patient_flow with transition tests
# ============================================================================


class TestAdvancePatientFlowTransition:
    """Test advance_patient_flow triggers transition at day 16."""

    @pytest.mark.asyncio
    async def test_force_day_16_transitions_onboarding_to_daily(self):
        """Core test: force_day=16 on an onboarding flow triggers transition."""
        patient_id = uuid4()
        flow_state = _make_flow_state(
            patient_id=patient_id,
            flow_type_value="onboarding",
            current_step=15,
            step_data={},
            version=0,
        )

        # DB session only needed for _commit_flow_state_with_lock version check
        db = _AsyncLikeSession([0])

        service = _make_service(db, active_flow=flow_state)
        service.flow_broadcaster = Mock()
        service.flow_broadcaster.broadcast_flow_state_change = AsyncMock()
        service.flow_broadcaster.broadcast_flow_progression = AsyncMock()
        service.platform_sync = Mock()
        service.platform_sync.sync_patient_record_update = AsyncMock()

        result = await service.advance_patient_flow(patient_id, force_day=16)

        assert result["status"] == "success"
        assert result["transitioned"] is True
        assert result["flow_type"] == "daily_follow_up"
        assert result["previous_flow_type"] == "onboarding"
        assert result["current_day"] == 16

    @pytest.mark.asyncio
    async def test_force_day_16_records_transition_in_step_data(self):
        """Verify step_data.transitions is populated after transition."""
        patient_id = uuid4()
        flow_state = _make_flow_state(
            patient_id=patient_id,
            flow_type_value="onboarding",
            current_step=15,
            step_data={},
            version=0,
        )

        db = _AsyncLikeSession([0])

        service = _make_service(db, active_flow=flow_state)
        service.flow_broadcaster = Mock()
        service.flow_broadcaster.broadcast_flow_state_change = AsyncMock()
        service.flow_broadcaster.broadcast_flow_progression = AsyncMock()
        service.platform_sync = Mock()
        service.platform_sync.sync_patient_record_update = AsyncMock()

        await service.advance_patient_flow(patient_id, force_day=16)

        # Verify step_data has transitions
        transitions = flow_state.step_data.get("transitions", [])
        assert len(transitions) == 1
        t = transitions[0]
        assert t["from_flow"] == "onboarding"
        assert t["to_flow"] == "daily_follow_up"
        assert t["at_day"] == 16
        assert "timestamp" in t

    @pytest.mark.asyncio
    async def test_force_day_16_step_data_has_flow_kind(self):
        """Verify step_data includes flow_kind after transition."""
        patient_id = uuid4()
        flow_state = _make_flow_state(
            patient_id=patient_id,
            flow_type_value="onboarding",
            current_step=15,
            step_data={},
            version=0,
        )

        db = _AsyncLikeSession([0])

        service = _make_service(db, active_flow=flow_state)
        service.flow_broadcaster = Mock()
        service.flow_broadcaster.broadcast_flow_state_change = AsyncMock()
        service.flow_broadcaster.broadcast_flow_progression = AsyncMock()
        service.platform_sync = Mock()
        service.platform_sync.sync_patient_record_update = AsyncMock()

        await service.advance_patient_flow(patient_id, force_day=16)

        assert flow_state.step_data["flow_kind"] == "daily_follow_up"
        assert flow_state.step_data["current_flow_day"] == 16
        assert "last_advancement" in flow_state.step_data

    @pytest.mark.asyncio
    async def test_force_day_15_no_transition(self):
        """Day 15 stays in onboarding — no transition."""
        patient_id = uuid4()
        flow_state = _make_flow_state(
            patient_id=patient_id,
            flow_type_value="onboarding",
            current_step=14,
            step_data={},
            version=0,
        )

        db = _AsyncLikeSession([0])

        service = _make_service(db, active_flow=flow_state)
        service.flow_broadcaster = Mock()
        service.flow_broadcaster.broadcast_flow_state_change = AsyncMock()
        service.flow_broadcaster.broadcast_flow_progression = AsyncMock()
        service.platform_sync = Mock()
        service.platform_sync.sync_patient_record_update = AsyncMock()

        result = await service.advance_patient_flow(patient_id, force_day=15)

        assert result["transitioned"] is False
        assert result["flow_type"] == "onboarding"
        assert "transitions" not in flow_state.step_data

    @pytest.mark.asyncio
    async def test_broadcasts_flow_transition_milestone(self):
        """Transition should broadcast milestone='flow_transition'."""
        patient_id = uuid4()
        flow_state = _make_flow_state(
            patient_id=patient_id,
            flow_type_value="onboarding",
            current_step=15,
            step_data={},
            version=0,
        )

        db = _AsyncLikeSession([0])

        service = _make_service(db, active_flow=flow_state)
        service.flow_broadcaster = Mock()
        service.flow_broadcaster.broadcast_flow_state_change = AsyncMock()
        service.flow_broadcaster.broadcast_flow_progression = AsyncMock()
        service.platform_sync = Mock()
        service.platform_sync.sync_patient_record_update = AsyncMock()

        await service.advance_patient_flow(patient_id, force_day=16)

        service.flow_broadcaster.broadcast_flow_progression.assert_awaited_once()
        call_kwargs = service.flow_broadcaster.broadcast_flow_progression.call_args[1]
        assert call_kwargs["milestone_reached"] == "flow_transition"
        assert call_kwargs["flow_type"] == "daily_follow_up"
        assert call_kwargs["from_day"] == 15
        assert call_kwargs["to_day"] == 16

    @pytest.mark.asyncio
    async def test_blocked_when_awaiting_response(self):
        """Cannot advance when awaiting patient response."""
        from app.exceptions import FlowStateConflictError

        patient_id = uuid4()
        flow_state = _make_flow_state(
            patient_id=patient_id,
            flow_type_value="onboarding",
            current_step=15,
            step_data={"awaiting_response": True},
            version=0,
        )

        db = _AsyncLikeSession()

        service = _make_service(db, active_flow=flow_state)
        service.flow_broadcaster = Mock()
        service.platform_sync = Mock()

        with pytest.raises(FlowStateConflictError):
            await service.advance_patient_flow(patient_id, force_day=16)

    @pytest.mark.asyncio
    async def test_sync_records_flow_advancement_with_transition_flag(self):
        """Platform sync receives transitioned=True in flow_interaction_data."""
        patient_id = uuid4()
        flow_state = _make_flow_state(
            patient_id=patient_id,
            flow_type_value="onboarding",
            current_step=15,
            step_data={},
            version=0,
        )

        db = _AsyncLikeSession([0])

        service = _make_service(db, active_flow=flow_state)
        service.flow_broadcaster = Mock()
        service.flow_broadcaster.broadcast_flow_state_change = AsyncMock()
        service.flow_broadcaster.broadcast_flow_progression = AsyncMock()
        service.platform_sync = Mock()
        service.platform_sync.sync_patient_record_update = AsyncMock()

        await service.advance_patient_flow(patient_id, force_day=16)

        service.platform_sync.sync_patient_record_update.assert_awaited_once()
        call_kwargs = service.platform_sync.sync_patient_record_update.call_args[1]
        advancement_data = call_kwargs["flow_interaction_data"]["flow_advancement"]
        assert advancement_data["transitioned"] is True
        assert advancement_data["flow_type"] == "daily_follow_up"
        assert advancement_data["current_day"] == 16
