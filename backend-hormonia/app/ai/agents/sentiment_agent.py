from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent, ModelRetry, ModelSettings, PromptedOutput, RunContext

from app.ai.agents.base import PIISafeAgent
from app.ai.agents.deps import AIDeps
from app.services.ai.guardrails import _BANNED_PATTERNS, _PROMPT_LEAK_MARKERS


class SentimentResult(BaseModel):
    sentiment: str = "neutral"
    confidence: float = 0.5
    emotional_indicators: list[str] = Field(default_factory=list)
    medical_concerns: list[str] = Field(default_factory=list)
    requires_attention: bool = False
    key_themes: list[str] = Field(default_factory=list)
    suggested_follow_up: str = "standard"

    @field_validator("sentiment", mode="before")
    @classmethod
    def normalize_sentiment(cls, value: Any) -> str:
        if not isinstance(value, str):
            return "neutral"
        normalized = value.strip().lower()
        allowed = {"positive", "negative", "neutral", "concerning"}
        return normalized if normalized in allowed else "neutral"

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> float:
        if value is None:
            return 0.5
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, numeric))

    @field_validator("medical_concerns", mode="before")
    @classmethod
    def normalize_medical_concerns(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, bool):
            return ["possible_medical_concern"] if value else []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, list):
            normalized: list[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    normalized.append(text)
            return normalized
        return []


_sentiment_agent = Agent(
    model=None,
    output_type=PromptedOutput(SentimentResult),
    deps_type=AIDeps,
    retries=1,
    output_retries=1,
    model_settings=ModelSettings(timeout=30.0),
    defer_model_check=True,
)


@_sentiment_agent.output_validator
def validate_sentiment_output(
    ctx: RunContext[AIDeps],
    result: SentimentResult,
) -> SentimentResult:
    del ctx
    for pattern in _BANNED_PATTERNS:
        for value in [result.suggested_follow_up, *result.key_themes]:
            if re.search(pattern, str(value)):
                raise ModelRetry("Output contains banned pattern -- regenerate")

    suggested_follow_up = result.suggested_follow_up or ""
    for marker in _PROMPT_LEAK_MARKERS:
        if marker.lower() in suggested_follow_up.lower():
            raise ModelRetry("Output contains banned pattern -- regenerate")

    return result


class SentimentAgent(PIISafeAgent):
    _agent = _sentiment_agent

    async def analyze(
        self,
        response: str,
        context_snapshot: dict,
        deps: AIDeps,
    ) -> SentimentResult:
        from app.ai.agents.helpers import build_sentiment_prompt

        prompt = build_sentiment_prompt(
            response=response,
            context_snapshot=context_snapshot or {},
        )
        return await self._safe_run(prompt, deps, operation="sentiment")
