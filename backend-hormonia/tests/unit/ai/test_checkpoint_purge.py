"""Unit tests for LangGraph checkpoint purge script."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scripts.purge_langgraph_checkpoints import purge_langgraph_checkpoints


@patch("scripts.purge_langgraph_checkpoints.get_sync_redis_client")
@patch("scripts.purge_langgraph_checkpoints._ensure_db0_client")
def test_purge_langgraph_checkpoints_deletes_keys_in_batches(
    mock_ensure_db0_client: MagicMock,
    mock_get_sync_redis_client: MagicMock,
) -> None:
    redis_client = MagicMock()
    redis_client.scan_iter.return_value = [
        "langgraph:checkpoint:1",
        "langgraph:checkpoint:2",
        "langgraph:checkpoint:3",
    ]
    redis_client.delete.return_value = 3
    mock_get_sync_redis_client.return_value = redis_client
    mock_ensure_db0_client.return_value = redis_client

    deleted = purge_langgraph_checkpoints()

    assert deleted == 3
    redis_client.scan_iter.assert_called_once_with(
        match="langgraph:checkpoint:*",
        count=100,
    )
    redis_client.delete.assert_called_once_with(
        "langgraph:checkpoint:1",
        "langgraph:checkpoint:2",
        "langgraph:checkpoint:3",
    )


@patch("scripts.purge_langgraph_checkpoints.get_sync_redis_client")
@patch("scripts.purge_langgraph_checkpoints._ensure_db0_client")
def test_purge_langgraph_checkpoints_handles_empty_scan(
    mock_ensure_db0_client: MagicMock,
    mock_get_sync_redis_client: MagicMock,
) -> None:
    redis_client = MagicMock()
    redis_client.scan_iter.return_value = []
    mock_get_sync_redis_client.return_value = redis_client
    mock_ensure_db0_client.return_value = redis_client

    deleted = purge_langgraph_checkpoints()

    assert deleted == 0
    redis_client.scan_iter.assert_called_once_with(
        match="langgraph:checkpoint:*",
        count=100,
    )
    redis_client.delete.assert_not_called()
