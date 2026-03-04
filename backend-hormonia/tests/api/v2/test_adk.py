from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient


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
            "session_id": "session-123",
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
            "session_id": "session-321",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(calls) == 1
    assert calls[0]["operation"] == "adk_endpoint_run"
    assert calls[0]["context"] == {
        "tool_name": "sentiment",
        "user_id": "user-321",
        "session_id": "session-321",
    }


def test_adk_run_invalid_payload_returns_422_and_does_not_call_wrapper(
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
        json={"tool_name": "sentiment", "session_id": "missing-prompt"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert calls == []
