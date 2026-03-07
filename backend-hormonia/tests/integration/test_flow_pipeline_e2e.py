"""Phase 53 pipeline integration coverage for webhook ingress and flow continuation."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request
from sqlalchemy.orm import Session

from app.integrations.wuzapi.webhook import wuzapi_webhook
import app.integrations.wuzapi.webhook as wuzapi_webhook_module
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
from app.models.message import Message
from app.models.patient import Patient
from app.services.flow._flow_response_flow import load_response_context
from app.services.flow.config_validation import DayConfigValidationError, validate_day_config
from app.services.flow.sequential_message_handler import SequentialMessageHandler
from app.utils.structured_logger import correlation_id as correlation_id_var
from tests.conftest import SyncToAsyncSessionAdapter


os.environ.setdefault("WHATSAPP_WUZAPI_TOKEN", "test-token")


class DictRedis:
    """Minimal async Redis fake for webhook idempotency checks."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(
        self,
        key: str,
        value: str,
        nx: bool | None = None,
        ex: int | None = None,
    ) -> bool:
        _ = ex
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True


def _message_payload(*, event_id: str, text: str = "resposta do paciente") -> dict[str, Any]:
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


async def _request_from_payload(
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> Request:
    body = json.dumps(payload).encode("utf-8")
    raw_headers = [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v2/webhooks/wuzapi",
        "raw_path": b"/api/v2/webhooks/wuzapi",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("testclient", 123),
        "server": ("testserver", 80),
    }

    received = False

    async def _receive() -> dict[str, Any]:
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive=_receive)


