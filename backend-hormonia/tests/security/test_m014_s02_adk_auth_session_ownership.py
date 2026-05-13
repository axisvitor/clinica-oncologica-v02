from __future__ import annotations

import logging
import json
from typing import Any

import pytest
from fastapi import Request, status
from fastapi.testclient import TestClient

from app.ai.adk import session_store as session_store_module
from app.ai.adk.runtime import (
    ADKInvocationControls,
    ADKSessionControls,
    ADKToolRunRequest,
    run_adk_tool,
)
from app.ai.adk.session_store import ADKSessionStore
from app.ai.agents.deps import AIDeps
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


def _runtime_denial_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if getattr(record, "event_type", None) == "adk_runtime_denied"
    ]


_LOG_EXTRA_KEYS = (
    "event_type",
    "reason",
    "route",
    "method",
    "tool_name",
    "lifecycle_action",
    "request_id",
    "correlation_id",
)


def _diagnostic_records_text(records: list[logging.LogRecord]) -> str:
    payload = []
    for record in records:
        payload.append(
            {
                "message": record.getMessage(),
                **{
                    key: getattr(record, key)
                    for key in _LOG_EXTRA_KEYS
                    if hasattr(record, key)
                },
            }
        )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _assert_diagnostics_exclude(
    records: list[logging.LogRecord],
    unsafe_values: list[str],
) -> str:
    diagnostics = _diagnostic_records_text(records)
    for unsafe_value in unsafe_values:
        assert unsafe_value not in diagnostics
    return diagnostics


@pytest.fixture
def adk_runtime_store(monkeypatch: pytest.MonkeyPatch) -> ADKSessionStore:
    session_store_module._MEMORY_SESSIONS.clear()
    session_store_module._MEMORY_INVOCATIONS.clear()
    store = ADKSessionStore(redis_client=None)
    monkeypatch.setattr("app.ai.adk.runtime.ADKSessionStore", lambda: store)
    yield store
    session_store_module._MEMORY_SESSIONS.clear()
    session_store_module._MEMORY_INVOCATIONS.clear()


def _install_runtime_tool_registry(
    monkeypatch: pytest.MonkeyPatch,
    *,
    calls: dict[str, int],
) -> None:
    from app.ai.adk import runtime

    async def direct_handler(*, prompt, deps, context=None):
        calls["handler"] += 1
        return {"status": "success", "result": {"text": "ok", "context": context}}

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(
        runtime,
        "get_tool_registry",
        lambda: {"sentiment": direct_handler, "humanize": direct_handler},
    )


def _block_runtime_execute_request(
    monkeypatch: pytest.MonkeyPatch,
    *,
    calls: dict[str, int],
) -> None:
    from app.ai.adk import runtime

    async def fail_execute_request(*args, **kwargs):
        calls["execute_request"] += 1
        raise AssertionError("Denied ADK lifecycle calls must not execute requests")

    monkeypatch.setattr(runtime, "_execute_request", fail_execute_request)


async def _poison_session_owner(
    store: ADKSessionStore,
    session_id: str,
    owner: Any,
) -> None:
    session = await store.get_session(session_id)
    assert session is not None
    if owner is None:
        session.pop("user_id", None)
    else:
        session["user_id"] = owner
    await store._write_session(session, ttl_seconds=store.session_ttl_seconds)


