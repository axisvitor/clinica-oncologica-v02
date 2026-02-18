"""LangGraph runtime guardrails for Redis checkpointer health validation."""

from __future__ import annotations

import pytest

from app.ai.langgraph import runtime


class _DeadRedisClient:
    def ping(self) -> None:
        raise TimeoutError("redis unreachable")


def _clear_checkpointers() -> None:
    with runtime._CHECKPOINTERS_LOCK:
        runtime._CHECKPOINTERS.clear()


def test_get_graph_checkpointer_falls_back_when_redis_ping_fails(monkeypatch) -> None:
    if runtime.MemorySaver is None:
        pytest.skip("MemorySaver unavailable in current LangGraph runtime")

    _clear_checkpointers()

    import app.core.redis_manager as redis_manager

    monkeypatch.setattr(
        redis_manager,
        "get_sync_redis_client",
        lambda: _DeadRedisClient(),
    )

    checkpointer = runtime.get_graph_checkpointer("unit:redis-timeout")

    assert checkpointer is not None
    assert not isinstance(checkpointer, runtime.RedisCheckpointer)


def test_get_graph_checkpointer_discards_stale_cached_redis_checkpointer(
    monkeypatch,
) -> None:
    if runtime.MemorySaver is None:
        pytest.skip("MemorySaver unavailable in current LangGraph runtime")

    stale = runtime.RedisCheckpointer(_DeadRedisClient(), ttl=60, prefix="unit:test:")

    with runtime._CHECKPOINTERS_LOCK:
        runtime._CHECKPOINTERS["unit:stale"] = stale

    import app.core.redis_manager as redis_manager

    monkeypatch.setattr(redis_manager, "get_sync_redis_client", lambda: None)

    refreshed = runtime.get_graph_checkpointer("unit:stale")

    assert refreshed is not None
    assert refreshed is not stale
    assert not isinstance(refreshed, runtime.RedisCheckpointer)
