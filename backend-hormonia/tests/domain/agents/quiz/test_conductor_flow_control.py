from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.agents.quiz.conductor import QuizConductor


def _build_conductor() -> QuizConductor:
    conductor = object.__new__(QuizConductor)
    conductor.max_questions_per_session = 10
    conductor.stress_threshold = 0.7
    conductor.send_message = AsyncMock()
    conductor._logger = MagicMock()

    conductor.notification_manager = SimpleNamespace(
        send_quiz_introduction=AsyncMock(),
        send_adaptation_message=AsyncMock(),
        send_completion_message=AsyncMock(),
        get_adaptation_reason=MagicMock(return_value="reason"),
    )
    conductor.question_presenter = SimpleNamespace(
        send_quiz_question=AsyncMock(
            return_value={"success": True, "question_id": "q1", "question_index": 0}
        )
    )
    conductor.progress_tracker = SimpleNamespace(
        stress_threshold=0.7,
        engagement_threshold=0.4,
        should_adapt_quiz=lambda context: False,
        determine_adaptation=lambda context: None,
    )
    conductor.session_coordinator = SimpleNamespace(
        complete_quiz_session=AsyncMock(),
    )
    conductor._should_adapt_quiz = AsyncMock(return_value=False)
    return conductor


@pytest.mark.asyncio
async def test_conduct_adaptive_quiz_sends_only_one_question_per_call():
    conductor = _build_conductor()
    context = SimpleNamespace(
        patient_id=uuid4(),
        session=SimpleNamespace(id=uuid4()),
        template=SimpleNamespace(
            questions=[
                {"id": "q1", "text": "Pergunta 1", "type": "open_text"},
                {"id": "q2", "text": "Pergunta 2", "type": "open_text"},
                {"id": "q3", "text": "Pergunta 3", "type": "open_text"},
            ]
        ),
        current_question=0,
        adaptation_history=[],
        mood_indicators={},
        stress_level=0.1,
        engagement_score=0.8,
        responses_so_far=[],
        knowledge_context={},
        patient_data=SimpleNamespace(name="Maria"),
    )

    result = await QuizConductor._conduct_adaptive_quiz(conductor, context)

    assert result["completed"] is False
    assert result["awaiting_response"] is True
    assert result["questions_asked"] == 1
    assert context.current_question == 0
    conductor.question_presenter.send_quiz_question.assert_awaited_once()


@pytest.mark.asyncio
async def test_conduct_adaptive_quiz_handles_missing_template_safely():
    conductor = _build_conductor()
    context = SimpleNamespace(
        patient_id=uuid4(),
        session=SimpleNamespace(id=uuid4()),
        template=None,
        current_question=0,
        adaptation_history=[],
        mood_indicators={},
        stress_level=0.1,
        engagement_score=0.8,
        responses_so_far=[],
        knowledge_context={},
        patient_data=SimpleNamespace(name="Maria"),
    )

    result = await QuizConductor._conduct_adaptive_quiz(conductor, context)

    assert result["completed"] is False
    assert "template" in result["error"].lower()
    conductor.question_presenter.send_quiz_question.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_task_uses_task_type_contract():
    conductor = object.__new__(QuizConductor)
    payload = {"patient_id": str(uuid4())}

    valid = await QuizConductor.validate_task(
        conductor,
        {"task_type": "conduct_quiz_session", "payload": payload},
    )
    legacy = await QuizConductor.validate_task(
        conductor,
        {"type": "conduct_quiz_session", "payload": payload},
    )

    assert valid is True
    assert legacy is False


@pytest.mark.asyncio
async def test_process_task_routes_with_task_type():
    conductor = _build_conductor()
    conductor._conduct_quiz_session = AsyncMock(return_value={"success": True})

    result = await QuizConductor.process_task(
        conductor,
        {
            "task_type": "conduct_quiz_session",
            "payload": {"patient_id": str(uuid4())},
        },
    )

    assert result == {"success": True}
    conductor._conduct_quiz_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_adapt_quiz_delegates_to_progress_tracker():
    conductor = _build_conductor()
    context = SimpleNamespace()
    should_adapt = MagicMock(return_value=True)
    conductor.progress_tracker.should_adapt_quiz = should_adapt

    result = await QuizConductor._should_adapt_quiz(conductor, context)

    assert result is True
    should_adapt.assert_called_once_with(context)


@pytest.mark.asyncio
async def test_determine_adaptation_delegates_to_progress_tracker():
    conductor = _build_conductor()
    context = SimpleNamespace()
    adaptation = object()
    determine_adaptation = MagicMock(return_value=adaptation)
    conductor.progress_tracker.determine_adaptation = determine_adaptation

    result = await QuizConductor._determine_adaptation(conductor, context)

    assert result is adaptation
    determine_adaptation.assert_called_once_with(context)


@pytest.mark.asyncio
async def test_conduct_adaptive_quiz_uses_tracker_stress_threshold_for_messages():
    conductor = _build_conductor()
    conductor.progress_tracker.stress_threshold = 0.33
    context = SimpleNamespace(
        patient_id=uuid4(),
        session=SimpleNamespace(id=uuid4()),
        template=SimpleNamespace(
            questions=[{"id": "q1", "text": "Pergunta 1", "type": "open_text"}]
        ),
        current_question=0,
        adaptation_history=[],
        mood_indicators={},
        stress_level=0.1,
        engagement_score=0.8,
        responses_so_far=[],
        knowledge_context={},
        patient_data=SimpleNamespace(name="Maria"),
    )

    result = await QuizConductor._conduct_adaptive_quiz(conductor, context)

    assert result["awaiting_response"] is True
    conductor.notification_manager.send_quiz_introduction.assert_awaited_once_with(
        context,
        conductor.max_questions_per_session,
        0.33,
    )
    conductor.question_presenter.send_quiz_question.assert_awaited_once_with(
        context,
        conductor.max_questions_per_session,
        0.33,
    )
