from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.adk import session_store as session_store_module
from app.ai.adk import tools
from app.ai.adk.runtime import (
    ADKInvocationControls,
    ADKRuntimeControls,
    ADKSessionControls,
    ADKToolRunRequest,
    run_adk_tool,
)
from app.ai.adk.session_store import ADKSessionStore
from app.ai.adk.wrapper import PIISafeADKWrapper
from app.ai.agents.deps import AIDeps


@pytest.fixture
def adk_runtime_store(monkeypatch: pytest.MonkeyPatch) -> ADKSessionStore:
    session_store_module._MEMORY_SESSIONS.clear()
    session_store_module._MEMORY_INVOCATIONS.clear()
    store = ADKSessionStore(redis_client=None)
    monkeypatch.setattr("app.ai.adk.runtime.ADKSessionStore", lambda: store)
    yield store
    session_store_module._MEMORY_SESSIONS.clear()
    session_store_module._MEMORY_INVOCATIONS.clear()


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


@pytest.mark.asyncio
async def test_wrapper_invoke_adk_normalizes_tool_policy_context(monkeypatch):
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
        context={
            "tool_name": "sentiment",
            "policy": {
                "blocked_tools": {
                    "sentiment": {
                        "reason": "manual_review_required",
                    }
                }
            },
        },
    )

    assert result == {"status": "success", "result": "ok"}
    req = captured["request"]
    assert getattr(req, "context")["tool_policy"] == {
        "blocked_tools": {
            "sentiment": {
                "reason": "manual_review_required",
            }
        }
    }


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
            session=ADKSessionControls(action="create", session_id="session-1"),
            context={"patient_context": {"tumor_type": "mama"}},
        )
    )

    assert calls["runner_calls"] == 1
    assert calls["direct_dispatch"] == 0
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_run_adk_tool_auto_creates_session_and_persists_state(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    async def direct_handler(*, prompt, deps, context=None):
        return {"status": "success", "result": {"text": f"direct:{prompt}"}}

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": direct_handler})

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="como voce esta?",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            context={"patient_context": {"tumor_type": "mama"}},
        )
    )

    assert result["status"] == "success"
    assert result["session_id"]
    session = await adk_runtime_store.get_session(result["session_id"])
    assert session is not None
    assert session["status"] == "open"
    assert session["tool_name"] == "sentiment"
    assert session["state"]["patient_context"] == {"tumor_type": "mama"}
    assert session["state"]["recent_successful_turn"]["prompt"] == "como voce esta?"


@pytest.mark.asyncio
async def test_run_adk_tool_close_session_returns_closed_status(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    async def direct_handler(*, prompt, deps, context=None):
        return {"status": "success", "result": "should-not-run"}

    session = await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id="user-1",
        session_id="session-close",
    )

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": direct_handler})

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            session=ADKSessionControls(action="close", session_id=session["session_id"]),
        )
    )

    assert result["status"] == "closed"
    assert result["session_id"] == "session-close"
    stored_session = await adk_runtime_store.get_session("session-close")
    assert stored_session is not None
    assert stored_session["status"] == "closed"


@pytest.mark.asyncio
async def test_run_adk_tool_resume_rejects_closed_session(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    async def direct_handler(*, prompt, deps, context=None):
        return {"status": "success", "result": "should-not-run"}

    await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id="user-1",
        session_id="session-closed",
    )
    await adk_runtime_store.close_session("session-closed")

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": direct_handler})

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="retomar",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            session=ADKSessionControls(action="resume", session_id="session-closed"),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "session_closed"


@pytest.mark.asyncio
async def test_run_adk_tool_enforces_timeout(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    async def slow_handler(*, prompt, deps, context=None):
        await asyncio.sleep(0.05)
        return {"status": "success", "result": "late"}

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": slow_handler})

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="demora",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            runtime=ADKRuntimeControls(timeout_seconds=0.01),
        )
    )

    assert result["status"] == "timeout"
    assert result["result"]["type"] == "timeout"
    invocation = await adk_runtime_store.get_invocation(result["invocation_id"])
    assert invocation is not None
    assert invocation["status"] == "timeout"


