from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.flow.health import FlowHealthService


class FakeResult:
    def __init__(self, *, scalar_value=None, rows: list[dict] | None = None) -> None:
        self._scalar_value = scalar_value
        self._rows = rows or []

    def scalar(self):
        return self._scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value

    def mappings(self):
        return self

    def all(self) -> list[dict]:
        return list(self._rows)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_get_health_summary_returns_counts_for_all_categories(mock_db):
    mock_db.execute.side_effect = [
        FakeResult(scalar_value=7),
        FakeResult(scalar_value=2),
        FakeResult(scalar_value=1),
        FakeResult(scalar_value=9),
    ]
    service = FlowHealthService(mock_db)

    summary = await service.get_health_summary()

    assert summary == {
        "active": 7,
        "stalled": 2,
        "failed": 1,
        "completed": 9,
    }
    assert mock_db.execute.await_count == 4


@pytest.mark.asyncio
async def test_check_and_fire_stall_alerts_logs_each_stalled_flow(mock_db, caplog):
    stalled_flows = [
        {
            "patient_id": str(uuid4()),
            "flow_state_id": str(uuid4()),
            "last_interaction_at": datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc),
            "hours_stuck": 8.5,
        },
        {
            "patient_id": str(uuid4()),
            "flow_state_id": str(uuid4()),
            "last_interaction_at": None,
            "hours_stuck": 12.0,
        },
    ]
    mock_db.execute.return_value = FakeResult(rows=stalled_flows)
    service = FlowHealthService(mock_db)

    with caplog.at_level("WARNING"):
        result = await service.check_and_fire_stall_alerts()

    assert result == [
        {
            **stalled_flows[0],
            "last_interaction_at": "2026-03-06T12:00:00+00:00",
        },
        {
            **stalled_flows[1],
            "last_interaction_at": None,
        },
    ]
    assert len(caplog.records) == 2
    assert caplog.records[0].message == "flow_stall_alert"
    assert caplog.records[0].patient_id == stalled_flows[0]["patient_id"]
    assert caplog.records[0].flow_state_id == stalled_flows[0]["flow_state_id"]
    assert caplog.records[0].hours_stuck == stalled_flows[0]["hours_stuck"]
    assert caplog.records[0].alert_type == "flow_stall"


@pytest.mark.asyncio
async def test_check_and_fire_stall_alerts_posts_webhook_when_configured(
    mock_db, monkeypatch
):
    stalled_flows = [
        {
            "patient_id": str(uuid4()),
            "flow_state_id": str(uuid4()),
            "last_interaction_at": datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc),
            "hours_stuck": 8.5,
        }
    ]
    mock_db.execute.return_value = FakeResult(rows=stalled_flows)
    service = FlowHealthService(mock_db)
    response = MagicMock()
    response.raise_for_status = MagicMock()
    post = AsyncMock(return_value=response)
    client = MagicMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = AsyncMock()
    client.post = post

    monkeypatch.setattr(
        "app.services.flow.health.FLOW_STALL_ALERT_WEBHOOK_URL",
        "https://alerts.example.com/stalls",
    )
    monkeypatch.setattr("app.services.flow.health.httpx.AsyncClient", MagicMock(return_value=client))

    result = await service.check_and_fire_stall_alerts()

    assert len(result) == 1
    post.assert_awaited_once()
    _, kwargs = post.await_args
    assert kwargs["url"] == "https://alerts.example.com/stalls"
    assert kwargs["json"]["stalled_flows"][0]["patient_id"] == stalled_flows[0]["patient_id"]
    assert kwargs["json"]["threshold_hours"] == 6


@pytest.mark.asyncio
async def test_check_and_fire_stall_alerts_skips_webhook_when_unset(
    mock_db, monkeypatch
):
    stalled_flows = [
        {
            "patient_id": str(uuid4()),
            "flow_state_id": str(uuid4()),
            "last_interaction_at": datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc),
            "hours_stuck": 8.5,
        }
    ]
    mock_db.execute.return_value = FakeResult(rows=stalled_flows)
    service = FlowHealthService(mock_db)
    async_client = MagicMock()

    monkeypatch.setattr("app.services.flow.health.FLOW_STALL_ALERT_WEBHOOK_URL", "")
    monkeypatch.setattr("app.services.flow.health.httpx.AsyncClient", async_client)

    result = await service.check_and_fire_stall_alerts()

    assert len(result) == 1
    async_client.assert_not_called()
