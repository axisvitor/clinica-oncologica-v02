"""Focused tests for webhook DLQ Celery tasks."""

import asyncio
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest


def _scoped_session(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


class _FakeAsyncRedis:
    def __init__(self, events_by_key):
        self.events_by_key = events_by_key
        self.scan_match_calls = []
        self.lrem_calls = []
        self.keys_called = False

    async def scan_iter(self, match=None, count=None):
        self.scan_match_calls.append(match)
        for key in self.events_by_key:
            yield key

    async def lrange(self, key, start, end):
        return self.events_by_key[key]

    async def lrem(self, key, count, value):
        self.lrem_calls.append((key, count, value))
        return 1

    async def keys(self, pattern):
        self.keys_called = True
        raise AssertionError("cleanup_old_dlq_events should not call KEYS")


def test_cleanup_old_dlq_events_uses_scan_iter_and_preserves_cleanup_semantics():
    from app.tasks.webhook_dlq import cleanup_old_dlq_events

    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    old_event = json.dumps({"timestamp": (fixed_now - timedelta(days=10)).isoformat()})
    recent_event = json.dumps({"timestamp": (fixed_now - timedelta(days=1)).isoformat()})
    older_event = json.dumps({"timestamp": (fixed_now - timedelta(days=20)).isoformat()})

    redis_client = _FakeAsyncRedis(
        {
            "webhook:dlq:message.received": [old_event, recent_event, "{invalid-json"],
            "webhook:dlq:message.sent": [older_event],
        }
    )

    async def _get_async_redis():
        return redis_client

    def _run_async(coro, timeout=None):
        return asyncio.run(coro)

    dlq_service = Mock()
    dlq_service.DLQ_KEY_PREFIX = "webhook:dlq"

    with patch(
        "app.tasks.webhook_dlq.get_scoped_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.tasks.webhook_dlq.get_webhook_dlq", return_value=dlq_service
    ), patch(
        "app.core.redis_manager.get_async_redis_client", side_effect=_get_async_redis
    ), patch(
        "app.tasks.webhook_dlq.run_async", side_effect=_run_async
    ), patch(
        "app.tasks.webhook_dlq.now_sao_paulo", return_value=fixed_now
    ):
        result = cleanup_old_dlq_events.run(days_old=7)

    assert result["success"] is True
    assert result["cleaned_count"] == 3
    assert result["days_old"] == 7

    assert redis_client.scan_match_calls == ["webhook:dlq:*"]
    assert len(redis_client.lrem_calls) == 3
    assert redis_client.keys_called is False


def test_monitor_dlq_health_uses_run_async_and_preserves_alert_shape():
    from app.tasks.webhook_dlq import (
        WEBHOOK_DLQ_PROCESSING_TIMEOUT,
        monitor_dlq_health,
    )

    fixed_now = datetime(2026, 1, 20, 9, 30, tzinfo=timezone.utc)
    dlq_service = Mock()
    dlq_service.get_dlq_stats.return_value = "stats-coro"

    stats_payload = {
        "overflow_alert": True,
        "total_pending": 1200,
        "max_dlq_size": 1000,
        "by_event_type": {
            "message.received": {
                "total_processed": 100,
                "total_dead_letter": 20,
            }
        },
    }

    with patch(
        "app.tasks.webhook_dlq.get_scoped_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.tasks.webhook_dlq.get_webhook_dlq", return_value=dlq_service
    ), patch(
        "app.tasks.webhook_dlq.run_async", return_value=stats_payload
    ) as run_async_mock, patch(
        "app.tasks.webhook_dlq.now_sao_paulo", return_value=fixed_now
    ), patch(
        "app.tasks.webhook_dlq.logger.error"
    ), patch(
        "app.tasks.webhook_dlq.logger.warning"
    ):
        result = monitor_dlq_health.run()

    assert result["success"] is True
    assert result["alert_count"] == 2
    assert result["stats"] == stats_payload
    run_async_mock.assert_called_once_with(
        "stats-coro",
        timeout=WEBHOOK_DLQ_PROCESSING_TIMEOUT,
    )


def test_process_webhook_dlq_propagates_failures_for_celery_retry():
    from app.tasks.webhook_dlq import process_webhook_dlq

    dlq_service = Mock()
    dlq_service.process_dlq.return_value = "process-coro"

    with patch(
        "app.tasks.webhook_dlq.get_scoped_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.tasks.webhook_dlq.get_webhook_dlq", return_value=dlq_service
    ), patch(
        "app.tasks.webhook_dlq.run_async", side_effect=RuntimeError("dlq boom")
    ):
        with pytest.raises(RuntimeError, match="dlq boom"):
            process_webhook_dlq.run(batch_size=10)


def test_cleanup_old_dlq_events_raises_retry_instead_of_swallowing_failure():
    from app.tasks.webhook_dlq import cleanup_old_dlq_events

    with patch(
        "app.tasks.webhook_dlq.get_scoped_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.tasks.webhook_dlq.get_webhook_dlq",
        side_effect=RuntimeError("service unavailable"),
    ), patch.object(
        cleanup_old_dlq_events,
        "retry",
        side_effect=RuntimeError("retry-called"),
    ) as retry_mock:
        with pytest.raises(RuntimeError, match="retry-called"):
            cleanup_old_dlq_events.run(days_old=7)

    retry_mock.assert_called_once()


def test_monitor_dlq_health_propagates_failures():
    from app.tasks.webhook_dlq import monitor_dlq_health

    dlq_service = Mock()
    dlq_service.get_dlq_stats.return_value = "stats-coro"

    with patch(
        "app.tasks.webhook_dlq.get_scoped_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.tasks.webhook_dlq.get_webhook_dlq", return_value=dlq_service
    ), patch(
        "app.tasks.webhook_dlq.run_async", side_effect=RuntimeError("stats failed")
    ):
        with pytest.raises(RuntimeError, match="stats failed"):
            monitor_dlq_health.run()