@pytest.mark.asyncio
async def test_run_adk_tool_enforces_llm_budget(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    calls = {"direct_dispatch": 0}

    async def direct_handler(*, prompt, deps, context=None):
        calls["direct_dispatch"] += 1
        return {"status": "success", "result": "should-not-run"}

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": direct_handler})

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="sem orcamento",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            runtime=ADKRuntimeControls(max_llm_calls=1),
        )
    )

    assert result["status"] == "limit_exceeded"
    assert result["result"]["type"] == "limit_exceeded"
    assert calls["direct_dispatch"] == 0
    invocation = await adk_runtime_store.get_invocation(result["invocation_id"])
    assert invocation is not None
    assert invocation["status"] == "limit_exceeded"


@pytest.mark.asyncio
async def test_run_adk_tool_cancel_discards_late_result(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    started = asyncio.Event()

    async def long_handler(*, prompt, deps, context=None):
        started.set()
        await asyncio.sleep(1)
        return {"status": "success", "result": "late-success"}

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": long_handler})

    run_task = asyncio.create_task(
        run_adk_tool(
            ADKToolRunRequest(
                prompt="demorado",
                tool_name="sentiment",
                deps=AIDeps(gemini_api_key="k"),
                user_id="user-1",
                invocation=ADKInvocationControls(action="run", invocation_id="inv-cancel"),
                session=ADKSessionControls(action="create", session_id="session-cancel"),
            )
        )
    )
    await started.wait()

    cancel_result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            invocation=ADKInvocationControls(action="cancel", invocation_id="inv-cancel"),
        )
    )
    run_result = await run_task

    assert cancel_result["status"] == "cancelled"
    assert run_result["status"] == "cancelled"
    invocation = await adk_runtime_store.get_invocation("inv-cancel")
    assert invocation is not None
    assert invocation["status"] == "cancelled"


@pytest.mark.asyncio
async def test_run_adk_tool_resume_rejects_oversized_session_after_prune(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    async def direct_handler(*, prompt, deps, context=None):
        return {"status": "success", "result": "should-not-run"}

    session = await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id="user-1",
        session_id="session-oversized",
        state_size_limit_bytes=64,
    )
    session["state"] = {"patient_context": {"clinical_summary": "x" * 512}}
    session["state_size_bytes"] = 512
    await adk_runtime_store._write_session(
        session,
        ttl_seconds=adk_runtime_store.session_ttl_seconds,
    )

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": direct_handler})

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="retomar",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            session=ADKSessionControls(action="resume", session_id="session-oversized"),
        )
    )

    assert result["status"] == "error"
    assert result["result"]["type"] == "session_state_limit_exceeded"


@pytest.mark.asyncio
async def test_run_adk_tool_resume_prunes_recent_turns_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    async def direct_handler(*, prompt, deps, context=None):
        return {"status": "success", "result": {"text": "ok"}}

    session = await adk_runtime_store.create_session(
        tool_name="sentiment",
        user_id="user-1",
        session_id="session-prune",
        state_size_limit_bytes=256,
    )
    session["state"] = {
        "patient_context": {"tumor_type": "mama"},
        "recent_turns": [{"prompt": f"q-{idx}", "output": "x" * 80} for idx in range(5)],
    }
    await adk_runtime_store._write_session(
        session,
        ttl_seconds=adk_runtime_store.session_ttl_seconds,
    )

    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": direct_handler})

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="retomar",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            session=ADKSessionControls(action="resume", session_id="session-prune"),
        )
    )

    assert result["status"] == "success"
    updated = await adk_runtime_store.get_session("session-prune")
    assert updated is not None
    assert updated["state_size_bytes"] <= 256
    assert updated["state"]["patient_context"] == {"tumor_type": "mama"}
    assert len(updated["state"].get("recent_turns", [])) < 5


