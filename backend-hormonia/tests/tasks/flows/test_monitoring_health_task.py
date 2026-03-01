"""Focused tests for flow monitoring task Redis key scanning behavior."""

from contextlib import contextmanager
from unittest.mock import Mock, patch


def _scoped_session(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


def _query_with_results(rows):
    query = Mock()
    query.join.return_value = query
    query.filter.return_value = query
    query.limit.return_value = query
    query.all.return_value = rows
    return query


def test_monitor_flow_task_health_uses_scan_iter_for_failed_tasks():
    from app.tasks.flows.monitoring import monitor_flow_task_health

    db = Mock()
    db.execute.return_value = None
    db.query.side_effect = [
        _query_with_results([1, 2]),
        _query_with_results([1]),
    ]

    redis_client = Mock()
    redis_client.ping.return_value = True
    redis_client.scan_iter.return_value = iter(
        ["task_result:1", "task_result:2", "task_result:3"]
    )
    redis_client.get.side_effect = [
        '{"status":"failure"}',
        '{"status":"success"}',
        "task failure payload",
    ]

    redis_manager = Mock()
    redis_manager.get_sync_client.return_value = redis_client

    gemini_client = Mock()
    gemini_client.health_check.return_value = object()

    with patch(
        "app.tasks.flows.monitoring.get_scoped_session", return_value=_scoped_session(db)
    ), patch(
        "app.core.redis_manager.get_redis_manager", return_value=redis_manager
    ), patch(
        "app.tasks.flows.monitoring.get_gemini_client", return_value=gemini_client
    ), patch(
        "app.tasks.flows.monitoring.run_async_in_sync", return_value=True
    ):
        result = monitor_flow_task_health.run()

    assert result["failed_tasks_count"] == 2
    assert result["active_flows_count"] == 2
    assert result["pending_messages_count"] == 1
    assert result["overall_healthy"] is True

    redis_client.scan_iter.assert_called_once_with(match="task_result:*", count=100)
    redis_client.keys.assert_not_called()