def _create_patient(db_session: Session, *, suffix: str) -> Patient:
    patient = Patient(name=f"Pipeline Test {suffix}")
    patient.phone = f"+55119{suffix[-8:]}"
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_template_version(
    db_session: Session,
    *,
    flow_kind: str = "onboarding",
    steps: list[dict[str, Any]] | None = None,
) -> FlowTemplateVersion:
    kind = db_session.query(FlowKind).filter(FlowKind.kind_key == flow_kind).first()
    if kind is None:
        kind = FlowKind(
            kind_key=flow_kind,
            display_name=flow_kind.title(),
            is_active=True,
        )
        db_session.add(kind)
        db_session.commit()
        db_session.refresh(kind)

    latest_template = (
        db_session.query(FlowTemplateVersion)
        .filter(FlowTemplateVersion.flow_kind_id == kind.id)
        .order_by(FlowTemplateVersion.version_number.desc())
        .first()
    )
    next_version = int(getattr(latest_template, "version_number", 0) or 0) + 1

    template = FlowTemplateVersion(
        flow_kind_id=kind.id,
        version_number=next_version,
        template_name=f"{flow_kind.title()} v{next_version}",
        is_active=True,
        is_draft=False,
        steps=steps or [],
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


def _create_flow_state(
    db_session: Session,
    *,
    patient: Patient,
    step_data: dict[str, Any],
    flow_kind: str = "onboarding",
    status: str = "active",
) -> PatientFlowState:
    template = _create_template_version(
        db_session,
        flow_kind=flow_kind,
        steps=[{"content": "placeholder"}],
    )
    flow_state = PatientFlowState(
        patient_id=patient.id,
        flow_template_version_id=template.id,
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
    day_config: dict[str, Any],
    flow_state: PatientFlowState | None = None,
) -> tuple[SequentialMessageHandler, AsyncMock]:
    async_db = SyncToAsyncSessionAdapter(db_session)
    handler = SequentialMessageHandler(async_db, use_ai_personalization=False)
    send_mock = AsyncMock(return_value=True)
    handler.whatsapp_service.send_message = send_mock
    handler._get_day_config = AsyncMock(return_value=day_config)
    handler._inject_quiz_link_if_needed = AsyncMock(side_effect=lambda content, patient: content)
    handler._personalize_message_ai = AsyncMock(
        side_effect=lambda msg, patient, day_number, flow_kind, day_config, message_index=0: msg["content"]
    )
    handler._await_inter_message_delay = AsyncMock(return_value=None)
    if flow_state is not None:
        handler._get_or_create_flow_state = AsyncMock(return_value=flow_state)
    return handler, send_mock


def _response_context(
    *,
    prompt_message_id: str,
    response_message_id: str,
    flow_day: int = 1,
    flow_kind: str = "onboarding",
    message_index: int = 0,
) -> dict[str, Any]:
    return {
        "flow_day": flow_day,
        "flow_kind": flow_kind,
        "message_index": message_index,
        "awaiting_response": True,
        "prompt_message_id": prompt_message_id,
        "response_message_id": response_message_id,
    }


@pytest.mark.pipeline_e2e
@pytest.mark.integration
class TestFlowPipelineE2E:
    @pytest.mark.asyncio
    async def test_wuzapi_webhook_respects_header_correlation_id(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        request = await _request_from_payload(
            _message_payload(event_id="pipeline-webhook-1"),
            headers={"X-Correlation-ID": "cid-phase53"},
        )

        monkeypatch.setattr(
            wuzapi_webhook_module.settings,
            "WHATSAPP_WUZAPI_WEBHOOK_SECRET",
            "",
            raising=False,
        )

        with patch.object(
            wuzapi_webhook_module,
            "get_async_redis_client",
            new=AsyncMock(return_value=DictRedis()),
        ):
            result = await wuzapi_webhook(request, db=SyncToAsyncSessionAdapter(db_session))

        assert result["status"] == "processed"
        assert result["message_id"] == "pipeline-webhook-1"
        assert result["correlation_id"] == "cid-phase53"

    @pytest.mark.asyncio
    async def test_wuzapi_webhook_generates_correlation_id_when_header_missing(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        request = await _request_from_payload(_message_payload(event_id="pipeline-webhook-2"))
        generated_uuid = uuid.uuid4()

        monkeypatch.setattr(
            wuzapi_webhook_module.settings,
            "WHATSAPP_WUZAPI_WEBHOOK_SECRET",
            "",
            raising=False,
        )

        with patch.object(
            wuzapi_webhook_module,
            "get_async_redis_client",
            new=AsyncMock(return_value=DictRedis()),
        ), patch.object(wuzapi_webhook_module, "uuid4", return_value=generated_uuid):
            result = await wuzapi_webhook(request, db=SyncToAsyncSessionAdapter(db_session))

        assert result["status"] == "processed"
        assert result["correlation_id"] == str(generated_uuid)

    @pytest.mark.asyncio
    async def test_handle_response_and_continue_sends_next_wait_each_message(
        self,
        db_session: Session,
    ) -> None:
        patient = _create_patient(db_session, suffix=uuid.uuid4().hex[:12])
        prompt_message_id = str(uuid.uuid4())
        response_message_id = str(uuid.uuid4())
        flow_state = _create_flow_state(
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
                    "prompt_message_id": prompt_message_id,
                },
            },
        )
        handler, send_mock = _build_async_handler(
            db_session,
            day_config={
                "send_mode": "wait_each",
                "messages": [
                    {"content": "Como voce se sentiu hoje?", "expects_response": True},
                    {"content": "Qual e sua dor agora?", "expects_response": True},
                ],
            },
        )

        result = await handler.handle_response_and_continue(
            patient_id=patient.id,
            response_context=_response_context(
                prompt_message_id=prompt_message_id,
                response_message_id=response_message_id,
            ),
        )

        db_session.refresh(flow_state)
        outbound_messages = (
            db_session.query(Message)
            .filter(Message.patient_id == patient.id)
            .order_by(Message.created_at.asc())
            .all()
        )

        assert result["status"] == "waiting"
        assert result["message_index"] == 1
        assert result["awaiting_response"] is True
        assert send_mock.await_count == 1
        assert len(outbound_messages) == 1
        assert outbound_messages[0].content == "Qual e sua dor agora?"
        assert outbound_messages[0].message_metadata["message_index"] == 1
        assert flow_state.step_data["current_day_message_index"] == 1
        assert flow_state.step_data["awaiting_response"] is True
        assert flow_state.step_data["pending_response_context"]["message_index"] == 1

    @pytest.mark.asyncio
    async def test_load_response_context_resets_waiting_after_retry_limit(
        self,
        db_session: Session,
    ) -> None:
        patient = _create_patient(db_session, suffix=uuid.uuid4().hex[:12])
        expected_prompt_message_id = str(uuid.uuid4())
        flow_state = _create_flow_state(
            db_session,
            patient=patient,
            step_data={
                "current_flow_day": 2,
                "flow_kind": "onboarding",
                "current_day_message_index": 0,
                "awaiting_response": True,
                "context_mismatch_count": 2,
                "pending_response_context": {
                    "flow_day": 2,
                    "flow_kind": "onboarding",
                    "message_index": 0,
                    "prompt_message_id": expected_prompt_message_id,
                },
            },
        )
        handler, _ = _build_async_handler(
            db_session,
            day_config={
                "send_mode": "wait_each",
                "messages": [
                    {"content": "Pergunta 1", "expects_response": True},
                    {"content": "Pergunta 2", "expects_response": True},
                ],
            },
        )

        result = await load_response_context(
            {
                "patient_id": patient.id,
                "response_context": _response_context(
                    prompt_message_id=str(uuid.uuid4()),
                    response_message_id=str(uuid.uuid4()),
                    flow_day=2,
                    message_index=0,
                ),
            },
            config={
                "configurable": {
                    "thread_id": f"flow_response:{patient.id}",
                    "handler": handler,
                }
            },
        )

        db_session.refresh(flow_state)

        assert result["result"]["status"] == "context_mismatch_reset"
        assert result["result"]["reset_after"] == 3
        assert flow_state.step_data["awaiting_response"] is False
        assert flow_state.step_data["context_mismatch_count"] == 0
        assert "pending_response_context" not in flow_state.step_data
        assert flow_state.step_data["last_mismatch_reset_at"]

    @pytest.mark.asyncio
    async def test_send_day_messages_returns_structured_validation_errors(
        self,
        db_session: Session,
    ) -> None:
        patient = _create_patient(db_session, suffix=uuid.uuid4().hex[:12])
        flow_state = _create_flow_state(
            db_session,
            patient=patient,
            step_data={
                "current_flow_day": 1,
                "flow_kind": "onboarding",
                "current_day_message_index": 0,
                "awaiting_response": False,
            },
        )
        invalid_day_config = {
            "send_mode": "single",
            "messages": [{"content": "   "}],
        }
        handler, _ = _build_async_handler(
            db_session,
            day_config=invalid_day_config,
            flow_state=flow_state,
        )

        with pytest.raises(DayConfigValidationError) as exc_info:
            validate_day_config(invalid_day_config, flow_kind="onboarding", day_number=1)

        assert "messages[0].content is empty" in exc_info.value.errors

        result = await handler.send_day_messages(
            patient_id=patient.id,
            day_number=1,
            flow_kind="onboarding",
        )

        assert result["status"] == "error"
        assert "validation_errors" in result
        assert "messages[0].content is empty" in result["validation_errors"]

    @pytest.mark.asyncio
    async def test_load_response_context_logs_correlation_id_on_success(
        self,
        db_session: Session,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        patient = _create_patient(db_session, suffix=uuid.uuid4().hex[:12])
        prompt_message_id = str(uuid.uuid4())
        _create_flow_state(
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
                    "prompt_message_id": prompt_message_id,
                },
            },
        )
        handler, _ = _build_async_handler(
            db_session,
            day_config={
                "send_mode": "wait_each",
                "messages": [
                    {"content": "Pergunta 1", "expects_response": True},
                    {"content": "Pergunta 2", "expects_response": True},
                ],
            },
        )

        caplog.set_level("INFO", logger="app.services.flow._flow_response_flow")
        correlation_id_var.set("cid-flow-log")

        result = await load_response_context(
            {
                "patient_id": patient.id,
                "response_context": _response_context(
                    prompt_message_id=prompt_message_id,
                    response_message_id=str(uuid.uuid4()),
                    flow_day=2,
                    message_index=0,
                ),
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
            getattr(record, "correlation_id", None) == "cid-flow-log"
            and "Loaded response context for continuation" in record.getMessage()
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_send_day_messages_marks_day_complete_and_verified_for_non_response_day(
        self,
        db_session: Session,
    ) -> None:
        patient = _create_patient(db_session, suffix=uuid.uuid4().hex[:12])
        flow_state = _create_flow_state(
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
                    {"content": "Mensagem informativa 1", "expects_response": False},
                    {"content": "Mensagem informativa 2", "expects_response": False},
                ],
            },
            flow_state=flow_state,
        )

        result = await handler.send_day_messages(
            patient_id=patient.id,
            day_number=1,
            flow_kind="onboarding",
        )

        db_session.refresh(flow_state)

        assert result["status"] == "complete"
        assert result["sent_count"] == 2
        assert send_mock.await_count == 2
        assert flow_state.step_data["day_complete"] is True
        assert flow_state.step_data["day_advance_verified"] is True
        assert flow_state.step_data["current_day_message_index"] == 1
        assert flow_state.step_data["awaiting_response"] is False
