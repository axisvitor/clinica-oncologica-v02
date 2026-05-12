"""Auth contract tests for WhatsApp management routes."""

from datetime import datetime, timezone

import pytest
from fastapi import Request

from app.dependencies.auth_dependencies import get_current_user_from_session
from app.integrations.whatsapp.api import routes as whatsapp_routes
from app.main import app
from app.middleware.csrf import COOKIE_NAME, get_csrf_token


VALID_SEND_BODY = {
    "instance_name": "primary",
    "to": "5511999999999",
    "message_type": "text",
    "text": "auth ordering check",
}

MANAGEMENT_REQUESTS = [
    ("POST", "/api/v2/whatsapp/messages", {"json": VALID_SEND_BODY}),
    ("GET", "/api/v2/whatsapp/messages?instance=primary", {}),
    ("GET", "/api/v2/whatsapp/messages/stats?instance=primary", {}),
    ("GET", "/api/v2/whatsapp/messages/primary/statistics", {}),
    ("GET", "/api/v2/whatsapp/messages/primary/history/chat-1", {}),
    ("POST", "/api/v2/whatsapp/contacts/primary/sync", {}),
    ("GET", "/api/v2/whatsapp/contacts/primary", {}),
    ("GET", "/api/v2/whatsapp/queue/stats", {}),
    ("POST", "/api/v2/whatsapp/queue/process", {}),
    ("GET", "/api/v2/whatsapp/instances", {}),
]


def _install_csrf_tokens(client) -> None:
    """Attach valid CSRF double-submit tokens without authenticating the request."""

    token = get_csrf_token()
    client.headers["X-CSRF-Token"] = token
    client.cookies.set(COOKIE_NAME, token)


def _install_management_side_effect_sentries(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Fail the test if a management handler side effect starts before auth."""

    calls = {"service": 0, "queue": 0, "db": 0}

    async def _failing_message_service():
        calls["service"] += 1
        raise AssertionError("message service dependency ran before admin auth")

    async def _failing_async_db():
        calls["db"] += 1
        raise AssertionError("database dependency ran before admin auth")
        yield  # pragma: no cover - keeps this override shaped like get_async_db

    class _FailingMessageQueue:
        def __init__(self, *args, **kwargs):
            calls["queue"] += 1
            raise AssertionError("message queue constructed before admin auth")

    app.dependency_overrides[whatsapp_routes.get_message_service] = _failing_message_service
    app.dependency_overrides[whatsapp_routes.get_async_db] = _failing_async_db
    monkeypatch.setattr(whatsapp_routes, "MessageQueue", _FailingMessageQueue)
    return calls


def _assert_no_management_side_effects(calls: dict[str, int]) -> None:
    assert calls == {"service": 0, "queue": 0, "db": 0}


def test_anonymous_management_routes_fail_closed_before_services(client, monkeypatch):
    _install_csrf_tokens(client)
    calls = _install_management_side_effect_sentries(monkeypatch)

    for method, url, kwargs in MANAGEMENT_REQUESTS:
        response = client.request(method, url, **kwargs)
        assert response.status_code in {401, 403}, (method, url, response.status_code, response.text)

    _assert_no_management_side_effects(calls)


def test_non_admin_session_is_rejected_before_management_side_effects(client, monkeypatch):
    _install_csrf_tokens(client)
    calls = _install_management_side_effect_sentries(monkeypatch)

    async def _doctor_session(request: Request):
        request.state.user_id = "doctor-session-user"
        request.state.user_role = "doctor"
        return {
            "id": "doctor-session-user",
            "email": "doctor@example.test",
            "role": "doctor",
            "is_active": True,
            "permissions": ["patients.read"],
        }

    app.dependency_overrides[get_current_user_from_session] = _doctor_session

    response = client.post("/api/v2/whatsapp/messages", json=VALID_SEND_BODY)

    assert response.status_code == 403
    _assert_no_management_side_effects(calls)


def test_public_whatsapp_health_remains_available_without_auth(client):
    response = client.get("/api/v2/whatsapp/health")

    assert response.status_code == 200
    assert response.json()["service"] == "whatsapp-integration"


def test_admin_session_reaches_mocked_send_operation(client):
    _install_csrf_tokens(client)
    sent_requests = []

    async def _admin_session(request: Request):
        request.state.user_id = "admin-session-user"
        request.state.user_role = "admin"
        return {
            "id": "admin-session-user",
            "email": "admin@example.test",
            "role": "admin",
            "is_active": True,
            "permissions": ["admin.read", "admin.write"],
        }

    class _FakeMessageService:
        async def send_message(self, request):
            sent_requests.append(request)
            return {
                "id": "msg-admin-1",
                "external_id": "wuzapi-admin-1",
                "status": "sent",
                "message": "sent by fake service",
                "timestamp": datetime.now(timezone.utc),
                "message_data": {"test": "admin-auth"},
            }

    async def _fake_message_service():
        return _FakeMessageService()

    app.dependency_overrides[get_current_user_from_session] = _admin_session
    app.dependency_overrides[whatsapp_routes.get_message_service] = _fake_message_service

    response = client.post("/api/v2/whatsapp/messages", json=VALID_SEND_BODY)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == "msg-admin-1"
    assert response.json()["status"] == "sent"
    assert len(sent_requests) == 1
    assert sent_requests[0].instance_name == "primary"
