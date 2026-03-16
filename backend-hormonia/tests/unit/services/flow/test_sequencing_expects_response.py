"""
Tests for expects_response sequencing behavior across send modes.

Reproduces the bulk-send bug: _send_all_sequential sends ALL messages
regardless of per-message expects_response flags, only checking the
LAST message. These tests confirm the bug exists (pre-fix) and will
go green after the fix.
"""

import pytest
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# ── shims for heavy imports (same pattern as test_sequential_message_handler.py)

if "app.services.unified_whatsapp_service" not in sys.modules:
    _whatsapp_module = types.ModuleType("app.services.unified_whatsapp_service")

    class UnifiedWhatsAppService:  # pragma: no cover - test shim
        def __init__(self, db):
            self.db = db

        async def send_message(self, message, flow_context=None):
            return True

    _whatsapp_module.UnifiedWhatsAppService = UnifiedWhatsAppService
    sys.modules["app.services.unified_whatsapp_service"] = _whatsapp_module

if "app.services.enhanced_flow_engine" not in sys.modules:
    _engine_module = types.ModuleType("app.services.enhanced_flow_engine")

    class EnhancedFlowEngine:  # pragma: no cover - test shim
        def __init__(self, db):
            self.db = db

        async def generate_flow_message(self, **kwargs):
            return None

    _engine_module.EnhancedFlowEngine = EnhancedFlowEngine
    sys.modules["app.services.enhanced_flow_engine"] = _engine_module

from app.services.flow.sequential_message_handler import SequentialMessageHandler
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.config import settings as app_settings

# Module path for patching advance_day_atomic inside sequencing.py
_ADVANCE_DAY_ATOMIC = (
    "app.services.flow.sequential_message_handler_pkg.sequencing.advance_day_atomic"
)


# ── fixtures ──

@pytest.fixture(autouse=True)
def force_direct_framework(monkeypatch):
    if hasattr(app_settings, "AI_FLOW_FRAMEWORK"):
        monkeypatch.setattr(app_settings, "AI_FLOW_FRAMEWORK", "direct", raising=False)
    else:
        monkeypatch.setenv("AI_FLOW_FRAMEWORK", "direct")


@pytest.fixture(autouse=True)
def patch_advance_day_atomic():
    """Prevent advance_day_atomic from hitting real DB in all tests."""
    with patch(_ADVANCE_DAY_ATOMIC, new_callable=AsyncMock) as mock_adv:
        mock_adv.return_value = {"day_complete": True}
        yield mock_adv


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_patient():
    patient = MagicMock(spec=Patient)
    patient.id = uuid4()
    patient.name = "Test Patient"
    patient.phone = "+5511999999999"
    return patient


@pytest.fixture
def mock_flow_state():
    flow_state = MagicMock(spec=PatientFlowState)
    flow_state.id = uuid4()
    flow_state.step_data = {}
    flow_state.last_interaction_at = None
    return flow_state


@pytest.fixture
def handler(mock_db):
    handler = SequentialMessageHandler(mock_db, use_ai_personalization=False)
    handler.whatsapp_service = MagicMock()
    handler.whatsapp_service.send_message = AsyncMock(return_value=True)
    handler.message_repo = MagicMock()
    handler.message_repo.get_by_idempotency_key = MagicMock(return_value=None)
    # stub personalization to pass-through content
    handler._personalize_message_ai = AsyncMock(
        side_effect=lambda m, *a, **kw: m.get("content", "")
    )
    # stub actual send to return True
    handler._send_flow_message = AsyncMock(return_value=True)
    # stub delay to no-op
    handler._await_inter_message_delay = AsyncMock()
    # stub message id resolution
    handler._resolve_sent_message_id = MagicMock(return_value=str(uuid4()))
    # stub _mark_last_message_sent (used by advance_day_atomic)
    handler._mark_last_message_sent = MagicMock(
        side_effect=lambda sd: sd.update({"last_message_sent_at": "test"})
    )
    return handler


# ── helpers ──

def _make_messages(*expects_flags: bool) -> list:
    """Build message dicts from a sequence of expects_response booleans."""
    return [
        {
            "content": f"Message {i}",
            "expects_response": flag,
        }
        for i, flag in enumerate(expects_flags)
    ]


# =============================================================================
# _send_all_sequential — sequential_auto mode
# =============================================================================


class TestSequentialAutoStopsAtExpectsResponse:
    """BUG REPRODUCTION: _send_all_sequential must stop when a message
    in the middle of the list has expects_response=true.

    Current code sends ALL messages and only checks expects_response on
    the LAST message. This test should FAIL pre-fix.
    """

    @pytest.mark.asyncio
    async def test_sequential_auto_stops_at_expects_response(
        self, handler, mock_patient, mock_flow_state
    ):
        # 3 messages: [false, true, false]
        # Expected: send msg 0, send msg 1, STOP. send_flow_message called 2x.
        messages = _make_messages(False, True, False)

        result = await handler._send_all_sequential(
            patient=mock_patient,
            messages=messages,
            flow_state=mock_flow_state,
            day_number=5,
            flow_kind="onboarding",
        )

        # Must stop at index 1 and wait for response
        assert handler._send_flow_message.await_count == 2, (
            f"Expected 2 calls (stop at expects_response=true on index 1), "
            f"got {handler._send_flow_message.await_count}"
        )
        assert result["status"] == "waiting"
        step_data = mock_flow_state.step_data
        assert step_data.get("awaiting_response") is True
        assert step_data.get("current_day_message_index") == 1


