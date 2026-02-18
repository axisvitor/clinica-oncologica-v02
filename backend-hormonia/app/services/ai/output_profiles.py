"""
Centralized output guardrail profiles for Gemini generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from app.services.ai.guardrails import OutputKind


@dataclass(frozen=True)
class OutputProfile:
    """Guardrail profile used by GeminiClient.generate_content."""

    name: str
    output_kind: OutputKind
    min_length: int = 3
    max_length: int = 1600
    required_keys: Tuple[str, ...] = ()
    require_ending_punctuation: bool = False
    allow_placeholders: bool = False
    guardrail_retries: int = 2

    def required_keys_iterable(self) -> Optional[Iterable[str]]:
        return self.required_keys or None


MESSAGE_STANDARD = OutputProfile(
    name="message_standard",
    output_kind=OutputKind.MESSAGE,
    min_length=3,
    max_length=1600,
    require_ending_punctuation=True,
    allow_placeholders=True,
    guardrail_retries=2,
)

MESSAGE_HUMANIZED = OutputProfile(
    name="message_humanized",
    output_kind=OutputKind.MESSAGE,
    min_length=6,
    max_length=1800,
    require_ending_punctuation=True,
    allow_placeholders=True,
    guardrail_retries=2,
)

JSON_SENTIMENT = OutputProfile(
    name="json_sentiment",
    output_kind=OutputKind.JSON,
    min_length=10,
    max_length=2400,
    required_keys=(
        "sentiment",
        "confidence",
        "emotional_indicators",
        "medical_concerns",
        "requires_attention",
        "key_themes",
        "suggested_follow_up",
    ),
    guardrail_retries=2,
)

JSON_RISK = OutputProfile(
    name="json_risk",
    output_kind=OutputKind.JSON,
    min_length=10,
    max_length=3200,
    required_keys=(
        "risk_level",
        "risk_score",
        "risk_factors",
        "protective_factors",
        "recommendations",
        "trend",
        "confidence",
    ),
    guardrail_retries=2,
)

JSON_QUALITY = OutputProfile(
    name="json_quality",
    output_kind=OutputKind.JSON,
    min_length=10,
    max_length=2800,
    required_keys=(
        "quality_score",
        "readability_score",
        "empathy_score",
        "professionalism_score",
        "clarity_score",
        "suggestions",
        "strengths",
    ),
    guardrail_retries=2,
)

JSON_INSIGHTS = OutputProfile(
    name="json_insights",
    output_kind=OutputKind.JSON,
    min_length=10,
    max_length=5000,
    required_keys=(
        "overall_status",
        "risk_level",
        "adherence_score",
        "key_insights",
        "alerts",
        "engagement_metrics",
        "sentiment_trends",
    ),
    guardrail_retries=2,
)

JSON_RECOMMENDATIONS = OutputProfile(
    name="json_recommendations",
    output_kind=OutputKind.JSON,
    min_length=10,
    max_length=2400,
    required_keys=("recommendations",),
    guardrail_retries=2,
)


_PROFILES: Dict[str, OutputProfile] = {
    profile.name: profile
    for profile in (
        MESSAGE_STANDARD,
        MESSAGE_HUMANIZED,
        JSON_SENTIMENT,
        JSON_RISK,
        JSON_QUALITY,
        JSON_INSIGHTS,
        JSON_RECOMMENDATIONS,
    )
}


def resolve_output_profile(profile: OutputProfile | str | None) -> OutputProfile | None:
    """Resolve profile objects or profile names into OutputProfile."""
    if profile is None:
        return None
    if isinstance(profile, OutputProfile):
        return profile
    key = str(profile).strip().lower()
    try:
        return _PROFILES[key]
    except KeyError as exc:
        available = ", ".join(sorted(_PROFILES))
        raise ValueError(f"Unknown output profile '{profile}'. Available: {available}") from exc


def list_output_profiles() -> Tuple[str, ...]:
    """Return available profile names (useful for debugging/tests)."""
    return tuple(sorted(_PROFILES.keys()))
