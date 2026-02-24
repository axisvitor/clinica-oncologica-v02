from __future__ import annotations

import re

from pydantic_ai import Agent, ModelRetry, ModelSettings, RunContext

from app.ai.agents.base import PIISafeAgent
from app.ai.agents.deps import AIDeps
from app.ai.agents.helpers import (
    _build_non_repetitive_question,
    _coerce_recent_interactions,
    _extract_recent_questions,
    _is_too_similar_to_recent,
    _replace_patient_name,
    build_question_variation_prompt,
)
from app.services.ai.guardrails import _BANNED_PATTERNS, _PROMPT_LEAK_MARKERS

_MIN_LENGTH = 3
_MAX_LENGTH = 1600
_ENDING_PUNCTUATION_PATTERN = re.compile(r"[.!?…][\"')\]]*$")

_variation_agent = Agent(
    model=None,
    output_type=str,
    deps_type=AIDeps,
    retries=1,
    output_retries=1,
    model_settings=ModelSettings(timeout=30.0),
    defer_model_check=True,
)


@_variation_agent.output_validator
def validate_variation_output(ctx: RunContext[AIDeps], result: str) -> str:
    del ctx
    text = (result or "").strip()

    if len(text) < _MIN_LENGTH:
        raise ModelRetry("Output too short -- regenerate")
    if len(text) > _MAX_LENGTH:
        raise ModelRetry("Output too long -- regenerate")

    for pattern in _BANNED_PATTERNS:
        if re.search(pattern, text):
            raise ModelRetry("Banned pattern in output -- regenerate")

    lowered = text.lower()
    for marker in _PROMPT_LEAK_MARKERS:
        if marker.lower() in lowered:
            raise ModelRetry("Prompt echo detected -- regenerate")

    if not _ENDING_PUNCTUATION_PATTERN.search(text.rstrip()):
        text = f"{text.rstrip()}."

    return text


class VariationAgent(PIISafeAgent):
    _agent = _variation_agent

    async def vary(
        self,
        base_question: str,
        previous_questions: list,
        patient_context: dict,
        ai_instructions: str | None,
        deps: AIDeps,
    ) -> str:
        context = patient_context or {}
        patient_name = context.get("patient_name") or context.get("name") or ""
        recent_interactions = _coerce_recent_interactions(
            context.get("recent_interactions"),
            fallback_history=previous_questions or [],
        )
        recent_questions = _extract_recent_questions(
            recent_interactions,
            previous_questions or [],
        )
        question_with_name = _replace_patient_name(base_question, patient_name)
        prompt = build_question_variation_prompt(
            base_question=question_with_name,
            ai_instructions=ai_instructions,
            recent_interactions=recent_interactions,
        )
        output = await self._safe_run(prompt, deps, operation="variation")
        if _is_too_similar_to_recent(output, recent_questions):
            output = _build_non_repetitive_question(base_question, recent_questions)
        return output
