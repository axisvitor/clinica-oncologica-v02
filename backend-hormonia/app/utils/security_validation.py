"""
Security Key Validation Utilities - Compatibility Layer

This module re-exports all security validation functions from the
modular app/utils/security/ package for backward compatibility.

New code should import from app.utils.security directly.

Example:
    # Legacy import (still works)
    from app.utils.security_validation import validate_csrf_secret

    # New recommended import
    from app.utils.key_validation import validate_csrf_secret
"""

# Re-export everything from the new modular package
from app.utils.key_validation import (
    # Models
    KeyStrengthResult,
    calculate_shannon_entropy,
    calculate_entropy,
    # Placeholder
    generate_secure_key,
    generate_secure_secret,
    # HMAC
    verify_hmac_signature,
    generate_hmac_signature,
    # Validators
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
    # New comprehensive API (AUTH-001 fix)
    "KeyStrengthResult",
    "calculate_shannon_entropy",
    "validate_secret_entropy",
    "validate_key_strength",
    "mask_secret_for_logging",
    "generate_secure_key",
    "validate_all_secrets",
    "is_production_ready",
    # Legacy API (backward compatibility)
    "calculate_entropy",
    "validate_csrf_secret",
    "validate_secret_key",
    "validate_webhook_secret",
    "generate_secure_secret",
    "verify_hmac_signature",
    "generate_hmac_signature",
]
