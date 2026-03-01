import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.analytics import RiskLevel
from app.services.data_integrity_monitoring import DataIntegrityMonitoringService
from app.services.flow_alerts import FlowAlertsService
from app.services.flow_dashboard_pkg.models import DashboardTimeframe
from app.services.flow_dashboard_pkg.service import FlowDashboardService


@dataclass
class _FakeScalarResult:
    values: list

    def all(self):
        return list(self.values)


@dataclass
class _FakeExecuteResult:
    rows: list | None = None
    scalar_rows: list | None = None
    scalar_value: int | None = None

    def all(self):
        return list(self.rows or [])

    def scalars(self):
        return _FakeScalarResult(self.scalar_rows or [])

    def scalar_one(self):
        return self.scalar_value


class _IntegrityAsyncSession:
    def __init__(self):
        self.execute_calls = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        idx = len(self.execute_calls)
        if idx % 3 == 1:
            return _FakeExecuteResult(scalar_value=12)
        if idx % 3 == 2:
            return _FakeExecuteResult(scalar_value=8)
        return _FakeExecuteResult(scalar_value=4)

    async def scalars(self, statement):
        return _FakeScalarResult([])

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


class _FlowAlertsAsyncSession:
    def __init__(self):
        self.template_id = uuid4()
        self.template = SimpleNamespace(id=self.template_id, flow_kind_id=uuid4())
        self.flow_state = SimpleNamespace(id=uuid4(), patient_id=uuid4())
        self.negative_event = SimpleNamespace(
            id=uuid4(),
            patient_id=uuid4(),
            sentiment_score=-0.8,
            success_rate=-0.8,
            timestamp=datetime.now(timezone.utc),
            calculated_at=datetime.now(timezone.utc),
        )
        self.execute_calls = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        sql = str(statement).lower()

        if "sum(case" in sql:
            return _FakeExecuteResult(rows=[(self.template_id, "onboarding", 4, 1)])
        if "avg(extract" in sql:
            return _FakeExecuteResult(rows=[(self.template_id, "onboarding", 40 * 86400)])
        if "coalesce" in sql:
            return _FakeExecuteResult(scalar_rows=[self.flow_state])
        if "flow_template_versions.is_active" in sql:
            return _FakeExecuteResult(scalar_rows=[self.template])
        if "active_patients" in sql:
            return _FakeExecuteResult(rows=[(self.template_id, 0)])
        if "flow_analytics" in sql and (
            "sentiment_score" in sql or "success_rate" in sql
        ):
            return _FakeExecuteResult(scalar_rows=[self.negative_event])

        raise AssertionError(f"Unhandled statement for flow alerts test: {statement}")

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


class _FlowDashboardAsyncSession:
    def __init__(self):
        self.execute_calls = []
        self.concern_event = SimpleNamespace(
            id=uuid4(),
            patient_id=uuid4(),
            flow_type="onboarding",
            flow_template_version_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            calculated_at=datetime.now(timezone.utc),
            event_data={"reason": "concern"},
            step_analytics={"reason": "concern"},
        )

    async def execute(self, statement):
        self.execute_calls.append(statement)
        sql = str(statement).lower()

        if "distinct" in sql and "flow_analytics.flow_template_version_id" in sql:
            return _FakeExecuteResult(rows=[(self.concern_event.flow_template_version_id,)])
        if "from flow_analytics" in sql and "order by" in sql:
            return _FakeExecuteResult(scalar_rows=[self.concern_event])
        if "flow_analytics.success_rate" in sql:
            return _FakeExecuteResult(scalar_rows=[0.9, 0.55, 0.1])

        raise AssertionError(f"Unhandled statement for flow dashboard test: {statement}")

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


def _metric():
    return SimpleNamespace(
        total_messages_sent=10,
        total_responses_received=7,
        response_rate=0.7,
        average_response_time=None,
        engagement_score=81.0,
        sentiment_distribution={"neutral": 1.0},
        completion_rates={"onboarding": 0.8},
    )


@pytest.mark.asyncio
async def test_phase22_async_load_paths_emit_zero_missinggreenlet_logs(monkeypatch, caplog):
    integrity_db = _IntegrityAsyncSession()
    flow_alerts_db = _FlowAlertsAsyncSession()
    flow_dashboard_db = _FlowDashboardAsyncSession()

    integrity_service = DataIntegrityMonitoringService(integrity_db)
    integrity_service._scan_patient_integrity = AsyncMock(
        return_value={"entities_scanned": 1, "issues_found": 0}
    )
    integrity_service._scan_flow_integrity = AsyncMock(
        return_value={"entities_scanned": 1, "issues_found": 0}
    )
    integrity_service._scan_message_integrity = AsyncMock(
        return_value={"entities_scanned": 1, "issues_found": 0}
    )

    alert_manager = AsyncMock()
    monkeypatch.setattr("app.services.flow_alerts.get_alert_manager", lambda: alert_manager)
    flow_alerts_service = FlowAlertsService(flow_alerts_db)

    analytics_service = AsyncMock()
    analytics_service.calculate_engagement_metrics = AsyncMock(return_value=_metric())
    analytics_service.identify_at_risk_patients = AsyncMock(
        return_value=[SimpleNamespace(risk_level=RiskLevel.HIGH)]
    )
    flow_dashboard_service = FlowDashboardService(
        db=flow_dashboard_db,
        analytics_service=analytics_service,
    )

    with caplog.at_level(logging.ERROR):
        await asyncio.gather(
            *[
                integrity_service.run_comprehensive_integrity_scan(limit=5)
                for _ in range(3)
            ],
            *[integrity_service.get_integrity_dashboard() for _ in range(3)],
            *[flow_alerts_service.evaluate_alerts() for _ in range(3)],
            *[flow_dashboard_service.get_dashboard_overview() for _ in range(3)],
            *[
                flow_dashboard_service.get_patient_engagement_trends(
                    timeframe=DashboardTimeframe.LAST_24_HOURS,
                    flow_type="onboarding",
                )
                for _ in range(3)
            ],
        )

    missing_greenlet_logs = [
        rec
        for rec in caplog.records
        if "missinggreenlet" in rec.getMessage().lower()
    ]

    assert not missing_greenlet_logs
    assert len(integrity_db.execute_calls) == 9
    assert len(flow_alerts_db.execute_calls) >= 15
    assert len(flow_dashboard_db.execute_calls) >= 9
