from __future__ import annotations

import logging

import pytest
from prometheus_client import REGISTRY

from app.ai.adk.metrics import (
    ADK_INVOCATION_DURATION_SECONDS,
    ADK_INVOCATIONS_IN_FLIGHT,
    ADK_INVOCATIONS_TOTAL,
    record_adk_invocation,
    track_adk_invocation,
)


def _sample_value(name: str, labels: dict[str, str]) -> float:
    value = REGISTRY.get_sample_value(name, labels=labels)
    return 0.0 if value is None else float(value)


def test_counter_increments() -> None:
    labels = {"tool_name": "sentiment", "status": "success"}
    before = _sample_value("adk_invocations_total", labels)

    record_adk_invocation(
        tool_name="sentiment",
        status="success",
        duration_seconds=0.42,
    )

    after = _sample_value("adk_invocations_total", labels)
    assert after == before + 1.0


def test_histogram_records_duration() -> None:
    labels = {"tool_name": "humanize", "status": "timeout"}
    before = _sample_value("adk_invocation_duration_seconds_count", labels)

    record_adk_invocation(
        tool_name="humanize",
        status="timeout",
        duration_seconds=5.0,
    )

    after = _sample_value("adk_invocation_duration_seconds_count", labels)
    assert after == before + 1.0


def test_in_flight_gauge() -> None:
    labels = {"tool_name": "sentiment"}
    before = _sample_value("adk_invocations_in_flight", labels)

    with track_adk_invocation("sentiment") as context:
        assert isinstance(context["start"], float)
        assert _sample_value("adk_invocations_in_flight", labels) == before + 1.0

    assert _sample_value("adk_invocations_in_flight", labels) == before


def test_structured_log_emitted(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.ai.adk.metrics"):
        record_adk_invocation(
            tool_name="sentiment",
            status="success",
            duration_seconds=0.42,
            invocation_id="inv-123",
            session_id="session-123",
        )

    record = caplog.records[-1]
    assert record.getMessage() == "ADK invocation completed"
    assert record.adk_tool_name == "sentiment"
    assert record.adk_status == "success"
    assert record.adk_duration_ms == 420.0
    assert record.adk_invocation_id == "inv-123"
    assert record.adk_session_id == "session-123"
    assert record.metric_type == "adk_invocation"


def test_in_flight_gauge_decrements_on_exception() -> None:
    labels = {"tool_name": "sentiment"}
    before = _sample_value("adk_invocations_in_flight", labels)

    with pytest.raises(RuntimeError):
        with track_adk_invocation("sentiment"):
            assert _sample_value("adk_invocations_in_flight", labels) == before + 1.0
            raise RuntimeError("boom")

    assert _sample_value("adk_invocations_in_flight", labels) == before
