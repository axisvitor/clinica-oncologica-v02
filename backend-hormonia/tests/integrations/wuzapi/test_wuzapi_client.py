import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.wuzapi.client import (
    RateLimiter,
    WuzAPIClient,
    normalize_session_status,
)
from app.integrations.wuzapi.errors import WuzAPIError


def make_mock_response(status: int, json_data: dict):
    """Create a mock aiohttp response context manager."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    resp.text = AsyncMock(return_value=json.dumps(json_data))
    resp.headers = {"Content-Type": "application/json"}
    return resp


class MockRequestContext:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        if self._exc:
            raise self._exc
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False


def make_client() -> WuzAPIClient:
    client = WuzAPIClient(base_url="http://wuzapi.test", token="token-123")
    client._circuit_breaker._fallback_to_memory = True
    client._circuit_breaker.reset()
    return client


@pytest.mark.asyncio
async def test_send_text_returns_message_id():
    client = make_client()
    response = make_mock_response(
        200,
        {
            "code": 200,
            "data": {"Id": "ABC123", "Details": "Sent"},
            "success": True,
        },
    )
    session = MagicMock()
    session.request = MagicMock(return_value=MockRequestContext(response=response))
    client.session = session

    result = await client.send_text("5511987654321", "Hello")

    assert result["data"]["Id"] == "ABC123"
    session.request.assert_called_once_with(
        "POST",
        "http://wuzapi.test/chat/send/text",
        json={"Phone": "5511987654321", "Body": "Hello"},
        params=None,
    )


@pytest.mark.asyncio
async def test_send_text_uses_correct_auth_header():
    client = make_client()

    with patch("app.integrations.wuzapi.client.ClientSession") as session_cls:
        await client.connect()

    headers = session_cls.call_args.kwargs["headers"]
    assert headers["Token"] == "token-123"
    assert "Authorization" not in headers


@pytest.mark.asyncio
async def test_send_text_phone_format():
    client = make_client()
    response = make_mock_response(
        200,
        {
            "code": 200,
            "data": {"Id": "ABC123", "Details": "Sent"},
            "success": True,
        },
    )
    session = MagicMock()
    session.request = MagicMock(return_value=MockRequestContext(response=response))
    client.session = session

    await client.send_text("5511987654321", "Hello")

    request_body = session.request.call_args.kwargs["json"]
    assert request_body["Phone"] == "5511987654321"
    assert "@s.whatsapp.net" not in request_body["Phone"]


@pytest.mark.asyncio
async def test_retry_on_503():
    client = make_client()
    first = make_mock_response(503, {"success": False, "code": 503})
    second = make_mock_response(
        200,
        {
            "code": 200,
            "data": {"Id": "ABC123", "Details": "Sent"},
            "success": True,
        },
    )
    session = MagicMock()
    session.request = MagicMock(
        side_effect=[
            MockRequestContext(response=first),
            MockRequestContext(response=second),
        ]
    )
    client.session = session

    with patch("backoff._async.asyncio.sleep", new=AsyncMock()):
        result = await client.send_text("5511987654321", "Hello")

    assert result["data"]["Id"] == "ABC123"
    assert session.request.call_count == 2


@pytest.mark.asyncio
async def test_retry_on_429():
    client = make_client()
    first = make_mock_response(429, {"success": False, "code": 429})
    second = make_mock_response(
        200,
        {
            "code": 200,
            "data": {"Id": "ABC123", "Details": "Sent"},
            "success": True,
        },
    )
    session = MagicMock()
    session.request = MagicMock(
        side_effect=[
            MockRequestContext(response=first),
            MockRequestContext(response=second),
        ]
    )
    client.session = session

    with patch("backoff._async.asyncio.sleep", new=AsyncMock()):
        result = await client.send_text("5511987654321", "Hello")

    assert result["data"]["Id"] == "ABC123"
    assert session.request.call_count == 2


@pytest.mark.asyncio
async def test_no_retry_on_400():
    client = make_client()
    response = make_mock_response(400, {"success": False, "code": 400})
    session = MagicMock()
    session.request = MagicMock(return_value=MockRequestContext(response=response))
    client.session = session

    with pytest.raises(WuzAPIError):
        await client.send_text("5511987654321", "Hello")

    assert session.request.call_count == 1


@pytest.mark.asyncio
async def test_no_retry_on_401():
    client = make_client()
    response = make_mock_response(401, {"success": False, "code": 401})
    session = MagicMock()
    session.request = MagicMock(return_value=MockRequestContext(response=response))
    client.session = session

    with pytest.raises(WuzAPIError):
        await client.send_text("5511987654321", "Hello")

    assert session.request.call_count == 1


@pytest.mark.asyncio
async def test_max_retries_exhausted():
    client = make_client()
    response = make_mock_response(503, {"success": False, "code": 503})
    session = MagicMock()
    session.request = MagicMock(
        side_effect=[
            MockRequestContext(response=response),
            MockRequestContext(response=response),
            MockRequestContext(response=response),
        ]
    )
    client.session = session

    with patch("backoff._async.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(WuzAPIError):
            await client.send_text("5511987654321", "Hello")

    assert session.request.call_count == 3


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_full():
    limiter = RateLimiter(max_requests=2, window_seconds=60)

    assert await limiter.acquire() is True
    assert await limiter.acquire() is True
    assert await limiter.acquire() is False


@pytest.mark.asyncio
async def test_client_connect_creates_session():
    client = make_client()

    with patch("app.integrations.wuzapi.client.ClientSession") as session_cls:
        await client.connect()

    kwargs = session_cls.call_args.kwargs
    assert kwargs["headers"]["Token"] == "token-123"
    assert "Authorization" not in kwargs["headers"]
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert client.session is not None


@pytest.mark.asyncio
async def test_client_disconnect_closes_session():
    client = make_client()
    session = AsyncMock()
    client.session = session

    await client.disconnect()

    session.close.assert_awaited_once()
    assert client.session is None


@pytest.mark.asyncio
async def test_non_success_response_raises():
    client = make_client()
    response = make_mock_response(200, {"code": 200, "data": {}, "success": False})
    session = MagicMock()
    session.request = MagicMock(return_value=MockRequestContext(response=response))
    client.session = session

    with pytest.raises(WuzAPIError):
        await client.send_text("5511987654321", "Hello")


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"data": {"Connected": True, "LoggedIn": True}}, {"connected": True, "logged_in": True}),
        ({"data": {"connected": True, "loggedIn": True}}, {"connected": True, "logged_in": True}),
        ({"data": {"connected": "true", "logged_in": "1"}}, {"connected": True, "logged_in": True}),
        ({"data": {"connected": False, "loggedIn": True}}, {"connected": False, "logged_in": True}),
    ],
)
def test_normalize_session_status_accepts_live_and_legacy_casing(payload, expected):
    assert normalize_session_status(payload) == expected
