"""
Shared Redis scan helper for flow error components.
"""

from __future__ import annotations

from typing import Any


async def scan_keys(redis_client: Any, pattern: str, count: int = 200) -> list[Any]:
    """List keys using SCAN to avoid blocking Redis with KEYS."""
    keys: list[Any] = []
    if hasattr(redis_client, "scan_iter"):
        async for key in redis_client.scan_iter(match=pattern, count=count):
            keys.append(key)
        return keys

    cursor: Any = 0
    while True:
        cursor, batch = await redis_client.scan(cursor=cursor, match=pattern, count=count)
        keys.extend(batch)
        if cursor in (0, "0"):
            break
    return keys
