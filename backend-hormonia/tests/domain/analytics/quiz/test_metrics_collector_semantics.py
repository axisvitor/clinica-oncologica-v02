from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.analytics.quiz.metrics_collector import QuizMetricsCollector


@pytest.mark.asyncio
async def test_record_response_latency_tracks_response_count_key():
    collector = QuizMetricsCollector()
    redis = AsyncMock()
    collector._get_redis = AsyncMock(return_value=redis)

    template_id = uuid4()
    question_id = "q1"
    session_id = uuid4()

    await collector.record_response_latency(
        template_id=template_id,
        question_id=question_id,
        session_id=session_id,
        latency_seconds=1.25,
    )

    response_count_key = (
        f"{collector.METRICS_KEY_PREFIX}:{collector.RESPONSE_COUNT_KEY}:{template_id}:{question_id}"
    )
    redis.incr.assert_any_await(response_count_key)


@pytest.mark.asyncio
async def test_get_clarification_rate_returns_ratio_when_response_count_exists():
    collector = QuizMetricsCollector()
    redis = AsyncMock()
    collector._get_redis = AsyncMock(return_value=redis)

    template_id = uuid4()
    question_id = "q2"
    clarification_key = (
        f"{collector.METRICS_KEY_PREFIX}:{collector.CLARIFICATION_KEY}:{template_id}:{question_id}"
    )
    response_count_key = (
        f"{collector.METRICS_KEY_PREFIX}:{collector.RESPONSE_COUNT_KEY}:{template_id}:{question_id}"
    )

    async def _get_side_effect(key):
        if key == clarification_key:
            return "2"
        if key == response_count_key:
            return "10"
        return None

    redis.get.side_effect = _get_side_effect

    rate = await collector.get_clarification_rate(template_id, question_id)

    assert rate == 0.2


@pytest.mark.asyncio
async def test_get_clarification_rate_keeps_legacy_count_fallback_without_denominator():
    collector = QuizMetricsCollector()
    redis = AsyncMock()
    collector._get_redis = AsyncMock(return_value=redis)

    template_id = uuid4()
    question_id = "q3"
    clarification_key = (
        f"{collector.METRICS_KEY_PREFIX}:{collector.CLARIFICATION_KEY}:{template_id}:{question_id}"
    )
    response_count_key = (
        f"{collector.METRICS_KEY_PREFIX}:{collector.RESPONSE_COUNT_KEY}:{template_id}:{question_id}"
    )

    async def _get_side_effect(key):
        if key == clarification_key:
            return "3"
        if key == response_count_key:
            return None
        return None

    redis.get.side_effect = _get_side_effect

    rate_or_count = await collector.get_clarification_rate(template_id, question_id)

    assert rate_or_count == 3.0


@pytest.mark.asyncio
async def test_get_clarification_count_returns_integer_count():
    collector = QuizMetricsCollector()
    redis = AsyncMock()
    collector._get_redis = AsyncMock(return_value=redis)

    template_id = uuid4()
    question_id = "q4"
    clarification_key = (
        f"{collector.METRICS_KEY_PREFIX}:{collector.CLARIFICATION_KEY}:{template_id}:{question_id}"
    )

    async def _get_side_effect(key):
        if key == clarification_key:
            return "7"
        return None

    redis.get.side_effect = _get_side_effect

    count = await collector.get_clarification_count(template_id, question_id)

    assert count == 7
