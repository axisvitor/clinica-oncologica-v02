"""
Security Validation Utilities

This module provides validation functions for security-critical configuration values
such as CSRF secrets, JWT secrets, and other cryptographic keys.

Includes Shannon entropy calculation for cryptographic strength validation.

Usage:
    from app.utils.security_validation import validate_csrf_secret, calculate_entropy

    try:
        validate_csrf_secret(csrf_secret)
    except ValueError as e:
        logger.error(f"CSRF secret validation failed: {e}")
        raise
"""

import secrets
import re
import math
import logging
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)


def calculate_entropy(data: str) -> float:
    """
    Calculate Shannon entropy of a string to measure randomness.

    Shannon entropy measures the unpredictability/randomness of data.
    Higher entropy indicates more secure secrets with better randomness.

    Args:
        data: String to calculate entropy for

    Returns:
        float: Entropy in bits per character (0.0 to ~8.0 for byte strings)

    Examples:
        >>> calculate_entropy("aaaaaaaaaa")  # All same char
        0.0
        >>> calculate_entropy("abcdefghij")  # Low entropy
        3.321...
        >>> calculate_entropy("aB3$xY9@zK")  # High entropy with mixed chars
        ~4.5
        >>> calculate_entropy(secrets.token_urlsafe(32))  # Excellent entropy
        ~5.9

    Entropy Thresholds:
        - 0.0-3.0: REJECTED (predictable patterns)
        - 3.0-4.0: REJECTED (insufficient randomness)
        - 4.0-5.0: ACCEPTABLE (minimum for secrets)
        - 5.0+: EXCELLENT (cryptographically strong)

    Maximum Theoretical Entropy by Character Set:
        - Lowercase only: ~4.7 bits/char
        - Alphanumeric: ~5.95 bits/char
        - URL-safe base64: ~6.0 bits/char

    Algorithm:
        Shannon Entropy = -Σ(P(x) * log2(P(x)))
        where P(x) is the probability of character x appearing

    Security Note:
        This function is used to validate that secrets have sufficient
        randomness to resist brute-force and pattern-based attacks.
        Minimum recommended entropy for production secrets: 4.0 bits/char
    """
    if not data:
        return 0.0

    # Count frequency of each character
    counter = Counter(data)
    length = len(data)

    # Calculate Shannon entropy
    entropy = -sum(
        (count / length) * math.log2(count / length)
        for count in counter.values()
    )

    return entropy


