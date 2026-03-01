"""Regression tests for thread-local event loop lifecycle helpers."""

import time

import pytest

from app.utils import async_helpers


async def _async_value(value):
    return value


@pytest.fixture(autouse=True)
def _cleanup_cached_loops():
    async_helpers.cleanup_all_event_loops()
    yield
    async_helpers.cleanup_all_event_loops()


def test_run_async_reuses_cached_loop_and_manual_cleanup():
    loop_a = async_helpers.get_or_create_event_loop()

    result = async_helpers.run_async(_async_value("ok"))
    assert result == "ok"

    loop_b = async_helpers.get_or_create_event_loop()
    assert loop_b is loop_a

    was_closed = async_helpers.cleanup_event_loop()
    assert was_closed is True
    assert loop_a.is_closed()

    loop_c = async_helpers.get_or_create_event_loop()
    assert loop_c is not loop_a


def test_stale_loop_cleanup_rotates_idle_thread_local_loop():
    loop_a = async_helpers.get_or_create_event_loop()

    async_helpers._thread_local_loop.last_used = time.monotonic() - 10
    cleaned = async_helpers.cleanup_stale_event_loop(max_idle_seconds=0)

    assert cleaned is True
    assert loop_a.is_closed()

    loop_b = async_helpers.get_or_create_event_loop()
    assert loop_b is not loop_a


def test_cleanup_all_event_loops_closes_registered_loop():
    loop = async_helpers.get_or_create_event_loop()

    closed_count = async_helpers.cleanup_all_event_loops()

    assert closed_count >= 1
    assert loop.is_closed()
