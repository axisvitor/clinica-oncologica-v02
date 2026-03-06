from __future__ import annotations

from typing import Any

import pytest

from app.ai.adk import runtime as runtime_module
from app.ai.adk import session_store as session_store_module
from app.ai.adk.runtime import ADKSessionControls, ADKToolRunRequest, run_adk_tool
from app.ai.adk.session_store import ADKSessionStore
from app.ai.agents.deps import AIDeps

SMOKE_PATIENT_CONTEXT = {
    "tumor_type": "mama",
    "treatment_cycle": "quimioterapia-ciclo-3",
}

SUCCESS_CASES = [
    {
        "tool_name": "sentiment",
        "prompt": "Paciente relata nausea persistente apos quimioterapia e preocupa-se com a hidratação.",
        "context": {"patient_context": SMOKE_PATIENT_CONTEXT},
        "method_name": "analyze_response_sentiment",
        "expected_kwargs": {
            "response": "Paciente relata nausea persistente apos quimioterapia e preocupa-se com a hidratação.",
            "patient_context": SMOKE_PATIENT_CONTEXT,
        },
        "result": {"sentiment": "negative", "confidence": 0.9},
    },
    {
        "tool_name": "humanize",
        "prompt": "Precisamos saber se voce conseguiu se alimentar hoje.",
        "context": {
            "patient_name": "Maria",
            "patient_context": SMOKE_PATIENT_CONTEXT,
            "conversation_history": ["Oi Maria, como voce ficou depois da ultima sessao?"],
            "personalization_hints": ["tom acolhedor", "linguagem simples"],
        },
        "method_name": "humanize_flow_message",
        "expected_kwargs": {
            "template": "Precisamos saber se voce conseguiu se alimentar hoje.",
            "patient_name": "Maria",
            "patient_context": SMOKE_PATIENT_CONTEXT,
            "conversation_history": ["Oi Maria, como voce ficou depois da ultima sessao?"],
            "personalization_hints": ["tom acolhedor", "linguagem simples"],
        },
        "result": {"humanized_text": "Maria, conseguiu se alimentar um pouco hoje?"},
    },
    {
        "tool_name": "variation",
        "prompt": "Como ficou seu apetite desde a ultima aplicacao?",
        "context": {
            "previous_questions": ["Como voce passou a noite depois da quimioterapia?"],
            "patient_context": SMOKE_PATIENT_CONTEXT,
        },
        "method_name": "generate_varied_question",
        "expected_kwargs": {
            "base_question": "Como ficou seu apetite desde a ultima aplicacao?",
            "previous_questions": ["Como voce passou a noite depois da quimioterapia?"],
            "patient_context": SMOKE_PATIENT_CONTEXT,
        },
        "result": {"variation": "Depois da ultima aplicacao, voce conseguiu se alimentar melhor?"},
    },
    {
        "tool_name": "empathy",
        "prompt": "Estou com medo de a nausea piorar antes da proxima consulta.",
        "context": {
            "conversation_history": ["Obrigada por nos contar como esta se sentindo."],
            "patient_context": SMOKE_PATIENT_CONTEXT,
        },
        "method_name": "create_empathetic_follow_up",
        "expected_kwargs": {
            "patient_response": "Estou com medo de a nausea piorar antes da proxima consulta.",
            "conversation_history": ["Obrigada por nos contar como esta se sentindo."],
            "patient_context": SMOKE_PATIENT_CONTEXT,
        },
        "result": {
            "followup": "Entendo sua preocupação. Vamos acompanhar juntos os sintomas ate a proxima consulta."
        },
    },
]


@pytest.fixture
def adk_runtime_store(monkeypatch: pytest.MonkeyPatch) -> ADKSessionStore:
    session_store_module._MEMORY_SESSIONS.clear()
    session_store_module._MEMORY_INVOCATIONS.clear()
    store = ADKSessionStore(redis_client=None)
    monkeypatch.setattr("app.ai.adk.runtime.ADKSessionStore", lambda: store)
    monkeypatch.setattr(runtime_module, "HAS_ADK_RUNTIME", False, raising=False)
    yield store
    session_store_module._MEMORY_SESSIONS.clear()
    session_store_module._MEMORY_INVOCATIONS.clear()


