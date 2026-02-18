"""Unit tests for LangGraph runtime helpers."""

from __future__ import annotations

from app.ai.langgraph import runtime


class _DummyRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self.set_calls: list[tuple[str, int, str]] = []
        self.get_calls: list[str] = []

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.storage[key] = value
        self.set_calls.append((key, ttl, value))

    def get(self, key: str) -> str | None:
        self.get_calls.append(key)
        return self.storage.get(key)


def test_validate_thread_id_rejects_none() -> None:
    try:
        runtime.validate_thread_id(None)
        raise AssertionError("Expected ValueError for missing thread_id")
    except ValueError as exc:
        assert "thread_id missing" in str(exc)


def test_validate_thread_id_normalizes_whitespace() -> None:
    normalized = runtime.validate_thread_id("  patient 123 \nrun\t01  ")
    assert normalized == "patient-123-run-01"


def test_validate_thread_id_hashes_long_values() -> None:
    normalized = runtime.validate_thread_id("x" * 180)
    assert len(normalized) <= 65
    assert ":" in normalized


def test_require_configurable_thread_id_requires_configurable_mapping() -> None:
    try:
        runtime.require_configurable_thread_id({})
        raise AssertionError("Expected ValueError for missing config.configurable")
    except ValueError as exc:
        assert "thread_id missing" in str(exc)


def test_supported_checkpointer_duck_typed_compatibility() -> None:
    class DuckCheckpointer:
        def get(self, config: dict) -> dict | None:
            return None

        def put(self, config: dict, checkpoint: dict) -> dict:
            return config

    expected = runtime.BaseCheckpointSaver is None
    assert runtime._is_supported_checkpointer(DuckCheckpointer()) is expected


def test_redis_checkpointer_skips_get_when_thread_id_missing() -> None:
    redis = _DummyRedis()
    checkpointer = runtime.RedisCheckpointer(redis)

    assert checkpointer.get({}) is None
    assert redis.get_calls == []


def test_redis_checkpointer_skips_put_when_thread_id_missing() -> None:
    redis = _DummyRedis()
    checkpointer = runtime.RedisCheckpointer(redis)
    config = {}

    returned = checkpointer.put(config, {"k": "v"})

    assert returned is config
    assert redis.set_calls == []


def test_redis_checkpointer_roundtrip_with_valid_thread_id() -> None:
    redis = _DummyRedis()
    checkpointer = runtime.RedisCheckpointer(redis)
    config = runtime.build_graph_config(thread_id="patient 42")
    checkpoint = {"id": "ckpt-1", "answer": 42}

    returned = checkpointer.put(config, checkpoint)
    loaded = checkpointer.get(config)

    assert returned["configurable"]["checkpoint_id"] == "ckpt-1"
    assert loaded == checkpoint
    assert redis.set_calls
    key_used, ttl, _ = redis.set_calls[0]
    assert "patient-42" in key_used
    assert ttl == 3600
