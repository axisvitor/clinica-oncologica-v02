from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.domain.quizzes.delivery.service import DeliveryService
from app.domain.quizzes.integration.flow_integration.response_handler import (
    ConversationalQuizService,
)
from app.domain.quizzes.manager import QuizSessionManager
from app.domain.quizzes.queries.history import HistoryQuery
from app.domain.quizzes.question_renderer import QuestionRenderer
from app.domain.quizzes.report_generator import ReportGenerator
from app.domain.quizzes.resilience.link_resilience import QuizLinkResilienceService
from app.domain.quizzes.score_calculator import ScoreCalculator
from app.domain.quizzes.security.token_rotation import submit_quiz_response_with_rotation
from app.domain.quizzes.templates.template_service import QuizTemplateService
from app.exceptions import NotFoundError, ValidationError
from app.models.quiz import QuizResponse
from app.schemas.monthly_quiz import DeliveryMethod
from app.utils.timezone import now_sao_paulo


@pytest.mark.asyncio
async def test_delivery_service_skips_manual_and_does_not_use_whatsapp():
    service = DeliveryService(db=MagicMock())
    patient = SimpleNamespace(id=uuid4(), name="Paciente")
    template = SimpleNamespace()
    session = SimpleNamespace(id=uuid4())

    with patch("app.domain.quizzes.delivery.service.MessageFactory") as message_factory, patch(
        "app.domain.quizzes.delivery.service.UnifiedWhatsAppService"
    ) as whatsapp_service:
        result = await service.send_quiz_link_notification(
            patient=patient,
            template=template,
            session=session,
            link_url="https://example.test/q",
            delivery_method=DeliveryMethod.MANUAL,
            expiry_hours=72,
            custom_message=None,
        )

    assert result["sent"] is False
    assert result["reason"] == "manual_delivery"
    assert result["attempts"] == 0
    message_factory.assert_not_called()
    whatsapp_service.assert_not_called()


@pytest.mark.asyncio
async def test_delivery_service_whatsapp_branch_still_sends():
    service = DeliveryService(db=MagicMock())
    patient = SimpleNamespace(id=uuid4(), name="Paciente")
    template = SimpleNamespace()
    session = SimpleNamespace(id=uuid4())
    fake_message = SimpleNamespace(id=uuid4())

    with patch("app.domain.quizzes.delivery.service.MessageFactory") as message_factory, patch(
        "app.domain.quizzes.delivery.service.UnifiedWhatsAppService"
    ) as whatsapp_service:
        message_factory.return_value.create_monthly_quiz_link_message.return_value = (
            fake_message
        )
        whatsapp_service.return_value.send_message = AsyncMock(return_value=True)

        result = await service.send_quiz_link_notification(
            patient=patient,
            template=template,
            session=session,
            link_url="https://example.test/q",
            delivery_method=DeliveryMethod.WHATSAPP,
            expiry_hours=72,
            custom_message=None,
        )

    assert result["sent"] is True
    assert result["attempts"] == 1
    assert result["message_id"] == str(fake_message.id)


def test_score_calculator_counts_falsy_answers_as_answered():
    db = MagicMock()
    calculator = ScoreCalculator(db)
    session_id = uuid4()

    response_false = MagicMock(spec=QuizResponse)
    response_false.response_value = False
    response_false.response_metadata = {}

    response_zero = MagicMock(spec=QuizResponse)
    response_zero.response_value = 0
    response_zero.response_metadata = {}

    response_none = MagicMock(spec=QuizResponse)
    response_none.response_value = None
    response_none.response_metadata = {}

    response_query = MagicMock()
    response_query.filter.return_value.all.return_value = [
        response_false,
        response_zero,
        response_none,
    ]

    session_query = MagicMock()
    session_query.filter.return_value.first.return_value = SimpleNamespace(
        id=session_id,
        status="in_progress",
        started_at=now_sao_paulo(),
        completed_at=None,
    )

    db.query.side_effect = [response_query, session_query]

    stats = calculator.calculate_session_statistics(session_id)
    assert stats["answered_questions"] == 2


def test_question_renderer_questions_remaining_is_not_off_by_one():
    renderer = QuestionRenderer()
    template = SimpleNamespace(
        name="Template",
        version="1.0",
        questions=[
            {"id": "q1", "type": "open_text", "text": "Q1"},
            {"id": "q2", "type": "open_text", "text": "Q2"},
            {"id": "q3", "type": "open_text", "text": "Q3"},
        ],
    )

    first_context = renderer.build_question_context(template, current_question_index=0)
    last_context = renderer.build_question_context(template, current_question_index=2)

    assert first_context["questions_remaining"] == 2
    assert last_context["questions_remaining"] == 0


def test_report_generator_uses_delivery_method_key_in_attempts():
    db = MagicMock()
    report_generator = ReportGenerator(db)
    session = SimpleNamespace(
        session_metadata={
            "delivery_attempts": [
                {"status": "sent", "delivery_method": "email"},
                {"status": "failed", "method": "sms"},
            ],
            "delivery_method": "whatsapp",
        }
    )

    db.query.return_value.filter.return_value.all.return_value = [session]

    report = report_generator.generate_delivery_report()
    assert report["by_method"]["email"]["successful"] == 1
    assert report["by_method"]["sms"]["failed"] == 1


