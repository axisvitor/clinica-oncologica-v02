"""Security utilities for the application."""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse, urlunparse

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.exceptions import AuthenticationError

# Password hashing context with configurable bcrypt rounds
# Production recommended: 12-15 rounds for optimal security
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS  # Configurable via environment variable
)


def mask_sensitive_url(url: str) -> str:
    """
    Mask sensitive information in URLs (passwords, tokens, etc.).

    Args:
        url: The URL that may contain sensitive information

    Returns:
        The URL with sensitive parts masked
    """
    if not url:
        return url

    try:
        # Parse the URL
        parsed = urlparse(url)

        # If there's a password in the URL, mask it
        if parsed.password:
            # Replace password with asterisks
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"

            if parsed.username:
                netloc = f"{parsed.username}:****@{netloc}"
            else:
                netloc = f":****@{netloc}"

            # Reconstruct the URL with masked password
            masked = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            return masked

        # Also mask any token-like strings in the URL
        # Look for patterns like tokens, keys, secrets
        patterns = [
            (r'(token|key|secret|password|pwd|pass|api_key|apikey|auth)=([^&\s]+)', r'\1=****'),
            (r'(Bearer\s+)[\w\-\.]+', r'\1****'),
            (r'(Basic\s+)[\w\-\.]+', r'\1****'),
        ]

        masked = url
        for pattern, replacement in patterns:
            masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)

        return masked

    except Exception:
        # If we can't parse the URL, better to mask it entirely than expose it
        if "@" in url and "://" in url:
            # Likely contains credentials, mask everything after ://
            scheme = url.split("://")[0]
            return f"{scheme}://****"
        return url


def mask_dict_secrets(data: dict, keys_to_mask: Optional[list] = None) -> dict:
    """
    Mask sensitive values in a dictionary.

    Args:
        data: Dictionary that may contain sensitive information
        keys_to_mask: List of keys to mask. If None, uses common sensitive keys

    Returns:
        Dictionary with sensitive values masked
    """
    if not data:
        return data

    if keys_to_mask is None:
        # Common sensitive keys
        keys_to_mask = [
            'password', 'pwd', 'pass', 'secret', 'token', 'key', 'api_key',
            'apikey', 'auth', 'authorization', 'credential', 'private',
            'DATABASE_URL', 'REDIS_URL', 'JWT_SECRET', 'SECRET_KEY',
            'AWS_SECRET_ACCESS_KEY', 'SUPABASE_KEY', 'SUPABASE_ANON_KEY'
        ]

    masked_data = {}
    for key, value in data.items():
        # Check if key contains sensitive terms (case insensitive)
        is_sensitive = any(
            sensitive_key.lower() in key.lower()
            for sensitive_key in keys_to_mask
        )

        if is_sensitive:
            if isinstance(value, str):
                # If it's a URL, use URL masking
                if '://' in value:
                    masked_data[key] = mask_sensitive_url(value)
                else:
                    # Otherwise mask the entire value
                    masked_data[key] = '****'
            else:
                masked_data[key] = '****'
        else:
            # Recursively mask nested dictionaries
            if isinstance(value, dict):
                masked_data[key] = mask_dict_secrets(value, keys_to_mask)
            else:
                masked_data[key] = value

    return masked_data


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Ensure plain_password is a string
        if isinstance(plain_password, bytes):
            plain_password = plain_password.decode('utf-8', errors='ignore')
        else:
            plain_password = str(plain_password)

        # Log password info for debugging (without exposing the actual password)
        password_bytes = plain_password.encode('utf-8')
        logger.debug(f"Password verification - length: {len(plain_password)} chars, {len(password_bytes)} bytes")

        # Bcrypt has a 72 byte limit, truncate password if necessary
        if len(password_bytes) > 72:
            logger.warning(f"Password exceeds 72 bytes ({len(password_bytes)} bytes), truncating...")
            password_bytes = password_bytes[:72]
            plain_password = password_bytes.decode('utf-8', errors='ignore')

        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        logger.error(f"Password length was: {len(plain_password)} chars")
        # Re-raise the exception
        raise


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Ensure password is a string
        if isinstance(password, bytes):
            password = password.decode('utf-8', errors='ignore')
        else:
            password = str(password)

        password_bytes = password.encode('utf-8')

        # Bcrypt has a 72 byte limit, truncate password if necessary
        if len(password_bytes) > 72:
            logger.warning(f"Password exceeds 72 bytes ({len(password_bytes)} bytes), truncating...")
            password_bytes = password_bytes[:72]
            password = password_bytes.decode('utf-8', errors='ignore')

        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        logger.error(f"Password length was: {len(password)} chars")
        raise


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Convert to timestamp for JWT
    to_encode.update({"exp": int(expire.timestamp()), "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    Create JWT refresh token.
    
    Uses REFRESH_TOKEN_EXPIRE_DAYS from settings (default: 7 days).
    Can be configured via environment variable.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Convert to timestamp for JWT
    to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[Any]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # Check token type
        if payload.get("type") != token_type:
            return None

        # Check expiration
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp) < datetime.utcnow():
            return None

        # Return a simple object with email for compatibility with tests
        from app.schemas.auth import TokenData
        email = payload.get("sub")
        if email is None:
            return None
        return TokenData(email=email)

    except JWTError:
        return None


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def hash_api_key(api_key: str) -> str:
    """Hash API key for secure storage."""
    return get_password_hash(api_key)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify API key against its hash."""
    return verify_password(plain_key, hashed_key)


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


def validate_password_strength(password: str) -> dict[str, Union[bool, List[str]]]:
    """
    Validate password strength and return detailed feedback.

    Returns:
        Dict with 'is_valid' boolean and 'issues' list
    """
    issues = []

    if len(password) < 8:
        issues.append("Password must be at least 8 characters long")

    if len(password) > 128:
        issues.append("Password must be less than 128 characters long")

    if not re.search(r'[a-z]', password):
        issues.append("Password must contain at least one lowercase letter")

    if not re.search(r'[A-Z]', password):
        issues.append("Password must contain at least one uppercase letter")

    if not re.search(r'\d', password):
        issues.append("Password must contain at least one digit")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        issues.append("Password must contain at least one special character")

    # Check for common patterns
    common_patterns = [
        r'(.)\1{2,}',  # Repeated characters
        r'(012|123|234|345|456|567|678|789|890)',  # Sequential numbers
        r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)',  # Sequential letters
    ]

    for pattern in common_patterns:
        if re.search(pattern, password.lower()):
            issues.append("Password contains common patterns and may be easily guessed")
            break

    return {
        'is_valid': len(issues) == 0,
        'issues': issues
    }