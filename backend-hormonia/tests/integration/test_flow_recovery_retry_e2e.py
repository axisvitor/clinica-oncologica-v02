"""Phase 53 recovery and retry integration coverage."""

from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.orm import Session

from app.exceptions import ExternalServiceError
from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
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
from app.tasks.flows.followup_retry import FOLLOWUP_RETRY_MAX, retry_failed_followup_send
from app.tasks.flows.send_retry import (
    SEND_RETRY_BACKOFF_FACTOR,
    SEND_RETRY_BASE_DELAY,
    SEND_RETRY_MAX_RETRIES,
    retry_failed_flow_send,
)
from app.tasks.flows.stuck_detection import detect_stuck_flows
from app.utils.timezone import now_sao_paulo


os.environ.setdefault("WHATSAPP_WUZAPI_TOKEN", "test-token")


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


def _create_template_version(
    db: Session,
    *,
    flow_kind: str = "onboarding",
    steps: list[dict] | None = None,
) -> FlowTemplateVersion:
    kind = db.query(FlowKind).filter(FlowKind.kind_key == flow_kind).first()
    if kind is None:
        kind = FlowKind(kind_key=flow_kind, display_name=flow_kind.title(), is_active=True)
        db.add(kind)
        db.commit()
        db.refresh(kind)

    latest_template = (
        db.query(FlowTemplateVersion)
        .filter(FlowTemplateVersion.flow_kind_id == kind.id)
        .order_by(FlowTemplateVersion.version_number.desc())
        .first()
    )
    next_version = int(getattr(latest_template, "version_number", 0) or 0) + 1

    template = FlowTemplateVersion(
        flow_kind_id=kind.id,
        version_number=next_version,
        template_name=f"{flow_kind.title()} recovery {next_version}",
        is_active=True,
        is_draft=False,
        steps=steps or [{"content": "placeholder"}],
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def _create_flow_state(
    db: Session,
    *,
    patient_id,
    step_data: dict,
    current_step: int = 1,
    last_interaction_at=None,
    flow_kind: str = "onboarding",
) -> PatientFlowState:
    template = _create_template_version(db, flow_kind=flow_kind)
    flow_state = PatientFlowState(
        patient_id=patient_id,
        flow_template_version_id=template.id,
        current_step=current_step,
        status="active",
        step_data=dict(step_data),
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
    def test_find_stuck_flows_detects_only_stale_waiting_flows(
        self,
        db_session: Session,
    ):
        stale_patient = _create_patient(db_session, "Stale Flow", "+5511999000001")
        recent_patient = _create_patient(db_session, "Recent Flow", "+5511999000002")

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

        stuck_flows = recovery_service.find_stuck_flows(db_session, threshold_hours=1)

        assert [flow.id for flow in stuck_flows] == [stale_flow.id]
        assert recent_flow.id not in {flow.id for flow in stuck_flows}

    def test_detect_stuck_flows_task_recovers_stale_prompt_via_retry_task(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        patient = _create_patient(db_session, "Recover Task", "+5511999000003")
        message = _create_failed_message(
            db_session,
            patient_id=patient.id,
            message_metadata={"source": "flow_sequential"},
        )
        flow_state = _create_flow_state(
            db_session,
            patient_id=patient.id,
            current_step=2,
            last_interaction_at=now_sao_paulo() - timedelta(hours=2),
            step_data={
                "awaiting_response": True,
                "flow_kind": "onboarding",
                "current_flow_day": 2,
                "current_day_message_index": 0,
                "pending_response_context": {
                    "prompt_message_id": str(message.id),
                },
            },
        )

        async def _send_message(message_to_send: Message, flow_context=None):
            message_to_send.status = MessageStatus.SENT
            message_to_send.message_metadata = dict(message_to_send.message_metadata or {})
            message_to_send.message_metadata["last_flow_context"] = flow_context
            db_session.add(message_to_send)
            db_session.commit()
            return True

        send_service = _patch_send_retry_task(
            monkeypatch=monkeypatch,
            db_session=db_session,
            send_side_effect=_send_message,
        )
        monkeypatch.setattr(stuck_detection_task, "get_scoped_session", lambda: _scoped_session(db_session))
        monkeypatch.setattr(
            stuck_detection_task,
            "get_redis_manager",
            lambda: SimpleNamespace(get_sync_client=lambda: FakeRedis()),
        )
        monkeypatch.setattr(
            stuck_detection_task,
            "find_stuck_flows",
            lambda db: recovery_service.find_stuck_flows(db, threshold_hours=1),
        )

        summary = detect_stuck_flows.run()

        db_session.refresh(flow_state)
        db_session.refresh(message)

        assert summary["detected_count"] == 1
        assert summary["recovered_count"] == 1
        assert summary["failed_count"] == 0
        assert flow_state.step_data["recovery_attempts"] == 1
        assert message.status == MessageStatus.SENT
        send_service.send_message.assert_awaited_once()

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


@pytest.mark.pipeline_e2e
@pytest.mark.integration
class TestSendRetryMechanics:
    def test_retry_failed_flow_send_succeeds_and_updates_message(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        patient = _create_patient(db_session, "Retry Success", "+5511999000007")
        message = _create_failed_message(
            db_session,
            patient_id=patient.id,
            message_metadata={
                "source": "flow_sequential",
                "flow_context": {"flow_kind": "onboarding", "flow_day": 2, "message_index": 1},
            },
        )

        async def _send_message(message_to_send: Message, flow_context=None):
            message_to_send.status = MessageStatus.SENT
            message_to_send.message_metadata = dict(message_to_send.message_metadata or {})
            message_to_send.message_metadata["flow_context"] = flow_context
            db_session.add(message_to_send)
            db_session.commit()
            return True

        service = _patch_send_retry_task(
            monkeypatch=monkeypatch,
            db_session=db_session,
            send_side_effect=_send_message,
        )

        result = retry_failed_flow_send.run(str(message.id))

        db_session.refresh(message)

        assert result == {
            "status": "ok",
            "message_id": str(message.id),
            "attempt": 1,
        }
        assert message.status == MessageStatus.SENT
        assert message.retry_count == 1
        service.send_message.assert_awaited_once()

    def test_retry_failed_flow_send_retries_with_exponential_backoff(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        patient = _create_patient(db_session, "Retry Backoff", "+5511999000008")
        message = _create_failed_message(db_session, patient_id=patient.id)
        retry_failed_flow_send.request.retries = 1

        monkeypatch.setattr(send_retry_task, "get_scoped_session", lambda: _scoped_session(db_session))
        monkeypatch.setattr(
            send_retry_task,
            "UnifiedWhatsAppService",
            lambda db: SimpleNamespace(send_message=AsyncMock(side_effect=ExternalServiceError("provider_error"))),
        )
        monkeypatch.setattr(send_retry_task, "async_to_sync", _async_to_sync_bridge)

        with patch.object(send_retry_task.random, "randint", return_value=7), patch.object(
            send_retry_task.retry_failed_flow_send,
            "retry",
            side_effect=RuntimeError("retry called"),
        ) as retry_mock:
            with pytest.raises(RuntimeError, match="retry called"):
                retry_failed_flow_send.run(str(message.id))

        db_session.refresh(message)

        expected_countdown = (
            SEND_RETRY_BASE_DELAY
            * (SEND_RETRY_BACKOFF_FACTOR ** retry_failed_flow_send.request.retries)
        ) + 7
        assert retry_mock.call_args.kwargs["countdown"] == expected_countdown
        assert isinstance(retry_mock.call_args.kwargs["exc"], ExternalServiceError)
        assert message.retry_count == 2
        assert message.next_retry_at is not None

    def test_retry_failed_flow_send_records_permanent_failure_after_exhaustion(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        patient = _create_patient(db_session, "Retry Exhausted", "+5511999000009")
        flow_state = _create_flow_state(
            db_session,
            patient_id=patient.id,
            current_step=4,
            step_data={"awaiting_response": True},
        )
        message = _create_failed_message(
            db_session,
            patient_id=patient.id,
            message_metadata={"source": "flow_sequential"},
        )
        retry_failed_flow_send.request.retries = SEND_RETRY_MAX_RETRIES

        monkeypatch.setattr(send_retry_task, "get_scoped_session", lambda: _scoped_session(db_session))
        monkeypatch.setattr(
            send_retry_task,
            "UnifiedWhatsAppService",
            lambda db: SimpleNamespace(send_message=AsyncMock(side_effect=ExternalServiceError("provider_error"))),
        )
        monkeypatch.setattr(send_retry_task, "async_to_sync", _async_to_sync_bridge)

        with patch.object(
            send_retry_task.retry_failed_flow_send,
            "retry",
            side_effect=MaxRetriesExceededError("done"),
        ):
            result = retry_failed_flow_send.run(str(message.id), flow_context={"flow_kind": "onboarding"})

        db_session.refresh(message)
        db_session.refresh(flow_state)

        assert result["status"] == "permanently_failed"
        assert result["message_id"] == str(message.id)
        assert result["attempts"] == SEND_RETRY_MAX_RETRIES
        assert message.status == MessageStatus.FAILED
        assert flow_state.step_data["delivery_failures"][0]["message_id"] == str(message.id)
        assert flow_state.step_data["skip_waiting_for_message"] == str(message.id)

    def test_retry_failed_followup_send_succeeds_and_marks_action_executed(
        self,
        db_session: Session,
    ):
        follow_up_service = MagicMock()
        follow_up_service.action_executor._schedule_message_action = AsyncMock(return_value=True)
        follow_up_service.redis_store.update_action_status = AsyncMock(return_value=True)

        action_id = uuid4()
        patient_id = uuid4()

        with patch.object(
            followup_retry_task,
            "get_scoped_session",
            return_value=_scoped_session(db_session),
        ), patch.object(
            followup_retry_task,
            "async_to_sync",
            side_effect=_async_to_sync_bridge,
        ), patch(
            "app.services.follow_up_system.service.FollowUpSystemService",
            return_value=follow_up_service,
        ):
            result = retry_failed_followup_send.run(
                str(action_id),
                str(patient_id),
                parameters={"message_content": "Retry me"},
                follow_up_type=FollowUpType.CONVERSATION_CONTINUATION.value,
                priority="medium",
            )

        assert result == {
            "status": "ok",
            "action_id": str(action_id),
            "attempt": 1,
        }
        follow_up_service.redis_store.update_action_status.assert_awaited_once()
        assert (
            follow_up_service.redis_store.update_action_status.await_args.kwargs["status"]
            == "executed"
        )

    def test_retry_failed_followup_send_marks_terminal_failure_after_exhaustion(
        self,
        db_session: Session,
    ):
        follow_up_service = MagicMock()
        follow_up_service.action_executor._schedule_message_action = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        follow_up_service.redis_store.update_action_status = AsyncMock(return_value=True)
        retry_failed_followup_send.request.retries = FOLLOWUP_RETRY_MAX

        with patch.object(
            followup_retry_task,
            "get_scoped_session",
            return_value=_scoped_session(db_session),
        ), patch.object(
            followup_retry_task,
            "async_to_sync",
            side_effect=_async_to_sync_bridge,
        ), patch(
            "app.services.follow_up_system.service.FollowUpSystemService",
            return_value=follow_up_service,
        ), patch.object(
            followup_retry_task.retry_failed_followup_send,
            "retry",
            side_effect=MaxRetriesExceededError("done"),
        ):
            result = retry_failed_followup_send.run(
                str(uuid4()),
                str(uuid4()),
                parameters={"message_content": "Retry me"},
                follow_up_type=FollowUpType.CONVERSATION_CONTINUATION.value,
            )

        assert result["status"] == "permanently_failed"
        assert result["attempts"] == FOLLOWUP_RETRY_MAX
        assert (
            follow_up_service.redis_store.update_action_status.await_args.kwargs["status"]
            == "failed"
        )
