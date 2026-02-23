"""AI helper functions for prompt building and output parsing.

Node wrappers removed in Phase 8 (AI-03) — logic moved to GeminiDomainClient and direct callers.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from app.schemas.ai_schemas import AIResponseValidation

from .prompts import (
    _replace_patient_name,
    build_empathetic_prompt,
    build_humanization_prompt,
    build_question_variation_prompt,
    build_sentiment_prompt,
)

logger = logging.getLogger(__name__)


_WHITESPACE_RE = re.compile(r"\s+")


def _coerce_recent_interactions(
    recent_interactions: Any,
    *,
    fallback_history: Any = None,
    max_items: int = 5,
) -> list[Dict[str, str]] | None:
    """Normalize recent interactions to the prompt shape used by builders."""
    normalized: list[Dict[str, str]] = []

    if isinstance(recent_interactions, list):
        for item in recent_interactions:
            if isinstance(item, dict):
                question = str(item.get("question") or item.get("text") or "").strip()
                answer = str(item.get("answer") or item.get("response") or "").strip()
                if question or answer:
                    normalized.append({"question": question, "answer": answer})
            elif isinstance(item, str):
                question = item.strip()
                if question:
                    normalized.append({"question": question, "answer": ""})

    if not normalized and isinstance(fallback_history, list):
        for item in fallback_history:
            question = str(item).strip()
            if question:
                normalized.append({"question": question, "answer": ""})

    if not normalized:
        return None
    return normalized[-max_items:]


def _normalize_phrase(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip().lower())


def _extract_recent_questions(
    recent_interactions: list[dict[str, str]] | None,
    fallback_history: Any,
) -> list[str]:
    recent_questions: list[str] = []

    if isinstance(recent_interactions, list):
        for item in recent_interactions:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or item.get("text") or "").strip()
            if question:
                recent_questions.append(question)

    if isinstance(fallback_history, list):
        for item in fallback_history:
            if isinstance(item, dict):
                question = str(item.get("question") or item.get("text") or "").strip()
            else:
                question = str(item or "").strip()
            if question:
                recent_questions.append(question)

    # Keep only the most recent entries and preserve order.
    return recent_questions[-8:]


def _is_too_similar_to_recent(candidate: str, recent_questions: list[str]) -> bool:
    normalized_candidate = _normalize_phrase(candidate)
    if not normalized_candidate:
        return True

    candidate_words = set(normalized_candidate.split())
    for recent in recent_questions:
        normalized_recent = _normalize_phrase(recent)
        if not normalized_recent:
            continue
        if normalized_candidate == normalized_recent:
            return True
        recent_words = set(normalized_recent.split())
        if not candidate_words or not recent_words:
            continue
        overlap = len(candidate_words & recent_words) / max(
            len(candidate_words), len(recent_words)
        )
        if overlap >= 0.88:
            return True
    return False


def _build_non_repetitive_question(
    base_question: str,
    recent_questions: list[str],
) -> str:
    question = (base_question or "").strip()
    if not question:
        return question

    wrappers = (
        "Queria te perguntar: {question}",
        "So para acompanharmos melhor: {question}",
        "Para eu registrar certinho: {question}",
        "Me conta rapidinho: {question}",
    )
    normalized_recent = {_normalize_phrase(item) for item in recent_questions if item}

    for wrapper in wrappers:
        candidate = wrapper.format(question=question).strip()
        if _normalize_phrase(candidate) not in normalized_recent:
            return candidate

    return question


def _get_gemini_client():
    from app.ai.client import get_gemini_client

    return get_gemini_client()


def _parse_sentiment_analysis(text: str) -> Dict[str, Any]:
    from json import JSONDecodeError

    try:
        parsed = json.loads(text)
    except (JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON in sentiment analysis: {exc}") from exc

    validated = AIResponseValidation.validate_sentiment(parsed)
    return validated.model_dump()
