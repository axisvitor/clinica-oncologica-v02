"""
Integration tests for Redis-backed circuit breaker scenarios.
"""

import asyncio

import pytest

from app.core.redis_circuit_breaker import RedisCircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_circuit_transitions_closed_to_open():
    breaker = RedisCircuitBreaker(
        name="test_cb",
        failure_threshold=5,
        recovery_timeout=1,
        success_threshold=3,
    )
    breaker._fallback_to_memory = True

    async def fail():
        raise Exception("failure")

    for _ in range(5):
        with pytest.raises(Exception):
            await breaker.call(fail)

    state = await breaker.get_state_async()
    assert state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_transitions_open_to_half_open():
    breaker = RedisCircuitBreaker(
        name="test_cb_half_open",
        failure_threshold=2,
        recovery_timeout=1,
        success_threshold=3,
    )
    breaker._fallback_to_memory = True

    async def fail():
        raise Exception("failure")

    async def success():
        return "ok"

    for _ in range(2):
        with pytest.raises(Exception):
            await breaker.call(fail)

    await asyncio.sleep(1.1)

    await breaker.call(success)
    state = await breaker.get_state_async()
    assert state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_circuit_transitions_half_open_to_closed():
    breaker = RedisCircuitBreaker(
        name="test_cb_close",
        failure_threshold=2,
        recovery_timeout=1,
        success_threshold=3,
    )
    breaker._fallback_to_memory = True

    async def fail():
        raise Exception("failure")

    async def success():
        return "ok"

    for _ in range(2):
        with pytest.raises(Exception):
            await breaker.call(fail)

    await asyncio.sleep(1.1)

    for _ in range(3):
        await breaker.call(success)

    state = await breaker.get_state_async()
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_half_open_failure_reopens():
    breaker = RedisCircuitBreaker(
        name="test_cb_reopen",
        failure_threshold=2,
        recovery_timeout=1,
        success_threshold=3,
    )
    breaker._fallback_to_memory = True

    async def fail():
        raise Exception("failure")

    for _ in range(2):
        with pytest.raises(Exception):
            await breaker.call(fail)

    await asyncio.sleep(1.1)

    with pytest.raises(Exception):
        await breaker.call(fail)

    state = await breaker.get_state_async()
    assert state == CircuitState.OPEN
