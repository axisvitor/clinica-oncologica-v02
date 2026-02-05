"""
Unit tests for SequentialMessageHandler bug fixes.

Tests cover:
1. Skip for days without config (FIX 1)
2. Reset message index when day changes (FIX 2)
3. Auto-advance in wait_each mode (FIX 3)
4. Skip handling in flow_automation (FIX 4)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from app.services.flow.sequential_message_handler import SequentialMessageHandler
from app.ai.langgraph.nodes import (
    load_flow_context,
    dispatch_send_mode,
    load_response_context,
    dispatch_response_continuation,
)
from app.models.flow import PatientFlowState
from app.models.patient import Patient


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def mock_patient():
    """Create a mock patient."""
    patient = MagicMock(spec=Patient)
    patient.id = uuid4()
    patient.name = "Test Patient"
    patient.phone = "+5511999999999"
    return patient


@pytest.fixture
def mock_flow_state():
    """Create a mock flow state."""
    flow_state = MagicMock(spec=PatientFlowState)
    flow_state.id = uuid4()
    flow_state.step_data = {}
    flow_state.last_interaction_at = None
    return flow_state


@pytest.fixture
def handler(mock_db):
    """Create handler with mocked dependencies."""
    handler = SequentialMessageHandler(mock_db, use_ai_personalization=False)
    handler.whatsapp_service = MagicMock()
    handler.whatsapp_service.send_message = AsyncMock(return_value=True)
    handler.message_repo = MagicMock()
    handler.message_repo.get_by_idempotency_key = MagicMock(return_value=None)
    return handler


class _FlowGraphStub:
    async def ainvoke(self, state, config=None):
        updates = await load_flow_context(state, config=config)
        state = {**state, **updates}
        if state.get("result"):
            return state
        updates = await dispatch_send_mode(state, config=config)
        return {**state, **updates}


class _ResponseGraphStub:
    async def ainvoke(self, state, config=None):
        updates = await load_response_context(state, config=config)
        state = {**state, **updates}
        if state.get("result"):
            return state
        updates = await dispatch_response_continuation(state, config=config)
        return {**state, **updates}


@pytest.fixture(autouse=True)
def mock_langgraph_graphs(monkeypatch):
    """Stub LangGraph to avoid dependency for unit tests."""
    monkeypatch.setattr(
        "app.services.flow.sequential_message_handler.get_flow_message_graph",
        lambda: _FlowGraphStub(),
    )
    monkeypatch.setattr(
        "app.services.flow.sequential_message_handler.get_flow_response_graph",
        lambda: _ResponseGraphStub(),
    )


class TestSkipForMissingDayConfig:
    """FIX 1: Days without config should return 'skip' not 'error'."""

    @pytest.mark.asyncio
    async def test_missing_day_returns_skip_status(self, handler, mock_db, mock_patient):
        """When day config doesn't exist, return skip instead of error."""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient
        handler._get_day_config = AsyncMock(return_value=None)
        
        # Act
        result = await handler.send_day_messages(
            patient_id=mock_patient.id,
            day_number=4,  # Day 4 has no messages in onboarding
            flow_kind="onboarding"
        )
        
        # Assert
        assert result["status"] == "skip"
        assert "No messages configured" in result["message"]

    @pytest.mark.asyncio
    async def test_skip_status_includes_day_number(self, handler, mock_db, mock_patient):
        """Skip message should include the day number for debugging."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient
        handler._get_day_config = AsyncMock(return_value=None)
        
        result = await handler.send_day_messages(
            patient_id=mock_patient.id,
            day_number=6,
            flow_kind="onboarding"
        )
        
        assert "day 6" in result["message"].lower()


class TestResetIndexOnDayChange:
    """FIX 2: Message index should reset when day changes."""

    @pytest.mark.asyncio
    async def test_index_resets_when_day_changes(
        self, handler, mock_db, mock_patient, mock_flow_state
    ):
        """current_day_message_index should reset to 0 when day changes."""
        # Arrange
        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient
        
        # Simulate previous day state
        mock_flow_state.step_data = {
            "current_flow_day": 3,
            "current_day_message_index": 2,  # Was on message 3 of day 3
            "day_complete": True,
            "awaiting_response": True
        }
        
        handler._get_or_create_flow_state = AsyncMock(return_value=mock_flow_state)
        handler._get_day_config = AsyncMock(return_value={
            "day": 5,
            "send_mode": "single",
            "messages": [{"content": "Test", "expects_response": True}]
        })
        handler._send_all_sequential = AsyncMock(return_value={"status": "ok"})
        
        # Act
        await handler.send_day_messages(
            patient_id=mock_patient.id,
            day_number=5,  # Different from previous day (3)
            flow_kind="onboarding"
        )
        
        # Assert - step_data should have been reset
        step_data = mock_flow_state.step_data
        assert step_data.get("current_day_message_index", -1) == 0
        assert step_data.get("day_complete") == False
        assert step_data.get("awaiting_response") == False

    @pytest.mark.asyncio
    async def test_index_not_reset_when_same_day(
        self, handler, mock_db, mock_patient, mock_flow_state
    ):
        """Index should NOT reset if same day (continuation after response)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient
        
        mock_flow_state.step_data = {
            "current_flow_day": 5,
            "current_day_message_index": 1,
            "awaiting_response": True
        }
        
        handler._get_or_create_flow_state = AsyncMock(return_value=mock_flow_state)
        handler._get_day_config = AsyncMock(return_value={
            "day": 5,
            "send_mode": "single",
            "messages": [
                {"content": "Msg 1", "expects_response": True},
                {"content": "Msg 2", "expects_response": False}
            ]
        })
        handler._send_all_sequential = AsyncMock(return_value={"status": "ok"})
        
        await handler.send_day_messages(
            patient_id=mock_patient.id,
            day_number=5,  # Same day
            flow_kind="onboarding"
        )
        
        # Index should remain at 1, not reset to 0
        assert mock_flow_state.step_data["current_day_message_index"] == 1


