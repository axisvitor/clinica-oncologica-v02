from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi import Request, status
from fastapi.testclient import TestClient

from app.dependencies.auth_dependencies import get_current_user_from_session
from app.main import app
from app.middleware.csrf import get_csrf_token


ADK_ROUTE = "/api/v2/adk/run"


def _csrf_headers() -> dict[str, str]:
    csrf_token = get_csrf_token()
    return {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}",
        "X-Request-ID": "adk-auth-route-test",
    }


def _install_auth_override(user_data: dict[str, Any]) -> None:
    async def _override_session(request: Request) -> dict[str, Any]:
        request.state.user_id = user_data.get("id") or user_data.get("user_id")
        request.state.user_role = user_data.get("role", "doctor")
        return user_data

    app.dependency_overrides[get_current_user_from_session] = _override_session


def _install_denied_side_effect_sentries(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"aideps": 0, "safe_run": 0}

    def fake_aideps(*args, **kwargs):
        calls["aideps"] += 1
        raise AssertionError("AIDeps must not be constructed for denied ADK route calls")

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls["safe_run"] += 1
        raise AssertionError("PIISafeADKWrapper.safe_run must not be called")

    monkeypatch.setattr("app.api.v2.routers.adk.AIDeps", fake_aideps)
    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )
    return calls


def _denial_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if getattr(record, "event_type", None) == "adk_route_denied"
    ]


def test_adk_run_missing_auth_denies_before_wrapper(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_denied_side_effect_sentries(monkeypatch)

    response = client.post(
        ADK_ROUTE,
        headers=_csrf_headers(),
        json={
            "prompt": "secret prompt must not echo",
            "tool_name": "sentiment",
            "session": {"action": "resume", "session_id": "session-a"},
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert calls == {"aideps": 0, "safe_run": 0}
    assert "secret prompt" not in response.text
    assert "AIza" not in response.text
    assert "csrf_token" not in response.text


def test_adk_run_payload_user_mismatch_returns_403_before_wrapper(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _install_auth_override({"id": "user-a", "role": "doctor"})
    calls = _install_denied_side_effect_sentries(monkeypatch)
    caplog.set_level(logging.WARNING, logger="app.api.v2.routers.adk")

    response = client.post(
        ADK_ROUTE,
        headers=_csrf_headers(),
        json={
            "prompt": "payload mismatch prompt must not echo",
            "tool_name": "sentiment",
            "user_id": "user-b",
            "session": {"action": "resume", "session_id": "session-a"},
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    body = response.json()
    assert body["detail"] == "Forbidden"
    assert calls == {"aideps": 0, "safe_run": 0}
    assert "payload mismatch prompt" not in response.text
    assert "user-a" not in response.text
    assert "user-b" not in response.text

    records = _denial_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.reason == "payload_user_mismatch"
    assert record.route == ADK_ROUTE
    assert record.tool_name == "sentiment"
    assert record.lifecycle_action == "authorize"
    assert "payload mismatch prompt" not in caplog.text
    assert "user-a" not in caplog.text
    assert "user-b" not in caplog.text


def test_adk_run_blank_canonical_user_denies_before_wrapper(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _install_auth_override({"id": "   ", "role": "doctor"})
    calls = _install_denied_side_effect_sentries(monkeypatch)
    caplog.set_level(logging.WARNING, logger="app.api.v2.routers.adk")

    response = client.post(
        ADK_ROUTE,
        headers=_csrf_headers(),
        json={
            "prompt": "blank identity prompt must not echo",
            "tool_name": "sentiment",
            "session": {"action": "resume", "session_id": "session-a"},
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    body = response.json()
    assert body["detail"] == "Authentication required"
    assert calls == {"aideps": 0, "safe_run": 0}
    assert "blank identity prompt" not in response.text

    records = _denial_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.reason == "missing_canonical_user"
    assert record.route == ADK_ROUTE
    assert record.tool_name == "sentiment"
    assert record.lifecycle_action == "authenticate"
    assert "blank identity prompt" not in caplog.text


@pytest.mark.parametrize("payload_user_id", [None, "user-a"])
def test_adk_run_absent_or_matching_payload_user_uses_canonical_identity(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    payload_user_id: str | None,
) -> None:
    _install_auth_override({"id": "user-a", "role": "doctor"})
    calls: list[dict[str, Any]] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append({"prompt": prompt, "operation": operation, "context": context})
        return {"status": "success", "result": {"text": "ok"}}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    body: dict[str, Any] = {
        "prompt": "allowed prompt",
        "tool_name": "sentiment",
        "session": {"action": "resume", "session_id": "session-a"},
    }
    if payload_user_id is not None:
        body["user_id"] = payload_user_id

    response = client.post(ADK_ROUTE, headers=_csrf_headers(), json=body)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"
    assert len(calls) == 1
    assert calls[0]["operation"] == "adk_endpoint_run"
    assert calls[0]["context"]["user_id"] == "user-a"


def test_adk_run_user_id_field_falls_back_to_canonical_identity(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_auth_override({"user_id": "user-a", "role": "doctor"})
    calls: list[dict[str, Any]] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append(context)
        return {"status": "success", "result": {"text": "ok"}}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        ADK_ROUTE,
        headers=_csrf_headers(),
        json={
            "prompt": "allowed prompt",
            "tool_name": "sentiment",
            "user_id": "user-a",
            "session": {"action": "resume", "session_id": "session-a"},
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(calls) == 1
    assert calls[0]["user_id"] == "user-a"


def test_adk_run_context_cannot_override_route_owned_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_auth_override({"id": "user-a", "role": "doctor"})
    calls: list[dict[str, Any]] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append(context)
        return {
            "status": "success",
            "session_id": context["session_id"],
            "result": {"text": "ok"},
        }

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        ADK_ROUTE,
        headers=_csrf_headers(),
        json={
            "prompt": "nested override attempt",
            "tool_name": "sentiment",
            "user_id": "user-a",
            "runtime": {"max_llm_calls": 3, "timeout_seconds": 5},
            "session": {
                "action": "resume",
                "session_id": "session-route",
                "state_size_limit_bytes": 4096,
            },
            "invocation": {"action": "run", "invocation_id": "inv-route"},
            "context": {
                "tool_name": "evil-tool",
                "user_id": "user-b",
                "request_source": "evil-source",
                "runtime": {"max_llm_calls": 32, "timeout_seconds": 99},
                "session": {"action": "close", "session_id": "session-evil"},
                "invocation": {"action": "cancel", "invocation_id": "inv-evil"},
                "session_id": "session-evil",
                "invocation_id": "inv-evil",
                "patient_context": {"tumor_type": "mama"},
            },
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(calls) == 1
    context = calls[0]
    assert context["tool_name"] == "sentiment"
    assert context["user_id"] == "user-a"
    assert context["request_source"] == "api_v2_adk"
    assert context["runtime"] == {"max_llm_calls": 3, "timeout_seconds": 5.0}
    assert context["session"] == {
        "action": "resume",
        "session_id": "session-route",
        "state_size_limit_bytes": 4096,
    }
    assert context["invocation"] == {"action": "run", "invocation_id": "inv-route"}
    assert context["session_id"] == "session-route"
    assert context["invocation_id"] == "inv-route"
    assert context["patient_context"] == {"tumor_type": "mama"}
