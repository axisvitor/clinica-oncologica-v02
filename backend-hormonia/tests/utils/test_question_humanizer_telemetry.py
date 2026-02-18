from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.services.question_humanizer import QuestionHumanizer


class _FakeRedis:
    def __init__(self) -> None:
        self.rpush_calls: list[tuple[str, str]] = []
        self.expire_calls: list[tuple[str, int]] = []

    async def rpush(self, key: str, value: str) -> None:
        self.rpush_calls.append((key, value))

    async def expire(self, key: str, ttl: int) -> None:
        self.expire_calls.append((key, ttl))


@pytest.mark.asyncio
async def test_log_telemetry_serializes_uuid_patient_id() -> None:
    humanizer = QuestionHumanizer.__new__(QuestionHumanizer)
    redis = _FakeRedis()

    async def _fake_get_redis_client() -> _FakeRedis:
        return redis

    humanizer._get_redis_client = _fake_get_redis_client  # type: ignore[method-assign]
    patient_id = uuid4()

    await QuestionHumanizer._log_telemetry(
        humanizer,
        patient_id,
        "Pergunta original",
        "Pergunta reescrita",
        "success",
    )

    assert redis.rpush_calls
    key, payload = redis.rpush_calls[0]
    assert key.startswith("telemetry:humanization:")
    data = json.loads(payload)
    assert data["patient_id"] == str(patient_id)

    assert redis.expire_calls
    assert redis.expire_calls[0][0] == key
    assert redis.expire_calls[0][1] == 2592000
