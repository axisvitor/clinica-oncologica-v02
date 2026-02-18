from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.agents.quiz import response_handler as response_handler_module
from app.domain.agents.quiz.response_handler import ResponseHandler


def _build_handler(active_session=None) -> ResponseHandler:
    db_session = MagicMock()
    quiz_session_service = MagicMock()
    quiz_response_service = MagicMock()

    if active_session is None:
        active_session = SimpleNamespace(
            id=uuid4(),
            current_question=0,
            quiz_template_id=uuid4(),
        )
    quiz_session_service.get_active_session.return_value = active_session

    return ResponseHandler(
        db_session=db_session,
        quiz_session_service=quiz_session_service,
        quiz_response_service=quiz_response_service,
        agent_id="agent-test",
        logger=MagicMock(),
    )


def _build_context(active_session, current_question=0):
    return SimpleNamespace(
        patient_id=uuid4(),
        session=active_session,
        template=SimpleNamespace(
            questions=[
                {"id": "q1", "text": "Como você está?", "type": "open_text"},
                {"id": "q2", "text": "Sua energia hoje?", "type": "scale"},
            ]
        ),
        current_question=current_question,
        responses_so_far=[],
        adaptation_history=[],
        mood_indicators={},
        stress_level=0.1,
        engagement_score=0.8,
        patient_data=SimpleNamespace(name="Maria"),
    )


@pytest.mark.asyncio
async def test_process_quiz_response_triggers_next_question_callback(monkeypatch):
    active_session = SimpleNamespace(
        id=uuid4(),
        current_question=0,
        quiz_template_id=uuid4(),
    )
    handler = _build_handler(active_session=active_session)
    context = _build_context(active_session)

    async def _fake_debounce(*args, **kwargs):
        return {"success": True, "action": "next_question", "question_index": 1}

    monkeypatch.setattr(
        response_handler_module, "process_quiz_response_with_debounce", _fake_debounce
    )

    build_context = AsyncMock(return_value=context)
    send_next_question = AsyncMock(return_value={"success": True})
    complete_session = AsyncMock()
    send_clarification = AsyncMock()

    result = await handler.process_quiz_response(
        payload={"patient_id": str(uuid4()), "response_text": "ok"},
        build_context_callback=build_context,
        send_next_question_callback=send_next_question,
        complete_session_callback=complete_session,
        send_clarification_callback=send_clarification,
    )

    assert result["action"] == "next_question"
    send_next_question.assert_awaited_once_with(context)
    complete_session.assert_not_awaited()
    send_clarification.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_quiz_response_triggers_completion_callback(monkeypatch):
    active_session = SimpleNamespace(
        id=uuid4(),
        current_question=1,
        quiz_template_id=uuid4(),
    )
    handler = _build_handler(active_session=active_session)
    context = _build_context(active_session, current_question=1)

    async def _fake_debounce(*args, **kwargs):
        return {"success": True, "action": "quiz_completed", "session_id": str(active_session.id)}

    monkeypatch.setattr(
        response_handler_module, "process_quiz_response_with_debounce", _fake_debounce
    )

    build_context = AsyncMock(return_value=context)
    send_next_question = AsyncMock()
    complete_session = AsyncMock()
    send_clarification = AsyncMock()

    result = await handler.process_quiz_response(
        payload={"patient_id": str(uuid4()), "response_text": "ok"},
        build_context_callback=build_context,
        send_next_question_callback=send_next_question,
        complete_session_callback=complete_session,
        send_clarification_callback=send_clarification,
    )

    assert result["action"] == "quiz_completed"
    complete_session.assert_awaited_once_with(context)
    send_next_question.assert_not_awaited()
    send_clarification.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_quiz_response_triggers_clarification_callback(monkeypatch):
    active_session = SimpleNamespace(
        id=uuid4(),
        current_question=0,
        quiz_template_id=uuid4(),
    )
    handler = _build_handler(active_session=active_session)
    context = _build_context(active_session)

    async def _fake_debounce(*args, **kwargs):
        return {
            "success": False,
            "action": "request_clarification",
            "error": "Resposta inválida",
        }

    monkeypatch.setattr(
        response_handler_module, "process_quiz_response_with_debounce", _fake_debounce
    )

    build_context = AsyncMock(return_value=context)
    send_next_question = AsyncMock()
    complete_session = AsyncMock()
    send_clarification = AsyncMock()

    result = await handler.process_quiz_response(
        payload={"patient_id": str(uuid4()), "response_text": "??"},
        build_context_callback=build_context,
        send_next_question_callback=send_next_question,
        complete_session_callback=complete_session,
        send_clarification_callback=send_clarification,
    )

    assert result["action"] == "clarification_requested"
    send_clarification.assert_awaited_once_with(context, "Resposta inválida")
    send_next_question.assert_not_awaited()
    complete_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_quiz_response_uses_fallback_when_primary_flow_fails(monkeypatch):
    active_session = SimpleNamespace(
        id=uuid4(),
        current_question=0,
        quiz_template_id=uuid4(),
    )
    handler = _build_handler(active_session=active_session)
    context = _build_context(active_session)

    async def _fake_debounce(*args, **kwargs):
        return {"success": False, "action": "error", "error": "ai_failure"}

    monkeypatch.setattr(
        response_handler_module, "process_quiz_response_with_debounce", _fake_debounce
    )
    handler.process_response_with_swarm = AsyncMock(
        return_value={"valid": False, "error": "Não entendi"}
    )

    build_context = AsyncMock(return_value=context)
    send_next_question = AsyncMock()
    complete_session = AsyncMock()
    send_clarification = AsyncMock()

    result = await handler.process_quiz_response(
        payload={"patient_id": str(uuid4()), "response_text": "texto"},
        build_context_callback=build_context,
        send_next_question_callback=send_next_question,
        complete_session_callback=complete_session,
        send_clarification_callback=send_clarification,
    )

    assert result["fallback"] is True
    assert result["action"] == "clarification_requested"
    send_clarification.assert_awaited_once()
    send_next_question.assert_not_awaited()
    complete_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_response_with_swarm_handles_missing_template():
    handler = _build_handler()
    context = SimpleNamespace(template=None, current_question=0)

    result = await handler.process_response_with_swarm(context, "resposta")

    assert result["valid"] is False
    assert "template" in result["error"].lower()


@pytest.mark.asyncio
async def test_process_response_with_swarm_tolerates_ai_failure():
    handler = _build_handler()
    context = SimpleNamespace(
        template=SimpleNamespace(
            questions=[
                {
                    "id": "q1",
                    "text": "Escolha uma opção",
                    "type": "multiple_choice",
                    "options": [{"value": "a", "text": "Opção A"}],
                }
            ]
        ),
        current_question=0,
        responses_so_far=[],
        patient_data=SimpleNamespace(name="Maria"),
        session=SimpleNamespace(id=uuid4()),
    )
    handler.ai_enhanced_processing = AsyncMock(side_effect=RuntimeError("AI offline"))

    result = await handler.process_response_with_swarm(context, "resposta inválida")

    assert result["valid"] is False
    assert result["confidence"] == 0.2
