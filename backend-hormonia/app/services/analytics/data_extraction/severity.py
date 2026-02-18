"""
Shared concern severity helpers.
"""

from __future__ import annotations

from app.services.ai import ConcernLevel


def concern_level_rank(level: ConcernLevel) -> int:
    """Rank concern levels for comparison."""
    ranks = {
        ConcernLevel.LOW: 1,
        ConcernLevel.MEDIUM: 2,
        ConcernLevel.HIGH: 3,
        ConcernLevel.CRITICAL: 4,
    }
    return ranks.get(level, 1)


def concern_level_from_score(severity_score: int) -> ConcernLevel:
    """Map numeric severity score to concern level."""
    if severity_score >= 9:
        return ConcernLevel.CRITICAL
    if severity_score >= 7:
        return ConcernLevel.HIGH
    if severity_score >= 4:
        return ConcernLevel.MEDIUM
    return ConcernLevel.LOW

