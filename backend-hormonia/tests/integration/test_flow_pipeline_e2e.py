"""Phase 53 pipeline integration coverage for webhook, gate, continuation, and send."""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

import app.integrations.wuzapi.webhook as wuzapi_webhook
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.services.flow._flow_response_flow import load_response_context
from app.services.flow.config_validation import (
    DayConfigValidationError,
    validate_day_config,
)
from app.services.flow.management.advancement import advance_day_atomic
from app.services.flow.sequential_message_handler import SequentialMessageHandler
from app.services.flow.sequential_response_gate import (
    MAX_CONTEXT_MISMATCH_RETRIES,
    evaluate_sequential_gate,
    reset_awaiting_on_mismatch_limit,
)
from app.services.webhook.handlers.message_handler import MessageWebhookHandler
from app.utils.structured_logger import correlation_id as correlation_id_var
from tests.conftest import SyncToAsyncSessionAdapter


os.environ.setdefault("WHATSAPP_WUZAPI_TOKEN", "test-token")


class DictRedis:
    """Minimal dict-backed async Redis fake for webhook idempotency tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool | None = None, ex: int | None = None):
        _ = ex
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True

    async def get(self, key: str):
        return self._store.get(key)


def _message_payload(*, event_id: str, text: str = "resposta do paciente") -> dict:
    return {
        "type": "Message",
        "event": {
            "Info": {
                "ID": event_id,
                "Sender": "5511999999999@s.whatsapp.net",
            },
            "Message": {
                "Conversation": text,
            },
        },
    }


def _make_patient(db_session: Session, *, suffix: str) -> Patient:
    patient = Patient(name=f"Pipeline Test {suffix}")
    patient.phone = f"+55119{suffix[-8:]}"
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _make_flow_state(
    db_session: Session,
    *,
    patient: Patient,
    step_data: dict,
    status: str = "active",
) -> PatientFlowState:
    flow_state = PatientFlowState(
        patient_id=patient.id,
        flow_template_version_id=patient.id,
        current_step=int(step_data.get("current_flow_day", 1) or 1),
        status=status,
        step_data=dict(step_data),
    )
    db_session.add(flow_state)
    db_session.commit()
    db_session.refresh(flow_state)
    return flow_state


def _build_async_handler(
    db_session: Session,
    *,
    day_config: dict,
) -> tuple[SequentialMessageHandler, AsyncMock]:
    async_db = SyncToAsyncSessionAdapter(db_session)
    handler = SequentialMessageHandler(async_db, use_ai_personalization=False)
    send_mock = AsyncMock(return_value=True)
    handler.whatsapp_service = SimpleNamespace(send_message=send_mock)
    handler._get_day_config = AsyncMock(return_value=day_config)
    handler._inject_quiz_link_if_needed = AsyncMock(side_effect=lambda content, patient: content)
    handler._personalize_message_ai = AsyncMock(
        side_effect=lambda msg, patient, day_number, flow_kind, day_config, message_index=0: msg["content"]
    )
    return handler, send_mock


def _build_webhook_handler(db_session: Session) -> MessageWebhookHandler:
    with patch(
        "app.services.webhook.handlers.message_handler.get_langchain_orchestrator",
        return_value=MagicMock(),
    ), patch("app.services.enhanced_flow_engine.EnhancedFlowEngine", return_value=MagicMock()):
        return MessageWebhookHandler(db_session)


@pytest.mark.pipeline_e2e
@pytest.mark.integration
class TestFlowPipelineE2E:
    @pytest.mark.asyncio
    async def test_webhook_response_passes_gate_and_sends_next_question(
        self,
        client,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_redis = DictRedis()
        suffix = uuid.uuid4().hex[:12]
        patient = _make_patient(db_session, suffix=suffix)
        flow_state = _make_flow_state(
            db_session,
            patient=patient,
            step_data={
                "current_flow_day": 1,
                "flow_kind": "onboarding",
                "current_day_message_index": 0,
                "awaiting_response": True,
                "pending_response_context": {
                    "flow_day": 1,
                    "flow_kind": "onboarding",
                    "message_index": 0,
                    "prompt_message_id": "prompt-001",
                },
            },
        )
        _, send_mock = _build_async_handler(
            db_session,
            day_config={
                "send_mode": "wait_each",
                "messages": [
                    {"content": "Como voce se sentiu hoje?", "expects_response": True},
                    {"content": "Qual e sua dor agora?", "expects_response": True},
                ],
            },
        )

        monkeypatch.setattr(
            wuzapi_webhook.settings,
            "WHATSAPP_WUZAPI_WEBHOOK_SECRET",
            "",
            raising=False,
        )

        with patch(
            "app.integrations.wuzapi.webhook.get_async_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            response = client.post(
                "/api/v2/webhooks/wuzapi",
                json=_message_payload(event_id="pipeline-happy-1"),
                headers={"X-Correlation-ID": "cid-happy-path"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        assert send_mock.await_count == 1
        db_session.refresh(flow_state)
        assert flow_state.step_data["current_day_message_index"] == 1

    @pytest.mark.asyncio
    async def test_gate_mismatch_recovery_resets_waiting_state_after_retry_limit(
        self,
    ) -> None:
        step_data = {
            "current_flow_day": 3,
            "flow_kind": "onboarding",
            "current_day_message_index": 1,
            "awaiting_response": True,
            "pending_response_context": {
                "prompt_message_id": "prompt-expected",
            },
        }

        for attempt in range(1, MAX_CONTEXT_MISMATCH_RETRIES + 1):
            allowed, reason, normalized = evaluate_sequential_gate(
                step_data,
                {
                    "flow_day": 3,
                    "flow_kind": "onboarding",
                    "message_index": 1,
                    "awaiting_response": True,
                    "prompt_message_id": f"prompt-wrong-{attempt}",
                    "response_message_id": f"response-{attempt}",
                },
            )

            assert allowed is False
            assert reason == "prompt_message_id_mismatch"
            assert normalized["prompt_message_id"] == f"prompt-wrong-{attempt}"

            did_reset, payload = reset_awaiting_on_mismatch_limit(
                step_data,
                {
                    "prompt_message_id": {
                        "expected": "prompt-expected",
                        "received": normalized["prompt_message_id"],
                    }
                },
                lambda: None,
            )

            if attempt < MAX_CONTEXT_MISMATCH_RETRIES:
                assert did_reset is False
                assert payload["status"] == "waiting"
                assert payload["mismatch_count"] == attempt
                assert step_data["awaiting_response"] is True
            else:
                assert did_reset is True
                assert payload["status"] == "context_mismatch_reset"
                assert payload["reset_after"] == MAX_CONTEXT_MISMATCH_RETRIES
                assert step_data["awaiting_response"] is False
                assert step_data["context_mismatch_count"] == 0
                assert "pending_response_context" not in step_data

    @pytest.mark.asyncio
    async def test_day_config_validation_returns_structured_errors(
        self,
        db_session: Session,
    ) -> None:
        invalid_day_config = {
            "send_mode": "single",
            "messages": [
                {"content": "   "},
            ],
        }

        with pytest.raises(DayConfigValidationError) as exc_info:
            validate_day_config(
                invalid_day_config,
                flow_kind="onboarding",
                day_number=1,
            )

        assert "messages[0].content is empty" in exc_info.value.errors

        patient = _make_patient(db_session, suffix=uuid.uuid4().hex[:12])
        handler, _ = _build_async_handler(
            db_session,
            day_config=invalid_day_config,
        )

        result = await handler.send_day_messages(
            patient_id=patient.id,
            day_number=1,
            flow_kind="onboarding",
        )

        assert result["status"] == "error"
        assert "validation_errors" in result
        assert "messages[0].content is empty" in result["validation_errors"]

    @pytest.mark.asyncio
    async def test_correlation_id_header_and_flow_logs_share_same_trace(
        self,
        client,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        fake_redis = DictRedis()
        header_correlation_id = "cid-pipeline-trace"
        patient = _make_patient(db_session, suffix=uuid.uuid4().hex[:12])
        _make_flow_state(
            db_session,
            patient=patient,
            step_data={
                "current_flow_day": 2,
                "flow_kind": "onboarding",
                "current_day_message_index": 0,
                "awaiting_response": True,
                "pending_response_context": {
                    "flow_day": 2,
                    "flow_kind": "onboarding",
                    "message_index": 0,
                    "prompt_message_id": "prompt-correlation",
                },
            },
        )
        handler, _ = _build_async_handler(
            db_session,
            day_config={
                "send_mode": "wait_each",
                "messages": [
                    {"content": "Mensagem 1", "expects_response": True},
                    {"content": "Mensagem 2", "expects_response": True},
                ],
            },
        )

        monkeypatch.setattr(
            wuzapi_webhook.settings,
            "WHATSAPP_WUZAPI_WEBHOOK_SECRET",
            "",
            raising=False,
        )

        with patch(
            "app.integrations.wuzapi.webhook.get_async_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ):
            response = client.post(
                "/api/v2/webhooks/wuzapi",
                json=_message_payload(event_id="pipeline-correlation-1"),
                headers={"X-Correlation-ID": header_correlation_id},
            )

        assert response.status_code == 200
        assert response.json()["correlation_id"] == header_correlation_id

        caplog.set_level("INFO", logger="app.services.flow._flow_response_flow")
        correlation_id_var.set(header_correlation_id)
        result = await load_response_context(
            {
                "patient_id": patient.id,
                "response_context": {
                    "flow_day": 2,
                    "flow_kind": "onboarding",
                    "message_index": 0,
                    "awaiting_response": True,
                    "prompt_message_id": "prompt-correlation",
                    "response_message_id": "response-correlation-1",
                },
            },
            config={
                "configurable": {
                    "thread_id": f"flow_response:{patient.id}",
                    "handler": handler,
                }
            },
        )

        assert result["current_index"] == 1
        assert any(
            getattr(record, "correlation_id", None) == header_correlation_id
            for record in caplog.records
        )

        generated_uuid = uuid.uuid4()
        correlation_id_var.set("")
        with patch(
            "app.integrations.wuzapi.webhook.get_async_redis_client",
            new=AsyncMock(return_value=DictRedis()),
        ), patch("app.integrations.wuzapi.webhook.uuid4", return_value=generated_uuid):
            generated_response = client.post(
                "/api/v2/webhooks/wuzapi",
                json=_message_payload(event_id="pipeline-correlation-2"),
            )

        assert generated_response.status_code == 200
        assert generated_response.json()["correlation_id"] == str(generated_uuid)

    @pytest.mark.asyncio
    async def test_day_completion_marks_verified_and_advances_day(
        self,
        db_session: Session,
    ) -> None:
        patient = _make_patient(db_session, suffix=uuid.uuid4().hex[:12])
        flow_state = _make_flow_state(
            db_session,
            patient=patient,
            step_data={
                "current_flow_day": 1,
                "flow_kind": "onboarding",
                "current_day_message_index": 0,
                "awaiting_response": False,
            },
        )
        handler, send_mock = _build_async_handler(
            db_session,
            day_config={
                "send_mode": "wait_each",
                "messages": [
                    {"content": "Mensagem sem resposta 1", "expects_response": False},
                    {"content": "Mensagem sem resposta 2", "expects_response": False},
                ],
            },
        )

        with patch(
            "app.services.flow.sequential_message_handler_pkg.sequencing.advance_day_atomic",
            new=AsyncMock(wraps=advance_day_atomic),
        ) as advance_mock:
            result = await handler.send_day_messages(
                patient_id=patient.id,
                day_number=1,
                flow_kind="onboarding",
            )

        assert result["status"] == "complete"
        assert send_mock.await_count == 2
        assert advance_mock.await_count == 1

        db_session.refresh(flow_state)
        assert flow_state.step_data["day_complete"] is True
        assert flow_state.step_data["day_advance_verified"] is True
        assert flow_state.step_data["current_flow_day"] == 2
