"""
Secure key generation utilities.

Provides cryptographically secure random key generation.
"""

import secrets


def generate_secure_key(length: int = 32) -> str:
    """
    Generate cryptographically secure random key.

    Uses secrets module for CSPRNG (Cryptographically Secure PRNG).

    Args:
        length: Desired length in characters (default: 32)

    Returns:
        URL-safe base64 encoded random key

    Example:
        >>> key = generate_secure_key(32)
        >>> result = validate_key_strength(key)
        >>> assert result.is_valid
    """
    return secrets.token_urlsafe(length)


def generate_secure_secret(length: int = 32) -> str:
    """
    Generate a cryptographically secure random secret.

    This is a helper function that can be used in development/testing
    or for generating migration secrets. For production, secrets should
    be generated externally and injected via environment variables.

    Args:
        length: Number of random bytes to generate (default: 32)
                The output will be longer due to URL-safe base64 encoding

    Returns:
        str: URL-safe base64-encoded random string

    Example:
        >>> secret = generate_secure_secret(32)
        >>> len(secret) >= 32
        True
        >>> secret == generate_secure_secret(32)  # Should be different
        False

    Note:
        This function uses secrets.token_urlsafe() which is cryptographically
        secure and suitable for password, account authentication, security tokens,
        and related secrets.
    """
    return secrets.token_urlsafe(length)


__all__ = [
    'generate_secure_key',
    'generate_secure_secret',
]
