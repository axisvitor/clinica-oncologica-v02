from unittest.mock import AsyncMock, call, patch
from uuid import uuid4

import pytest

from app.api.v2.templates_shared import _invalidate_template_cache


@pytest.mark.asyncio
async def test_invalidate_template_cache_uses_scan_iteration() -> None:
    redis_client = AsyncMock()
    redis_client.scan = AsyncMock(
        side_effect=[
            (1, ["templates:v2:flow:a", "templates:v2:flow:b"]),
            (0, ["templates:v2:flow:c"]),
        ]
    )
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.keys = AsyncMock()

    with patch("app.api.v2.templates_shared.get_async_redis", return_value=redis_client):
        await _invalidate_template_cache("flow")

    redis_client.keys.assert_not_awaited()
    assert redis_client.scan.await_args_list == [
        call(cursor=0, match="templates:v2:flow:*", count=200),
        call(cursor=1, match="templates:v2:flow:*", count=200),
    ]
    assert redis_client.delete.await_args_list == [
        call("templates:v2:flow:a", "templates:v2:flow:b"),
        call("templates:v2:flow:c"),
    ]


@pytest.mark.asyncio
async def test_invalidate_template_cache_deletes_in_batches() -> None:
    keys = [f"templates:v2:flow:{index}" for index in range(205)]

    redis_client = AsyncMock()
    redis_client.scan = AsyncMock(return_value=(0, keys))
    redis_client.delete = AsyncMock(return_value=1)

    with patch("app.api.v2.templates_shared.get_async_redis", return_value=redis_client):
        await _invalidate_template_cache("flow")

    assert redis_client.delete.await_count == 2
    first_batch = redis_client.delete.await_args_list[0].args
    second_batch = redis_client.delete.await_args_list[1].args
    assert len(first_batch) == 200
    assert len(second_batch) == 5


@pytest.mark.asyncio
async def test_invalidate_template_cache_deletes_specific_template_key() -> None:
    template_id = uuid4()
    redis_client = AsyncMock()
    redis_client.scan = AsyncMock(return_value=(0, []))
    redis_client.delete = AsyncMock(return_value=1)

    with patch("app.api.v2.templates_shared.get_async_redis", return_value=redis_client):
        await _invalidate_template_cache("quiz", template_id)

    redis_client.delete.assert_awaited_once_with(f"templates:v2:quiz:{template_id}")
