from __future__ import annotations

import pytest

from app.ai.langgraph import nodes_ai


class _DummyClient:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[tuple[str, object]] = []

    async def generate_content(self, prompt: str, *, profile: object) -> str:
        self.calls.append((prompt, profile))
        return self.output


@pytest.mark.asyncio
async def test_question_variation_node_uses_history_when_recent_interactions_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _DummyClient("Pergunta variada")
    captured: dict[str, object] = {}

    def _fake_prompt(
        *,
        base_question: str,
        ai_instructions: str | None,
        recent_interactions: list[dict[str, str]] | None = None,
    ) -> str:
        captured["base_question"] = base_question
        captured["ai_instructions"] = ai_instructions
        captured["recent_interactions"] = recent_interactions
        return "PROMPT"

    monkeypatch.setattr(nodes_ai, "_get_gemini_client", lambda: dummy)
    monkeypatch.setattr(nodes_ai, "build_question_variation_prompt", _fake_prompt)

    result = await nodes_ai.question_variation_node(
        {
            "input_text": "Como voce esta hoje?",
            "context": {},
            "history": ["Como voce esta hoje?", "Teve algum desconforto?"],
        }
    )

    assert result["output"] == "Pergunta variada"
    assert captured["base_question"] == "Como voce esta hoje?"
    assert captured["recent_interactions"] == [
        {"question": "Como voce esta hoje?", "answer": ""},
        {"question": "Teve algum desconforto?", "answer": ""},
    ]


@pytest.mark.asyncio
async def test_question_variation_node_normalizes_context_recent_interactions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _DummyClient("Pergunta variada")
    captured: dict[str, object] = {}

    def _fake_prompt(
        *,
        base_question: str,
        ai_instructions: str | None,
        recent_interactions: list[dict[str, str]] | None = None,
    ) -> str:
        captured["recent_interactions"] = recent_interactions
        return "PROMPT"

    monkeypatch.setattr(nodes_ai, "_get_gemini_client", lambda: dummy)
    monkeypatch.setattr(nodes_ai, "build_question_variation_prompt", _fake_prompt)

    await nodes_ai.question_variation_node(
        {
            "input_text": "Como voce esta hoje?",
            "context": {
                "recent_interactions": [
                    "Tudo bem?",
                    {"question": "Dormiu bem?", "answer": "Sim"},
                    {"text": "Teve dor?", "response": "Nao"},
                ]
            },
            "history": ["Historico ignorado"],
        }
    )

    assert captured["recent_interactions"] == [
        {"question": "Tudo bem?", "answer": ""},
        {"question": "Dormiu bem?", "answer": "Sim"},
        {"question": "Teve dor?", "answer": "Nao"},
    ]


@pytest.mark.asyncio
async def test_question_variation_node_applies_fallback_when_output_repeats_recent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _DummyClient("Como voce esta hoje?")
    monkeypatch.setattr(nodes_ai, "_get_gemini_client", lambda: dummy)

    result = await nodes_ai.question_variation_node(
        {
            "input_text": "Como voce esta hoje?",
            "context": {},
            "history": ["Como voce esta hoje?"],
        }
    )

    assert result["output"] != "Como voce esta hoje?"
    assert "Como voce esta hoje?" in result["output"]


@pytest.mark.asyncio
async def test_question_variation_node_keeps_output_when_not_repetitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _DummyClient("Como voce se sentiu hoje durante o tratamento?")
    monkeypatch.setattr(nodes_ai, "_get_gemini_client", lambda: dummy)

    result = await nodes_ai.question_variation_node(
        {
            "input_text": "Como voce esta hoje?",
            "context": {},
            "history": ["Como voce esta hoje?"],
        }
    )

    assert (
        result["output"] == "Como voce se sentiu hoje durante o tratamento?"
    )