def validate_csrf_secret(csrf_secret: Optional[str], log_validation: bool = True) -> None:
    """
    Validate CSRF secret key strength with Shannon entropy checking.

    This function ensures that CSRF secrets meet minimum security standards:
    - Must be present (not None or empty)
    - Must be at least 32 characters long
    - Must not be a common placeholder value
    - Must have minimum 4.0 bits/char Shannon entropy (cryptographic strength)
    - Must not be a sequential pattern
    - Must not be a known weak secret

    Args:
        csrf_secret: The CSRF secret key to validate
        log_validation: Whether to log validation results (default: True)
                       Logging NEVER includes the actual secret value

    Raises:
        ValueError: If the secret key does not meet security requirements

    Examples:
        >>> validate_csrf_secret("my-secret")  # Too short
        ValueError: CSRF_SECRET_KEY must be at least 32 characters (got 9)

        >>> validate_csrf_secret("change_this_secret_key_in_production_ok")  # Placeholder
        ValueError: CSRF_SECRET_KEY appears to be a placeholder

        >>> validate_csrf_secret("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")  # Low entropy
        ValueError: CSRF_SECRET_KEY has insufficient entropy: 0.00 bits/char < 4.0

        >>> validate_csrf_secret(secrets.token_urlsafe(32))  # Valid!
        # Logs: CSRF secret validation passed: length=43, entropy=5.95 bits/char

    Security Notes:
        - Use secrets.token_urlsafe(32) to generate cryptographically secure keys
        - Never commit secrets to version control
        - Rotate secrets periodically in production (recommended: every 90 days)
        - Use different secrets for different environments
        - Minimum entropy: 4.0 bits/char (enforced)
        - Good entropy: 4.5-5.5 bits/char (recommended)
        - Excellent entropy: 5.5+ bits/char (cryptographically strong)
    """
    # Check 1: Secret must exist
    if not csrf_secret:
        raise ValueError(
            "CSRF_SECRET_KEY is required for CSRF protection. "
            "Generate a secure secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Check 2: Minimum length (32 characters recommended)
    min_length = 32
    if len(csrf_secret) < min_length:
        raise ValueError(
            f"CSRF_SECRET_KEY must be at least {min_length} characters (got {len(csrf_secret)}). "
            "Generate a strong secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Check 3: Not a common placeholder
    # Common placeholder patterns that developers might use
    placeholder_patterns = [
        'change_this',
        'your_secret',
        'secret_key',
        'replace_me',
        'changeme',
        'placeholder',
        'example',
        'test_secret',
        'dev_secret',
        'local_secret',
    ]

    csrf_lower = csrf_secret.lower()
    for pattern in placeholder_patterns:
        if pattern in csrf_lower:
            raise ValueError(
                f"CSRF_SECRET_KEY appears to be a placeholder (contains '{pattern}'). "
                "Generate a cryptographically secure secret with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

    # Check 4: Simple entropy check (detect obvious patterns)
    # Check for all same character (e.g., "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    if len(set(csrf_secret)) < 8:
        raise ValueError(
            "CSRF_SECRET_KEY has insufficient entropy (too few unique characters). "
            "Generate a random secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Check 5: Not a sequential pattern (e.g., "12345678901234567890123456789012")
    if re.match(r'^(0123456789|abcdefghijklmnopqrstuvwxyz|ABCDEFGHIJKLMNOPQRSTUVWXYZ)+$', csrf_secret):
        raise ValueError(
            "CSRF_SECRET_KEY appears to be a sequential pattern. "
            "Generate a random secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Check 6: Shannon entropy validation (NEW - cryptographic strength)
    # Minimum entropy threshold: 4.0 bits per character
    # This ensures the secret has sufficient randomness to resist attacks
    min_entropy = 4.0
    entropy = calculate_entropy(csrf_secret)

    if entropy < min_entropy:
        raise ValueError(
            f"CSRF_SECRET_KEY has insufficient entropy: {entropy:.2f} bits/char < {min_entropy}. "
            "This indicates the secret is not random enough for cryptographic use. "
            "Generate a cryptographically secure secret with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Check 7: Not a known weak/common secret
    # List of commonly used weak secrets that should never be accepted
    weak_secrets = [
        'changeme',
        'secret',
        'password',
        'admin',
        'root',
        '12345678901234567890123456789012',  # Sequential numbers
        'abcdefghijklmnopqrstuvwxyz123456',  # Sequential alphabet
    ]

    if csrf_secret in weak_secrets:
        raise ValueError(
            "CSRF_SECRET_KEY is a known weak/common value that appears in password dictionaries. "
            "Generate a cryptographically secure secret with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Success: Log validation metrics (WITHOUT exposing the secret itself)
    if log_validation:
        logger.info(
            f"✅ CSRF secret validation passed: "
            f"length={len(csrf_secret)}, "
            f"entropy={entropy:.2f} bits/char, "
            f"unique_chars={len(set(csrf_secret))}"
        )


def validate_secret_key(secret_key: Optional[str], key_name: str = "SECRET_KEY", min_length: int = 32) -> None:
    """
    Generic validation for any secret key (JWT, encryption, session, etc.)

    Args:
        secret_key: The secret key to validate
        key_name: Name of the key for error messages (e.g., "JWT_SECRET_KEY")
        min_length: Minimum required length (default: 32)

    Raises:
        ValueError: If the secret key does not meet security requirements

    Example:
        >>> validate_secret_key("my-jwt-secret", "JWT_SECRET_KEY", min_length=32)
        ValueError: JWT_SECRET_KEY must be at least 32 characters (got 13)
    """
    if not secret_key:
        raise ValueError(
            f"{key_name} is required. "
            f"Generate with: python -c 'import secrets; print(secrets.token_urlsafe({min_length}))'"
        )

    if len(secret_key) < min_length:
        raise ValueError(
            f"{key_name} must be at least {min_length} characters (got {len(secret_key)}). "
            f"Generate with: python -c 'import secrets; print(secrets.token_urlsafe({min_length}))'"
        )

    # Check for placeholder patterns
    placeholder_keywords = ['change', 'your_', 'replace', 'example', 'test', 'placeholder']
    key_lower = secret_key.lower()
    for keyword in placeholder_keywords:
        if keyword in key_lower:
            raise ValueError(
                f"{key_name} appears to be a placeholder value (contains '{keyword}'). "
                f"Generate with: python -c 'import secrets; print(secrets.token_urlsafe({min_length}))'"
            )


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


def validate_webhook_secret(webhook_secret: Optional[str], key_name: str = "WEBHOOK_SECRET") -> None:
    """
    Validate webhook secret key strength.

    Webhook secrets are used for HMAC signature validation and must be
    cryptographically secure to prevent signature forgery attacks.

    Args:
        webhook_secret: The webhook secret key to validate
        key_name: Name of the key for error messages (e.g., "EVOLUTION_WEBHOOK_SECRET")

    Raises:
        ValueError: If the secret key does not meet security requirements

    Example:
        >>> validate_webhook_secret("my-webhook-secret", "EVOLUTION_WEBHOOK_SECRET")
        ValueError: EVOLUTION_WEBHOOK_SECRET must be at least 32 characters

        >>> validate_webhook_secret(secrets.token_urlsafe(32), "EVOLUTION_WEBHOOK_SECRET")
        # Success - no exception raised

    Security Requirements:
        - Minimum 32 characters
        - Not a placeholder value
        - Cryptographically random (use secrets.token_urlsafe)
        - Different from other secrets (JWT, CSRF, etc.)
    """
    # Use generic validation with minimum 32 characters
    validate_secret_key(webhook_secret, key_name=key_name, min_length=32)

    # Additional webhook-specific validation
    if webhook_secret:
        # Check for common webhook placeholder patterns
        webhook_placeholders = ['webhook', 'evolution', 'whatsapp']
        secret_lower = webhook_secret.lower()

        for pattern in webhook_placeholders:
            if pattern in secret_lower and any(
                placeholder in secret_lower
                for placeholder in ['secret', 'key', 'change', 'replace']
            ):
                raise ValueError(
                    f"{key_name} appears to be a placeholder value (contains '{pattern}'). "
                    "Generate a cryptographically secure secret with: "
                    "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

        # Calculate entropy
        entropy = calculate_entropy(webhook_secret)
        min_entropy = 4.0

        if entropy < min_entropy:
            raise ValueError(
                f"{key_name} has insufficient entropy: {entropy:.2f} bits/char < {min_entropy}. "
                f"Generate a cryptographically secure secret with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        logger.info(
            f"✅ {key_name} validation passed: "
            f"length={len(webhook_secret)}, entropy={entropy:.2f} bits/char"
        )


def verify_hmac_signature(
    message: bytes,
    signature: str,
    secret_key: str,
    algorithm: str = 'sha256'
) -> bool:
    """
    Verify HMAC signature for webhook or API requests.

    This function performs constant-time comparison of HMAC signatures
    to prevent timing attacks.

    Args:
        message: Raw message bytes to verify
        signature: Hex-encoded HMAC signature to verify
        secret_key: Secret key used for HMAC generation
        algorithm: Hash algorithm (default: 'sha256')

    Returns:
        bool: True if signature is valid, False otherwise

    Example:
        >>> message = b'{"event": "webhook.received"}'
        >>> secret = "my-secret-key"
        >>> signature = generate_hmac_signature(message, secret)
        >>> verify_hmac_signature(message, signature, secret)
        True
        >>> verify_hmac_signature(message, "invalid-signature", secret)
        False

    Security:
        - Uses hmac.compare_digest for constant-time comparison
        - Prevents timing attacks on signature verification
        - Supports multiple hash algorithms (sha256, sha512, etc.)
    """
    import hmac
    import hashlib

    try:
        # Get hash algorithm
        hash_algo = getattr(hashlib, algorithm)

        # Compute expected signature
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            message,
            hash_algo
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(signature, expected_signature)

    except (AttributeError, TypeError) as e:
        logger.error(f"Error verifying HMAC signature: {e}")
        return False


def generate_hmac_signature(
    message: bytes,
    secret_key: str,
    algorithm: str = 'sha256'
) -> str:
    """
    Generate HMAC signature for message.

    Args:
        message: Raw message bytes
        secret_key: Secret key for HMAC
        algorithm: Hash algorithm (default: 'sha256')

    Returns:
        str: Hex-encoded HMAC signature

    Example:
        >>> message = b'{"event": "webhook.received"}'
        >>> signature = generate_hmac_signature(message, "my-secret")
        >>> len(signature)
        64  # SHA-256 produces 64 hex characters
    """
    import hmac
    import hashlib

    hash_algo = getattr(hashlib, algorithm)
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message,
        hash_algo
    )
    return signature.hexdigest()


__all__ = [
    'calculate_entropy',
    'validate_csrf_secret',
    'validate_secret_key',
    'validate_webhook_secret',
    'generate_secure_secret',
    'verify_hmac_signature',
    'generate_hmac_signature',
]
