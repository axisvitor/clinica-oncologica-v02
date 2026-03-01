import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.domain.agents.quiz.question_presenter import QuestionPresenter


@pytest.mark.asyncio
async def test_apply_ai_personalization_accepts_string_response():
    gemini_client = MagicMock()
    gemini_client.generate_content = AsyncMock(return_value="Texto personalizado")

    presenter = QuestionPresenter(
        db_session=MagicMock(),
        quiz_template_service=MagicMock(),
        message_sender=MagicMock(),
        agent_id="agent-1",
        gemini_client=gemini_client,
    )

    question = {"text": "Como voce se sente?", "description": "Descricao"}
    context = {
        "patient_name": "Maria",
        "mood_trend": 0.1,
        "stress_level": 0.2,
        "engagement_score": 0.5,
        "current_day": 3,
    }

    result = await presenter.apply_ai_personalization(question, context)

    gemini_client.generate_content.assert_awaited_once()
    assert result is not None
    assert result["text"] == "Texto personalizado"


@pytest.mark.asyncio
async def test_send_quiz_question_returns_safe_error_when_template_is_missing():
    presenter = QuestionPresenter(
        db_session=MagicMock(),
        quiz_template_service=MagicMock(),
        message_sender=MagicMock(),
        agent_id="agent-1",
        gemini_client=None,
    )

    context = SimpleNamespace(
        patient_id="patient-id",
        session=SimpleNamespace(id="session-id"),
        template=None,
        current_question=0,
        patient_data=SimpleNamespace(name="Maria"),
        stress_level=0.1,
    )

    result = await presenter.send_quiz_question(
        context=context,
        max_questions=10,
        stress_threshold=0.7,
    )

    assert result["success"] is False
    assert "template" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_or_create_quiz_template_falls_back_to_cached_template_name():
    template = SimpleNamespace(id="template-id", name="fallback_template")
    quiz_template_service = MagicMock()

    def _mock_get_template_by_name(name: str):
        if name == "fallback_template":
            return template
        return None

    quiz_template_service.get_template_by_name.side_effect = _mock_get_template_by_name
    quiz_template_service.get_templates.return_value = ([], 0)

    presenter = QuestionPresenter(
        db_session=MagicMock(),
        quiz_template_service=quiz_template_service,
        message_sender=MagicMock(),
        agent_id="agent-1",
    )
    presenter.quiz_templates = {"fallback_template": {"name": "fallback_template"}}

    result = await presenter.get_or_create_quiz_template(
        quiz_type="unknown_type",
        context=SimpleNamespace(template=None),
    )

    assert result is template
