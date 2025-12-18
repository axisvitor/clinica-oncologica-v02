"""
Character distribution analysis for security keys.

Analyzes the diversity and distribution of characters in keys.
"""


def analyze_character_distribution(key: str) -> dict:
    """
    Analyze character type distribution in key.

    Args:
        key: Key to analyze

    Returns:
        Dict with character type counts
    """
    return {
        "lowercase": sum(1 for c in key if c.islower()),
        "uppercase": sum(1 for c in key if c.isupper()),
        "digits": sum(1 for c in key if c.isdigit()),
        "special": sum(1 for c in key if not c.isalnum()),
        "total": len(key),
    }


__all__ = ["analyze_character_distribution"]
