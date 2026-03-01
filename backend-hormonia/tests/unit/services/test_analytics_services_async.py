from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.v2.enhanced_analytics import MetricType
from app.services.analytics.enhanced_analytics_service import EnhancedAnalyticsService
from app.services.analytics.flow_analytics import FlowAnalyticsService
from app.services.analytics.metrics_collector import MetricsCollectorService
from app.models.user import UserRole


@dataclass
class _FakeScalarResult:
    values: list

    def all(self):
        return list(self.values)

    def first(self):
        return self.values[0] if self.values else None


@dataclass
class _FakeResult:
    rows: list | None = None
    scalar_rows: list | None = None
    scalar_value: object | None = None

    def all(self):
        return list(self.rows or [])

    def first(self):
        if self.rows:
            return self.rows[0]
        return None

    def scalars(self):
        return _FakeScalarResult(self.scalar_rows or [])

    def scalar(self):
        return self.scalar_value


class _QueueAsyncSession:
    def __init__(self, responses: list[_FakeResult]):
        self._responses = list(responses)
        self.execute_calls = []
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    async def execute(self, statement):
        self.execute_calls.append(statement)
        if not self._responses:
            raise AssertionError("Unexpected execute call with no queued response")
        return self._responses.pop(0)

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


@pytest.mark.asyncio
async def test_flow_analytics_engagement_metrics_uses_async_execute_path():
    row = SimpleNamespace(sent=12, received=9)
    db = _QueueAsyncSession([_FakeResult(rows=[row])])
    service = FlowAnalyticsService(db)

    metrics = await service.calculate_engagement_metrics(
        date_range=(datetime.now(timezone.utc) - timedelta(days=7), datetime.now(timezone.utc))
    )

    assert metrics.total_messages_sent == 12
    assert metrics.total_responses_received == 9
    assert metrics.response_rate == 0.75
    assert metrics.to_dict()["engagement_score"] == 7.5
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_metrics_collector_healthcare_summary_preserves_contract_fields():
    db = _QueueAsyncSession(
        [
            _FakeResult(scalar_value=20),
            _FakeResult(scalar_value=8),
            _FakeResult(scalar_value=40),
            _FakeResult(scalar_value=30),
            _FakeResult(scalar_value=100),
            _FakeResult(scalar_value=60),
            _FakeResult(scalar_value=14),
        ]
    )
    service = MetricsCollectorService(db=db, redis_client=None)

    async def _health_score():
        return 92.0

    service._calculate_system_health_score = _health_score

    payload = await service.get_healthcare_summary()

    assert payload["active_patients"] == 8
    assert payload["daily_messages"] == 14
    assert "engagement_rate" in payload
    assert "quiz_completion_rate" in payload
    assert "ai_personalization_impact" in payload
    assert "system_health_score" in payload
    assert len(db.execute_calls) == 7


@pytest.mark.asyncio
async def test_enhanced_analytics_realtime_stream_uses_async_execute_path(monkeypatch):
    db = _QueueAsyncSession(
        [
            _FakeResult(scalar_value=5),
            _FakeResult(scalar_value=3),
        ]
    )
    service = EnhancedAnalyticsService(db)

    async def _cache_get(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_get_cached_result", _cache_get)

    payload = await service.get_realtime_stream(UserRole.ADMIN, user_uuid=uuid4())

    assert payload["active_sessions"] == 5
    assert payload["recent_activity_1h"] == 3
    assert "system_health" in payload
    assert "metrics" in payload
    assert len(db.execute_calls) == 2


@pytest.mark.asyncio
async def test_enhanced_predictive_analytics_preserves_prediction_keys(monkeypatch):
    today = datetime.now(timezone.utc)
    row_one = SimpleNamespace(date=today.date().isoformat(), value=10)
    row_two = SimpleNamespace(date=(today - timedelta(days=1)).date().isoformat(), value=12)
    db = _QueueAsyncSession([_FakeResult(rows=[row_one, row_two])])
    service = EnhancedAnalyticsService(db)

    async def _cache_get(*args, **kwargs):
        return None

    async def _cache_set(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_get_cached_result", _cache_get)
    monkeypatch.setattr(service, "_set_cached_result", _cache_set)

    payload = await service.get_predictive_analytics(
        metric_type=MetricType.PATIENTS,
        forecast_days=3,
        confidence_threshold=0.7,
        role=UserRole.ADMIN,
        user_uuid=None,
    )

    assert payload["metric_type"] == MetricType.PATIENTS.value
    assert len(payload["predictions"]) == 3
    assert {"date", "predicted_value", "confidence_score"}.issubset(payload["predictions"][0].keys())
    assert len(db.execute_calls) == 1
