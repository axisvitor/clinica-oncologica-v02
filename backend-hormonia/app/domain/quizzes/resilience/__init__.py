"""Quiz link resilience and fallback management."""

from .link_resilience import (
    QuizLinkResilienceService,
    FailureReason,
    CircuitBreakerState,
    ResilienceMetrics,
)

__all__ = [
    "QuizLinkResilienceService",
    "FailureReason",
    "CircuitBreakerState",
    "ResilienceMetrics",
]
