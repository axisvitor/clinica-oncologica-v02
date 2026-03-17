"""Focused tests for flow monitoring task Redis key scanning behavior."""

import pytest
from unittest.mock import AsyncMock, Mock, patch


@pytest.mark.asyncio
async def test_monitor_flow_task_health_uses_scan_iter_for_failed_tasks():
    from app.tasks.flows_taskiq import monitor_flow_task_health

    # Mock async db session — monitor_flow_task_health uses await db.execute()
    db = AsyncMock()

    # db.execute returns: SELECT 1, active flows query, pending messages query
    select_1_result = Mock()
    active_result = Mock()
    active_result.all.return_value = [1, 2]
    pending_result = Mock()
    pending_result.all.return_value = [1]
    db.execute.side_effect = [select_1_result, active_result, pending_result]

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
    gemini_client.health_check = AsyncMock(return_value=True)

    with patch(
        "app.core.redis_manager.get_redis_manager", return_value=redis_manager
    ), patch(
        "app.ai.client.get_gemini_client", return_value=gemini_client
    ), patch(
        "app.config.settings.tasks.HEALTH_CHECK_TIMEOUT", 5
    ), patch(
        "app.config.settings.tasks.HEALTH_ACTIVE_FLOWS_LIMIT", 100
    ):
        result = await monitor_flow_task_health.fn(db=db)

    assert result["failed_tasks_count"] == 2
    assert result["active_flows_count"] == 2
    assert result["pending_messages_count"] == 1
    assert result["overall_healthy"] is True

    redis_client.scan_iter.assert_called_once_with(match="task_result:*", count=100)
    redis_client.keys.assert_not_called()
