"""
CSRF Token Generation and Validation

Contains the core CSRF token logic: settings, secret key resolution,
token generation (HMAC-SHA256 signed), and token validation with
expiration and constant-time comparison.

Extracted from csrf.py to keep both modules under 500 lines.

Usage:
    from app.middleware.csrf_tokens import generate_csrf_token, validate_csrf_token
"""

import hashlib
import hmac
import logging
import secrets
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Token Configuration Defaults
# ============================================================================

TOKEN_EXPIRY = 3600  # 1 hour
COOKIE_NAME = "csrf_token"
COOKIE_PATH = "/"
COOKIE_SAMESITE = "strict"


# ============================================================================
# Settings
# ============================================================================

class CSRFSettings:
    """CSRF configuration settings."""

    def __init__(
        self,
        secret_key: str,
        cookie_name: str = COOKIE_NAME,
        token_expires_in: int = TOKEN_EXPIRY,
        cookie_path: str = COOKIE_PATH,
        cookie_domain: Optional[str] = None,
        cookie_secure: bool = False,
        cookie_httponly: bool = True,
        cookie_samesite: str = COOKIE_SAMESITE,
    ):
        self.secret_key = secret_key
        self.cookie_name = cookie_name
        self.token_expires_in = token_expires_in
        self.cookie_path = cookie_path
        self.cookie_domain = cookie_domain
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite


def build_csrf_settings(
    *,
    secret_key_resolver: Callable[[], str],
    production_resolver: Callable[[], bool],
) -> CSRFSettings:
    """Build CSRF settings from the provided resolver functions."""
    from app.config import settings

    secret_key = secret_key_resolver()
    return CSRFSettings(
        secret_key=secret_key,
        cookie_name=COOKIE_NAME,
        token_expires_in=TOKEN_EXPIRY,
        cookie_path=COOKIE_PATH,
        cookie_domain=None,
        cookie_secure=getattr(
            settings,
            "SESSION_ENABLE_COOKIE_SECURE",
            production_resolver(),
        ),
        cookie_httponly=True,
        cookie_samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", COOKIE_SAMESITE),
    )


def get_csrf_settings() -> CSRFSettings:
    """
    Get CSRF settings from application configuration.

    Returns CSRFSettings with values from environment or defaults.
    """
    return build_csrf_settings(
        secret_key_resolver=_get_secret_key,
        production_resolver=_is_production,
    )


# ============================================================================
# Internal Helpers
# ============================================================================

def _get_secret_key() -> str:
    """Get CSRF secret key from settings."""
    from app.config import settings

    secret = getattr(settings, "SECURITY_CSRF_SECRET_KEY", None)
    if secret and hasattr(secret, "get_secret_value"):
        secret = secret.get_secret_value()

    if not secret or len(str(secret)) < 32:
        raise ValueError(
            "SECURITY_CSRF_SECRET_KEY must be at least 32 characters. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    return str(secret)


def _is_production() -> bool:
    """Check if running in production."""
    from app.config import settings
    return str(getattr(settings, "APP_ENVIRONMENT", "development")).lower() == "production"


# ============================================================================
# Token Generation and Validation
# ============================================================================

def generate_csrf_token(secret_key: Optional[str] = None) -> str:
    """
    Generate a cryptographically signed CSRF token with high entropy.

    Token Format: {timestamp}.{random_hex}.{hmac_signature}

    Components:
        - timestamp: Current Unix timestamp (replay attack prevention)
        - random_hex: 64 hexadecimal characters (256 bits entropy)
        - hmac_signature: HMAC-SHA256 signature (prevents tampering)

    Security Properties:
        - 256-bit random entropy (cryptographically secure)
        - HMAC-SHA256 signature for integrity
        - Timestamp for expiration enforcement
        - Hexadecimal encoding (URL-safe, auditable)

    Args:
        secret_key: Optional HMAC secret key (uses configured key if None)

    Returns:
        str: Signed CSRF token in hexadecimal format

    Raises:
        ValueError: If secret key is invalid or too short

    Example:
        >>> token = generate_csrf_token()
        >>> # Returns: "1734695123.a1b2c3d4e5f6...signature"
    """
    if secret_key is None:
        secret_key = _get_secret_key()

    # Validate secret key strength
    if not secret_key or len(secret_key) < 32:
        raise ValueError(
            "CSRF secret key must be at least 32 characters. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

    timestamp = str(int(time.time()))
    # Use 32 bytes (256 bits) of cryptographically secure random data
    random_data = secrets.token_hex(32)
    payload = f"{timestamp}.{random_data}"

    # Generate HMAC-SHA256 signature for integrity protection
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    token = f"{payload}.{signature}"

    # Log token generation for security monitoring (without exposing the token)
    logger.debug(f"CSRF token generated: length={len(token)}, timestamp={timestamp}")

    return token


def validate_csrf_token(token: str, secret_key: Optional[str] = None) -> bool:
    """
    Validate a CSRF token's format, signature, and expiration.

    Uses constant-time comparison to prevent timing attacks.
    Handles edge cases including None tokens, non-ASCII characters,
    and invalid formats.

    Args:
        token: CSRF token string to validate (format: timestamp.random.signature)
        secret_key: Optional secret key for HMAC validation

    Returns:
        bool: True if token is valid, False otherwise

    Security considerations:
        - Uses hmac.compare_digest for constant-time comparison
        - Validates token format before processing
        - Checks timestamp for expiration and clock skew
        - Handles None and invalid inputs gracefully
    """
    # Handle None and empty tokens
    if token is None or not isinstance(token, str) or not token.strip():
        logger.debug("CSRF validation failed: token is None or empty")
        return False

    if secret_key is None:
        secret_key = _get_secret_key()

    try:
        parts = token.split(".")
        if len(parts) != 3:
            logger.debug(f"CSRF validation failed: invalid token format (expected 3 parts, got {len(parts)})")
            return False

        timestamp_str, random_data, signature = parts

        # Verify signature (constant-time)
        # Convert to ASCII-safe encoding to prevent non-ASCII comparison errors
        payload = f"{timestamp_str}.{random_data}"
        expected = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Ensure both strings are ASCII-safe before comparison
        try:
            signature_bytes = signature.encode('ascii')
            expected_bytes = expected.encode('ascii')
        except UnicodeEncodeError:
            logger.debug("CSRF validation failed: non-ASCII characters in token")
            return False

        if not hmac.compare_digest(signature_bytes, expected_bytes):
            logger.debug("CSRF validation failed: signature mismatch")
            return False

        # Check expiration
        timestamp = int(timestamp_str)
        current_time = int(time.time())
        age = current_time - timestamp

        # Token is expired if older than TOKEN_EXPIRY
        if age > TOKEN_EXPIRY:
            logger.debug(f"CSRF validation failed: token expired (age: {age}s, max: {TOKEN_EXPIRY}s)")
            return False

        # Token is invalid if timestamp is too far in the future (60s clock skew allowed)
        if age < -60:
            logger.debug(f"CSRF validation failed: token timestamp too far in future (age: {age}s)")
            return False

        return True

    except (ValueError, IndexError, UnicodeDecodeError, AttributeError) as e:
        logger.debug(f"CSRF validation failed: {type(e).__name__}: {str(e)}")
        return False


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "CSRFSettings",
    "get_csrf_settings",
    "generate_csrf_token",
    "validate_csrf_token",
    "TOKEN_EXPIRY",
    "COOKIE_NAME",
    "COOKIE_PATH",
    "COOKIE_SAMESITE",
]
