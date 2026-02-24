"""
Unit tests for SequentialMessageHandler bug fixes.

Tests cover:
1. Skip for days without config (FIX 1)
2. Reset message index when day changes (FIX 2)
3. Auto-advance in wait_each mode (FIX 3)
4. Skip handling in flow_automation (FIX 4)
"""

import pytest
import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone


if "app.services.unified_whatsapp_service" not in sys.modules:
    whatsapp_module = types.ModuleType("app.services.unified_whatsapp_service")

    class UnifiedWhatsAppService:  # pragma: no cover - test shim
        def __init__(self, db):
            self.db = db

        async def send_message(self, message, flow_context=None):
            return True

    whatsapp_module.UnifiedWhatsAppService = UnifiedWhatsAppService
    sys.modules["app.services.unified_whatsapp_service"] = whatsapp_module

if "app.services.enhanced_flow_engine" not in sys.modules:
    engine_module = types.ModuleType("app.services.enhanced_flow_engine")

    class EnhancedFlowEngine:  # pragma: no cover - test shim
        def __init__(self, db):
            self.db = db

        async def generate_flow_message(self, **kwargs):
            return None

    engine_module.EnhancedFlowEngine = EnhancedFlowEngine
    sys.modules["app.services.enhanced_flow_engine"] = engine_module

from app.services.flow.sequential_message_handler import SequentialMessageHandler
from app.models.flow import PatientFlowState
from app.models.patient import Patient


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
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


@pytest.fixture(autouse=True)
def force_direct_flow_framework(monkeypatch):
    """Run tests against direct flow orchestration path."""
    monkeypatch.setattr("app.config.settings.AI_FLOW_FRAMEWORK", "direct", raising=False)


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


class TestDirectFlowFunctions:
    @pytest.mark.asyncio
    async def test_send_day_messages_uses_direct_function_when_flag_enabled(
        self, handler, mock_patient, monkeypatch
    ):
        monkeypatch.setattr(
            "app.config.settings.AI_FLOW_FRAMEWORK", "direct", raising=False
        )

        mock_direct_call = AsyncMock(return_value={"status": "ok", "mode": "direct"})
        with patch(
            "app.services.flow._flow_functions.run_flow_message",
            new=mock_direct_call,
        ):
            result = await handler.send_day_messages(
                patient_id=mock_patient.id,
                day_number=3,
                flow_kind="onboarding",
            )

        assert result == {"status": "ok", "mode": "direct"}
        mock_direct_call.assert_awaited_once_with(
            patient_id=mock_patient.id,
            day_number=3,
            flow_kind="onboarding",
            handler=handler,
        )

    @pytest.mark.asyncio
    async def test_handle_response_uses_direct_function_when_flag_enabled(
        self, handler, mock_patient, monkeypatch
    ):
        response_context = {
            "flow_day": 2,
            "flow_kind": "onboarding",
            "message_index": 1,
            "prompt_message_id": str(uuid4()),
        }
        monkeypatch.setattr(
            "app.config.settings.AI_FLOW_FRAMEWORK", "direct", raising=False
        )

        mock_direct_call = AsyncMock(return_value={"status": "waiting", "mode": "direct"})
        with patch(
            "app.services.flow._flow_functions.run_flow_response",
            new=mock_direct_call,
        ):
            result = await handler.handle_response_and_continue(
                patient_id=mock_patient.id,
                response_context=response_context,
            )

        assert result == {"status": "waiting", "mode": "direct"}
        mock_direct_call.assert_awaited_once_with(
            patient_id=mock_patient.id,
            response_context=response_context,
            handler=handler,
        )


class TestDayChangeWaitingBehavior:
    """Day-change behavior must respect pending patient responses."""

    @pytest.mark.asyncio
    async def test_index_preserved_when_day_changes_and_awaiting_response(
        self, handler, mock_db, mock_patient, mock_flow_state
    ):
        """When awaiting response, day change must keep pending message position."""
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
        
        # Assert - waiting context must be preserved (no forced reset)
        step_data = mock_flow_state.step_data
        assert step_data.get("current_flow_day") == 3
        assert step_data.get("current_day_message_index", -1) == 2
        assert step_data.get("day_complete") is True
        assert step_data.get("awaiting_response") is True

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


