"""LangGraph AI processing nodes that call the Gemini client."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from app.services.ai.guardrails import OutputKind
from app.services.ai.output_profiles import (
    JSON_SENTIMENT,
    MESSAGE_HUMANIZED,
    MESSAGE_STANDARD,
)
from app.schemas.ai_schemas import AIResponseValidation

from .ai_state import AIState, validate_ai_state
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


def _validate_ai_state_for_node(
    state: AIState,
    *,
    required_keys: tuple[str, ...],
    node_name: str,
) -> AIState:
    try:
        return validate_ai_state(state, required_keys=required_keys)
    except (TypeError, ValueError):
        logger.exception("AI state validation failed in %s", node_name)
        raise


def _parse_sentiment_analysis(text: str) -> Dict[str, Any]:
    from json import JSONDecodeError

    try:
        parsed = json.loads(text)
    except (JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON in sentiment analysis: {exc}") from exc

    validated = AIResponseValidation.validate_sentiment(parsed)
    return validated.model_dump()


async def humanize_node(state: AIState) -> AIState:
    """Node for humanizing a template message."""
    state = _validate_ai_state_for_node(
        state,
        required_keys=("template",),
        node_name="humanize_node",
    )
    client = _get_gemini_client()
    context = state.get("context", {}) or {}
    patient_name = context.get("patient_name") or context.get("name") or "Paciente"
    recent_interactions = _coerce_recent_interactions(
        context.get("recent_interactions"),
        fallback_history=state.get("history"),
    )
    template = state.get("template", "") or ""
    template = _replace_patient_name(template, patient_name)
    metadata = state.get("metadata") or {}
    prompt = build_humanization_prompt(
        template=template,
        ai_instructions=metadata.get("ai_instructions"),
        recent_interactions=recent_interactions,
    )
    output = await client.generate_content(
        prompt,
        profile=MESSAGE_HUMANIZED,
    )
    return {**state, "output": output, "confidence": 0.9}


async def sentiment_node(state: AIState) -> AIState:
    """Node for analyzing patient response sentiment."""
    state = _validate_ai_state_for_node(
        state,
        required_keys=("input_text",),
        node_name="sentiment_node",
    )
    client = _get_gemini_client()
    context = state.get("context", {}) or {}
    from app.ai.context_compactor import compact_patient_context

    context_snapshot = compact_patient_context(context)
    prompt = build_sentiment_prompt(
        response=state.get("input_text", ""),
        context_snapshot=context_snapshot,
    )
    analysis_text = await client.generate_content(
        prompt,
        profile=JSON_SENTIMENT,
    )
    analysis = _parse_sentiment_analysis(analysis_text)
    return {**state, "output": analysis, "confidence": analysis.get("confidence", 0.0)}


async def question_variation_node(state: AIState) -> AIState:
    """Node for question variation."""
    state = _validate_ai_state_for_node(
        state,
        required_keys=("input_text",),
        node_name="question_variation_node",
    )
    client = _get_gemini_client()
    context = state.get("context", {}) or {}
    patient_name = context.get("patient_name") or context.get("name") or ""
    recent_interactions = _coerce_recent_interactions(
        context.get("recent_interactions"),
        fallback_history=state.get("history"),
    )
    recent_questions = _extract_recent_questions(
        recent_interactions,
        state.get("history"),
    )
    metadata = state.get("metadata") or {}
    base_question = _replace_patient_name(state.get("input_text", "") or "", patient_name)
    prompt = build_question_variation_prompt(
        base_question=base_question,
        ai_instructions=metadata.get("ai_instructions"),
        recent_interactions=recent_interactions,
    )
    output = await client.generate_content(
        prompt,
        profile=MESSAGE_STANDARD,
    )
    if _is_too_similar_to_recent(output, recent_questions):
        output = _build_non_repetitive_question(base_question, recent_questions)
    return {**state, "output": output, "confidence": 0.9}


async def empathetic_follow_up_node(state: AIState) -> AIState:
    """Node for empathetic follow-up generation."""
    state = _validate_ai_state_for_node(
        state,
        required_keys=("input_text",),
        node_name="empathetic_follow_up_node",
    )
    client = _get_gemini_client()
    context = state.get("context", {}) or {}
    from app.ai.context_compactor import compact_patient_context

    context_snapshot = compact_patient_context(context)
    metadata = state.get("metadata") or {}
    prompt = build_empathetic_prompt(
        patient_response=state.get("input_text", "") or "",
        conversation_history=state.get("history", []) or [],
        context_snapshot=context_snapshot,
        examples=metadata.get("few_shot_examples") or [],
        allow_questions=bool(metadata.get("allow_questions", False)),
        day_complete=bool(metadata.get("day_complete", False)),
    )
    output = await client.generate_content(
        prompt,
        profile=MESSAGE_HUMANIZED,
    )
    return {**state, "output": output, "confidence": 0.9}


async def generate_node(state: AIState) -> AIState:
    """Node for generic content generation."""
    state = _validate_ai_state_for_node(
        state,
        required_keys=("input_text",),
        node_name="generate_node",
    )
    client = _get_gemini_client()
    # Extract parameters
    prompt = state.get("input_text", "")
    output_kind_str = state.get("output_kind", "message")

    try:
        output_kind = OutputKind(output_kind_str)
    except ValueError:
        output_kind = OutputKind.MESSAGE

    metadata = dict(state.get("metadata") or {})
    profile = metadata.pop("profile", None)

    # Delegate to GeminiClient
    output = await client.generate_content(
        prompt=prompt,
        profile=profile,
        output_kind=output_kind,
        **metadata
    )

    return {**state, "output": output}
