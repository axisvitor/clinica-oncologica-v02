"""
Validation tests for a full 30-day daily flow sequence.

This isolates day-by-day coverage to ensure responses are attributed
to the correct day/message and that sequential continuation completes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.flow.sequential_message_handler import SequentialMessageHandler


DAY_START = 16
DAY_END = 45
FLOW_KIND = "daily_follow_up"


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def patient():
    """Create a mock patient."""
    patient = MagicMock(spec=Patient)
    patient.id = uuid4()
    patient.name = "Test Patient"
    patient.preferred_name = None
    patient.treatment_type = "hormone_therapy"
    return patient


@pytest.fixture
def flow_state():
    """Create a flow state instance with mutable state data."""
    state = PatientFlowState()
    state.id = uuid4()
    state.step_data = {}
    state.current_step = 0
    state.status = "active"
    return state


@pytest.fixture
def day_configs():
    """Build a 30-day config map with variable question counts (>= 6 on some days)."""
    configs = {}
    for day in range(DAY_START, DAY_END + 1):
        question_count = 2 + (day % 5)  # 2..6 questions/day
        messages = []
        for idx in range(question_count):
            messages.append(
                {"content": f"Dia {day} - pergunta {idx + 1}", "expects_response": True}
            )
        configs[day] = {
            "day": day,
            "send_mode": "wait_each",
            "messages": messages,
        }
    return configs


@pytest.fixture
def handler(mock_db, patient, flow_state, day_configs):
    """Create SequentialMessageHandler with mocked dependencies."""
    handler = SequentialMessageHandler(mock_db, use_ai_personalization=False)
    mock_db.query.return_value.filter.return_value.first.return_value = patient

    handler._get_or_create_flow_state = AsyncMock(return_value=flow_state)
    handler._get_day_config = AsyncMock(
        side_effect=lambda kind, day: day_configs.get(day)
    )
    handler._personalize_message_ai = AsyncMock(
        side_effect=lambda message, *args, **kwargs: message.get("content", "")
    )
    handler._send_flow_message = AsyncMock(return_value=True)
    handler.flow_state_repo = MagicMock()
    handler.flow_state_repo.get_active_flow = MagicMock(return_value=flow_state)
    return handler


@pytest.fixture
def engine(mock_db, patient, flow_state):
    """Create EnhancedFlowEngine with mocked AI dependencies."""
    mock_gemini = MagicMock()
    mock_gemini.analyze_response_sentiment = AsyncMock(
        return_value={
            "sentiment": "neutral",
            "requires_attention": False,
            "medical_concerns": False,
            "emotional_indicators": [],
        }
    )

    mock_memory = MagicMock()
    mock_memory.update_last_pattern_engagement = AsyncMock(return_value=None)
    mock_memory.store_message_pattern = AsyncMock(return_value=None)

    engine = EnhancedFlowEngine(
        mock_db,
        gemini_client=mock_gemini,
        conversation_memory=mock_memory,
        platform_sync=MagicMock(),
        template_loader=MagicMock(),
        template_cache=MagicMock(),
    )
    engine.patient_repo = MagicMock()
    engine.patient_repo.get = MagicMock(return_value=patient)
    engine.flow_state_repo = MagicMock()
    engine.flow_state_repo.get_active_flow = MagicMock(return_value=flow_state)
    return engine


@pytest.mark.asyncio
async def test_30_day_daily_flow_sequence(handler, engine, patient, flow_state, day_configs):
    """Validate a full 30-day sequence day-by-day with per-question responses."""
    response_keys = []

    for day in range(DAY_START, DAY_END + 1):
        flow_state.current_step = day

        send_result = await handler.send_day_messages(
            patient_id=patient.id,
            day_number=day,
            flow_kind=FLOW_KIND,
        )
        assert send_result["status"] == "waiting"

        total_questions = len(day_configs[day]["messages"])
        assert total_questions >= 2

        for idx in range(total_questions):
            step_data = flow_state.step_data
            assert step_data["current_flow_day"] == day
            assert step_data["current_day_message_index"] == idx
            if "awaiting_response" in step_data:
                assert step_data["awaiting_response"] is True

            response_context = {
                "flow_day": step_data.get("current_flow_day"),
                "flow_kind": step_data.get("flow_kind"),
                "message_index": step_data.get("current_day_message_index"),
                "response_message_id": str(uuid4()),
            }
            prompt_message_id = (
                step_data.get("pending_response_context", {}) or {}
            ).get("prompt_message_id")
            if prompt_message_id:
                response_context["prompt_message_id"] = str(prompt_message_id)
            response_text = f"Resposta dia {day} pergunta {idx + 1}"

            response_result = await engine.process_patient_response(
                patient_id=patient.id,
                response_text=response_text,
                response_context=response_context,
            )
            assert response_result["status"] == "processed"

            response_key = f"day_{day}_msg_{idx}"
            response_keys.append(response_key)
            stored = flow_state.state_data["responses_by_message"][response_key]
            assert stored["response_text"] == response_text
            assert stored["flow_day"] == day
            assert stored["message_index"] == idx

            assert flow_state.state_data["responses"][f"step_{day}"] == response_text

            continuation = await handler.handle_response_and_continue(
                patient.id,
                response_context=response_context,
            )
            if idx < total_questions - 1:
                assert continuation["status"] == "waiting"
                assert continuation["message_index"] == idx + 1
                assert flow_state.step_data["current_day_message_index"] == idx + 1
                if "awaiting_response" in flow_state.step_data:
                    assert flow_state.step_data["awaiting_response"] is True
            else:
                assert continuation["status"] == "day_complete"
                assert flow_state.step_data["day_complete"] is True
                if "awaiting_response" in flow_state.step_data:
                    assert flow_state.step_data["awaiting_response"] is False
                assert (
                    flow_state.step_data["current_day_message_index"]
                    == total_questions - 1
                )

    assert len(flow_state.state_data["responses_by_message"]) == len(response_keys)
    for key in response_keys:
        assert key in flow_state.state_data["responses_by_message"]
