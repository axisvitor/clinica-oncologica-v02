from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.exceptions import ExternalServiceError
from app.models.message import MessageStatus, MessageType
from app.services.dispatcher import FlowDispatcher
from app.services.unified_whatsapp_service import UnifiedWhatsAppService


class _AsyncLikeSession:
    def __init__(self):
        self.execute_calls = []
        self.commit_calls = 0

    async def execute(self, statement):
        self.execute_calls.append(statement)

    async def commit(self):
        self.commit_calls += 1


def _message_stub():
    return SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        direction=SimpleNamespace(value="outbound"),
        type=MessageType.TEXT,
        content="hello",
        status=MessageStatus.PENDING,
        whatsapp_id=None,
        message_metadata={},
    )


@pytest.mark.asyncio
async def test_unified_whatsapp_mark_failed_uses_async_session_paths(monkeypatch):
    db = _AsyncLikeSession()
    service = UnifiedWhatsAppService(db=db, redis_url="redis://localhost:6379/0")
    monkeypatch.setattr("app.services.websocket_events.websocket_events", None)
    message = _message_stub()

    await service._mark_message_failed(message, {"reason": "gateway timeout"})

    assert len(db.execute_calls) == 1
    assert db.commit_calls == 1


@pytest.mark.asyncio
async def test_unified_whatsapp_direct_send_failure_commits_async_error_status(monkeypatch):
    db = _AsyncLikeSession()
    service = UnifiedWhatsAppService(db=db, redis_url="redis://localhost:6379/0")
    message = _message_stub()

    service._ensure_patient_loaded = AsyncMock(
        return_value=SimpleNamespace(phone_decrypted="+5511987654321")
    )
    service._get_queue_client = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(ExternalServiceError):
        await service._send_via_direct_api(message)

    assert db.commit_calls == 1
    assert message.status == MessageStatus.FAILED
    assert message.message_metadata["error"] == "boom"


@pytest.mark.asyncio
async def test_flow_dispatcher_initialize_flow_preserves_contract_with_async_session(monkeypatch):
    captured = {}

    class _FakePatientFlowService:
        def __init__(self, db):
            captured["db"] = db

        async def initialize_default_flow(self, patient, current_user_id=None, auto_commit=True):
            captured["patient"] = patient
            captured["current_user_id"] = current_user_id
            captured["auto_commit"] = auto_commit
            return "ok"

    fake_db = object()
    patient = SimpleNamespace(id=uuid4())
    user_id = uuid4()
    dispatcher = FlowDispatcher(fake_db)

    monkeypatch.setattr(
        "app.services.patient.flow_service.PatientFlowService", _FakePatientFlowService
    )
    dispatcher._get_feature_flags = lambda: SimpleNamespace(log_dispatcher_routing=False)

    result = await dispatcher.initialize_flow(
        patient=patient,
        current_user_id=user_id,
        auto_commit=False,
    )

    assert result == "ok"
    assert captured["db"] is fake_db
    assert captured["patient"] is patient
    assert captured["current_user_id"] == user_id
    assert captured["auto_commit"] is False


def test_flow_dispatcher_is_new_patient_sync_compatible(monkeypatch):
    captured = {}

    class _FakeRepo:
        def __init__(self, db):
            captured["db"] = db

        def get_active_flow(self, patient_id):
            captured["patient_id"] = patient_id
            return None

    fake_db = object()
    patient_id = uuid4()
    dispatcher = FlowDispatcher(fake_db)

    monkeypatch.setattr("app.repositories.flow.FlowStateRepository", _FakeRepo)
    dispatcher._get_feature_flags = lambda: SimpleNamespace(log_dispatcher_routing=False)

    assert dispatcher.is_new_patient(patient_id) is True
    assert captured["db"] is fake_db
    assert captured["patient_id"] == patient_id
