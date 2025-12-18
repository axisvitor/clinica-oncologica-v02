"""
Security key validation functions.

Main validation logic for cryptographic keys including:
- Entropy validation
- Key strength analysis
- CSRF secret validation
- Webhook secret validation
"""

import re
import logging
from typing import List, Optional

from .models import (
    KeyStrengthResult,
    MIN_ENTROPY_PRODUCTION,
    MIN_ENTROPY_DEVELOPMENT,
    MIN_KEY_LENGTH,
)
from .entropy import calculate_shannon_entropy, calculate_entropy
from .placeholder import contains_placeholder
from .distribution import analyze_character_distribution

logger = logging.getLogger(__name__)


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
        1
        for count in [
            char_dist["lowercase"],
            char_dist["uppercase"],
            char_dist["digits"],
            char_dist["special"],
        ]
        if count > 0
    )

    if char_types_used < 3:
        issues.append(f"Low character diversity: only {char_types_used} types used")
        recommendations.append(
            "Use mix of uppercase, lowercase, digits, and special chars"
        )

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
        MIN_ENTROPY_PRODUCTION
        if environment == "production"
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


def validate_csrf_secret(
    csrf_secret: Optional[str], log_validation: bool = True
) -> None:
    """
    Validate CSRF secret key strength with Shannon entropy checking.

    This function ensures that CSRF secrets meet minimum security standards.

    Args:
        csrf_secret: The CSRF secret key to validate
        log_validation: Whether to log validation results (default: True)

    Raises:
        ValueError: If the secret key does not meet security requirements
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
    placeholder_patterns = [
        "change_this",
        "your_secret",
        "secret_key",
        "replace_me",
        "changeme",
        "placeholder",
        "example",
        "test_secret",
        "dev_secret",
        "local_secret",
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
    if len(set(csrf_secret)) < 8:
        raise ValueError(
            "CSRF_SECRET_KEY has insufficient entropy (too few unique characters). "
            "Generate a random secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Check 5: Not a sequential pattern
    if re.match(
        r"^(0123456789|abcdefghijklmnopqrstuvwxyz|ABCDEFGHIJKLMNOPQRSTUVWXYZ)+$",
        csrf_secret,
    ):
        raise ValueError(
            "CSRF_SECRET_KEY appears to be a sequential pattern. "
            "Generate a random secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Check 6: Shannon entropy validation
    min_entropy = 4.0
    entropy = calculate_entropy(csrf_secret)

    if entropy < min_entropy:
        raise ValueError(
            f"CSRF_SECRET_KEY has insufficient entropy: {entropy:.2f} bits/char < {min_entropy}. "
            "Generate a cryptographically secure secret with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Check 7: Not a known weak/common secret
    weak_secrets = [
        "changeme",
        "secret",
        "password",
        "admin",
        "root",
        "12345678901234567890123456789012",
        "abcdefghijklmnopqrstuvwxyz123456",
    ]

    if csrf_secret in weak_secrets:
        raise ValueError(
            "CSRF_SECRET_KEY is a known weak/common value. "
            "Generate a cryptographically secure secret with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    # Success: Log validation metrics
    if log_validation:
        logger.info(
            f"✅ CSRF secret validation passed: "
            f"length={len(csrf_secret)}, "
            f"entropy={entropy:.2f} bits/char, "
            f"unique_chars={len(set(csrf_secret))}"
        )


def validate_secret_key(
    secret_key: Optional[str], key_name: str = "SECRET_KEY", min_length: int = 32
) -> None:
    """
    Generic validation for any secret key (JWT, encryption, session, etc.)

    Args:
        secret_key: The secret key to validate
        key_name: Name of the key for error messages
        min_length: Minimum required length (default: 32)

    Raises:
        ValueError: If the secret key does not meet security requirements
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
    placeholder_keywords = [
        "change",
        "your_",
        "replace",
        "example",
        "test",
        "placeholder",
    ]
    key_lower = secret_key.lower()
    for keyword in placeholder_keywords:
        if keyword in key_lower:
            raise ValueError(
                f"{key_name} appears to be a placeholder value (contains '{keyword}'). "
                f"Generate with: python -c 'import secrets; print(secrets.token_urlsafe({min_length}))'"
            )


def validate_webhook_secret(
    webhook_secret: Optional[str], key_name: str = "WEBHOOK_SECRET"
) -> None:
    """
    Validate webhook secret key strength.

    Args:
        webhook_secret: The webhook secret key to validate
        key_name: Name of the key for error messages

    Raises:
        ValueError: If the secret key does not meet security requirements
    """
    # Use generic validation with minimum 32 characters
    validate_secret_key(webhook_secret, key_name=key_name, min_length=32)

    # Additional webhook-specific validation
    if webhook_secret:
        webhook_placeholders = ["webhook", "evolution", "whatsapp"]
        secret_lower = webhook_secret.lower()

        for pattern in webhook_placeholders:
            if pattern in secret_lower and any(
                placeholder in secret_lower
                for placeholder in ["secret", "key", "change", "replace"]
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
                "Generate a cryptographically secure secret with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        logger.info(
            f"✅ {key_name} validation passed: "
            f"length={len(webhook_secret)}, entropy={entropy:.2f} bits/char"
        )


__all__ = [
    "validate_secret_entropy",
    "validate_key_strength",
    "mask_secret_for_logging",
    "validate_all_secrets",
    "is_production_ready",
    "validate_csrf_secret",
    "validate_secret_key",
    "validate_webhook_secret",
]