class TestWaitEachAutoAdvance:
    """FIX 3: wait_each mode should auto-advance through non-response messages."""

    @pytest.mark.asyncio
    async def test_auto_advances_through_non_response_messages(
        self, handler, mock_db, mock_patient, mock_flow_state
    ):
        """Messages with expects_response=False should auto-advance."""
        mock_flow_state.step_data = {}
        
        # Day 15 style: intro (no response) -> questions (response each)
        messages = [
            {"content": "Intro - no response", "expects_response": False},
            {"content": "Question 1", "expects_response": True},
            {"content": "Question 2", "expects_response": True},
        ]
        
        handler._personalize_message_ai = AsyncMock(
            side_effect=lambda m, *a, **k: m.get("content", "")
        )
        handler._send_flow_message = AsyncMock(return_value=True)
        
        result = await handler._send_wait_each_with_auto_advance(
            patient=mock_patient,
            messages=messages,
            start_index=0,
            flow_state=mock_flow_state,
            day_number=15,
            flow_kind="onboarding"
        )
        
        # Should have stopped at message index 1 (first expects_response=True)
        assert result["status"] == "waiting"
        assert result["message_index"] == 1
        assert result["sent_count"] == 2  # Sent msg 0 and msg 1

    @pytest.mark.asyncio
    async def test_completes_day_if_all_non_response(
        self, handler, mock_db, mock_patient, mock_flow_state
    ):
        """If all messages are expects_response=False, complete the day."""
        mock_flow_state.step_data = {}
        
        messages = [
            {"content": "Info 1", "expects_response": False},
            {"content": "Info 2", "expects_response": False},
        ]
        
        handler._personalize_message_ai = AsyncMock(
            side_effect=lambda m, *a, **k: m.get("content", "")
        )
        handler._send_flow_message = AsyncMock(return_value=True)
        
        result = await handler._send_wait_each_with_auto_advance(
            patient=mock_patient,
            messages=messages,
            start_index=0,
            flow_state=mock_flow_state,
            day_number=2,
            flow_kind="onboarding"
        )
        
        assert result["status"] == "complete"
        assert result["sent_count"] == 2

    @pytest.mark.asyncio
    async def test_default_expects_response_true_for_wait_each(
        self, handler, mock_db, mock_patient, mock_flow_state
    ):
        """Messages without expects_response field should default to True."""
        mock_flow_state.step_data = {}
        
        # Message without expects_response field
        messages = [
            {"content": "Question without explicit expects_response"}
        ]
        
        handler._personalize_message_ai = AsyncMock(
            side_effect=lambda m, *a, **k: m.get("content", "")
        )
        handler._send_flow_message = AsyncMock(return_value=True)
        
        result = await handler._send_wait_each_with_auto_advance(
            patient=mock_patient,
            messages=messages,
            start_index=0,
            flow_state=mock_flow_state,
            day_number=15,
            flow_kind="onboarding"
        )
        
        # Should wait for response (default True)
        assert result["status"] == "waiting"
        assert result["awaiting_response"] == True


class TestFlowAutomationSkipHandling:
    """FIX 4: Skip status should not count as questions_sent."""

    def test_skip_increments_skipped_not_sent(self):
        """When handler returns skip, increment skipped counter."""
        # This would be an integration test with flow_automation.py
        # For now, we just document the expected behavior
        
        # Expected behavior:
        # if result.get("status") == "skip":
        #     skipped += 1
        #     continue  # Don't increment questions_sent
        
        # The actual test would mock the entire flow_automation task
        pass
