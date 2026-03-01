"""Synchronous test client backed by httpx.AsyncClient + ASGITransport.

This avoids TestClient/BlockingPortal issues in constrained environments while
preserving a synchronous API (`get`, `post`, `request`, etc.) for test suites.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import httpx
from fastapi.encoders import jsonable_encoder


class AsyncTestClient:
    """Sync-friendly client wrapper for ASGI apps."""

    def __init__(
        self,
        app: Any,
        base_url: str = "http://testserver",
        timeout: float = 30.0,
        raise_app_exceptions: bool = True,
    ) -> None:
        self._app = app
        self._base_url = base_url
        self._timeout = timeout
        self._raise_app_exceptions = raise_app_exceptions
        self.headers: dict[str, str] = {}
        self.cookies = httpx.Cookies()

    @property
    def app(self) -> Any:
        """Compatibility shim for tests expecting Starlette TestClient.app."""
        return self._app

    def _run_coroutine(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result: dict[str, Any] = {}
        error: dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result["value"] = asyncio.run(coro)
            except BaseException as exc:  # pragma: no cover - defensive
                error["value"] = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if "value" in error:
            raise error["value"]
        return result.get("value")

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async def _do_request() -> httpx.Response:
            transport = httpx.ASGITransport(
                app=self._app,
                raise_app_exceptions=self._raise_app_exceptions,
            )

            request_headers = dict(self.headers)
            extra_headers = kwargs.pop("headers", None)
            if extra_headers:
                request_headers.update(dict(extra_headers))

            request_cookies = kwargs.pop("cookies", None)
            cookies = httpx.Cookies()
            cookies.update(self.cookies)
            if request_cookies:
                cookies.update(request_cookies)

            async with httpx.AsyncClient(
                transport=transport,
                base_url=self._base_url,
                follow_redirects=True,
                timeout=self._timeout,
            ) as client:
                if "json" in kwargs:
                    kwargs["json"] = jsonable_encoder(kwargs["json"])
                try:
                    response = await asyncio.wait_for(
                        client.request(
                            method,
                            url,
                            headers=request_headers,
                            cookies=cookies,
                            **kwargs,
                        ),
                        timeout=self._timeout,
                    )
                except asyncio.TimeoutError:
                    # Helpful diagnostics for deadlocks/timeouts in test runs.
                    for task in asyncio.all_tasks():
                        if task.done():
                            continue
                        print(f"[AsyncTestClient] pending task: {task!r}")
                        for frame in task.get_stack():
                            print(f"[AsyncTestClient]   {frame.f_code.co_filename}:{frame.f_lineno}")
                    raise
                self.cookies.update(response.cookies)
                return response

        return self._run_coroutine(_do_request())

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("OPTIONS", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("HEAD", url, **kwargs)

    def close(self) -> None:
        # Stateless wrapper; no persistent async resources.
        return None

    def __enter__(self) -> "AsyncTestClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
