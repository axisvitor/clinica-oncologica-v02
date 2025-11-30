"""
Security Key Validation Utilities

Provides entropy validation and strength analysis for cryptographic keys
to prevent weak/placeholder keys in production environments.

Security Issues Addressed:
- AUTH-001: Placeholder key detection (Severity 9.5/10)
- SECRET-002: Secret masking for logs (Severity 8.0/10)

Usage:
    from app.utils.security_validation import (
        validate_secret_entropy,
        validate_key_strength,
        mask_secret_for_logging
    )

    # Validate key entropy
    if not validate_secret_entropy(key, min_bits=128):
        raise ValueError("Key has insufficient entropy")

    # Get detailed analysis
    result = validate_key_strength(key, environment="production")
    if not result.is_valid:
        print(f"Issues: {result.issues}")
        print(f"Recommendations: {result.recommendations}")

    # Safe logging
    logger.info(f"Key: {mask_secret_for_logging(key)}")
"""

import secrets
import re
import math
import logging
from collections import Counter
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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
    has_placeholder: bool = Field(default=False, description="Contains placeholder text")


# Minimum entropy requirements (in bits)
MIN_ENTROPY_PRODUCTION = 128  # ~19 random alphanumeric chars
MIN_ENTROPY_DEVELOPMENT = 64  # ~10 random alphanumeric chars
MIN_KEY_LENGTH = 32  # Minimum characters

# Common placeholder patterns
PLACEHOLDER_PATTERNS = [
    r"change[\s_-]?this",
    r"your[\s_-]?secret",
    r"your[\s_-]?key",
    r"replace[\s_-]?me",
    r"todo",
    r"xxx+",
    r"example",
    r"test[\s_-]?key",
    r"default",
    r"password",
    r"secret[\s_-]?key",
    r"(abc|123)+",
]


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
        (count / length) * math.log2(count / length)
        for count in counter.values()
    )

    return entropy


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


def validate_secret_entropy(
    secret: str,
    min_bits: int = MIN_ENTROPY_PRODUCTION,
    allow_placeholder_in_dev: bool = False,
) -> bool:
    """
    Validate that secret key has minimum entropy.

    This is the primary validation function for security keys.

    Args:
        secret: Secret key to validate
        min_bits: Minimum required entropy in bits
        allow_placeholder_in_dev: If True, allow placeholders (dev mode only)

    Returns:
        True if secret meets minimum entropy requirement

    Raises:
        ValueError: If secret is empty or None

    Security Issue: AUTH-001
    """
    if not secret:
        raise ValueError("Secret cannot be empty")

    # Check for placeholders (unless explicitly allowed in dev)
    if not allow_placeholder_in_dev and contains_placeholder(secret):
        return False

    # Calculate and validate entropy
    entropy = calculate_shannon_entropy(secret)
    return entropy >= min_bits


