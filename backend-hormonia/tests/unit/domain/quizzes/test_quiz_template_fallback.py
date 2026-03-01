from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.domain.quizzes.integration.flow_integration.trigger_service import QuizTriggerService
from app.services.monthly_quiz_message_integration import MonthlyQuizMessageIntegration


@pytest.mark.asyncio
async def test_trigger_patient_quiz_missing_template_returns_continue_result():
    service = object.__new__(QuizTriggerService)
    service.db = MagicMock()
    service._get_or_create_monthly_template = AsyncMock(return_value=None)

    fallback_sender = MagicMock()
    fallback_sender.send_template_missing_message = AsyncMock(
        return_value={
            "delivery_attempted": True,
            "message_sent": True,
            "error": None,
            "message_id": str(uuid4()),
        }
    )

    flow_state = SimpleNamespace(
        patient_id=uuid4(), flow_type="quiz_mensal", state_data={}
    )
    quiz_info = {"monthly_cycle": 3}

    with patch(
        "app.domain.quizzes.integration.flow_integration.trigger_service.MonthlyQuizMessageIntegration",
        return_value=fallback_sender,
    ):
        result = await service._trigger_patient_quiz(flow_state, quiz_info)

    assert result["success"] is True
    assert result["fallback_applied"] is True
    assert result["continue_flow"] is True
    assert result["delivery_attempted"] is True
    assert result["message_sent"] is True
    assert result["link_url"] is None


@pytest.mark.asyncio
async def test_trigger_patient_quiz_missing_template_updates_flow_state():
    service = object.__new__(QuizTriggerService)
    service.db = MagicMock()
    service._get_or_create_monthly_template = AsyncMock(return_value=None)

    fallback_sender = MagicMock()
    fallback_sender.send_template_missing_message = AsyncMock(
        return_value={
            "delivery_attempted": True,
            "message_sent": False,
            "error": "fallback_delivery_failed",
        }
    )

    flow_state = SimpleNamespace(
        patient_id=uuid4(), flow_type="quiz_mensal", state_data={}
    )

    with patch(
        "app.domain.quizzes.integration.flow_integration.trigger_service.MonthlyQuizMessageIntegration",
        return_value=fallback_sender,
    ):
        await service._trigger_patient_quiz(flow_state, {"monthly_cycle": 2})

    assert flow_state.state_data["quiz_template_missing_fallback"] is True
    assert flow_state.state_data["quiz_state"] == "skipped_no_template"
    assert flow_state.state_data["quiz_fallback_reason"] == "template_not_found"
    assert flow_state.state_data["quiz_fallback_delivery_attempted"] is True
    assert flow_state.state_data["quiz_fallback_message_sent"] is False
    assert flow_state.state_data["quiz_link_available"] is False
    assert "quiz_fallback_at" in flow_state.state_data
    service.db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_patient_quiz_missing_template_logs_warning(caplog: pytest.LogCaptureFixture):
    service = object.__new__(QuizTriggerService)
    service.db = MagicMock()
    service._get_or_create_monthly_template = AsyncMock(return_value=None)

    fallback_sender = MagicMock()
    fallback_sender.send_template_missing_message = AsyncMock(
        return_value={
            "delivery_attempted": True,
            "message_sent": True,
            "error": None,
        }
    )

    patient_id = uuid4()
    flow_state = SimpleNamespace(
        patient_id=patient_id, flow_type="quiz_mensal", state_data={}
    )

    with patch(
        "app.domain.quizzes.integration.flow_integration.trigger_service.MonthlyQuizMessageIntegration",
        return_value=fallback_sender,
    ):
        with caplog.at_level("WARNING"):
            await service._trigger_patient_quiz(flow_state, {"monthly_cycle": 4})

    assert "Quiz template not found" in caplog.text
    assert str(patient_id) in caplog.text


@pytest.mark.asyncio
async def test_send_quiz_link_missing_template_returns_gracefully():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=uuid4(), name="Paciente"
    )
    service = MonthlyQuizMessageIntegration(db)

    with patch(
        "app.services.monthly_quiz_message_integration.QuizTemplateRepository"
    ) as repo_cls:
        repo_cls.return_value.get.return_value = None
        service.send_template_missing_message = AsyncMock(
            return_value={
                "delivery_attempted": True,
                "message_sent": True,
                "error": None,
                "message_id": "msg-1",
            }
        )
        result = await service.send_quiz_link(
            patient_id=uuid4(),
            quiz_template_id=uuid4(),
            send_immediately=False,
        )

    assert result["fallback_reason"] == "template_not_found"
    assert result["fallback_applied"] is True
    assert result["continue_flow"] is True
    assert result["message_sent"] is True
    assert result["delivery_attempted"] is True
    assert result["quiz_link_available"] is False
    assert result["link_url"] is None


@pytest.mark.asyncio
async def test_trigger_patient_quiz_missing_template_attempts_no_link_delivery():
    service = object.__new__(QuizTriggerService)
    service.db = MagicMock()
    service._get_or_create_monthly_template = AsyncMock(return_value=None)

    fallback_sender = MagicMock()
    fallback_sender.send_template_missing_message = AsyncMock(
        return_value={
            "delivery_attempted": True,
            "message_sent": True,
            "error": None,
        }
    )

    flow_state = SimpleNamespace(
        patient_id=uuid4(), flow_type="quiz_mensal", state_data={}
    )

    with patch(
        "app.domain.quizzes.integration.flow_integration.trigger_service.MonthlyQuizMessageIntegration",
        return_value=fallback_sender,
    ):
        await service._trigger_patient_quiz(
            flow_state,
            {"monthly_cycle": 2, "trigger_reason": "monthly_trigger"},
        )

    fallback_sender.send_template_missing_message.assert_awaited_once()
    kwargs = fallback_sender.send_template_missing_message.await_args.kwargs
    assert kwargs["patient_id"] == flow_state.patient_id
    assert kwargs["fallback_reason"] == "template_not_found"
    assert kwargs["flow_context"]["flow_type"] == "quiz_mensal"
    assert kwargs["flow_context"]["monthly_cycle"] == 2


@pytest.mark.asyncio
async def test_trigger_patient_quiz_with_valid_template_unchanged():
    service = object.__new__(QuizTriggerService)
    service.db = MagicMock()

    template = SimpleNamespace(id=uuid4())
    service._get_or_create_monthly_template = AsyncMock(return_value=template)
    service._trigger_quiz_via_link = AsyncMock(return_value={"success": True})
    service._trigger_quiz_via_whatsapp = AsyncMock(return_value={"success": True})

    flow_state = SimpleNamespace(
        patient_id=uuid4(), flow_type="quiz_mensal", state_data={}
    )

    with patch(
        "app.domain.quizzes.integration.flow_integration.trigger_service.should_use_link_based_quiz",
        return_value=True,
    ):
        result = await service._trigger_patient_quiz(flow_state, {"monthly_cycle": 1})

    assert result["success"] is True
    service._trigger_quiz_via_link.assert_awaited_once()
    service._trigger_quiz_via_whatsapp.assert_not_awaited()
