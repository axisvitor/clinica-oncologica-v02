from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.ai.adk import tools
from app.ai.adk.runtime import ADKToolRunRequest, run_adk_tool
from app.ai.adk.wrapper import PIISafeADKWrapper
from app.ai.agents.deps import AIDeps


@pytest.mark.asyncio
async def test_sentiment_tool_delegates_to_domain_client(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls.append((response, patient_context))
            return {"sentiment": "negative"}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await tools.sentiment_tool(
        prompt="estou com dor",
        deps=AIDeps(gemini_api_key="k"),
        context={"patient_context": {"tumor_type": "mama"}},
    )

    assert result == {"status": "success", "result": {"sentiment": "negative"}}
    assert calls == [("estou com dor", {"tumor_type": "mama"})]


@pytest.mark.asyncio
async def test_humanize_tool_delegates_to_domain_client(monkeypatch):
    class FakeClient:
        async def humanize_flow_message(self, **kwargs):
            assert kwargs["template"] == "pergunta"
            assert kwargs["patient_name"] == "Ana"
            return "mensagem humanizada"

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await tools.humanize_tool(
        prompt="pergunta",
        deps=AIDeps(gemini_api_key="k"),
        context={"patient_name": "Ana", "patient_context": {}, "conversation_history": [], "personalization_hints": []},
    )

    assert result == {"status": "success", "result": "mensagem humanizada"}


@pytest.mark.asyncio
async def test_variation_tool_delegates_to_domain_client(monkeypatch):
    class FakeClient:
        async def generate_varied_question(self, **kwargs):
            assert kwargs["base_question"] == "como voce esta hoje?"
            return "como foi seu dia?"

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await tools.variation_tool(
        prompt="como voce esta hoje?",
        deps=AIDeps(gemini_api_key="k"),
        context={"previous_questions": [], "patient_context": {}},
    )

    assert result == {"status": "success", "result": "como foi seu dia?"}


@pytest.mark.asyncio
async def test_empathy_tool_delegates_to_domain_client(monkeypatch):
    class FakeClient:
        async def create_empathetic_follow_up(self, **kwargs):
            assert kwargs["patient_response"] == "estou preocupado"
            return "entendo sua preocupacao"

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)

    result = await tools.empathy_tool(
        prompt="estou preocupado",
        deps=AIDeps(gemini_api_key="k"),
        context={"conversation_history": [], "patient_context": {}},
    )

    assert result == {"status": "success", "result": "entendo sua preocupacao"}


@pytest.mark.asyncio
async def test_wrapper_invoke_adk_delegates_to_runtime(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_run(request):
        captured["request"] = request
        return {"status": "success", "result": "ok"}

    monkeypatch.setattr("app.ai.adk.wrapper.run_adk_tool", fake_run, raising=False)

    wrapper = PIISafeADKWrapper()
    result = await wrapper._invoke_adk(
        "safe prompt",
        AIDeps(gemini_api_key="k", model_name="gemini-test"),
        operation="adk-test",
        context={"tool_name": "sentiment", "session_id": "s-1", "user_id": "u-1"},
    )

    assert result == {"status": "success", "result": "ok"}
    req = captured["request"]
    assert getattr(req, "tool_name") == "sentiment"
    assert getattr(req, "prompt") == "safe prompt"


def test_adk_run_guard_script_accepts_runtime_path():
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_agent_run_calls.py"
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_get_adk_function_tools_structural_registry_has_all_capabilities() -> None:
    registry = tools.get_adk_function_tools()

    assert set(registry) == {"sentiment", "humanize", "variation", "empathy"}
    for tool_name, tool_obj in registry.items():
        func_ref = getattr(tool_obj, "func", None)
        if func_ref is None:
            func_ref = getattr(tool_obj, "callable", None)
        assert callable(func_ref), f"Tool {tool_name} does not expose callable function"


@pytest.mark.asyncio
async def test_run_adk_tool_prefers_runner_pipeline_when_available(monkeypatch) -> None:
    from app.ai.adk import runtime

    calls = {"direct_dispatch": 0, "runner_calls": 0}

    async def direct_handler(*, prompt, deps, context=None):
        calls["direct_dispatch"] += 1
        return {"status": "success", "result": f"direct:{prompt}"}

    class FakeFunctionTool:
        def __init__(self, func):
            self.func = func

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run_async(self, **kwargs):
            calls["runner_calls"] += 1
            yield {"content": {"parts": [{"text": "runner-output"}]}}

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", True, raising=False)
    monkeypatch.setattr(runtime, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(runtime, "Runner", FakeRunner, raising=False)
    monkeypatch.setattr(runtime, "InMemorySessionService", lambda: object(), raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": direct_handler})
    monkeypatch.setattr(
        runtime,
        "get_adk_function_tools",
        lambda: {"sentiment": FakeFunctionTool(direct_handler)},
        raising=False,
    )

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="como voce esta?",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            session_id="session-1",
            context={"patient_context": {"tumor_type": "mama"}},
        )
    )

    assert calls["runner_calls"] == 1
    assert calls["direct_dispatch"] == 0
    assert result["status"] == "success"
