from unittest.mock import patch

import pytest

from app.celery_app import run_async_in_celery


def test_run_async_in_celery_runs_in_sync_context():
    async def _sample():
        return "ok"

    coro = _sample()
    with patch(
        "app.core.async_context_manager.safe_run_coroutine",
        return_value="ok",
    ) as safe_run:
        result = run_async_in_celery(coro, timeout=12)
        coro.close()

    assert result == "ok"
    safe_run.assert_called_once()


@pytest.mark.asyncio
async def test_run_async_in_celery_rejects_running_loop():
    async def _sample():
        return "ok"

    coro = _sample()
    try:
        with pytest.raises(RuntimeError, match="Cannot call run_async_in_celery"):
            run_async_in_celery(coro)
    finally:
        coro.close()
