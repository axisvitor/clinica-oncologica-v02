from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.flow_monitoring_pkg.models import HealthStatus
from app.services.flow_monitoring_pkg.service import FlowMonitoringService


@dataclass
class _FakeExecuteResult:
    scalar_value: int | None = None
    rows: list | None = None

    def scalar(self):
        return self.scalar_value

    def all(self):
        return list(self.rows or [])


class _QueueAsyncSession:
    def __init__(self, responses: list[_FakeExecuteResult]):
        self._responses = list(responses)
        self.execute_calls = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        if not self._responses:
            raise AssertionError("Unexpected execute call with no queued response")
        return self._responses.pop(0)

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


class _FailingAsyncSession:
    def __init__(self, error: Exception):
        self.error = error
        self.execute_calls = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        raise self.error

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


class _FakeRedis:
    def __init__(self):
        self._values = {
            "operations_count_last_hour": "40",
        }

    def lrange(self, key, start, end):
        if key == "response_times":
            return ["1.0", "3.0"]
        return []

    def llen(self, key):
        return 2 if key.startswith("flow_errors:") else 0

    def get(self, key):
        return self._values.get(key)

    def info(self, section):
        if section == "memory":
            return {"used_memory": 50, "maxmemory": 100}
        return {}

    def ping(self):
        return True


def _build_service(db) -> FlowMonitoringService:
    return FlowMonitoringService(
        db=db,
        redis=_FakeRedis(),
        flow_repository=SimpleNamespace(),
        corruption_detector=SimpleNamespace(
            detect_bulk_corruption=AsyncMock(return_value=[])
        ),
    )


@pytest.mark.asyncio
async def test_collect_performance_metrics_uses_async_execute_and_preserves_contract():
    now = datetime.now(timezone.utc)
    completed_flow = SimpleNamespace(started_at=now - timedelta(minutes=20), completed_at=now)
    db = _QueueAsyncSession(
        [
            _FakeExecuteResult(scalar_value=3),
            _FakeExecuteResult(scalar_value=4),
            _FakeExecuteResult(scalar_value=10),
            _FakeExecuteResult(rows=[("onboarding", 5)]),
            _FakeExecuteResult(rows=[("onboarding", 3)]),
            _FakeExecuteResult(rows=[("onboarding", 2)]),
            _FakeExecuteResult(rows=[("onboarding", completed_flow)]),
        ]
    )
    service = _build_service(db)

    metrics = await service.collect_performance_metrics()

    assert metrics.total_active_flows == 3
    assert metrics.messages_sent_last_hour == 4
    assert metrics.messages_sent_last_24h == 10
    assert metrics.average_response_time == 2.0
    assert metrics.error_rate == 0.05
    assert metrics.success_rate == 0.95
    assert metrics.redis_memory_usage == 0.5
    assert len(db.execute_calls) == 7


@pytest.mark.asyncio
async def test_collect_performance_metrics_returns_fallback_on_execute_error():
    db = _FailingAsyncSession(RuntimeError("boom"))
    service = _build_service(db)

    metrics = await service.collect_performance_metrics()

    assert metrics.total_active_flows == 0
    assert metrics.messages_sent_last_hour == 0
    assert metrics.messages_sent_last_24h == 0
    assert metrics.error_rate == 1.0
    assert metrics.success_rate == 0.0


@pytest.mark.asyncio
async def test_database_connectivity_check_uses_async_execute():
    db = _QueueAsyncSession([_FakeExecuteResult(scalar_value=1)])
    service = _build_service(db)

    check = await service._check_database_connectivity()

    assert check["status"] == HealthStatus.HEALTHY.value
    assert "response_time" in check
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_flow_processing_health_check_uses_async_execute_without_query():
    db = _QueueAsyncSession([_FakeExecuteResult(scalar_value=0)])
    service = _build_service(db)

    check = await service._check_flow_processing_health()

    assert check["status"] == HealthStatus.WARNING.value
    assert check["recent_messages"] == 0
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_run_health_checks_reports_critical_when_database_unavailable():
    db = _FailingAsyncSession(RuntimeError("database offline"))
    service = _build_service(db)

    checks = await service.run_health_checks()

    assert checks["overall_status"] == HealthStatus.CRITICAL.value
    assert checks["checks"]["database_connectivity"]["status"] == HealthStatus.CRITICAL.value
