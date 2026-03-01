import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.alerts.types import Alert, AlertRuleType, AlertSeverity, AlertStatus
from app.services.flow_alerts import FlowAlertsService


@dataclass
class FakeScalarResult:
    values: list

    def all(self):
        return self.values


@dataclass
class FakeResult:
    rows: list | None = None
    scalar_rows: list | None = None

    def all(self):
        return self.rows or []

    def scalars(self):
        return FakeScalarResult(self.scalar_rows or [])


class QueueAsyncSession:
    def __init__(self, responses: list[FakeResult]):
        self._responses = list(responses)
        self.execute_calls = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        if not self._responses:
            raise AssertionError("Unexpected execute call with no queued response")
        return self._responses.pop(0)


class ConstantAsyncSession:
    def __init__(self, result: FakeResult):
        self._result = result
        self.execute_calls = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        return self._result


def _build_service(monkeypatch, db, alert_manager=None) -> FlowAlertsService:
    manager = alert_manager or AsyncMock()
    monkeypatch.setattr("app.services.flow_alerts.get_alert_manager", lambda: manager)
    return FlowAlertsService(db)


def _make_alert(title: str = "Test alert") -> Alert:
    return Alert(
        id=uuid4(),
        rule_id=uuid4(),
        rule_type=AlertRuleType.CUSTOM,
        severity=AlertSeverity.WARNING,
        status=AlertStatus.ACTIVE,
        title=title,
        message="message",
        context={},
        metadata={},
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_completion_rate_alerts_threshold_logic(monkeypatch):
    template_id = uuid4()
    db = QueueAsyncSession(
        [
            FakeResult(
                rows=[
                    (template_id, "onboarding", 10, 4),
                    (uuid4(), "monthly", 5, 5),
                    (uuid4(), "empty", 0, 0),
                ]
            )
        ]
    )
    service = _build_service(monkeypatch, db)

    alerts = await service._completion_rate_alerts()

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.title == "Low completion rate"
    assert alert.severity is AlertSeverity.WARNING
    assert alert.context["template_version_id"] == str(template_id)
    assert alert.context["flow_kind"] == "onboarding"
    assert alert.context["completion_rate"] == 0.4


@pytest.mark.asyncio
async def test_duration_alerts_threshold_logic(monkeypatch):
    long_duration_seconds = 31 * 86400
    db = QueueAsyncSession(
        [
            FakeResult(
                rows=[
                    (uuid4(), "onboarding", long_duration_seconds),
                    (uuid4(), "monthly", 10 * 86400),
                ]
            )
        ]
    )
    service = _build_service(monkeypatch, db)

    alerts = await service._duration_alerts()

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.title == "Long average flow duration"
    assert alert.severity is AlertSeverity.WARNING
    assert alert.context["average_duration_days"] == 31


@pytest.mark.asyncio
async def test_inconsistent_state_detection(monkeypatch):
    flow_state = SimpleNamespace(id=uuid4(), patient_id=uuid4())
    db = QueueAsyncSession([FakeResult(scalar_rows=[flow_state])])
    service = _build_service(monkeypatch, db)

    alerts = await service._inconsistent_state_alerts()

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.title == "Inconsistent flow state"
    assert alert.severity is AlertSeverity.CRITICAL
    assert alert.context["flow_id"] == str(flow_state.id)
    assert alert.context["patient_id"] == str(flow_state.patient_id)


@pytest.mark.asyncio
async def test_inactive_template_detection(monkeypatch):
    active_template_with_patients = SimpleNamespace(id=uuid4(), flow_kind_id=uuid4())
    inactive_template = SimpleNamespace(id=uuid4(), flow_kind_id=uuid4())
    db = QueueAsyncSession(
        [
            FakeResult(scalar_rows=[active_template_with_patients, inactive_template]),
            FakeResult(rows=[(active_template_with_patients.id, 3)]),
        ]
    )
    service = _build_service(monkeypatch, db)

    alerts = await service._inactive_template_alerts()

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.title == "Template without active patients"
    assert alert.severity is AlertSeverity.INFO
    assert alert.context["template_version_id"] == str(inactive_template.id)


@pytest.mark.asyncio
async def test_evaluate_alerts_processes_alerts_with_alert_manager(monkeypatch):
    manager = AsyncMock()
    service = _build_service(monkeypatch, QueueAsyncSession([]), alert_manager=manager)
    completion_alert = _make_alert("completion")
    inconsistent_alert = _make_alert("inconsistent")

    service._completion_rate_alerts = AsyncMock(return_value=[completion_alert])
    service._duration_alerts = AsyncMock(return_value=[])
    service._inconsistent_state_alerts = AsyncMock(return_value=[inconsistent_alert])
    service._inactive_template_alerts = AsyncMock(return_value=[])

    alerts = await service.evaluate_alerts()

    assert alerts == [completion_alert, inconsistent_alert]
    assert manager.process_alert.await_count == 2
    manager.process_alert.assert_any_await(completion_alert)
    manager.process_alert.assert_any_await(inconsistent_alert)


@pytest.mark.asyncio
async def test_completion_rate_alerts_support_concurrent_evaluations(monkeypatch):
    db = ConstantAsyncSession(FakeResult(rows=[(uuid4(), "onboarding", 4, 1)]))
    service = _build_service(monkeypatch, db)

    results = await asyncio.gather(
        *(service._completion_rate_alerts() for _ in range(8))
    )

    assert len(results) == 8
    assert all(len(alerts) == 1 for alerts in results)
    assert len(db.execute_calls) == 8
