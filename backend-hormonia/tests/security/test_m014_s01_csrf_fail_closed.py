"""M014/S01 CSRF fail-closed contract tests.

These tests prove browser/session-backed mutating ingress is denied by the
middleware before route dependencies or endpoint bodies can create side effects.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.middleware import csrf as csrf_module
from app.middleware.csrf import COOKIE_NAME, CSRFMiddleware, is_csrf_exempt

TEST_SECRET_KEY = "m014-s01-csrf-secret-key-minimum-32-characters!"


def _signed_token(*, age_seconds: int = 0) -> str:
    timestamp = str(int(time.time()) - age_seconds)
    random_data = secrets.token_hex(32)
    payload = f"{timestamp}.{random_data}"
    signature = hmac.new(
        TEST_SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


@pytest.fixture(autouse=True)
def csrf_secret(monkeypatch):
    monkeypatch.setattr(csrf_module, "_get_secret_key", lambda: TEST_SECRET_KEY)


@pytest.fixture
def sentinel_app():
    app = FastAPI()
    calls = {"dependency": 0, "endpoint": 0, "webhook": 0}

    async def dependency_sentinel():
        calls["dependency"] += 1
        return True

    @app.post("/api/v2/messages")
    @app.post("/api/v2/enhanced-messages")
    @app.post("/api/v2/flows")
    @app.post("/api/v2/auth/password/reset-request")
    @app.post("/api/v2/auth/password/reset-confirm")
    async def protected_mutation(_ok=Depends(dependency_sentinel)):
        calls["endpoint"] += 1
        return {"ok": True}

    @app.post("/api/v2/webhooks/provider")
    async def provider_webhook():
        calls["webhook"] += 1
        return {"accepted": True}

    app.add_middleware(CSRFMiddleware)
    return app, calls


def _reset_calls(calls: dict[str, int]) -> None:
    for key in calls:
        calls[key] = 0


def test_missing_and_invalid_csrf_denies_before_route_side_effects(sentinel_app):
    app, calls = sentinel_app
    client = TestClient(app)
    valid_token = _signed_token()
    different_valid_token = _signed_token()
    expired_token = _signed_token(age_seconds=3700)

    cases = [
        (
            "missing_header",
            {},
            {COOKIE_NAME: valid_token},
            "csrf_token_missing",
        ),
        (
            "invalid_header",
            {"X-CSRF-Token": "not-a-valid-csrf-token"},
            {COOKIE_NAME: valid_token},
            "csrf_token_invalid",
        ),
        (
            "missing_cookie",
            {"X-CSRF-Token": valid_token},
            {},
            "csrf_cookie_missing",
        ),
        (
            "invalid_cookie",
            {"X-CSRF-Token": valid_token},
            {COOKIE_NAME: "not-a-valid-csrf-token"},
            "csrf_cookie_invalid",
        ),
        (
            "mismatch",
            {"X-CSRF-Token": valid_token},
            {COOKIE_NAME: different_valid_token},
            "csrf_mismatch",
        ),
        (
            "expired",
            {"X-CSRF-Token": expired_token},
            {COOKIE_NAME: expired_token},
            "csrf_token_invalid",
        ),
    ]

    for name, headers, cookies, expected_error in cases:
        _reset_calls(calls)
        response = client.post(
            "/api/v2/messages",
            headers=headers,
            cookies=cookies,
            json={"case": name, "payload": "must-not-reach-endpoint"},
        )

        assert response.status_code == 403, response.text
        assert response.json()["error"] == expected_error
        assert calls["dependency"] == 0
        assert calls["endpoint"] == 0


@pytest.mark.parametrize(
    "path",
    [
        "/api/v2/auth/password/reset-request",
        "/api/v2/auth/password/reset-confirm",
        "/api/v2/enhanced-messages",
        "/api/v2/flows",
    ],
)
def test_contracted_session_paths_are_not_exempt_before_dependencies(sentinel_app, path):
    app, calls = sentinel_app
    client = TestClient(app)

    response = client.post(path, json={"payload": "must-not-reach-endpoint"})

    assert response.status_code == 403, response.text
    assert response.json()["error"] == "csrf_token_missing"
    assert calls["dependency"] == 0
    assert calls["endpoint"] == 0


def test_authorization_header_does_not_bypass_cookie_session_csrf(sentinel_app):
    app, calls = sentinel_app
    client = TestClient(app)

    response = client.post(
        "/api/v2/messages",
        headers={"Authorization": "Bearer legacy-session-token"},
        json={"payload": "must-not-reach-endpoint"},
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"] == "csrf_token_missing"
    assert calls["dependency"] == 0
    assert calls["endpoint"] == 0


def test_valid_double_submit_fixture_reaches_route(sentinel_app):
    app, calls = sentinel_app
    client = TestClient(app)
    token = _signed_token()

    response = client.post(
        "/api/v2/messages",
        headers={"X-CSRF-Token": token},
        cookies={COOKIE_NAME: token},
        json={"payload": "allowed"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}
    assert calls["dependency"] == 1
    assert calls["endpoint"] == 1


def test_provider_webhook_ingress_stays_csrf_exempt(sentinel_app):
    app, calls = sentinel_app
    client = TestClient(app)

    response = client.post(
        "/api/v2/webhooks/provider",
        json={"event": "hmac-covered-by-webhook-contract"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"accepted": True}
    assert calls["webhook"] == 1


def test_exemption_contract_is_narrowed_to_non_session_ingress():
    for protected_path in [
        "/api/v2/messages",
        "/api/v2/enhanced-messages",
        "/api/v2/flows",
        "/api/v2/auth/logout",
        "/api/v2/auth/password/reset-request",
        "/api/v2/auth/password/reset-confirm",
    ]:
        assert is_csrf_exempt(protected_path, "POST") is False

    assert is_csrf_exempt("/api/v2/webhooks/whatsapp", "POST") is True
    assert is_csrf_exempt("/api/v2/quiz-extensions/monthly/public/quiz-id/submit", "POST") is True
    assert is_csrf_exempt("/api/v2/messages-malicious", "POST") is False


def test_csrf_denial_log_is_structured_and_phi_safe(sentinel_app, caplog):
    app, calls = sentinel_app
    client = TestClient(app)
    valid_token = _signed_token()
    invalid_token = "not-a-valid-reset-token"
    authorization_value = "Bearer legacy-session-token"

    with caplog.at_level("WARNING", logger="app.middleware.csrf"):
        response = client.post(
            "/api/v2/messages",
            headers={
                "Authorization": authorization_value,
                "X-CSRF-Token": invalid_token,
                "X-Request-ID": "req-123",
            },
            cookies={COOKIE_NAME: valid_token},
            json={
                "email": "patient@example.com",
                "token": "reset-token-secret",
                "payload": "must-not-be-logged",
            },
        )

    assert response.status_code == 403, response.text
    assert response.json()["error"] == "csrf_token_invalid"
    assert calls["dependency"] == 0
    assert calls["endpoint"] == 0

    records = [
        record
        for record in caplog.records
        if getattr(record, "event_type", None) == "csrf_denied"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.reason == "invalid_header"
    assert record.method == "POST"
    assert record.path == "/api/v2/messages"
    assert record.request_id == "req-123"
    assert isinstance(record.client_identity_hash, str)
    assert len(record.client_identity_hash) == 16

    log_text = caplog.text
    assert invalid_token not in log_text
    assert valid_token not in log_text
    assert authorization_value not in log_text
    assert "patient@example.com" not in log_text
    assert "reset-token-secret" not in log_text
    assert COOKIE_NAME not in log_text
