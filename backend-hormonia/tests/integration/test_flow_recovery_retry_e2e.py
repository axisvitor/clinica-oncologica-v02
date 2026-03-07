import asyncio
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.orm import Session

from app.exceptions import ExternalServiceError
from app.models.flow import PatientFlowState
from app.models.message import (
    Message,
    MessageDirection,
    MessagePriority,
    MessageStatus,
    MessageType,
)
from app.models.patient import Patient
from app.services.flow import recovery as recovery_service
from app.services.follow_up_system.enums import FollowUpType
from app.tasks.flows import followup_retry as followup_retry_task
from app.tasks.flows import send_retry as send_retry_task
from app.tasks.flows import stuck_detection as stuck_detection_task
from app.tasks.flows.followup_retry import (
    FOLLOWUP_RETRY_MAX,
    retry_failed_followup_send,
)
from app.tasks.flows.send_retry import (
    SEND_RETRY_BACKOFF_FACTOR,
    SEND_RETRY_BASE_DELAY,
    SEND_RETRY_MAX_RETRIES,
    retry_failed_flow_send,
)
from app.tasks.flows.stuck_detection import detect_stuck_flows
from app.utils.timezone import now_sao_paulo

@contextmanager
def _scoped_session(db: Session):
    yield db


def _async_to_sync_bridge(fn):
    def _call(*args, **kwargs):
        result = fn(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result

    return _call


class FakeRedis:
    def __init__(self):
        self._values: dict[str, object] = {}
        self.expirations: dict[str, int | None] = {}

    def get(self, key: str):
        return self._values.get(key)

    def set(self, key: str, value, ex: int | None = None, nx: bool = False):
        if nx and key in self._values:
            return False
        self._values[key] = value
        self.expirations[key] = ex
        return True

    def setex(self, key: str, ttl: int, value):
        self._values[key] = value
        self.expirations[key] = ttl
        return True

    def delete(self, key: str):
        existed = key in self._values
        self._values.pop(key, None)
        self.expirations.pop(key, None)
        return 1 if existed else 0


@pytest.fixture(autouse=True)
def _task_context(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WHATSAPP_WUZAPI_TOKEN", "test-token")

    original_send_retries = retry_failed_flow_send.request.retries
    original_send_max = retry_failed_flow_send.max_retries
    original_followup_retries = retry_failed_followup_send.request.retries
    original_followup_max = retry_failed_followup_send.max_retries

    retry_failed_flow_send.request.retries = 0
    retry_failed_flow_send.max_retries = SEND_RETRY_MAX_RETRIES
    retry_failed_followup_send.request.retries = 0
    retry_failed_followup_send.max_retries = FOLLOWUP_RETRY_MAX

    yield

    retry_failed_flow_send.request.retries = original_send_retries
    retry_failed_flow_send.max_retries = original_send_max
    retry_failed_followup_send.request.retries = original_followup_retries
    retry_failed_followup_send.max_retries = original_followup_max


def _create_patient(db: Session, name: str, phone: str) -> Patient:
    patient = Patient(name=name)
    patient.phone = phone
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _create_flow_state(
    db: Session,
    *,
    patient_id,
    step_data: dict,
    current_step: int = 1,
    last_interaction_at=None,
) -> PatientFlowState:
    flow_state = PatientFlowState(
        patient_id=patient_id,
        flow_template_version_id=patient_id,
        current_step=current_step,
        status="active",
        step_data=step_data,
        last_interaction_at=last_interaction_at,
    )
    db.add(flow_state)
    db.commit()
    db.refresh(flow_state)
    return flow_state


def _create_failed_message(
    db: Session,
    *,
    patient_id,
    content: str = "Flow prompt",
    message_id: UUID | None = None,
    status: MessageStatus = MessageStatus.FAILED,
    message_metadata: dict | None = None,
) -> Message:
    message = Message(
        id=message_id or uuid4(),
        patient_id=patient_id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content=content,
        priority=MessagePriority.NORMAL,
        status=status,
        idempotency_key=uuid4().hex,
        message_metadata=message_metadata or {"source": "flow_sequential"},
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def _patch_send_retry_task(
    *,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    send_side_effect,
):
    service = SimpleNamespace(send_message=AsyncMock(side_effect=send_side_effect))

    monkeypatch.setattr(send_retry_task, "get_scoped_session", lambda: _scoped_session(db_session))
    monkeypatch.setattr(send_retry_task, "UnifiedWhatsAppService", lambda db: service)
    monkeypatch.setattr(send_retry_task, "async_to_sync", _async_to_sync_bridge)
    monkeypatch.setattr(
        send_retry_task.retry_failed_flow_send,
        "delay",
        lambda message_id, flow_context=None: retry_failed_flow_send.run(
            message_id,
            flow_context=flow_context,
        ),
    )

    return service


@pytest.mark.pipeline_e2e
@pytest.mark.integration
class TestStuckFlowRecovery:
    def test_detect_stuck_flows_finds_only_stale_waiting_flows(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        stale_patient = _create_patient(db_session, "Stale Flow", "+5511999000001")
        recent_patient = _create_patient(db_session, "Recent Flow", "+5511999000002")
        stale_message = _create_failed_message(
            db_session,
            patient_id=stale_patient.id,
            message_metadata={"source": "flow_sequential"},
        )

        stale_flow = _create_flow_state(
            db_session,
            patient_id=stale_patient.id,
            current_step=2,
            last_interaction_at=now_sao_paulo() - timedelta(hours=2),
            step_data={
                "awaiting_response": True,
                "flow_kind": "onboarding",
                "current_flow_day": 2,
                "current_day_message_index": 0,
                "pending_response_context": {
                    "prompt_message_id": str(stale_message.id),
                },
            },
        )
        recent_flow = _create_flow_state(
            db_session,
            patient_id=recent_patient.id,
            current_step=2,
            last_interaction_at=now_sao_paulo() - timedelta(minutes=10),
            step_data={
                "awaiting_response": True,
                "flow_kind": "onboarding",
                "current_flow_day": 2,
            },
        )

        async def _send_message(message: Message, flow_context=None):
            message.status = MessageStatus.SENT
            message.message_metadata = dict(message.message_metadata or {})
            message.message_metadata["last_flow_context"] = flow_context
            db_session.add(message)
            db_session.commit()
            return True

        redis_client = FakeRedis()
        send_service = _patch_send_retry_task(
            monkeypatch=monkeypatch,
            db_session=db_session,
            send_side_effect=_send_message,
        )
        monkeypatch.setattr(
            stuck_detection_task,
            "get_scoped_session",
            lambda: _scoped_session(db_session),
        )
        monkeypatch.setattr(
            stuck_detection_task,
            "get_redis_manager",
            lambda: SimpleNamespace(get_sync_client=lambda: redis_client),
        )
        monkeypatch.setattr(
            stuck_detection_task,
            "find_stuck_flows",
            lambda db: recovery_service.find_stuck_flows(db, threshold_hours=1),
        )

        stuck_flows = recovery_service.find_stuck_flows(db_session, threshold_hours=1)

        assert [flow.id for flow in stuck_flows] == [stale_flow.id]
        assert recent_flow.id not in {flow.id for flow in stuck_flows}

        summary = detect_stuck_flows.run()

        db_session.refresh(stale_flow)
        db_session.refresh(stale_message)

        assert summary["detected_count"] == 1
        assert summary["recovered_count"] == 1
        assert summary["skipped_count"] == 0
        assert stale_flow.step_data["recovery_attempts"] == 1
        assert stale_message.status == MessageStatus.SENT
        send_service.send_message.assert_awaited_once()

    def test_attempt_recovery_resends_prompt_and_increments_attempts(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        patient = _create_patient(db_session, "Recovery Resend", "+5511999000003")
        message = _create_failed_message(db_session, patient_id=patient.id)
        flow_state = _create_flow_state(
            db_session,
            patient_id=patient.id,
            current_step=2,
            last_interaction_at=now_sao_paulo() - timedelta(hours=5),
            step_data={
                "awaiting_response": True,
                "flow_kind": "onboarding",
                "current_flow_day": 2,
                "current_day_message_index": 1,
                "pending_response_context": {
                    "prompt_message_id": str(message.id),
                },
            },
        )

        async def _send_message(message_to_send: Message, flow_context=None):
            message_to_send.status = MessageStatus.SENT
            message_to_send.message_metadata = dict(message_to_send.message_metadata or {})
            message_to_send.message_metadata["flow_context"] = flow_context
            db_session.add(message_to_send)
            db_session.commit()
            return True

        send_service = _patch_send_retry_task(
            monkeypatch=monkeypatch,
            db_session=db_session,
            send_side_effect=_send_message,
        )
        result = recovery_service.attempt_recovery(db_session, flow_state, FakeRedis())

        db_session.refresh(flow_state)
        db_session.refresh(message)

        assert result == {
            "status": "recovered",
            "action": "resend_prompt",
            "flow_state_id": str(flow_state.id),
        }
        assert flow_state.step_data["recovery_attempts"] == 1
        assert message.status == MessageStatus.SENT
        assert send_service.send_message.await_args.args[0].id == message.id
        assert (
            send_service.send_message.await_args.kwargs["flow_context"]["prompt_message_id"]
            == str(message.id)
        )

    def test_attempt_recovery_advances_day_when_completion_is_unverified(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        patient = _create_patient(db_session, "Advance Flow", "+5511999000004")
        flow_state = _create_flow_state(
            db_session,
            patient_id=patient.id,
            current_step=3,
            last_interaction_at=now_sao_paulo() - timedelta(hours=5),
            step_data={
                "awaiting_response": True,
                "day_complete": True,
                "day_advance_verified": False,
                "current_flow_day": 3,
            },
        )

        class _Manager:
            async def advance_patient_flow(self, patient_id, force_day):
                latest = db_session.query(PatientFlowState).filter_by(id=flow_state.id).first()
                latest.current_step = force_day
                latest.step_data = dict(latest.step_data or {})
                latest.step_data["current_flow_day"] = force_day
                latest.step_data["day_advance_verified"] = True
                latest.step_data["awaiting_response"] = False
                db_session.add(latest)
                db_session.commit()
                return {"status": "advanced", "force_day": force_day}

        monkeypatch.setattr(recovery_service, "async_to_sync", _async_to_sync_bridge)
        monkeypatch.setattr(recovery_service, "FlowStateRepository", lambda db: SimpleNamespace(db=db))
        monkeypatch.setattr(recovery_service, "FlowManagementService", lambda flow_repo, db: _Manager())

        result = recovery_service.attempt_recovery(db_session, flow_state, FakeRedis())

        db_session.refresh(flow_state)

        assert result == {
            "status": "recovered",
            "action": "advance_day",
            "flow_state_id": str(flow_state.id),
        }
        assert flow_state.current_step == 4
        assert flow_state.step_data["current_flow_day"] == 4
        assert flow_state.step_data["day_advance_verified"] is True
        assert flow_state.step_data["awaiting_response"] is False

    def test_attempt_recovery_returns_already_recovering_when_lock_exists(
        self,
        db_session: Session,
    ):
        patient = _create_patient(db_session, "Locked Flow", "+5511999000005")
        flow_state = _create_flow_state(
            db_session,
            patient_id=patient.id,
            current_step=2,
            last_interaction_at=now_sao_paulo() - timedelta(hours=5),
            step_data={"awaiting_response": True, "recovery_attempts": 1},
        )
        redis_client = FakeRedis()
        redis_client.set(f"recovery:{flow_state.id}", "locked", ex=60)

        result = recovery_service.attempt_recovery(db_session, flow_state, redis_client)

        db_session.refresh(flow_state)

        assert result == {
            "status": "already_recovering",
            "flow_state_id": str(flow_state.id),
        }
        assert flow_state.step_data["recovery_attempts"] == 1

    def test_attempt_recovery_marks_manual_intervention_after_exhaustion(
        self,
        db_session: Session,
    ):
        patient = _create_patient(db_session, "Exhausted Flow", "+5511999000006")
        flow_state = _create_flow_state(
            db_session,
            patient_id=patient.id,
            current_step=2,
            last_interaction_at=now_sao_paulo() - timedelta(hours=5),
            step_data={
                "awaiting_response": True,
                "recovery_attempts": recovery_service.STUCK_FLOW_MAX_RECOVERY_ATTEMPTS,
            },
        )

        result = recovery_service.attempt_recovery(db_session, flow_state, FakeRedis())

        db_session.refresh(flow_state)

        assert result == {
            "status": "max_attempts_exceeded",
            "flow_state_id": str(flow_state.id),
        }
        assert flow_state.step_data["manual_intervention_required"] is True
        assert (
            flow_state.step_data["manual_intervention_reason"]
            == recovery_service.MANUAL_INTERVENTION_REASON
        )