@pytest.mark.asyncio
async def test_run_adk_tool_blocks_policy_before_direct_handler_executes(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    calls = {"domain": 0}

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls["domain"] += 1
            return {"sentiment": "negative"}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)
    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", False, raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": tools.sentiment_tool})

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="avaliar resposta",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            invocation=ADKInvocationControls(
                action="run",
                invocation_id="inv-policy-direct",
            ),
            context={
                "tool_policy": {
                    "required_context_keys": {
                        "sentiment": ["patient_context.clinical_summary"],
                    }
                },
                "patient_context": {},
            },
        )
    )

    assert result["status"] == "policy_block"
    assert result["result"]["type"] == "policy_block"
    assert result["result"]["reason"] == "missing_required_context"
    assert result["result"]["missing_context_keys"] == ["patient_context.clinical_summary"]
    assert calls["domain"] == 0

    invocation = await adk_runtime_store.get_invocation("inv-policy-direct")
    assert invocation is not None
    assert invocation["status"] == "policy_block"


@pytest.mark.asyncio
async def test_run_adk_tool_runner_policy_block_prevents_domain_client_execution(
    monkeypatch: pytest.MonkeyPatch,
    adk_runtime_store: ADKSessionStore,
) -> None:
    from app.ai.adk import runtime

    calls = {"domain": 0, "runner": 0}

    class FakeClient:
        async def analyze_response_sentiment(self, *, response: str, patient_context: dict):
            calls["domain"] += 1
            return {"sentiment": "negative"}

    class FakeFunctionTool:
        def __init__(self, func):
            self.func = func
            self.name = "sentiment"

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunner:
        def __init__(self, **kwargs):
            self.agent = kwargs["agent"]

        async def run_async(self, **kwargs):
            calls["runner"] += 1
            callback = self.agent.kwargs["before_tool_callback"]
            callback_result = await callback(
                SimpleNamespace(name="sentiment"),
                {
                    "prompt": kwargs["new_message"]["prompt"],
                    "context_json": json.dumps(
                        {
                            "tool_policy": {
                                "blocked_prompts": {
                                    "trigger review": {
                                        "reason": "manual_review_required",
                                    }
                                }
                            }
                        }
                    ),
                },
                None,
            )
            if callback_result is not None:
                yield {"result": callback_result}
                return
            yield {"content": {"parts": [{"text": "runner-output"}]}}

    monkeypatch.setattr("app.ai.adk.tools.GeminiDomainClient", FakeClient, raising=False)
    monkeypatch.setattr(runtime, "HAS_ADK_RUNTIME", True, raising=False)
    monkeypatch.setattr(runtime, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(runtime, "Runner", FakeRunner, raising=False)
    monkeypatch.setattr(runtime, "InMemorySessionService", lambda: object(), raising=False)
    monkeypatch.setattr(runtime, "get_tool_registry", lambda: {"sentiment": tools.sentiment_tool})
    monkeypatch.setattr(
        runtime,
        "get_adk_function_tools",
        lambda: {"sentiment": FakeFunctionTool(tools.sentiment_tool)},
        raising=False,
    )

    result = await run_adk_tool(
        ADKToolRunRequest(
            prompt="trigger review",
            tool_name="sentiment",
            deps=AIDeps(gemini_api_key="k"),
            user_id="user-1",
            invocation=ADKInvocationControls(
                action="run",
                invocation_id="inv-policy-runner",
            ),
            context={
                "tool_policy": {
                    "blocked_prompts": {
                        "trigger review": {
                            "reason": "manual_review_required",
                        }
                    }
                }
            },
        )
    )

    assert result["status"] == "policy_block"
    assert result["result"]["type"] == "policy_block"
    assert result["result"]["reason"] == "manual_review_required"
    assert calls["runner"] == 1
    assert calls["domain"] == 0

    invocation = await adk_runtime_store.get_invocation("inv-policy-runner")
    assert invocation is not None
    assert invocation["status"] == "policy_block"