def validate_key_strength(
    key: str,
    min_entropy: int = MIN_ENTROPY_PRODUCTION,
    environment: str = "production",
) -> KeyStrengthResult:
    """
    Comprehensive analysis of key strength.

    Performs multiple checks:
    - Shannon entropy calculation
    - Placeholder detection
    - Character distribution
    - Length requirements
    - Pattern detection

    Args:
        key: Key to analyze
        min_entropy: Minimum required entropy in bits
        environment: "production" or "development"

    Returns:
        KeyStrengthResult with detailed analysis

    Example:
        >>> result = validate_key_strength("CHANGE_THIS")
        >>> print(result.is_valid)
        False
        >>> print(result.issues)
        ['Contains placeholder text', ...]

    Security Issue: AUTH-001
    """
    issues: List[str] = []
    recommendations: List[str] = []

    # Basic validation
    if not key:
        return KeyStrengthResult(
            entropy_bits=0.0,
            is_valid=False,
            issues=["Key is empty"],
            recommendations=["Generate a random key using secrets.token_urlsafe(32)"],
            strength_level="none",
            key_length=0,
        )

    key_length = len(key)
    entropy_bits = calculate_shannon_entropy(key)
    has_placeholder = contains_placeholder(key)
    char_dist = analyze_character_distribution(key)

    # Check for placeholder text
    if has_placeholder:
        issues.append("Contains placeholder text that must be replaced")
        recommendations.append("Replace placeholder with cryptographically random key")

    # Check minimum length
    if key_length < MIN_KEY_LENGTH:
        issues.append(f"Key too short: {key_length} chars (minimum: {MIN_KEY_LENGTH})")
        recommendations.append(f"Use at least {MIN_KEY_LENGTH} characters")

    # Check entropy
    if entropy_bits < min_entropy:
        issues.append(
            f"Insufficient entropy: {entropy_bits:.1f} bits (minimum: {min_entropy})"
        )
        recommendations.append(
            f"Key needs {min_entropy - entropy_bits:.0f} more bits of entropy"
        )

    # Check character diversity
    char_types_used = sum(
        1 for count in [
            char_dist["lowercase"],
            char_dist["uppercase"],
            char_dist["digits"],
            char_dist["special"],
        ]
        if count > 0
    )

    if char_types_used < 3:
        issues.append(f"Low character diversity: only {char_types_used} types used")
        recommendations.append("Use mix of uppercase, lowercase, digits, and special chars")

    # Check for repeated patterns
    if re.search(r"(.{3,})\1{2,}", key):
        issues.append("Contains repeated patterns")
        recommendations.append("Avoid repeated character sequences")

    # Check for sequential characters
    if re.search(r"(abc|bcd|cde|123|234|345|678|789)", key.lower()):
        issues.append("Contains sequential characters")
        recommendations.append("Avoid sequential patterns (abc, 123, etc.)")

    # Determine strength level
    if has_placeholder or entropy_bits < MIN_ENTROPY_DEVELOPMENT:
        strength_level = "weak"
    elif entropy_bits < MIN_ENTROPY_PRODUCTION:
        strength_level = "medium"
    elif entropy_bits < MIN_ENTROPY_PRODUCTION * 1.5:
        strength_level = "strong"
    else:
        strength_level = "very_strong"

    # Overall validation
    is_valid = (
        not has_placeholder
        and entropy_bits >= min_entropy
        and key_length >= MIN_KEY_LENGTH
        and len(issues) == 0
    )

    # Environment-specific recommendations
    if environment == "production" and not is_valid:
        recommendations.insert(
            0,
            "CRITICAL: Generate production key with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'",
        )

    return KeyStrengthResult(
        entropy_bits=entropy_bits,
        is_valid=is_valid,
        issues=issues,
        recommendations=recommendations,
        strength_level=strength_level,
        key_length=key_length,
        has_placeholder=has_placeholder,
    )


def mask_secret_for_logging(secret: str, visible_chars: int = 4) -> str:
    """
    Mask secret for safe logging.

    Shows only first/last few characters, masks the rest with asterisks.
    Never logs full secrets.

    Args:
        secret: Secret to mask
        visible_chars: Number of chars to show at start/end

    Returns:
        Masked string like "abc***xyz"

    Security Issue: SECRET-002
    """
    if not secret:
        return "[EMPTY]"

    if len(secret) <= visible_chars * 2:
        # Too short to mask safely
        return "*" * len(secret)

    start = secret[:visible_chars]
    end = secret[-visible_chars:]
    masked_length = len(secret) - (visible_chars * 2)

    return f"{start}{'*' * min(masked_length, 20)}{end}"


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


def validate_all_secrets(secrets_dict: dict, environment: str = "production") -> dict:
    """
    Validate multiple secrets at once.

    Args:
        secrets_dict: Dict of {name: secret_value}
        environment: "production" or "development"

    Returns:
        Dict of {name: KeyStrengthResult}
    """
    min_entropy = (
        MIN_ENTROPY_PRODUCTION if environment == "production"
        else MIN_ENTROPY_DEVELOPMENT
    )

    results = {}
    for name, secret in secrets_dict.items():
        results[name] = validate_key_strength(
            secret,
            min_entropy=min_entropy,
            environment=environment,
        )

    return results


def is_production_ready(key: str) -> bool:
    """
    Quick check if key is production-ready.

    Args:
        key: Key to validate

    Returns:
        True if meets production requirements
    """
    result = validate_key_strength(key, MIN_ENTROPY_PRODUCTION, "production")
    return result.is_valid


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
    # New comprehensive API (AUTH-001 fix)
    'KeyStrengthResult',
    'calculate_shannon_entropy',
    'validate_secret_entropy',
    'validate_key_strength',
    'mask_secret_for_logging',
    'generate_secure_key',
    'validate_all_secrets',
    'is_production_ready',
    # Legacy API (backward compatibility)
    'calculate_entropy',
    'validate_csrf_secret',
    'validate_secret_key',
    'validate_webhook_secret',
    'generate_secure_secret',
    'verify_hmac_signature',
    'generate_hmac_signature',
]
