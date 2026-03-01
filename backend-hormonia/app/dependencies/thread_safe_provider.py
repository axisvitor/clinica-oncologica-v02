"""Shared lazy dependency for thread-safe ServiceProvider resolution."""

from __future__ import annotations

import inspect
from typing import Any, Callable


class ThreadSafeProviderDependency:
    """Callable class for lazy importing to prevent circular dependencies."""

    def __init__(self, provider_loader: Callable[[], Any]):
        self._provider_loader = provider_loader

    async def __call__(self):
        dependency_result = self._provider_loader()

        if inspect.isasyncgen(dependency_result):
            async for provider in dependency_result:
                yield provider
            return

        if inspect.isgenerator(dependency_result):
            try:
                provider = next(dependency_result)
            except StopIteration as stop:
                raise RuntimeError(
                    "get_thread_safe_service_provider did not yield a provider"
                ) from stop

            try:
                yield provider
            finally:
                dependency_result.close()
            return

        if inspect.isawaitable(dependency_result):
            provider = await dependency_result
            yield provider
            return

        yield dependency_result
