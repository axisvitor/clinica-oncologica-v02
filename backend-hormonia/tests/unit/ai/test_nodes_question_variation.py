"""Tests for question variation logic.

Phase 8 (AI-03): question_variation_node() removed — tests migrated to cover:
  1. GeminiDomainClient.generate_varied_question() (integration path)
  2. Helper functions _is_too_similar_to_recent and _build_non_repetitive_question directly
"""

from __future__ import annotations

import pytest

from app.ai.langgraph import nodes_ai


class _DummyGeminiClient:
    """Minimal stub for GeminiClient.generate_content."""

    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[tuple] = []

    async def generate_content(self, prompt: str, **kwargs) -> str:
        self.calls.append((prompt, kwargs))
        return self.output


# ---------------------------------------------------------------------------
# Tests for _is_too_similar_to_recent (helper, unchanged after Phase 8)
# ---------------------------------------------------------------------------

def test_is_too_similar_exact_match() -> None:
    assert nodes_ai._is_too_similar_to_recent(
        "Como voce esta hoje?", ["Como voce esta hoje?"]
    ) is True


def test_is_too_similar_high_overlap() -> None:
    # 88%+ overlap → considered too similar (8/9 words match = 88.9%)
    assert nodes_ai._is_too_similar_to_recent(
        "Como voce esta se sentindo hoje boa sorte para",
        ["Como voce esta se sentindo hoje boa sorte mesmo"],
    ) is True


def test_is_too_similar_different_enough() -> None:
    assert nodes_ai._is_too_similar_to_recent(
        "Teve alguma dificuldade para dormir?",
        ["Como voce esta hoje?"],
    ) is False


def test_is_too_similar_empty_candidate() -> None:
    assert nodes_ai._is_too_similar_to_recent("", ["Como voce esta hoje?"]) is True


# ---------------------------------------------------------------------------
# Tests for _build_non_repetitive_question (helper, unchanged after Phase 8)
# ---------------------------------------------------------------------------

def test_build_non_repetitive_question_wraps_with_prefix() -> None:
    result = nodes_ai._build_non_repetitive_question(
        "Como voce esta hoje?", []
    )
    # With no recent questions any wrapper passes
    assert "Como voce esta hoje?" in result


def test_build_non_repetitive_question_avoids_all_wrappers() -> None:
    # If all wrappers have been used, fall back to the base question.
    recent = [
        "Queria te perguntar: Como voce esta hoje?",
        "So para acompanharmos melhor: Como voce esta hoje?",
        "Para eu registrar certinho: Como voce esta hoje?",
        "Me conta rapidinho: Como voce esta hoje?",
    ]
    result = nodes_ai._build_non_repetitive_question("Como voce esta hoje?", recent)
    assert result == "Como voce esta hoje?"


# ---------------------------------------------------------------------------
# Tests for GeminiDomainClient.generate_varied_question (replaces node tests)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_varied_question_uses_history_when_recent_interactions_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """generate_varied_question should call generate_content and return a non-empty string."""
    from app.ai.client_domain import GeminiDomainClient

    dummy = _DummyGeminiClient("Pergunta completamente diferente sobre tratamento")

    client = GeminiDomainClient.__new__(GeminiDomainClient)
    client.generate_content = dummy.generate_content

    result = await client.generate_varied_question(
        base_question="Como voce esta hoje?",
        previous_questions=["Outro tema qualquer"],
        patient_context={},
    )

    assert result is not None
    assert len(result) > 0
    # generate_content should have been called once
    assert len(dummy.calls) == 1


@pytest.mark.asyncio
async def test_generate_varied_question_applies_fallback_when_output_repeats_recent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When AI output is too similar to recent questions, a non-repetitive wrapper is applied."""
    from app.ai.client_domain import GeminiDomainClient

    dummy = _DummyGeminiClient("Como voce esta hoje?")

    client = GeminiDomainClient.__new__(GeminiDomainClient)
    client.generate_content = dummy.generate_content

    result = await client.generate_varied_question(
        base_question="Como voce esta hoje?",
        previous_questions=["Como voce esta hoje?"],
        patient_context={},
    )

    # The output should not be the exact same as the recent question
    assert result != "Como voce esta hoje?"
    assert "Como voce esta hoje?" in result


@pytest.mark.asyncio
async def test_generate_varied_question_keeps_output_when_not_repetitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When AI output is sufficiently different, it is returned unchanged."""
    from app.ai.client_domain import GeminiDomainClient

    dummy = _DummyGeminiClient("Como voce se sentiu hoje durante o tratamento?")

    client = GeminiDomainClient.__new__(GeminiDomainClient)
    client.generate_content = dummy.generate_content

    result = await client.generate_varied_question(
        base_question="Como voce esta hoje?",
        previous_questions=["Como voce esta hoje?"],
        patient_context={},
    )

    assert result == "Como voce se sentiu hoje durante o tratamento?"
