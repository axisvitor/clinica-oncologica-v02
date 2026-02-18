"""
Security validation models and constants.

Contains:
- KeyStrengthResult: Result model for key strength analysis
- Security constants: Entropy requirements, patterns
"""

from typing import List
from pydantic import BaseModel, Field


class KeyStrengthResult(BaseModel):
    """
    Result of key strength analysis.

    Attributes:
        entropy_bits: Calculated Shannon entropy in bits
        is_valid: Whether key meets minimum security requirements
        issues: List of security issues detected
        recommendations: Suggested improvements
        strength_level: Categorization (weak/medium/strong/very_strong)
    """

    entropy_bits: float = Field(..., description="Shannon entropy in bits")
    is_valid: bool = Field(..., description="Meets minimum requirements")
    issues: List[str] = Field(default_factory=list, description="Security issues")
    recommendations: List[str] = Field(default_factory=list, description="Improvements")
    strength_level: str = Field(..., description="weak/medium/strong/very_strong")
    key_length: int = Field(..., description="Length of key in characters")
    has_placeholder: bool = Field(
        default=False, description="Contains placeholder text"
    )


# Minimum entropy requirements (in bits)
MIN_ENTROPY_PRODUCTION = 128  # ~19 random alphanumeric chars
MIN_ENTROPY_DEVELOPMENT = 64  # ~10 random alphanumeric chars
MIN_KEY_LENGTH = 32  # Minimum characters

# Common placeholder patterns
PLACEHOLDER_PATTERNS = [
    r"(?<![a-z0-9])change[\s_-]?this(?![a-z0-9])",
    r"(?<![a-z0-9])your[\s_-]?secret(?![a-z0-9])",
    r"(?<![a-z0-9])your[\s_-]?key(?![a-z0-9])",
    r"(?<![a-z0-9])replace[\s_-]?me(?![a-z0-9])",
    r"(?<![a-z0-9])todo(?![a-z0-9])",
    r"(?<![a-z0-9])x{8,}(?![a-z0-9])",
    r"(?<![a-z0-9])example(?![a-z0-9])",
    r"(?<![a-z0-9])test[\s_-]?key(?![a-z0-9])",
    r"(?<![a-z0-9])default(?![a-z0-9])",
    r"(?<![a-z0-9])password(?![a-z0-9])",
    r"(?<![a-z0-9])secret[\s_-]?key(?![a-z0-9])",
]


__all__ = [
    "KeyStrengthResult",
    "MIN_ENTROPY_PRODUCTION",
    "MIN_ENTROPY_DEVELOPMENT",
    "MIN_KEY_LENGTH",
    "PLACEHOLDER_PATTERNS",
]