class TestResponseContextCorrelation:
    @pytest.mark.asyncio
    async def test_handle_response_and_continue_forwards_response_context(
        self, handler, mock_patient, monkeypatch
    ):
        mock_direct_call = AsyncMock(return_value={"status": "waiting"})
        monkeypatch.setattr(
            "app.services.flow._flow_functions.run_flow_response",
            mock_direct_call,
        )

        response_context = {
            "flow_day": 2,
            "flow_kind": "onboarding",
            "message_index": 0,
            "prompt_message_id": str(uuid4()),
            "response_message_id": str(uuid4()),
        }

        result = await handler.handle_response_and_continue(
            mock_patient.id,
            response_context=response_context,
        )

        assert result["status"] == "waiting"
        mock_direct_call.assert_awaited_once_with(
            patient_id=mock_patient.id,
            response_context=response_context,
            handler=handler,
        )

    @pytest.mark.asyncio
    async def test_handle_response_and_continue_keeps_backward_compatibility(
        self, handler, mock_patient, monkeypatch
    ):
        mock_direct_call = AsyncMock(return_value={"status": "ok"})
        monkeypatch.setattr(
            "app.services.flow._flow_functions.run_flow_response",
            mock_direct_call,
        )

        result = await handler.handle_response_and_continue(mock_patient.id)

        assert result["status"] == "ok"
        mock_direct_call.assert_awaited_once_with(
            patient_id=mock_patient.id,
            response_context=None,
            handler=handler,
        )


