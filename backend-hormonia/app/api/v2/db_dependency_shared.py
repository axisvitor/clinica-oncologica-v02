"""
Shared DB dependency adapters for routers that support sync/async generators.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable


async def iter_db_dependency(provider: Callable[[], Any]):
    """Yield database session objects from sync/async dependency providers."""
    db_value = provider()
    if inspect.isasyncgen(db_value):
        async for db in db_value:
            yield db
    elif inspect.isgenerator(db_value):
        for db in db_value:
            yield db
    else:
        yield db_value
