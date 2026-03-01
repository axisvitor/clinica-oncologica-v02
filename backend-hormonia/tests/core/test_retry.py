import pytest

from app.core.retry import CircuitBreakerRetry, RetryStrategies, RetryStrategy


@pytest.mark.asyncio
async def test_retry_strategies_presets_return_fresh_instances() -> None:
    first = RetryStrategies.STANDARD
    second = RetryStrategies.STANDARD

    assert isinstance(first, RetryStrategy)
    assert isinstance(second, RetryStrategy)
    assert first is not second


@pytest.mark.asyncio
async def test_retry_strategy_stats_are_not_shared_between_presets() -> None:
    strategy_used = RetryStrategies.STANDARD
    untouched_strategy = RetryStrategies.STANDARD

    state = {"calls": 0}

    async def flaky() -> str:
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("first attempt fails")
        return "ok"

    result = await strategy_used.execute(flaky, exceptions=(RuntimeError,))

    assert result == "ok"
    assert strategy_used.stats["total_attempts"] == 2
    assert untouched_strategy.stats["total_attempts"] == 0


class _DummyCircuitBreaker:
    async def call(self, func, *args, fallback=None, **kwargs):
        _ = fallback
        return await func(*args, **kwargs)


def test_circuit_breaker_retry_default_strategy_is_not_shared() -> None:
    cb = _DummyCircuitBreaker()

    first = CircuitBreakerRetry(cb)
    second = CircuitBreakerRetry(cb)

    assert isinstance(first.retry_strategy, RetryStrategy)
    assert isinstance(second.retry_strategy, RetryStrategy)
    assert first.retry_strategy is not second.retry_strategy
