"""
Placeholder detection for security keys.

Detects common placeholder patterns that indicate non-production keys.
"""

import re
from .models import PLACEHOLDER_PATTERNS


def contains_placeholder(key: str) -> bool:
    """
    Check if key contains common placeholder patterns.

    Args:
        key: Key to check

    Returns:
        True if placeholder detected
    """
    key_lower = key.lower()

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, key_lower):
            return True

    return False


__all__ = ['contains_placeholder']
