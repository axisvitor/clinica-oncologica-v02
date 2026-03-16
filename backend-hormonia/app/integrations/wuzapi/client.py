from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import aiohttp
import backoff
from aiohttp import ClientError, ClientSession, ClientTimeout

from app.core.redis_circuit_breaker import RedisCircuitBreaker
from app.integrations.wuzapi.errors import WuzAPIConnectionError, WuzAPIError
from app.integrations.wuzapi.models import MEDIA_ENDPOINT_MAP, MEDIA_FIELD_MAP, WuzAPITextRequest


async def _safe_read_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
    try:
        return await response.json()
    except Exception:
        return {"raw": await response.text()}


class RateLimiter:
    """Sliding-window rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = datetime.now(tz=timezone.utc)
            cutoff = now - timedelta(seconds=self.window_seconds)
            self.requests = [request_time for request_time in self.requests if request_time > cutoff]

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False

    async def wait_for_availability(self) -> None:
        while not await self.acquire():
            await asyncio.sleep(1)


def _giveup(exc: Exception) -> bool:
    if isinstance(exc, WuzAPIError) and exc.status is not None:
        return 400 <= exc.status < 500 and exc.status != 429
    return False


class WuzAPIClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        max_requests: int = 100,
        window_seconds: int = 60,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.rate_limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
        self._circuit_breaker = RedisCircuitBreaker(
            name="wuzapi",
            failure_threshold=5,
            recovery_timeout=60,
            success_threshold=3,
        )
        self.session: ClientSession | None = None
        self.headers = {
            "Content-Type": "application/json",
            "Token": token,
        }

    async def __aenter__(self) -> "WuzAPIClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        _ = exc_type, exc_value, traceback
        await self.disconnect()

    async def connect(self) -> None:
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )
            self.session = ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers=self.headers,
            )

    async def disconnect(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    @backoff.on_exception(
        backoff.expo,
        (ClientError, asyncio.TimeoutError, WuzAPIError),
        max_tries=3,
        factor=2,
        max_value=60,
        giveup=_giveup,
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.rate_limiter.wait_for_availability()

        return await self._circuit_breaker.call(
            self._do_request,
            method,
            endpoint,
            data,
            params,
        )

    async def _do_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        if not self.session:
            await self.connect()

        assert self.session is not None
        url = urljoin(f"{self.base_url}/", endpoint.lstrip("/"))

        try:
            async with self.session.request(method, url, json=data, params=params) as response:
                response_data = await _safe_read_json(response)

                if response.status == 429 or response.status >= 500:
                    raise WuzAPIError(
                        "WuzAPI returned retryable error",
                        status=response.status,
                        response=response_data,
                    )

                if 400 <= response.status < 500:
                    raise WuzAPIError(
                        "WuzAPI returned client error",
                        status=response.status,
                        response=response_data,
                    )

                if not response_data.get("success", False):
                    raise WuzAPIError(
                        "WuzAPI response reported non-success",
                        status=response.status,
                        response=response_data,
                    )

                return response_data
        except asyncio.TimeoutError as exc:
            raise WuzAPIConnectionError("WuzAPI request timed out") from exc
        except ClientError as exc:
            raise WuzAPIConnectionError("WuzAPI request failed due to connection error") from exc

    async def send_text(self, phone: str, message: str) -> dict[str, Any]:
        payload = WuzAPITextRequest(Phone=phone, Body=message).model_dump()
        return await self._make_request("POST", "/chat/send/text", data=payload)

    async def send_media(
        self,
        media_type: str,
        phone: str,
        data_uri: str,
        caption: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Send image/audio/video/document as base64 data URI."""
        if media_type not in MEDIA_FIELD_MAP:
            raise ValueError(
                f"Unsupported media type: {media_type}. Must be one of: {list(MEDIA_FIELD_MAP)}"
            )

        field = MEDIA_FIELD_MAP[media_type]
        endpoint = MEDIA_ENDPOINT_MAP[media_type]

        body: dict[str, Any] = {"Phone": phone, field: data_uri}

        if caption and media_type in ("image", "video"):
            body["Caption"] = caption

        if filename and media_type == "document":
            body["FileName"] = filename

        return await self._make_request("POST", endpoint, data=body)

    async def session_connect(
        self,
        subscribe: list[str] | None = None,
        immediate: bool = False,
    ) -> dict[str, Any]:
        """POST /session/connect -- connect to WhatsApp servers.

        Args:
            subscribe: Event types to receive (e.g. ["Message"]).
            immediate: If True, connect immediately without waiting.

        Returns:
            WuzAPI response with connection details and JID.
        """
        payload: dict[str, Any] = {"Immediate": immediate}
        if subscribe:
            payload["Subscribe"] = subscribe
        return await self._make_request("POST", "/session/connect", data=payload)

    async def get_session_status(self) -> dict[str, Any]:
        """GET /session/status -- returns Connected and LoggedIn booleans."""
        return await self._make_request("GET", "/session/status")

    async def get_qr(self) -> dict[str, Any]:
        """GET /session/qr -- returns base64 QR code data URI for pairing."""
        return await self._make_request("GET", "/session/qr")