@pytest.mark.asyncio
async def test_history_query_raises_not_found_for_missing_patient():
    db = MagicMock()
    status_query = MagicMock()
    status_query._check_patient_exists_fast.return_value = False
    history_query = HistoryQuery(db, status_query)

    with pytest.raises(NotFoundError, match="not found"):
        await history_query.get_patient_history(uuid4())


@pytest.mark.asyncio
async def test_history_query_returns_empty_list_when_patient_has_no_sessions():
    db = MagicMock()
    status_query = MagicMock()
    status_query._check_patient_exists_fast.return_value = True
    history_query = HistoryQuery(db, status_query)

    (
        db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value
    ) = []

    result = await history_query.get_patient_history(uuid4())
    assert result == []


def test_template_service_accepts_types_supported_by_answer_validator():
    service = QuizTemplateService(db=MagicMock())

    assert (
        service._validate_question(
            {"id": "q_numeric", "type": "numeric", "text": "N"}, index=0
        )
        is True
    )
    assert (
        service._validate_question(
            {"id": "q_number", "type": "number", "text": "N2"}, index=1
        )
        is True
    )
    assert (
        service._validate_question(
            {"id": "q_date", "type": "date", "text": "D"}, index=2
        )
        is True
    )
    assert (
        service._validate_question(
            {"id": "q_bool", "type": "boolean", "text": "B"}, index=3
        )
        is True
    )


@pytest.mark.asyncio
async def test_response_handler_multiple_choice_without_value_uses_safe_fallback():
    service = object.__new__(ConversationalQuizService)

    question = {
        "id": "q1",
        "type": "multiple_choice",
        "text": "Como está hoje?",
        "options": [{"label": "Muito bem"}],
    }

    result = await service._process_question_response(question, "muito bem", uuid4())
    assert result["valid"] is True
    assert result["value"] == "Muito bem"


@pytest.mark.asyncio
async def test_response_handler_ai_interpretation_avoids_key_error_without_value():
    service = object.__new__(ConversationalQuizService)
    fake_client = SimpleNamespace(generate_content=AsyncMock(return_value="Excelente"))

    with patch(
        "app.domain.quizzes.integration.flow_integration.response_handler.get_gemini_client",
        return_value=fake_client,
    ):
        result = await service._interpret_multiple_choice_response(
            response_text="estou ótima",
            options=[{"label": "Excelente"}, {"value": "regular", "label": "Regular"}],
        )

    assert result == "Excelente"


@pytest.mark.asyncio
async def test_token_rotation_prefers_session_bound_to_token_session_id():
    patient_id = uuid4()
    template_id = uuid4()
    selected_session = SimpleNamespace(id=uuid4(), session_metadata={"token_hash": "x"})

    service = SimpleNamespace()
    service._verify_token = MagicMock(
        return_value={
            "patient_id": str(patient_id),
            "quiz_template_id": str(template_id),
            "session_id": str(selected_session.id),
        }
    )
    service.db = MagicMock()
    service.db.query.return_value.filter.return_value.first.return_value = (
        selected_session
    )
    service._validate_token_with_grace_period = MagicMock(
        return_value=(False, "token_mismatch")
    )

    submit_data = SimpleNamespace(token="token-x")

    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await submit_quiz_response_with_rotation(service, submit_data)

    service._validate_token_with_grace_period.assert_called_once_with(
        "token-x", selected_session
    )


@pytest.mark.asyncio
async def test_token_rotation_raises_not_found_when_no_session_matches_token():
    patient_id = uuid4()
    template_id = uuid4()

    service = SimpleNamespace()
    service._verify_token = MagicMock(
        return_value={
            "patient_id": str(patient_id),
            "quiz_template_id": str(template_id),
        }
    )
    service.db = MagicMock()
    service.db.query.return_value.filter.return_value.first.return_value = None

    submit_data = SimpleNamespace(token="token-x")

    with pytest.raises(NotFoundError, match="for this token"):
        await submit_quiz_response_with_rotation(service, submit_data)


@pytest.mark.asyncio
async def test_manager_rotate_token_stores_previous_token_invalidated_at():
    manager = object.__new__(QuizSessionManager)
    manager.db = MagicMock()
    manager.token_manager = MagicMock()
    manager.token_manager.generate_token.return_value = "new-token"
    manager.token_manager.hash_token.return_value = "new-hash"

    expires_at = now_sao_paulo() + timedelta(hours=2)
    session = SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        quiz_template_id=uuid4(),
        session_metadata={
            "expires_at": expires_at.isoformat(),
            "token_hash": "old-hash",
        },
    )

    new_token = await manager.rotate_token(session, template=SimpleNamespace())

    assert new_token == "new-token"
    assert session.session_metadata["previous_token_hash"] == "old-hash"
    assert "previous_token_invalidated_at" in session.session_metadata
    assert session.session_metadata["token_hash"] == "new-hash"
    manager.db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_link_resilience_async_bridge_works_inside_running_event_loop():
    service = object.__new__(QuizLinkResilienceService)

    async def coro() -> dict[str, bool]:
        return {"ok": True}

    result = service._run_async_safely(coro)
    assert result == {"ok": True}
