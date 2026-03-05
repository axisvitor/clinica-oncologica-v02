from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient


def _deterministic_runtime_result(runtime_status: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": runtime_status,
        "message": f"{runtime_status} happened",
        "tool_name": "sentiment",
    }
    if runtime_status == "policy_block":
        payload["reason"] = "manual_review_required"

    return {
        "status": runtime_status,
        "session_id": f"session-{runtime_status}",
        "result": payload,
    }


def test_adk_run_accepts_payload_and_returns_normalized_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        return {"status": "success", "result": {"text": f"processed:{prompt}"}}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={
            "prompt": "Paciente com dor leve",
            "tool_name": "sentiment",
            "user_id": "user-123",
            "session": {"action": "resume", "session_id": "session-123"},
        },
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["tool_name"] == "sentiment"
    assert payload["session_id"] == "session-123"
    assert payload["output"] == {"text": "processed:Paciente com dor leve"}


def test_adk_run_calls_wrapper_safe_run_once(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append(
            {
                "prompt": prompt,
                "operation": operation,
                "context": context,
                "deps": deps,
            }
        )
        return {"status": "success", "result": "ok"}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={
            "prompt": "teste wrapper",
            "tool_name": "sentiment",
            "user_id": "user-321",
            "session": {
                "action": "resume",
                "session_id": "session-321",
                "state_size_limit_bytes": 8192,
            },
            "runtime": {"max_llm_calls": 4, "timeout_seconds": 12.5},
            "invocation": {"action": "run", "invocation_id": "inv-321"},
            "context": {
                "patient_context": {"tumor_type": "mama"},
                "session": {"action": "should-not-win"},
            },
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(calls) == 1
    assert calls[0]["operation"] == "adk_endpoint_run"
    assert calls[0]["context"] == {
        "tool_name": "sentiment",
        "user_id": "user-321",
        "session_id": "session-321",
        "invocation_id": "inv-321",
        "request_source": "api_v2_adk",
        "runtime": {"max_llm_calls": 4, "timeout_seconds": 12.5},
        "session": {
            "action": "resume",
            "session_id": "session-321",
            "state_size_limit_bytes": 8192,
        },
        "invocation": {"action": "run", "invocation_id": "inv-321"},
        "patient_context": {"tumor_type": "mama"},
    }


def test_adk_run_preserves_canonical_policy_block_response_envelope(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        return {
            "status": "policy_block",
            "session_id": "session-policy",
            "result": {
                "type": "policy_block",
                "message": "Tool call blocked by policy",
                "reason": "manual_review_required",
                "tool_name": "sentiment",
            },
        }

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={
            "prompt": "trigger review",
            "tool_name": "sentiment",
            "session": {"action": "resume", "session_id": "session-policy"},
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "policy_block",
        "tool_name": "sentiment",
        "session_id": "session-policy",
        "output": {
            "type": "policy_block",
            "message": "Tool call blocked by policy",
            "reason": "manual_review_required",
            "tool_name": "sentiment",
        },
    }


@pytest.mark.parametrize(
    "runtime_status",
    ["policy_block", "tool_error", "upstream_error"],
)
def test_adk_run_preserves_repeated_deterministic_response_envelopes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    runtime_status: str,
) -> None:
    calls: list[str] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append(prompt)
        return _deterministic_runtime_result(runtime_status)

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    responses = []
    for _ in range(2):
        response = client.post(
            "/api/v2/adk/run",
            json={
                "prompt": "trigger deterministic error",
                "tool_name": "sentiment",
                "session": {
                    "action": "resume",
                    "session_id": f"session-{runtime_status}",
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        responses.append(response.json())

    expected_output = {
        "type": runtime_status,
        "message": f"{runtime_status} happened",
        "tool_name": "sentiment",
    }
    if runtime_status == "policy_block":
        expected_output["reason"] = "manual_review_required"

    assert calls == ["trigger deterministic error", "trigger deterministic error"]
    assert responses == [
        {
            "status": runtime_status,
            "tool_name": "sentiment",
            "session_id": f"session-{runtime_status}",
            "output": expected_output,
        },
        {
            "status": runtime_status,
            "tool_name": "sentiment",
            "session_id": f"session-{runtime_status}",
            "output": expected_output,
        },
    ]


def test_adk_run_rejects_missing_prompt_for_run_actions(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append("called")
        return {"status": "success", "result": "should-not-run"}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={"tool_name": "sentiment", "session": {"action": "resume", "session_id": "s-1"}},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert calls == []


def test_adk_run_rejects_close_without_session_id(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append("called")
        return {"status": "success", "result": "should-not-run"}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={"tool_name": "sentiment", "session": {"action": "close"}},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert calls == []


def test_adk_run_rejects_cancel_without_invocation_id(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append("called")
        return {"status": "success", "result": "should-not-run"}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={
            "tool_name": "sentiment",
            "invocation": {"action": "cancel"},
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert calls == []


def test_adk_run_rejects_cancel_and_create_combination(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append("called")
        return {"status": "success", "result": "should-not-run"}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={
            "tool_name": "sentiment",
            "session": {"action": "create"},
            "invocation": {"action": "cancel", "invocation_id": "inv-1"},
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert calls == []


def test_adk_run_rejects_mismatched_session_ids(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        calls.append("called")
        return {"status": "success", "result": "should-not-run"}

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={
            "prompt": "teste",
            "tool_name": "sentiment",
            "session_id": "legacy-session",
            "session": {"action": "resume", "session_id": "new-session"},
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert calls == []


@pytest.mark.parametrize(
    ("safe_result", "expected_status", "expected_session_id", "expected_type"),
    [
        (
            {
                "status": "success",
                "session_id": "session-auto",
                "result": {"text": "processed:novo"},
            },
            "success",
            "session-auto",
            None,
        ),
        (
            {
                "status": "closed",
                "session_id": "session-close",
                "result": {"message": "Session closed", "type": "session_closed"},
            },
            "closed",
            "session-close",
            "session_closed",
        ),
        (
            {
                "status": "cancelled",
                "session_id": "session-cancel",
                "result": {"message": "Invocation cancelled", "type": "cancelled"},
            },
            "cancelled",
            "session-cancel",
            "cancelled",
        ),
        (
            {
                "status": "timeout",
                "session_id": "session-timeout",
                "result": {"message": "ADK execution timed out", "type": "timeout"},
            },
            "timeout",
            "session-timeout",
            "timeout",
        ),
        (
            {
                "status": "limit_exceeded",
                "session_id": "session-limit",
                "result": {
                    "message": "LLM call budget exhausted",
                    "type": "limit_exceeded",
                },
            },
            "limit_exceeded",
            "session-limit",
            "limit_exceeded",
        ),
        (
            {
                "status": "error",
                "session_id": "session-closed",
                "result": {
                    "message": "Session closed",
                    "type": "session_closed",
                },
            },
            "error",
            "session-closed",
            "session_closed",
        ),
        (
            {
                "status": "error",
                "session_id": "session-budget",
                "result": {
                    "message": "Session exceeds configured state budget",
                    "type": "session_state_limit_exceeded",
                },
            },
            "error",
            "session-budget",
            "session_state_limit_exceeded",
        ),
    ],
)
def test_adk_run_normalizes_runtime_lifecycle_statuses(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    safe_result: dict[str, object],
    expected_status: str,
    expected_session_id: str,
    expected_type: str | None,
) -> None:
    async def fake_safe_run(self, prompt, deps, *, operation, context=None):
        return safe_result

    monkeypatch.setattr(
        "app.api.v2.routers.adk.PIISafeADKWrapper.safe_run",
        fake_safe_run,
        raising=False,
    )

    response = client.post(
        "/api/v2/adk/run",
        json={
            "prompt": "novo",
            "tool_name": "sentiment",
            "invocation": {"action": "run", "invocation_id": "inv-1"},
        },
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == expected_status
    assert payload["tool_name"] == "sentiment"
    assert payload["session_id"] == expected_session_id
    if expected_type is None:
        assert payload["output"] == {"text": "processed:novo"}
    else:
        assert payload["output"]["type"] == expected_type
