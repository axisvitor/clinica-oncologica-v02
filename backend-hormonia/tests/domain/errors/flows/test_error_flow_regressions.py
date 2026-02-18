"""
Regression tests for app.domain.errors.flows fixes.
"""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.errors.flows.audit_logger import ErrorAuditLogger
from app.domain.errors.flows.classifier import (
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
)
from app.domain.errors.flows import audit_logger as audit_logger_module
from app.domain.errors.flows.error_handler import FlowErrorHandler
from app.domain.errors.flows import recovery_strategy as recovery_strategy_module
from app.domain.errors.flows.recovery_strategy import EscalateManualAction, ResetFlowAction
from app.domain.errors.flows.retry_manager import (
    ErrorContext,
    ErrorRecord,
    RecoveryResult,
    RetryManager,
)
from app.utils.timezone import now_sao_paulo


class FakePipeline:
    def __init__(self, store: dict[str, str]):
        self._store = store
        self._keys: list[str] = []

    def get(self, key: str) -> None:
        self._keys.append(key)

    async def execute(self) -> list[str | None]:
        return [self._store.get(key) for key in self._keys]


class FakeRedis:
    def __init__(self, initial_data: dict[str, str] | None = None):
        self.store = dict(initial_data or {})
        self.setex_calls: list[tuple[str, int, str]] = []
        self.deleted_keys: list[str] = []

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        self.setex_calls.append((key, ttl_seconds, value))
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)
        self.store.pop(key, None)

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self.store)


def _build_error_record(
    *,
    flow_state_id=None,
    severity: ErrorSeverity = ErrorSeverity.HIGH,
    created_at=None,
) -> ErrorRecord:
    context = ErrorContext(
        patient_id=uuid4(),
        flow_state_id=flow_state_id,
        operation="execute_step",
    )
    return ErrorRecord(
        id=str(uuid4()),
        error_type="RuntimeError",
        category=ErrorCategory.SYSTEM_ERROR,
        severity=severity,
        message="boom",
        context=context,
        created_at=created_at or now_sao_paulo(),
    )


def test_generate_error_id_is_robust_uuid():
    handler = FlowErrorHandler.__new__(FlowErrorHandler)
    context = ErrorContext(patient_id=uuid4(), operation="send_message")

    ids = {handler._generate_error_id(context) for _ in range(5)}

    assert len(ids) == 5
    for value in ids:
        assert str(UUID(value)) == value


@pytest.mark.asyncio
async def test_schedule_retry_enforces_minimum_ttl_seconds():
    redis = FakeRedis()
    manager = RetryManager(redis_client=redis)
    error_record = _build_error_record()
    past_retry_at_naive = now_sao_paulo().replace(tzinfo=None) - timedelta(hours=2)

    scheduled = await manager.schedule_retry(error_record, past_retry_at_naive)

    assert scheduled is True
    _, ttl_seconds, payload = redis.setex_calls[0]
    assert ttl_seconds >= 1
    retry_data = json.loads(payload)
    assert "retry_at" in retry_data


@pytest.mark.asyncio
async def test_schedule_flow_resume_enforces_minimum_ttl_seconds():
    redis = FakeRedis()
    manager = RetryManager(redis_client=redis)
    past_resume_at_naive = now_sao_paulo().replace(tzinfo=None) - timedelta(hours=2)

    scheduled = await manager.schedule_flow_resume(uuid4(), past_resume_at_naive)

    assert scheduled is True
    _, ttl_seconds, payload = redis.setex_calls[0]
    assert ttl_seconds >= 1
    resume_data = json.loads(payload)
    assert "resume_at" in resume_data


@pytest.mark.asyncio
async def test_get_error_statistics_handles_naive_and_aware_timestamps():
    recent_naive = now_sao_paulo().replace(tzinfo=None).isoformat()
    recent_utc_z = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    redis = FakeRedis(
        {
            "flow_error:naive": json.dumps(
                {
                    "category": ErrorCategory.SYSTEM_ERROR.value,
                    "severity": ErrorSeverity.HIGH.value,
                    "resolved": True,
                    "created_at": recent_naive,
                }
            ),
            "flow_error:aware": json.dumps(
                {
                    "category": ErrorCategory.SYSTEM_ERROR.value,
                    "severity": ErrorSeverity.HIGH.value,
                    "resolved": False,
                    "created_at": recent_utc_z,
                }
            ),
        }
    )
    audit_logger = ErrorAuditLogger(redis_client=redis)
    audit_logger._scan_keys = AsyncMock(return_value=["flow_error:naive", "flow_error:aware"])

    stats = await audit_logger.get_error_statistics(timeframe_hours=24, use_cache=False)

    assert stats["total_errors"] == 2
    assert stats["resolved_errors"] == 1
    assert stats["pending_errors"] == 1
    assert stats["by_category"][ErrorCategory.SYSTEM_ERROR.value] == 2


@pytest.mark.asyncio
async def test_cleanup_old_errors_handles_mixed_timezone_datetimes():
    audit_logger = ErrorAuditLogger(redis_client=FakeRedis())
    old_naive = (now_sao_paulo() - timedelta(days=10)).replace(tzinfo=None)
    recent_aware = now_sao_paulo()

    error_records = {
        "old": _build_error_record(created_at=old_naive),
        "recent": _build_error_record(created_at=recent_aware),
    }

    cleaned = await audit_logger.cleanup_old_errors(error_records, days_old=7)

    assert cleaned == 1
    assert "old" not in error_records
    assert "recent" in error_records


@pytest.mark.asyncio
async def test_reset_flow_action_handles_current_step_none():
    flow_state = SimpleNamespace(current_step=None, state_data={"status": "corrupted"})
    flow_repo = Mock()
    flow_repo.get.return_value = flow_state
    db = Mock()
    context = SimpleNamespace(flow_repo=flow_repo, db=db, retry_manager=Mock())
    error_record = _build_error_record(flow_state_id=uuid4())

    result = await ResetFlowAction().execute(error_record, context)

    assert result.success is True
    assert flow_state.state_data["current_step"] == 1
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_audit_logger_escalation_alert_id_is_serializable(monkeypatch):
    broadcast_alert = AsyncMock(return_value=1)
    monkeypatch.setattr(
        audit_logger_module,
        "websocket_events",
        SimpleNamespace(broadcast_alert_event=broadcast_alert),
    )
    audit_logger = ErrorAuditLogger(redis_client=FakeRedis())
    error_record = _build_error_record(severity=ErrorSeverity.CRITICAL)
    recovery_result = RecoveryResult(
        success=False,
        strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
        attempts_made=1,
        error_resolved=False,
    )

    escalated = await audit_logger.escalate_error(error_record, recovery_result)

    assert escalated is True
    alert_data = broadcast_alert.call_args.kwargs["alert_data"]
    assert isinstance(alert_data["alert_id"], str)
    assert isinstance(alert_data["patient_id"], str)
    UUID(alert_data["alert_id"])


@pytest.mark.asyncio
async def test_manual_escalation_alert_id_is_serializable(monkeypatch):
    broadcast_alert = AsyncMock(return_value=1)
    monkeypatch.setattr(
        recovery_strategy_module,
        "websocket_events",
        SimpleNamespace(broadcast_alert_event=broadcast_alert),
    )
    context = SimpleNamespace()
    error_record = _build_error_record()

    result = await EscalateManualAction().execute(error_record, context)

    assert result.success is True
    alert_data = broadcast_alert.call_args.kwargs["alert_data"]
    assert isinstance(alert_data["alert_id"], str)
    assert isinstance(alert_data["patient_id"], str)
    UUID(alert_data["alert_id"])
