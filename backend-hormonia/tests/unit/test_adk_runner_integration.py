from __future__ import annotations

import asyncio

import pytest

from app.ai.adk.runtime import (
    ADKInvocationControls,
    ADKSessionControls,
    ADKToolRunRequest,
    run_adk_tool,
)
from app.ai.adk.tools import get_adk_function_tools
from app.ai.agents.deps import AIDeps

try:
    import google.adk  # noqa: F401

    HAS_ADK = True
except ModuleNotFoundError:
    HAS_ADK = False


def _make_request(
    *,
    prompt: str,
    session_id: str,
    context: dict | None = None,
    invocation: ADKInvocationControls | None = None,
) -> ADKToolRunRequest:
    return ADKToolRunRequest(
        prompt=prompt,
        tool_name="sentiment",
        deps=AIDeps(gemini_api_key="fake-key", model_name="gemini-2.0-flash"),
        user_id="integration-user",
        session_id=session_id,
        session=ADKSessionControls(action="create", session_id=session_id),
        context=context,
        invocation=invocation or ADKInvocationControls(action="run"),
    )


def _normalized_classification(result: dict) -> dict:
    payload = dict(result["result"])
    payload.pop("invocation_id", None)
    return {"status": result["status"], "result": payload}


def test_function_tool_registry_has_four_entries_with_callable_refs() -> None:
    registry = get_adk_function_tools()

    assert len(registry) == 4
    assert set(registry) == {"sentiment", "humanize", "variation", "empathy"}
    for value in registry.values():
        func_ref = getattr(value, "func", None)
        if func_ref is None:
            func_ref = getattr(value, "callable", None)
        assert callable(func_ref)