class TestSequentialAutoAllFalseSendsAll:
    """When all messages have expects_response=false, all should be sent
    and the day should advance. This should PASS pre-fix."""

    @pytest.mark.asyncio
    async def test_sequential_auto_all_false_sends_all(
        self, handler, mock_patient, mock_flow_state, patch_advance_day_atomic
    ):
        messages = _make_messages(False, False, False)

        result = await handler._send_all_sequential(
            patient=mock_patient,
            messages=messages,
            flow_state=mock_flow_state,
            day_number=3,
            flow_kind="onboarding",
        )

        assert handler._send_flow_message.await_count == 3
        assert result["status"] == "ok"
        assert result["sent_count"] == 3
        patch_advance_day_atomic.assert_awaited_once()


class TestSequentialAutoLastExpectsResponse:
    """When only the LAST message has expects_response=true, all should
    be sent and state should be awaiting_response. This PASSES pre-fix
    because current code checks the last message."""

    @pytest.mark.asyncio
    async def test_sequential_auto_last_expects_response(
        self, handler, mock_patient, mock_flow_state
    ):
        messages = _make_messages(False, False, True)

        result = await handler._send_all_sequential(
            patient=mock_patient,
            messages=messages,
            flow_state=mock_flow_state,
            day_number=3,
            flow_kind="onboarding",
        )

        assert handler._send_flow_message.await_count == 3
        step_data = mock_flow_state.step_data
        assert step_data.get("awaiting_response") is True
        assert step_data.get("current_day_message_index") == 2


# =============================================================================
# _send_remaining_after_response — continuation after patient response
# =============================================================================


class TestContinuationAfterResponseRespectsExpectsResponse:
    """_send_remaining_after_response already checks expects_response per
    message. This should PASS pre-fix."""

    @pytest.mark.asyncio
    async def test_continuation_after_response_respects_expects_response(
        self, handler, mock_patient, mock_flow_state
    ):
        # 4 messages total, continuing from index 2. msg[2]=true should stop.
        messages = [
            {"content": "Message 0", "expects_response": False},
            {"content": "Message 1", "expects_response": True},  # already answered
            {"content": "Message 2", "expects_response": True},  # should stop here
            {"content": "Message 3", "expects_response": False},
        ]

        result = await handler._send_remaining_after_response(
            patient=mock_patient,
            messages=messages,
            start_index=2,
            flow_state=mock_flow_state,
            day_number=5,
            flow_kind="onboarding",
        )

        # Should send msg[2] then stop (expects_response=true)
        assert handler._send_flow_message.await_count == 1
        assert result["status"] == "waiting"
        assert result["message_index"] == 2
        assert result["awaiting_response"] is True

    @pytest.mark.asyncio
    async def test_continuation_all_false_completes_day(
        self, handler, mock_patient, mock_flow_state, patch_advance_day_atomic
    ):
        messages = [
            {"content": "Message 0", "expects_response": True},  # already answered
            {"content": "Message 1", "expects_response": False},
            {"content": "Message 2", "expects_response": False},
        ]

        result = await handler._send_remaining_after_response(
            patient=mock_patient,
            messages=messages,
            start_index=1,
            flow_state=mock_flow_state,
            day_number=5,
            flow_kind="onboarding",
        )

        assert handler._send_flow_message.await_count == 2
        assert result["status"] == "complete"
        patch_advance_day_atomic.assert_awaited_once()


# =============================================================================
# _send_wait_each_with_auto_advance — wait_each mode
# =============================================================================


class TestWaitEachStopsAtFirstExpectsResponse:
    """wait_each mode already handles expects_response per message.
    Should PASS pre-fix."""

    @pytest.mark.asyncio
    async def test_wait_each_stops_at_expects_response(
        self, handler, mock_patient, mock_flow_state
    ):
        # msg[0] no wait, msg[1] waits — should send both, stop at 1
        messages = _make_messages(False, True)

        result = await handler._send_wait_each_with_auto_advance(
            patient=mock_patient,
            messages=messages,
            start_index=0,
            flow_state=mock_flow_state,
            day_number=10,
            flow_kind="onboarding",
        )

        assert handler._send_flow_message.await_count == 2
        assert result["status"] == "waiting"
        assert result["message_index"] == 1
        assert result["awaiting_response"] is True

    @pytest.mark.asyncio
    async def test_wait_each_completes_when_all_false(
        self, handler, mock_patient, mock_flow_state
    ):
        messages = _make_messages(False, False, False)

        result = await handler._send_wait_each_with_auto_advance(
            patient=mock_patient,
            messages=messages,
            start_index=0,
            flow_state=mock_flow_state,
            day_number=10,
            flow_kind="onboarding",
        )

        assert handler._send_flow_message.await_count == 3
        assert result["status"] == "complete"
        assert result["sent_count"] == 3
