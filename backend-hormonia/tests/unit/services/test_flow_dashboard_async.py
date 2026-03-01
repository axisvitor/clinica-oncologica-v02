import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.analytics import RiskLevel
from app.services.flow_dashboard_pkg.models import DashboardTimeframe
from app.services.flow_dashboard_pkg.service import FlowDashboardService


@dataclass
class _FakeScalarResult:
    values: list

    def all(self):
        return list(self.values)


@dataclass
class _FakeResult:
    rows: list | None = None
    scalar_rows: list | None = None

    def all(self):
        return list(self.rows or [])

    def scalars(self):
        return _FakeScalarResult(self.scalar_rows or [])


class _QueueAsyncSession:
    def __init__(self, responses: list[_FakeResult]):
        self._responses = list(responses)
        self.execute_calls = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        if not self._responses:
            raise AssertionError("Unexpected execute call with no queued response")
        return self._responses.pop(0)

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


def _metric(
    *,
    sent: int,
    responses: int,
    response_rate: float,
    engagement_score: float,
    completion_rates: dict,
):
    return SimpleNamespace(
        total_messages_sent=sent,
        total_responses_received=responses,
        response_rate=response_rate,
        average_response_time=None,
        engagement_score=engagement_score,
        sentiment_distribution={"neutral": 1.0},
        completion_rates=completion_rates,
    )


@pytest.mark.asyncio
async def test_flow_type_breakdown_uses_async_execute_and_preserves_shape():
    db = _QueueAsyncSession([_FakeResult(rows=[("onboarding",), ("followup",)])])
    analytics_service = AsyncMock()

    async def _calculate(*, flow_type, date_range):
        assert date_range
        return _metric(
            sent=10 if flow_type == "onboarding" else 5,
            responses=7 if flow_type == "onboarding" else 3,
            response_rate=0.7 if flow_type == "onboarding" else 0.6,
            engagement_score=88.0 if flow_type == "onboarding" else 70.0,
            completion_rates={"onboarding": 0.8, "followup": 0.5},
        )

    analytics_service.calculate_engagement_metrics = AsyncMock(side_effect=_calculate)
    service = FlowDashboardService(db=db, analytics_service=analytics_service)

    breakdown = await service._get_flow_type_breakdown(
        (datetime.now(timezone.utc), datetime.now(timezone.utc))
    )

    assert set(breakdown.keys()) == {"onboarding", "followup"}
    assert breakdown["onboarding"]["messages_sent"] == 10
    assert breakdown["followup"]["response_rate"] == 0.6
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_recent_alerts_uses_async_execute_and_preserves_key_fields():
    event = SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        flow_type="onboarding",
        timestamp=datetime.now(timezone.utc),
        event_data={"reason": "concern"},
    )
    db = _QueueAsyncSession([_FakeResult(scalar_rows=[event])])
    service = FlowDashboardService(db=db, analytics_service=AsyncMock())

    alerts = await service._get_recent_alerts(
        (datetime.now(timezone.utc), datetime.now(timezone.utc))
    )

    assert len(alerts) == 1
    assert alerts[0]["type"] == "patient_concern"
    assert alerts[0]["patient_id"] == str(event.patient_id)
    assert "timestamp" in alerts[0]
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_engagement_distribution_uses_async_execute_query_path():
    db = _QueueAsyncSession([_FakeResult(scalar_rows=[0.9, 0.55, 0.2, 0.1])])
    service = FlowDashboardService(db=db, analytics_service=AsyncMock())

    distribution = await service._get_engagement_distribution(
        (datetime.now(timezone.utc), datetime.now(timezone.utc)),
        flow_type="onboarding",
    )

    assert distribution["total_data_points"] == 4
    assert distribution["high"] == 25.0
    assert distribution["medium"] == 25.0
    assert distribution["low"] == 50.0
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_sentiment_alerts_uses_async_execute_query_path():
    event = SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        sentiment_score=-0.8,
        timestamp=datetime.now(timezone.utc),
    )
    db = _QueueAsyncSession([_FakeResult(scalar_rows=[event])])
    service = FlowDashboardService(db=db, analytics_service=AsyncMock())

    alerts = await service._check_sentiment_alerts()

    assert len(alerts) == 1
    assert alerts[0]["severity"] == "medium"
    assert alerts[0]["patient_id"] == str(event.patient_id)
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_dashboard_overview_preserves_router_payload_fields():
    analytics_service = AsyncMock()
    analytics_service.calculate_engagement_metrics = AsyncMock(
        return_value=_metric(
            sent=12,
            responses=9,
            response_rate=0.75,
            engagement_score=82.0,
            completion_rates={"onboarding": 0.8},
        )
    )
    analytics_service.identify_at_risk_patients = AsyncMock(
        return_value=[SimpleNamespace(risk_level=RiskLevel.HIGH)]
    )

    service = FlowDashboardService(db=_QueueAsyncSession([]), analytics_service=analytics_service)
    service._get_flow_type_breakdown = AsyncMock(return_value={"onboarding": {"messages_sent": 12}})
    service._calculate_trends = AsyncMock(return_value={"messages_sent": {"direction": "up"}})
    service._get_recent_alerts = AsyncMock(return_value=[{"id": "a1"}])

    payload = await service.get_dashboard_overview()

    assert "timeframe" in payload
    assert "overview_metrics" in payload
    assert "at_risk_summary" in payload
    assert "flow_type_breakdown" in payload
    assert "recent_alerts" in payload
    assert "generated_at" in payload
    assert payload["at_risk_summary"]["total_at_risk"] == 1


@pytest.mark.asyncio
async def test_mixed_concurrent_dashboard_calls_preserve_contract_fields():
    analytics_service = AsyncMock()
    analytics_service.calculate_engagement_metrics = AsyncMock(
        return_value=_metric(
            sent=4,
            responses=3,
            response_rate=0.75,
            engagement_score=80.0,
            completion_rates={"onboarding": 0.75},
        )
    )
    analytics_service.identify_at_risk_patients = AsyncMock(return_value=[])

    service = FlowDashboardService(db=_QueueAsyncSession([]), analytics_service=analytics_service)
    service._get_flow_type_breakdown = AsyncMock(return_value={"onboarding": {"messages_sent": 4}})
    service._calculate_trends = AsyncMock(return_value={"messages_sent": {"direction": "stable"}})
    service._get_recent_alerts = AsyncMock(return_value=[])
    service._get_engagement_distribution = AsyncMock(
        return_value={"high": 100.0, "medium": 0.0, "low": 0.0, "total_data_points": 1}
    )
    service._get_peak_engagement_times = AsyncMock(
        return_value={
            "best_day_of_week": "Tuesday",
            "best_hour_of_day": 10,
            "response_rate_by_hour": {},
            "response_rate_by_day": {},
        }
    )

    results = await asyncio.gather(
        *[service.get_dashboard_overview() for _ in range(6)],
        *[
            service.get_patient_engagement_trends(
                timeframe=DashboardTimeframe.LAST_24_HOURS,
                flow_type="onboarding",
            )
            for _ in range(6)
        ],
    )

    assert len(results) == 12
    overviews = results[:6]
    trends = results[6:]
    assert all("overview_metrics" in payload for payload in overviews)
    assert all("engagement_distribution" in payload for payload in trends)