@pytest.mark.asyncio
@pytest.mark.adk_smoke
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_exercises_runner_path_with_domain_client(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls.append((response, patient_context))
            return {"sentiment": "neutral"}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await run_adk_tool(
        _make_request(
            prompt="paciente relata melhora",
            session_id="integration-session",
            context={"patient_context": {"cycle": "Q1"}},
        )
    )

    assert result["status"] == "success"
    assert "result" in result
    assert calls, "Domain client was not called through ADK runtime path"


@pytest.mark.asyncio
@pytest.mark.adk_smoke
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_runner_path_repeats_tool_failures_as_tool_error(
    monkeypatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls.append((response, patient_context))
            raise RuntimeError("integration tool failure")

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    results = []
    for suffix in ("1", "2"):
        result = await run_adk_tool(
            _make_request(
                prompt="paciente relata piora",
                session_id=f"integration-session-tool-{suffix}",
                context={"patient_context": {"cycle": "Q2"}},
            )
        )
        results.append(result)

    assert [result["status"] for result in results] == ["tool_error", "tool_error"]
    for result in results:
        assert result["result"]["type"] == "tool_error"
    assert len(calls) == 2, "Domain client was not called before tool_error classification"


@pytest.mark.asyncio
@pytest.mark.adk_smoke
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_runner_path_repeats_runner_failures_as_upstream_error(
    monkeypatch,
) -> None:
    from app.ai.adk import runtime

    class ExplodingRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run_async(self, **kwargs):
            raise RuntimeError("integration runner failure")
            yield {"result": "unreachable"}

    monkeypatch.setattr(runtime, "Runner", ExplodingRunner, raising=False)

    results = []
    for suffix in ("1", "2"):
        result = await run_adk_tool(
            _make_request(
                prompt="paciente relata piora",
                session_id=f"integration-session-upstream-{suffix}",
                context={"patient_context": {"cycle": "Q2"}},
            )
        )
        results.append(result)

    assert [result["status"] for result in results] == [
        "upstream_error",
        "upstream_error",
    ]
    for result in results:
        assert result["result"]["type"] == "upstream_error"


@pytest.mark.asyncio
@pytest.mark.adk_smoke
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_runner_policy_block_no_side_effect(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls.append((response, patient_context))
            return {"sentiment": "neutral"}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await run_adk_tool(
        _make_request(
            prompt="paciente descreve febre",
            session_id="integration-session-policy-block",
            context={
                "patient_context": {"cycle": "Q3"},
                "tool_policy": {
                    "blocked_tools": {
                        "sentiment": "blocked_for_integration_test",
                    }
                },
            },
        )
    )

    assert result["status"] == "policy_block"
    assert result["result"]["type"] == "policy_block"
    assert result["result"]["reason"] == "blocked_for_integration_test"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.adk_smoke
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_runner_policy_block_repeated_deterministic(
    monkeypatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls.append((response, patient_context))
            return {"sentiment": "neutral"}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    results = []
    for suffix in ("1", "2"):
        result = await run_adk_tool(
            _make_request(
                prompt="paciente descreve febre",
                session_id=f"integration-session-policy-repeat-{suffix}",
                context={
                    "patient_context": {"cycle": "Q3"},
                    "tool_policy": {
                        "blocked_tools": {
                            "sentiment": "blocked_for_integration_test",
                        }
                    },
                },
            )
        )
        results.append(result)

    assert [result["status"] for result in results] == ["policy_block", "policy_block"]
    assert [result["result"]["type"] for result in results] == [
        "policy_block",
        "policy_block",
    ]
    assert _normalized_classification(results[0]) == _normalized_classification(results[1])
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.adk_smoke
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_runner_upstream_error_no_fallback_dispatch(
    monkeypatch,
) -> None:
    from app.ai.adk import runtime

    calls = {"direct_dispatch": 0}

    async def recording_execute_tool_handler(*, tool_name, handler, prompt, deps, context=None):
        del tool_name, handler, prompt, deps, context
        calls["direct_dispatch"] += 1
        return {"status": "success", "result": "should-not-run"}

    class ExplodingRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run_async(self, **kwargs):
            del kwargs
            raise RuntimeError("runner bootstrap failure")
            yield {"result": "unreachable"}

    monkeypatch.setattr(runtime, "Runner", ExplodingRunner, raising=False)
    monkeypatch.setattr(
        runtime,
        "execute_tool_handler",
        recording_execute_tool_handler,
        raising=False,
    )

    result = await run_adk_tool(
        _make_request(
            prompt="paciente relata piora",
            session_id="integration-session-upstream-no-fallback",
            context={"patient_context": {"cycle": "Q4"}},
        )
    )

    assert result["status"] == "upstream_error"
    assert result["result"]["type"] == "upstream_error"
    assert calls["direct_dispatch"] == 0


@pytest.mark.asyncio
@pytest.mark.adk_smoke
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_runner_cancel_terminates_invocation(monkeypatch) -> None:
    started = asyncio.Event()

    class SlowClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            del response, patient_context
            started.set()
            await asyncio.sleep(10)
            return {"sentiment": "neutral"}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", SlowClient, raising=False)

    invocation_id = "integration-invocation-cancel"
    run_task = asyncio.create_task(
        run_adk_tool(
            _make_request(
                prompt="paciente relata fadiga intensa",
                session_id="integration-session-cancel",
                context={"patient_context": {"cycle": "Q5"}},
                invocation=ADKInvocationControls(
                    action="run",
                    invocation_id=invocation_id,
                ),
            )
        )
    )

    await asyncio.wait_for(started.wait(), timeout=5)

    cancel_result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="fake-key", model_name="gemini-2.0-flash"),
            user_id="integration-user",
            invocation=ADKInvocationControls(
                action="cancel",
                invocation_id=invocation_id,
            ),
        )
    )
    run_result = await run_task

    assert cancel_result["status"] == "cancelled"
    assert cancel_result["result"]["type"] == "cancelled"
    assert run_result["status"] == "cancelled"
    assert run_result["result"]["type"] == "cancelled"
