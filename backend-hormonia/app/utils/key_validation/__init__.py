"""
Security Key Validation Utilities

Provides entropy validation and strength analysis for cryptographic keys
to prevent weak/placeholder keys in production environments.

Security Issues Addressed:
- AUTH-001: Placeholder key detection (Severity 9.5/10)
- SECRET-002: Secret masking for logs (Severity 8.0/10)

Architecture:
    app/utils/key_validation/
    ├── __init__.py          # This file (public API)
    ├── models.py            # KeyStrengthResult + constants
    ├── entropy.py           # Shannon entropy calculations
    ├── validators.py        # Main validation functions
    ├── placeholder.py       # Placeholder detection
    ├── distribution.py      # Character distribution analysis
    ├── hmac_utils.py        # HMAC sign/verify
    └── generators.py        # Secure key generation

Usage:
    from app.utils.key_validation import (
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

# Models and constants
from .models import (
    KeyStrengthResult,
    MIN_ENTROPY_PRODUCTION,
    MIN_ENTROPY_DEVELOPMENT,
    MIN_KEY_LENGTH,
    PLACEHOLDER_PATTERNS,
)

# Entropy calculations
from .entropy import (
    calculate_shannon_entropy,
    calculate_entropy,
)

# Placeholder detection
from .placeholder import contains_placeholder

# Character distribution
from .distribution import analyze_character_distribution

# Generators
from .generators import (
    generate_secure_key,
    generate_secure_secret,
)

# HMAC utilities
from .hmac_utils import (
    verify_hmac_signature,
    generate_hmac_signature,
)

# Main validators
from .validators import (
    validate_secret_entropy,
    validate_key_strength,
    mask_secret_for_logging,
    validate_all_secrets,
    is_production_ready,
    validate_csrf_secret,
    validate_secret_key,
    validate_webhook_secret,
)


__all__ = [
    # Models
    'KeyStrengthResult',
    'MIN_ENTROPY_PRODUCTION',
    'MIN_ENTROPY_DEVELOPMENT',
    'MIN_KEY_LENGTH',
    'PLACEHOLDER_PATTERNS',
    # Entropy
    'calculate_shannon_entropy',
    'calculate_entropy',
    # Placeholder
    'contains_placeholder',
    # Distribution
    'analyze_character_distribution',
    # Generators
    'generate_secure_key',
    'generate_secure_secret',
    # HMAC
    'verify_hmac_signature',
    'generate_hmac_signature',
    # Validators
    'validate_secret_entropy',
    'validate_key_strength',
    'mask_secret_for_logging',
    'validate_all_secrets',
    'is_production_ready',
    'validate_csrf_secret',
    'validate_secret_key',
    'validate_webhook_secret',
]

__version__ = "1.0.0"