async def _poison_invocation_owner(
    store: ADKSessionStore,
    invocation_id: str,
    owner: Any,
) -> None:
    invocation = await store.get_invocation(invocation_id)
    assert invocation is not None
    if owner is None:
        invocation.pop("user_id", None)
    else:
        invocation["user_id"] = owner
    await store._write_invocation(invocation)


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
    route_owner = "user-a"
    payload_owner = "user-b"
    route_prompt = "payload mismatch prompt Paciente Maria must not echo"
    route_payload_text = "payload text Paciente Maria Silva câncer de mama"
    route_cookie = "session_token=raw-route-cookie-secret"
    route_gemini_key = "AIzaSyRouteSecretShouldNotLog"
    raw_request_id = "Route request Paciente Maria 123"
    raw_correlation_id = "Route correlation Paciente Maria 456"
    _install_auth_override({"id": route_owner, "role": "doctor"})
    calls = _install_denied_side_effect_sentries(monkeypatch)
    caplog.set_level(logging.WARNING, logger="app.api.v2.routers.adk")
    headers = _csrf_headers()
    headers["Cookie"] = f"{headers['Cookie']}; {route_cookie}"
    headers["X-Request-ID"] = raw_request_id
    headers["X-Correlation-ID"] = raw_correlation_id

    response = client.post(
        ADK_ROUTE,
        headers=headers,
        json={
            "prompt": route_prompt,
            "tool_name": "sentiment",
            "user_id": payload_owner,
            "session": {"action": "resume", "session_id": "session-a"},
            "context": {
                "payload_note": route_payload_text,
                "cookie": route_cookie,
                "gemini_api_key": route_gemini_key,
                "patient_context": {
                    "patient_name": "Paciente Maria Silva",
                    "diagnosis": "carcinoma de mama",
                },
            },
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    body = response.json()
    assert body["detail"] == "Forbidden"
    assert calls == {"aideps": 0, "safe_run": 0}
    for unsafe_value in [
        route_prompt,
        route_payload_text,
        route_cookie,
        route_gemini_key,
        route_owner,
        payload_owner,
        "Paciente Maria Silva",
        "carcinoma de mama",
        "csrf_token",
    ]:
        assert unsafe_value not in response.text

    records = _denial_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.reason == "payload_user_mismatch"
    assert record.route == ADK_ROUTE
    assert record.tool_name == "sentiment"
    assert record.lifecycle_action == "authorize"
    assert record.request_id.startswith("hashed-")
    assert record.correlation_id.startswith("hashed-")
    diagnostics = _assert_diagnostics_exclude(
        records,
        [
            route_prompt,
            route_payload_text,
            route_cookie,
            route_gemini_key,
            route_owner,
            payload_owner,
            raw_request_id,
            raw_correlation_id,
            "Paciente Maria Silva",
            "carcinoma de mama",
            "csrf_token",
        ],
    )
    assert "payload_user_mismatch" in diagnostics


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


@pytest.mark.asyncio
async def test_runtime_same_user_resume_reaches_mocked_handler(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    calls = {"handler": 0, "execute_request": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    session = await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id="runtime-owner",
        session_id="runtime-session-same-owner",
    )
    session["state"] = {"patient_context": {"cycle": "Q1"}}
    await adk_runtime_store._write_session(
        session,
        ttl_seconds=adk_runtime_store.session_ttl_seconds,
    )

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="allowed runtime prompt",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="runtime-owner",
            session=ADKSessionControls(
                action="resume",
                session_id="runtime-session-same-owner",
            ),
        )
    )

    assert result["status"] == "success"
    assert calls["handler"] == 1
    assert result["result"]["context"]["patient_context"] == {"cycle": "Q1"}


@pytest.mark.asyncio
async def test_runtime_foreign_run_invocation_id_denies_before_session_or_invocation_mutation(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    calls = {"handler": 0, "execute_request": 0, "create_session": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    _block_runtime_execute_request(monkeypatch, calls=calls)
    await adk_runtime_store.register_invocation(
        invocation_id="runtime-invocation-foreign-run",
        session_id="runtime-session-existing-run-owner",
        tool_name="sentiment",
        user_id="stored-run-owner-secret",
        runtime={"timeout_seconds": 5, "max_llm_calls": 4},
    )

    async def fail_create_session(*args, **kwargs):
        calls["create_session"] += 1
        raise AssertionError("Foreign duplicate invocation ids must deny before session creation")

    monkeypatch.setattr(adk_runtime_store, "create_session", fail_create_session)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="foreign run invocation prompt Paciente Rosa must not echo",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="caller-run-owner-secret",
            invocation=ADKInvocationControls(
                action="run",
                invocation_id="runtime-invocation-foreign-run",
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "invocation_owner_mismatch"
    assert calls == {"handler": 0, "execute_request": 0, "create_session": 0}
    invocation = await adk_runtime_store.get_invocation("runtime-invocation-foreign-run")
    assert invocation is not None
    assert invocation["user_id"] == "stored-run-owner-secret"
    assert invocation["session_id"] == "runtime-session-existing-run-owner"
    assert invocation["status"] == "pending"
    serialized = json.dumps(result, ensure_ascii=False)
    for unsafe_value in [
        "runtime-invocation-foreign-run",
        "stored-run-owner-secret",
        "caller-run-owner-secret",
        "foreign run invocation prompt",
        "Paciente Rosa",
    ]:
        assert unsafe_value not in serialized


@pytest.mark.asyncio
async def test_runtime_same_owner_duplicate_run_invocation_id_rejects_without_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    calls = {"handler": 0, "execute_request": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    _block_runtime_execute_request(monkeypatch, calls=calls)
    await adk_runtime_store.register_invocation(
        invocation_id="runtime-invocation-duplicate-run",
        session_id="runtime-session-original-duplicate",
        tool_name="sentiment",
        user_id="same-run-owner-secret",
        runtime={"timeout_seconds": 5, "max_llm_calls": 4},
    )

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="duplicate invocation prompt must not execute",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="same-run-owner-secret",
            invocation=ADKInvocationControls(
                action="run",
                invocation_id="runtime-invocation-duplicate-run",
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"] == {
        "message": "Invocation already exists",
        "type": "invocation_exists",
    }
    assert calls == {"handler": 0, "execute_request": 0}
    invocation = await adk_runtime_store.get_invocation("runtime-invocation-duplicate-run")
    assert invocation is not None
    assert invocation["user_id"] == "same-run-owner-secret"
    assert invocation["session_id"] == "runtime-session-original-duplicate"
    assert invocation["status"] == "pending"


@pytest.mark.asyncio
async def test_runtime_foreign_create_existing_session_denies_without_existence_leak(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    calls = {"handler": 0, "execute_request": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    _block_runtime_execute_request(monkeypatch, calls=calls)
    await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id="stored-create-owner-secret",
        session_id="runtime-session-foreign-create",
    )

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="create existing session prompt Paciente Bia must not echo",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="caller-create-owner-secret",
            session=ADKSessionControls(
                action="create",
                session_id="runtime-session-foreign-create",
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "session_owner_mismatch"
    assert calls == {"handler": 0, "execute_request": 0}
    serialized = json.dumps(result, ensure_ascii=False)
    for unsafe_value in [
        "runtime-session-foreign-create",
        "stored-create-owner-secret",
        "caller-create-owner-secret",
        "create existing session prompt",
        "Paciente Bia",
    ]:
        assert unsafe_value not in serialized


@pytest.mark.asyncio
async def test_runtime_foreign_resume_denies_before_execute_request_and_logs_safely(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = {"handler": 0, "execute_request": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    _block_runtime_execute_request(monkeypatch, calls=calls)
    stored_owner = "stored-owner-secret"
    caller_owner = "caller-owner-secret"
    runtime_session_id = "runtime-session-token-foreign-resume"
    runtime_prompt = "foreign resume PHI prompt Paciente Julia must not echo"
    runtime_session_state = "session state Paciente Julia ciclo 3 terapia"
    runtime_cookie = "session_token=runtime-cookie-secret"
    runtime_gemini_key = "AIzaSyRuntimeSecretShouldNotLog"
    raw_request_id = "Runtime request Paciente Julia 123"
    raw_correlation_id = "Runtime correlation Paciente Julia 456"
    session = await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id=stored_owner,
        session_id=runtime_session_id,
    )
    session["state"] = {
        "patient_context": {
            "patient_name": "Paciente Julia Souza",
            "summary": runtime_session_state,
        }
    }
    await adk_runtime_store._write_session(
        session,
        ttl_seconds=adk_runtime_store.session_ttl_seconds,
    )
    caplog.set_level(logging.WARNING, logger="app.ai.adk.runtime")

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt=runtime_prompt,
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key=runtime_gemini_key),
            user_id=caller_owner,
            context={
                "request_id": raw_request_id,
                "correlation_id": raw_correlation_id,
                "cookie": runtime_cookie,
                "payload_note": runtime_session_state,
            },
            session=ADKSessionControls(
                action="resume",
                session_id=runtime_session_id,
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "session_owner_mismatch"
    assert calls == {"handler": 0, "execute_request": 0}
    serialized = json.dumps(result, ensure_ascii=False)
    for unsafe_value in [
        stored_owner,
        caller_owner,
        runtime_session_id,
        runtime_prompt,
        runtime_session_state,
        runtime_cookie,
        runtime_gemini_key,
        "Paciente Julia Souza",
    ]:
        assert unsafe_value not in serialized

    records = _runtime_denial_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.reason == "session_owner_mismatch"
    assert record.tool_name == "sentiment"
    assert record.lifecycle_action == "resume"
    assert record.request_id.startswith("hashed-")
    assert record.correlation_id.startswith("hashed-")
    diagnostics = _assert_diagnostics_exclude(
        records,
        [
            stored_owner,
            caller_owner,
            runtime_session_id,
            runtime_prompt,
            runtime_session_state,
            runtime_cookie,
            runtime_gemini_key,
            raw_request_id,
            raw_correlation_id,
            "Paciente Julia Souza",
        ],
    )
    assert "session_owner_mismatch" in diagnostics


@pytest.mark.asyncio
async def test_runtime_foreign_close_denies_before_close_mutation(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    calls = {"handler": 0, "execute_request": 0, "close_session": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id="stored-close-owner",
        session_id="runtime-session-foreign-close",
    )

    async def fail_close_session(session_id: str):
        calls["close_session"] += 1
        raise AssertionError("Foreign close must not mutate the session")

    monkeypatch.setattr(adk_runtime_store, "close_session", fail_close_session)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="close attempt must not echo",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="caller-close-owner",
            session=ADKSessionControls(
                action="close",
                session_id="runtime-session-foreign-close",
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "session_owner_mismatch"
    assert calls["close_session"] == 0
    stored = await adk_runtime_store.get_session("runtime-session-foreign-close")
    assert stored is not None
    assert stored["status"] == "open"
    serialized = json.dumps(result, ensure_ascii=False)
    assert "stored-close-owner" not in serialized
    assert "caller-close-owner" not in serialized


@pytest.mark.asyncio
async def test_runtime_foreign_invocation_cancel_denies_before_cancel_mutation_and_task_cancel(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    calls = {"handler": 0, "execute_request": 0, "cancel_invocation": 0, "cancel_task": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    await adk_runtime_store.register_invocation(
        invocation_id="runtime-invocation-foreign-cancel",
        session_id="runtime-session-cancel",
        tool_name="sentiment",
        user_id="stored-invocation-owner",
        runtime={"timeout_seconds": 5, "max_llm_calls": 4},
    )

    async def fail_cancel_invocation(invocation_id: str):
        calls["cancel_invocation"] += 1
        raise AssertionError("Foreign cancel must not mutate the invocation")

    def fail_cancel_task(invocation_id: str) -> None:
        calls["cancel_task"] += 1
        raise AssertionError("Foreign cancel must not cancel in-flight work")

    monkeypatch.setattr(adk_runtime_store, "cancel_invocation", fail_cancel_invocation)
    monkeypatch.setattr(runtime, "_cancel_in_flight_task", fail_cancel_task)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="cancel attempt must not echo",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="caller-invocation-owner",
            invocation=ADKInvocationControls(
                action="cancel",
                invocation_id="runtime-invocation-foreign-cancel",
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "invocation_owner_mismatch"
    assert calls["cancel_invocation"] == 0
    assert calls["cancel_task"] == 0
    invocation = await adk_runtime_store.get_invocation("runtime-invocation-foreign-cancel")
    assert invocation is not None
    assert invocation["status"] == "pending"
    serialized = json.dumps(result, ensure_ascii=False)
    assert "stored-invocation-owner" not in serialized
    assert "caller-invocation-owner" not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["resume", "close"])
async def test_runtime_missing_owner_session_denies_fail_closed_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
    action: str,
) -> None:
    calls = {"handler": 0, "execute_request": 0, "close_session": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    _block_runtime_execute_request(monkeypatch, calls=calls)
    await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id="temporary-owner",
        session_id=f"runtime-session-missing-owner-{action}",
    )
    await _poison_session_owner(
        adk_runtime_store,
        f"runtime-session-missing-owner-{action}",
        "   ",
    )

    async def fail_close_session(session_id: str):
        calls["close_session"] += 1
        raise AssertionError("Missing-owner close must not mutate the session")

    monkeypatch.setattr(adk_runtime_store, "close_session", fail_close_session)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="missing owner prompt must not echo",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="caller-for-missing-owner",
            session=ADKSessionControls(
                action=action,
                session_id=f"runtime-session-missing-owner-{action}",
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "session_owner_missing"
    assert calls["handler"] == 0
    assert calls["execute_request"] == 0
    assert calls["close_session"] == 0
    serialized = json.dumps(result, ensure_ascii=False)
    assert "caller-for-missing-owner" not in serialized
    assert "missing owner prompt" not in serialized


@pytest.mark.asyncio
async def test_runtime_expired_same_owner_session_denies_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = {"handler": 0, "execute_request": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    _block_runtime_execute_request(monkeypatch, calls=calls)
    runtime_session_id = "runtime-session-token-expired-same-owner"
    runtime_owner = "expired-owner-secret"
    runtime_prompt = "expired prompt Paciente Lia must not execute"
    runtime_state = "expired session state Paciente Lia terapia alvo"
    runtime_gemini_key = "AIzaSyExpiredRuntimeSecretShouldNotLog"
    raw_request_id = "Expired request Paciente Lia 123"
    raw_correlation_id = "Expired correlation Paciente Lia 456"
    session = await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id=runtime_owner,
        session_id=runtime_session_id,
    )
    session["expires_at"] = "2000-01-01T00:00:00-03:00"
    session["state"] = {"patient_context": {"summary": runtime_state}}
    await adk_runtime_store._write_session(
        session,
        ttl_seconds=adk_runtime_store.session_ttl_seconds,
    )
    caplog.set_level(logging.WARNING, logger="app.ai.adk.runtime")

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt=runtime_prompt,
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key=runtime_gemini_key),
            user_id=runtime_owner,
            context={
                "request_id": raw_request_id,
                "correlation_id": raw_correlation_id,
            },
            session=ADKSessionControls(
                action="resume",
                session_id=runtime_session_id,
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "session_expired"
    assert calls == {"handler": 0, "execute_request": 0}
    serialized = json.dumps(result, ensure_ascii=False)
    for unsafe_value in [
        runtime_session_id,
        runtime_owner,
        runtime_prompt,
        runtime_state,
        runtime_gemini_key,
    ]:
        assert unsafe_value not in serialized

    records = _runtime_denial_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.reason == "session_expired"
    assert record.tool_name == "sentiment"
    assert record.lifecycle_action == "resume"
    assert record.request_id.startswith("hashed-")
    assert record.correlation_id.startswith("hashed-")
    diagnostics = _assert_diagnostics_exclude(
        records,
        [
            runtime_session_id,
            runtime_owner,
            runtime_prompt,
            runtime_state,
            runtime_gemini_key,
            raw_request_id,
            raw_correlation_id,
        ],
    )
    assert "session_expired" in diagnostics


@pytest.mark.asyncio
async def test_runtime_missing_owner_invocation_cancel_denies_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    calls = {"handler": 0, "execute_request": 0, "cancel_invocation": 0, "cancel_task": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    await adk_runtime_store.register_invocation(
        invocation_id="runtime-invocation-missing-owner",
        session_id="runtime-session-missing-invocation-owner",
        tool_name="sentiment",
        user_id="temporary-invocation-owner",
        runtime={"timeout_seconds": 5, "max_llm_calls": 4},
    )
    await _poison_invocation_owner(
        adk_runtime_store,
        "runtime-invocation-missing-owner",
        None,
    )

    async def fail_cancel_invocation(invocation_id: str):
        calls["cancel_invocation"] += 1
        raise AssertionError("Missing-owner cancel must not mutate the invocation")

    def fail_cancel_task(invocation_id: str) -> None:
        calls["cancel_task"] += 1
        raise AssertionError("Missing-owner cancel must not cancel in-flight work")

    monkeypatch.setattr(adk_runtime_store, "cancel_invocation", fail_cancel_invocation)
    monkeypatch.setattr(runtime, "_cancel_in_flight_task", fail_cancel_task)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="missing invocation owner prompt must not echo",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="caller-for-missing-invocation-owner",
            invocation=ADKInvocationControls(
                action="cancel",
                invocation_id="runtime-invocation-missing-owner",
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "invocation_owner_missing"
    assert calls["cancel_invocation"] == 0
    assert calls["cancel_task"] == 0
    invocation = await adk_runtime_store.get_invocation("runtime-invocation-missing-owner")
    assert invocation is not None
    assert invocation["status"] == "pending"
    serialized = json.dumps(result, ensure_ascii=False)
    assert "caller-for-missing-invocation-owner" not in serialized
    assert "missing invocation owner prompt" not in serialized


@pytest.mark.asyncio
async def test_runtime_invocation_tool_mismatch_requires_same_owner_without_owner_leakage(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    calls = {"handler": 0, "execute_request": 0, "cancel_invocation": 0, "cancel_task": 0}
    _install_runtime_tool_registry(monkeypatch, calls=calls)
    await adk_runtime_store.register_invocation(
        invocation_id="runtime-invocation-tool-mismatch",
        session_id="runtime-session-tool-mismatch",
        tool_name="humanize",
        user_id="same-tool-owner-secret",
        runtime={"timeout_seconds": 5, "max_llm_calls": 4},
    )

    async def fail_cancel_invocation(invocation_id: str):
        calls["cancel_invocation"] += 1
        raise AssertionError("Tool mismatch cancel must not mutate the invocation")

    def fail_cancel_task(invocation_id: str) -> None:
        calls["cancel_task"] += 1
        raise AssertionError("Tool mismatch cancel must not cancel in-flight work")

    monkeypatch.setattr(adk_runtime_store, "cancel_invocation", fail_cancel_invocation)
    monkeypatch.setattr(runtime, "_cancel_in_flight_task", fail_cancel_task)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="tool mismatch prompt must not echo",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="same-tool-owner-secret",
            invocation=ADKInvocationControls(
                action="cancel",
                invocation_id="runtime-invocation-tool-mismatch",
            ),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "invocation_tool_mismatch"
    assert result["result"]["requested_tool"] == "sentiment"
    assert result["result"]["stored_tool"] == "humanize"
    assert calls["cancel_invocation"] == 0
    assert calls["cancel_task"] == 0
    serialized = json.dumps(result, ensure_ascii=False)
    assert "same-tool-owner-secret" not in serialized
    assert "tool mismatch prompt" not in serialized
