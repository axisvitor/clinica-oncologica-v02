"""
Shannon entropy calculations for cryptographic key analysis.

Provides entropy calculation functions for measuring key randomness.
"""

import math
from collections import Counter


def calculate_shannon_entropy(data: str) -> float:
    """
    Calculate Shannon entropy in bits (total entropy, not per character).

    Shannon entropy measures the randomness/unpredictability of data.
    Higher values indicate more randomness and stronger keys.

    Formula: H(X) = -Σ P(xi) * log2(P(xi)) * length

    Args:
        data: String to analyze

    Returns:
        Entropy in bits (0 to ~8 * len(data) for perfectly random data)

    Example:
        >>> calculate_shannon_entropy("aaaaa")  # Low entropy
        0.0
        >>> calculate_shannon_entropy("abcde")  # Higher entropy
        ~11.6 bits
        >>> calculate_shannon_entropy(secrets.token_urlsafe(32))
        ~250+ bits (strong)
    """
    if not data:
        return 0.0

    # Count character frequencies
    counter = Counter(data)
    length = len(data)

    # Calculate Shannon entropy (per character)
    entropy_per_char = 0.0
    for count in counter.values():
        probability = count / length
        if probability > 0:
            entropy_per_char -= probability * math.log2(probability)

    # Return total entropy (bits per char * length)
    return entropy_per_char * length


def calculate_entropy(data: str) -> float:
    """
    Calculate Shannon entropy per character (backward compatibility).

    This function maintains backward compatibility with existing code
    that expects entropy per character rather than total bits.

    Args:
        data: String to calculate entropy for

    Returns:
        float: Entropy in bits per character (0.0 to ~8.0)

    Note:
        For new code, use calculate_shannon_entropy() for total bits
        or validate_key_strength() for comprehensive analysis.
    """
    if not data:
        return 0.0

    # Count frequency of each character
    counter = Counter(data)
    length = len(data)

    # Calculate Shannon entropy per character
    entropy = -sum(
        (count / length) * math.log2(count / length) for count in counter.values()
    )

    return entropy


__all__ = [
    "calculate_shannon_entropy",
    "calculate_entropy",
]
