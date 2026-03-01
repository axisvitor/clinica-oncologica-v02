"""Regression tests for queue monitor Redis length retrieval."""

import asyncio
from unittest.mock import Mock, patch

from app.tasks.queue_monitor import QueueMonitor, monitor_queue_lengths_sync


def test_get_queue_length_uses_sync_redis_client_without_awaiting_value():
    redis_client = Mock()
    redis_client.llen.return_value = 7
    monitor = QueueMonitor(celery_app=Mock(), redis_client=redis_client, queues=["celery"])

    length = asyncio.run(monitor.get_queue_length("celery"))

    assert length == 7
    redis_client.llen.assert_called_once_with("celery:queue:celery")


def test_get_queue_length_returns_zero_when_sync_redis_raises():
    redis_client = Mock()
    redis_client.llen.side_effect = RuntimeError("redis unavailable")
    monitor = QueueMonitor(celery_app=Mock(), redis_client=redis_client, queues=["celery"])

    length = asyncio.run(monitor.get_queue_length("celery"))

    assert length == 0


def test_monitor_queue_lengths_sync_delegates_to_run_async():
    celery_app = Mock()
    monitor_task = Mock(return_value="task-coro")

    with patch(
        "app.tasks.queue_monitor.monitor_queue_lengths_task",
        new=monitor_task,
    ), patch("app.tasks.queue_monitor.run_async") as run_async_mock:
        monitor_queue_lengths_sync(celery_app)

    monitor_task.assert_called_once_with(celery_app)
    run_async_mock.assert_called_once_with("task-coro")


def test_monitor_queue_lengths_sync_logs_and_swallows_run_async_errors():
    celery_app = Mock()
    monitor_task = Mock(return_value="task-coro")

    with patch(
        "app.tasks.queue_monitor.monitor_queue_lengths_task",
        new=monitor_task,
    ), patch(
        "app.tasks.queue_monitor.run_async", side_effect=RuntimeError("loop failure")
    ), patch("app.tasks.queue_monitor.logger.error") as logger_error:
        monitor_queue_lengths_sync(celery_app)

    logger_error.assert_called_once()