def _make_request(
    tool_name: str,
    prompt: str,
    context: dict[str, Any] | None = None,
) -> ADKToolRunRequest:
    return ADKToolRunRequest(
        prompt=prompt,
        tool_name=tool_name,
        deps=AIDeps(gemini_api_key="smoke-key", model_name="gemini-2.0-flash"),
        user_id="smoke-user",
        context=context,
        session=ADKSessionControls(action="create"),
    )


def _fake_domain_client(case: dict[str, Any], calls: list[tuple[str, dict[str, Any]]]) -> type:
    async def _record_call(method_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        calls.append((method_name, kwargs))
        return case["result"]

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs

        async def analyze_response_sentiment(self, **kwargs: Any) -> dict[str, Any]:
            return await _record_call("analyze_response_sentiment", kwargs)

        async def humanize_flow_message(self, **kwargs: Any) -> dict[str, Any]:
            return await _record_call("humanize_flow_message", kwargs)

        async def generate_varied_question(self, **kwargs: Any) -> dict[str, Any]:
            return await _record_call("generate_varied_question", kwargs)

        async def create_empathetic_follow_up(self, **kwargs: Any) -> dict[str, Any]:
            return await _record_call("create_empathetic_follow_up", kwargs)

    return FakeClient


def _blocking_domain_client() -> type:
    class BlockingClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs

        async def analyze_response_sentiment(self, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError(f"policy_block should prevent sentiment execution: {kwargs}")

        async def humanize_flow_message(self, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError(f"policy_block should prevent humanize execution: {kwargs}")

        async def generate_varied_question(self, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError(f"policy_block should prevent variation execution: {kwargs}")

        async def create_empathetic_follow_up(self, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError(f"policy_block should prevent empathy execution: {kwargs}")

    return BlockingClient


@pytest.mark.adk_smoke
@pytest.mark.asyncio
@pytest.mark.parametrize("case", SUCCESS_CASES, ids=[case["tool_name"] for case in SUCCESS_CASES])
async def test_adk_smoke_success_trajectory_per_tool(
    case: dict[str, Any],
    adk_runtime_store: ADKSessionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del adk_runtime_store
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        "app.ai.adk.tools.GeminiDomainClient",
        _fake_domain_client(case, calls),
        raising=False,
    )

    result = await run_adk_tool(_make_request(case["tool_name"], case["prompt"], case["context"]))

    assert result["status"] == "success"
    assert "result" in result
    assert isinstance(result["result"], dict)
    assert result["result"] == case["result"]
    assert calls == [(case["method_name"], case["expected_kwargs"])]


@pytest.mark.adk_smoke
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "prompt"),
    [
        ("sentiment", "Paciente relata fadiga intensa apos quimioterapia."),
        ("humanize", "Pergunte se houve vomitos nas ultimas 24 horas."),
        ("variation", "Voce teve febre ou calafrios desde ontem?"),
        ("empathy", "Estou insegura porque nao consigo comer desde cedo."),
    ],
    ids=["sentiment", "humanize", "variation", "empathy"],
)
async def test_adk_smoke_policy_block_trajectory_per_tool(
    tool_name: str,
    prompt: str,
    adk_runtime_store: ADKSessionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del adk_runtime_store
    monkeypatch.setattr(
        "app.ai.adk.tools.GeminiDomainClient",
        _blocking_domain_client(),
        raising=False,
    )

    result = await run_adk_tool(
        _make_request(
            tool_name,
            prompt,
            {"tool_policy": {"blocked_tools": [tool_name]}},
        )
    )

    assert result["status"] == "policy_block"
    assert result["result"]["type"] == "policy_block"


@pytest.mark.adk_smoke
@pytest.mark.asyncio
async def test_adk_smoke_reports_unsupported_tool_status(
    adk_runtime_store: ADKSessionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del adk_runtime_store
    monkeypatch.setattr(runtime_module, "get_tool_registry", lambda: {})

    result = await run_adk_tool(
        _make_request(
            "nonexistent_tool",
            "Paciente pergunta se precisa adiantar a consulta por causa da dor.",
        )
    )

    assert result["status"] == "unsupported_tool"
    assert result["result"]["type"] == "unsupported_tool"
