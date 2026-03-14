"""Cutover proof for cookie-only canonical websocket session authentication."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.api import websockets as websocket_api
from app.config import settings

pytestmark = [pytest.mark.api, pytest.mark.auth]


class FakeConnectionManager:
    def __init__(self):
        self.sent_messages: list[tuple[str, dict]] = []
        self.disconnected: list[str] = []

    async def connect(self, _websocket: WebSocket, connection_id: str) -> str:
        return connection_id

    async def send_message(self, connection_id: str, message: dict) -> bool:
        self.sent_messages.append((connection_id, message))
        return True

    async def disconnect(self, connection_id: str) -> None:
        self.disconnected.append(connection_id)

    async def authenticate_connection(self, *_args, **_kwargs):  # pragma: no cover - defensive
        return None

    def get_connection_info(self, _connection_id: str):  # pragma: no cover - defensive
        return None


def _patch_session_cache(
    monkeypatch: pytest.MonkeyPatch,
    session_payload: dict | None,
    *,
    lookup_side_effect: Exception | None = None,
):
    get_session = AsyncMock(return_value=session_payload)
    if lookup_side_effect is not None:
        get_session = AsyncMock(side_effect=lookup_side_effect)

    fake_cache = SimpleNamespace(
        get_session=get_session,
        get_user_by_uid=AsyncMock(
            side_effect=AssertionError(
                "Canonical websocket session auth should not need firebase_uid cache lookups"
            )
        ),
    )

    import app.core.redis_manager as redis_manager_module

    monkeypatch.setattr(
        redis_manager_module,
        "get_redis_manager",
        lambda: SimpleNamespace(get_compatible_client=lambda _mode: object()),
    )
    monkeypatch.setattr(redis_manager_module, "FirebaseRedisCache", lambda _client: fake_cache)
    return fake_cache


def _build_websocket(*, headers: dict | None = None, cookies: dict | None = None) -> AsyncMock:
    websocket = AsyncMock(spec=WebSocket)
    websocket.headers = headers or {}
    websocket.cookies = cookies or {}
    websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect(code=1000))
    return websocket


@pytest.mark.asyncio
async def test_websocket_session_cookie_auth_accepts_user_id_centric_sessions(monkeypatch):
    manager = FakeConnectionManager()
    monkeypatch.setattr(websocket_api, "get_connection_manager", lambda: manager)

    session_payload = {
        "user_id": str(uuid4()),
        "email": "doctor.websocket@example.com",
        "role": "doctor",
        "is_active": True,
    }
    fake_cache = _patch_session_cache(monkeypatch, session_payload)

    websocket = _build_websocket(
        cookies={settings.SESSION_COOKIE_NAME: "cookie-session-123"}
    )

    await websocket_api.websocket_endpoint(
        websocket,
        token=None,
        session_id=None,
    )

    authenticated_messages = [
        message
        for _connection_id, message in manager.sent_messages
        if message.get("type") == "authenticated"
    ]

    assert authenticated_messages, "Expected an authenticated websocket message for canonical cookie auth"
    auth_message = authenticated_messages[0]
    assert auth_message["data"]["success"] is True
    assert auth_message["data"]["user_id"] == session_payload["user_id"]
    fake_cache.get_session.assert_awaited_once_with("cookie-session-123")
    fake_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "session_id", "expected_source"),
    [
        ({}, "legacy-query-session", "query"),
        ({"X-Session-ID": "legacy-header-session"}, None, "x-session-id"),
        ({"Authorization": "Bearer legacy-bearer-session"}, None, "authorization"),
    ],
)
async def test_websocket_rejects_legacy_session_transport_without_cookie(
    monkeypatch,
    headers: dict,
    session_id: str | None,
    expected_source: str,
):
    manager = FakeConnectionManager()
    monkeypatch.setattr(websocket_api, "get_connection_manager", lambda: manager)
    fake_cache = _patch_session_cache(monkeypatch, None)

    websocket = _build_websocket(headers=headers)

    await websocket_api.websocket_endpoint(
        websocket,
        token=None,
        session_id=session_id,
    )

    error_messages = [
        message for _connection_id, message in manager.sent_messages if message.get("type") == "error"
    ]

    assert error_messages, "Expected an explicit websocket auth error for rejected legacy transport"
    error_message = error_messages[0]
<<<<<<< HEAD
    assert error_message["data"]["error"] == "AUTH_WEBSOCKET_SESSION_INVALID"
    assert error_message["data"]["message"] == "WebSocket session requires a session cookie."
    assert error_message["data"]["details"]["connection_id"]
    assert error_message["data"]["details"]["session_source"] == expected_source
    fake_cache.get_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_invalid_cookie_session_emits_stable_error_diagnostics(monkeypatch):
    manager = FakeConnectionManager()
    monkeypatch.setattr(websocket_api, "get_connection_manager", lambda: manager)
    fake_cache = _patch_session_cache(monkeypatch, None)

    websocket = _build_websocket(
        cookies={settings.SESSION_COOKIE_NAME: "missing-cookie-session"}
    )

    await websocket_api.websocket_endpoint(
        websocket,
        token=None,
        session_id=None,
    )

    error_messages = [
        message for _connection_id, message in manager.sent_messages if message.get("type") == "error"
    ]

    assert error_messages, "Expected an explicit websocket auth error for invalid cookie sessions"
    error_message = error_messages[0]
    assert error_message["data"]["error"] == "AUTH_WEBSOCKET_SESSION_INVALID"
    assert error_message["data"]["details"]["connection_id"]
    assert error_message["data"]["details"]["session_source"] == "cookie"
    fake_cache.get_session.assert_awaited_once_with("missing-cookie-session")


@pytest.mark.asyncio
async def test_websocket_cookie_session_lookup_failure_emits_stable_error_diagnostics(monkeypatch):
    manager = FakeConnectionManager()
    monkeypatch.setattr(websocket_api, "get_connection_manager", lambda: manager)
    fake_cache = _patch_session_cache(
        monkeypatch,
        None,
        lookup_side_effect=RuntimeError("redis unavailable"),
    )

    websocket = _build_websocket(
        cookies={settings.SESSION_COOKIE_NAME: "lookup-failed-cookie-session"}
    )
=======
    assert error_message['data']['error'] == 'AUTH_WEBSOCKET_SESSION_INVALID'
    assert error_message['data']['details']['connection_id']


@pytest.mark.asyncio
async def test_websocket_session_lookup_failure_emits_stable_error_diagnostics(monkeypatch):
    manager = FakeConnectionManager()
    monkeypatch.setattr(websocket_api, 'get_connection_manager', lambda: manager)
    _patch_session_cache(
        monkeypatch,
        None,
        lookup_side_effect=RuntimeError('redis unavailable'),
    )

    websocket = AsyncMock(spec=WebSocket)
    websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect(code=1000))
>>>>>>> gsd/M003/S02

    await websocket_api.websocket_endpoint(
        websocket,
        token=None,
<<<<<<< HEAD
        session_id=None,
    )

    error_messages = [
        message for _connection_id, message in manager.sent_messages if message.get("type") == "error"
    ]

    assert error_messages, "Expected an explicit websocket auth error for cookie lookup failures"
    error_message = error_messages[0]
    assert error_message["data"]["error"] == "AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED"
    assert error_message["data"]["details"]["connection_id"]
    assert error_message["data"]["details"]["session_source"] == "cookie"
    fake_cache.get_session.assert_awaited_once_with("lookup-failed-cookie-session")
=======
        session_id='lookup-failed-session-id',
    )

    error_messages = [message for _connection_id, message in manager.sent_messages if message.get('type') == 'error']

    assert error_messages, 'Expected an explicit websocket auth error for lookup failures'
    error_message = error_messages[0]
    assert error_message['data']['error'] == 'AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED'
    assert error_message['data']['details']['connection_id']
>>>>>>> gsd/M003/S02
