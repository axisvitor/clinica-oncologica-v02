"""
HMAC signature generation and verification utilities.

Provides secure HMAC operations for webhook and API signature validation.
"""

import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)


def verify_hmac_signature(
    message: bytes, signature: str, secret_key: str, algorithm: str = "sha256"
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
    try:
        # Get hash algorithm
        hash_algo = getattr(hashlib, algorithm)

        # Compute expected signature
        expected_signature = hmac.new(
            secret_key.encode("utf-8"), message, hash_algo
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(signature, expected_signature)

    except (AttributeError, TypeError) as e:
        logger.error(f"Error verifying HMAC signature: {e}")
        return False


def generate_hmac_signature(
    message: bytes, secret_key: str, algorithm: str = "sha256"
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
    hash_algo = getattr(hashlib, algorithm)
    signature = hmac.new(secret_key.encode("utf-8"), message, hash_algo)
    return signature.hexdigest()


__all__ = [
    "verify_hmac_signature",
    "generate_hmac_signature",
]
