from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.ai.adk import tools
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