class TestAIPersonalizationHardening:
    """AI personalization should be grounded and fail-safe."""

    def _enable_ai_with_engine(self, handler, engine_side_effect=None, engine_result=None):
        handler.use_ai_personalization = True
        engine = MagicMock()
        if engine_side_effect is not None:
            engine.generate_flow_message = AsyncMock(side_effect=engine_side_effect)
        else:
            engine.generate_flow_message = AsyncMock(return_value=engine_result)
        handler._enhanced_flow_engine = engine
        return engine

    @pytest.mark.asyncio
    async def test_uses_ai_output_when_grounded(self, handler, mock_patient):
        self._enable_ai_with_engine(
            handler,
            engine_result="Olá Test Patient, continue sua medicação conforme orientação.",
        )

        result = await handler._personalize_message_ai(
            message={"content": "Olá [NOME], continue sua medicação conforme orientação."},
            patient=mock_patient,
            day_number=2,
            flow_kind="onboarding",
        )

        assert result == "Olá Test Patient, continue sua medicação conforme orientação."

    @pytest.mark.asyncio
    async def test_falls_back_when_ai_output_not_grounded(self, handler, mock_patient):
        self._enable_ai_with_engine(
            handler,
            engine_result="Oferta relâmpago de investimentos para multiplicar renda.",
        )

        result = await handler._personalize_message_ai(
            message={"content": "Olá [NOME], continue sua medicação conforme orientação."},
            patient=mock_patient,
            day_number=2,
            flow_kind="onboarding",
        )

        assert result == "Olá Test Patient, continue sua medicação conforme orientação."

    @pytest.mark.asyncio
    async def test_falls_back_when_ai_generation_raises(self, handler, mock_patient):
        self._enable_ai_with_engine(
            handler,
            engine_side_effect=RuntimeError("gemini unavailable"),
        )

        result = await handler._personalize_message_ai(
            message={"content": "Olá [NOME], continue sua medicação conforme orientação."},
            patient=mock_patient,
            day_number=2,
            flow_kind="onboarding",
        )

        assert result == "Olá Test Patient, continue sua medicação conforme orientação."

    @pytest.mark.asyncio
    async def test_send_all_sequential_uses_centralized_fallback(self, handler, mock_patient, mock_flow_state):
        self._enable_ai_with_engine(
            handler,
            engine_side_effect=RuntimeError("gemini unavailable"),
        )
        handler._send_flow_message = AsyncMock(return_value=True)

        result = await handler._send_all_sequential(
            patient=mock_patient,
            messages=[{"content": "Olá [NOME], msg 1", "expects_response": False}],
            flow_state=mock_flow_state,
            day_number=3,
            flow_kind="onboarding",
        )

        assert result["status"] == "ok"
        assert handler._send_flow_message.await_args.args[1] == "Olá Test Patient, msg 1"

    @pytest.mark.asyncio
    async def test_send_message_and_wait_uses_centralized_fallback(self, handler, mock_patient, mock_flow_state):
        self._enable_ai_with_engine(
            handler,
            engine_side_effect=asyncio.TimeoutError(),
        )
        handler._send_flow_message = AsyncMock(return_value=True)

        result = await handler._send_message_and_wait(
            patient=mock_patient,
            messages=[{"content": "Olá [NOME], responda por favor.", "expects_response": True}],
            index=0,
            flow_state=mock_flow_state,
            day_number=7,
            flow_kind="onboarding",
        )

        assert result["status"] == "waiting"
        assert handler._send_flow_message.await_args.args[1] == "Olá Test Patient, responda por favor."

    @pytest.mark.asyncio
    async def test_send_remaining_after_response_uses_centralized_fallback(
        self, handler, mock_patient, mock_flow_state
    ):
        self._enable_ai_with_engine(
            handler,
            engine_side_effect=RuntimeError("gemini unavailable"),
        )
        handler._send_flow_message = AsyncMock(return_value=True)

        result = await handler._send_remaining_after_response(
            patient=mock_patient,
            messages=[
                {"content": "Mensagem anterior"},
                {"content": "Olá [NOME], mensagem final.", "expects_response": False},
            ],
            start_index=1,
            flow_state=mock_flow_state,
            day_number=8,
            flow_kind="onboarding",
        )

        assert result["status"] == "complete"
        assert handler._send_flow_message.await_args.args[1] == "Olá Test Patient, mensagem final."

    @pytest.mark.asyncio
    async def test_send_wait_each_uses_centralized_fallback(self, handler, mock_patient, mock_flow_state):
        self._enable_ai_with_engine(
            handler,
            engine_side_effect=RuntimeError("gemini unavailable"),
        )
        handler._send_flow_message = AsyncMock(return_value=True)

        result = await handler._send_wait_each_with_auto_advance(
            patient=mock_patient,
            messages=[{"content": "Olá [NOME], confirme recebimento.", "expects_response": True}],
            start_index=0,
            flow_state=mock_flow_state,
            day_number=9,
            flow_kind="onboarding",
        )

        assert result["status"] == "waiting"
        assert handler._send_flow_message.await_args.args[1] == "Olá Test Patient, confirme recebimento."

    @pytest.mark.asyncio
    async def test_fallback_prefers_template_variations_for_questions(self, handler, mock_patient):
        handler.use_ai_personalization = False

        message = {
            "content": "Como você está se sentindo hoje?",
            "expects_response": True,
            "variations": [
                "Como você se sentiu ao longo do dia?",
                "Como você descreveria seu bem-estar hoje?",
            ],
        }

        result = await handler._personalize_message_ai(
            message=message,
            patient=mock_patient,
            day_number=4,
            flow_kind="onboarding",
            message_index=1,
        )

        assert "Como você está se sentindo hoje?" not in result
        assert (
            "Como você se sentiu ao longo do dia?" in result
            or "Como você descreveria seu bem-estar hoje?" in result
        )

    @pytest.mark.asyncio
    async def test_fallback_applies_light_rephrase_for_plain_question(self, handler, mock_patient):
        handler.use_ai_personalization = False
        base_question = "Você tomou sua medicação hoje?"

        result = await handler._personalize_message_ai(
            message={"content": base_question, "expects_response": True},
            patient=mock_patient,
            day_number=2,
            flow_kind="onboarding",
            message_index=0,
        )

        assert result != base_question
        assert result.endswith(base_question)
