from __future__ import annotations

import re

from pydantic_ai import Agent, ModelRetry, ModelSettings, RunContext

from app.ai.agents.base import PIISafeAgent
from app.ai.agents.deps import AIDeps
from app.ai.agents.helpers import build_empathetic_prompt
from app.ai.context_compactor import compact_patient_context
from app.services.ai.guardrails import _BANNED_PATTERNS, _PROMPT_LEAK_MARKERS

_MIN_LENGTH = 6
_MAX_LENGTH = 1800
_ENDING_PUNCTUATION_PATTERN = re.compile(r"[.!?…][\"')\]]*$")

_empathy_agent = Agent(
    model=None,
    output_type=str,
    deps_type=AIDeps,
    retries=1,
    output_retries=1,
    model_settings=ModelSettings(timeout=30.0),
    defer_model_check=True,
)


@_empathy_agent.output_validator
def validate_empathy_output(ctx: RunContext[AIDeps], result: str) -> str:
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


class EmpathyAgent(PIISafeAgent):
    _agent = _empathy_agent

    async def follow_up(
        self,
        patient_response: str,
        conversation_history: list,
        patient_context: dict,
        few_shot_examples: list | None,
        deps: AIDeps,
    ) -> str:
        context_snapshot = compact_patient_context(patient_context or {})
        prompt = build_empathetic_prompt(
            patient_response=patient_response,
            conversation_history=conversation_history or [],
            context_snapshot=context_snapshot,
            examples=few_shot_examples or [],
            allow_questions=False,
            day_complete=False,
        )
        return await self._safe_run(prompt, deps, operation="empathy")

    def follow_up_sync(
        self,
        patient_response: str,
        conversation_history: list,
        patient_context: dict,
        few_shot_examples: list | None,
        deps: AIDeps,
    ) -> str:
        context_snapshot = compact_patient_context(patient_context or {})
        prompt = build_empathetic_prompt(
            patient_response=patient_response,
            conversation_history=conversation_history or [],
            context_snapshot=context_snapshot,
            examples=few_shot_examples or [],
            allow_questions=False,
            day_complete=False,
        )
        return self._safe_run_sync(prompt, deps, operation="empathy")
