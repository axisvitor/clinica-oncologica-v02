from __future__ import annotations

import re

from pydantic_ai import Agent, ModelRetry, ModelSettings, RunContext

from app.ai.agents.base import PIISafeAgent
from app.ai.agents.deps import AIDeps
from app.ai.agents.helpers import (
    _coerce_recent_interactions,
    _replace_patient_name,
    build_humanization_prompt,
)
from app.services.ai.guardrails import _BANNED_PATTERNS, _PROMPT_LEAK_MARKERS

_MIN_LENGTH = 6
_MAX_LENGTH = 1800
_ENDING_PUNCTUATION_PATTERN = re.compile(r"[.!?…][\"')\]]*$")

_humanize_agent = Agent(
    model=None,
    output_type=str,
    deps_type=AIDeps,
    retries=1,
    output_retries=1,
    model_settings=ModelSettings(timeout=30.0),
    defer_model_check=True,
)


@_humanize_agent.output_validator
def validate_humanize_output(ctx: RunContext[AIDeps], result: str) -> str:
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


class HumanizeAgent(PIISafeAgent):
    _agent = _humanize_agent

    async def humanize(
        self,
        template: str,
        patient_name: str,
        patient_context: dict,
        conversation_history: list,
        personalization_hints: list,
        ai_instructions: str | None,
        deps: AIDeps,
    ) -> str:
        del personalization_hints
        context = {**(patient_context or {}), "patient_name": patient_name}
        recent_interactions = _coerce_recent_interactions(
            context.get("recent_interactions"),
            fallback_history=conversation_history or [],
        )
        template_with_name = _replace_patient_name(template, patient_name)
        prompt = build_humanization_prompt(
            template=template_with_name,
            ai_instructions=ai_instructions,
            recent_interactions=recent_interactions,
        )
        return await self._safe_run(prompt, deps, operation="humanize")

    def humanize_sync(
        self,
        template: str,
        patient_name: str,
        patient_context: dict,
        conversation_history: list,
        personalization_hints: list,
        ai_instructions: str | None,
        deps: AIDeps,
    ) -> str:
        del personalization_hints
        context = {**(patient_context or {}), "patient_name": patient_name}
        recent_interactions = _coerce_recent_interactions(
            context.get("recent_interactions"),
            fallback_history=conversation_history or [],
        )
        template_with_name = _replace_patient_name(template, patient_name)
        prompt = build_humanization_prompt(
            template=template_with_name,
            ai_instructions=ai_instructions,
            recent_interactions=recent_interactions,
        )
        return self._safe_run_sync(prompt, deps, operation="humanize")
