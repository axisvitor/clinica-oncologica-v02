from __future__ import annotations

import pytest

from app.ai.adk.runtime import ADKSessionControls, ADKToolRunRequest, run_adk_tool
from app.ai.adk.tools import get_adk_function_tools
from app.ai.agents.deps import AIDeps

try:
    import google.adk  # noqa: F401

    HAS_ADK = True
except ModuleNotFoundError:
    HAS_ADK = False


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
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_exercises_runner_path_with_domain_client(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls.append((response, patient_context))
            return {"sentiment": "neutral"}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="paciente relata melhora",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="fake-key", model_name="gemini-2.0-flash"),
            user_id="integration-user",
            session_id="integration-session",
            session=ADKSessionControls(action="create", session_id="integration-session"),
            context={"patient_context": {"cycle": "Q1"}},
        )
    )

    assert result["status"] == "success"
    assert "result" in result
    assert calls, "Domain client was not called through ADK runtime path"


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_runner_path_classifies_tool_failures_as_tool_error(
    monkeypatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls.append((response, patient_context))
            raise RuntimeError("integration tool failure")

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="paciente relata piora",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="fake-key", model_name="gemini-2.0-flash"),
            user_id="integration-user",
            session_id="integration-session",
            session=ADKSessionControls(action="create", session_id="integration-session"),
            context={"patient_context": {"cycle": "Q2"}},
        )
    )

    assert result["status"] == "tool_error"
    assert result["result"]["type"] == "tool_error"
    assert calls, "Domain client was not called before tool_error classification"


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_ADK, reason="google-adk not installed")
async def test_run_adk_tool_runner_path_classifies_runner_failures_as_upstream_error(
    monkeypatch,
) -> None:
    class ExplodingRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run_async(self, **kwargs):
            raise RuntimeError("integration runner failure")
            yield {"result": "unreachable"}

    monkeypatch.setattr("app.ai.adk.runtime.Runner", ExplodingRunner, raising=False)

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="paciente relata piora",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="fake-key", model_name="gemini-2.0-flash"),
            user_id="integration-user",
            session_id="integration-session",
            session=ADKSessionControls(action="create", session_id="integration-session"),
            context={"patient_context": {"cycle": "Q2"}},
        )
    )

    assert result["status"] == "upstream_error"
    assert result["result"]["type"] == "upstream_error"
