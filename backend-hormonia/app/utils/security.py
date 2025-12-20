"""
Security utilities with bcrypt fix for Railway deployment.
Handles password hashing bug in passlib/bcrypt.
"""

import logging
import os
from typing import Optional, Any, List, Union
from passlib.context import CryptContext
import bcrypt as bcrypt_lib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import re
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.config import settings

logger = logging.getLogger(__name__)

# Force builtin bcrypt to avoid detection bug
os.environ["PASSLIB_BUILTIN_BCRYPT"] = "enabled"

# Additional imports for public endpoint security
import html
import urllib.parse
from fastapi import Request, HTTPException, status

# Regex patterns for input validation
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")  # JWT-like tokens
SAFE_STRING_PATTERN = re.compile(r"^[\w\s.,!?-]+$")  # Safe text input
NUMBER_PATTERN = re.compile(r"^\d+$")  # Numbers only
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Suspicious patterns to detect potential attacks
SUSPICIOUS_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),  # XSS
    re.compile(r"javascript:", re.IGNORECASE),  # JavaScript URLs
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # Event handlers
    re.compile(
        r"\b(union|select|insert|update|delete|drop|create|alter)\b", re.IGNORECASE
    ),  # SQL injection
    re.compile(r"\.\.[\\/]", re.IGNORECASE),  # Path traversal
    re.compile(r"\${.*}"),  # Template injection
    re.compile(r"\[\[.*\]\]"),  # Template injection
    re.compile(r"{{.*}}"),  # Template injection
]

# Blocked user agents (bots, scanners)
BLOCKED_USER_AGENTS = [
    "sqlmap",
    "nmap",
    "nikto",
    "dirb",
    "gobuster",
    "wfuzz",
    "burp",
    "zap",
    "acunetix",
    "nessus",
    "openvas",
]


def create_pwd_context() -> CryptContext:
    """Create password context with proper configuration."""
    try:
        # Try to create with bcrypt
        pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12,
            bcrypt__ident="2b",  # Use 2b variant to avoid wraparound bug
        )

        # Try to set backend to avoid detection issues
        try:
            from passlib.hash import bcrypt as passlib_bcrypt

            passlib_bcrypt.set_backend("builtin")
            logger.info("Using builtin bcrypt backend")
        except (ValueError, RuntimeError, ImportError):
            try:
                from passlib.hash import bcrypt as passlib_bcrypt

                passlib_bcrypt.set_backend("bcrypt")
                logger.info("Using bcrypt library backend")
            except (ValueError, RuntimeError, ImportError):
                logger.warning("Could not set specific bcrypt backend")

        return pwd_context

    except Exception as e:
        logger.error(f"Failed to create bcrypt context: {e}")
        # Fallback to a simpler implementation
        return None


# Create global password context
pwd_context = create_pwd_context()


def hash_password(password: str) -> str:
    """Hash a password with bcrypt - handles edge cases."""
    if not password:
        raise ValueError("Password cannot be empty")

    # Ensure password is not too long (bcrypt limit is 72 bytes)
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        logger.warning("Password truncated to 72 bytes")
        password_bytes = password_bytes[:72]

    try:
        if pwd_context:
            # Use passlib
            return pwd_context.hash(password_bytes.decode("utf-8"))
        else:
            # Direct bcrypt fallback
            salt = bcrypt_lib.gensalt(rounds=12)
            hashed = bcrypt_lib.hashpw(password_bytes, salt)
            return hashed.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to hash password: {e}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash - handles edge cases."""
    if not plain_password or not hashed_password:
        return False

    # Ensure password is not too long
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    try:
        if pwd_context:
            # Use passlib - but handle the bug
            try:
                return pwd_context.verify(
                    password_bytes.decode("utf-8"), hashed_password
                )
            except ValueError as e:
                if "password cannot be longer than 72 bytes" in str(e):
                    # This is the bug - password is fine but passlib thinks it's too long
                    # Fall back to direct bcrypt
                    logger.warning("Passlib bcrypt bug detected, using direct bcrypt")
                    return bcrypt_lib.checkpw(
                        password_bytes, hashed_password.encode("utf-8")
                    )
                else:
                    raise
        else:
            # Direct bcrypt fallback
            return bcrypt_lib.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to verify password: {e}")
        return False


# Keep original functions for compatibility
def get_password_hash(password: str) -> str:
    """Alias for hash_password."""
    return hash_password(password)


def mask_sensitive_url(url: str, mask: str = "****") -> str:
    """Mask sensitive parts (password, tokens) in a URL for safe logging.

    Examples:
    - redis://:password@host:6379/0  -> redis://:****@host:6379/0
    - https://user:secret@api.example.com?token=abc -> https://user:****@api.example.com?token=****
    """
    if not isinstance(url, str) or not url:
        return ""
    try:
        parsed = urlparse(url)
        username = parsed.username or ""
        password = parsed.password

        # Mask credentials in netloc
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        userinfo = ""
        if username or password is not None:
            if username:
                userinfo = f"{username}:{mask}@"
            else:
                userinfo = f":{mask}@"
        netloc = f"{userinfo}{host}{port}"

        # Mask sensitive query params
        sensitive_keys = {
            "password",
            "pass",
            "token",
            "apikey",
            "api_key",
            "key",
            "secret",
        }
        query = parsed.query
        if parsed.query:
            pairs = []
            for k, v in parse_qsl(parsed.query, keep_blank_values=True):
                if k.lower() in sensitive_keys and v:
                    pairs.append((k, mask))
                else:
                    pairs.append((k, v))
            query = urlencode(pairs)

        sanitized = parsed._replace(netloc=netloc, query=query)
        return urlunparse(sanitized)
    except Exception:
        # Fallback: simple masking for userinfo
        return re.sub(r"(://)([^/@]*)(@)", rf"\1{mask}\3", url)


def mask_dict_secrets(data: dict, keys_to_mask: Optional[list] = None) -> dict:
    """Mask sensitive values in a dictionary (URLs and secret-like keys)."""
    if not data:
        return data
    if keys_to_mask is None:
        keys_to_mask = [
            "password",
            "pwd",
            "pass",
            "secret",
            "token",
            "key",
            "api_key",
            "apikey",
            "auth",
            "authorization",
            "credential",
            "private",
            "DATABASE_URL",
            "REDIS_URL",
            "JWT_SECRET",
            "SECRET_KEY",
            "AWS_SECRET_ACCESS_KEY",
            "SUPABASE_KEY",
            "SUPABASE_ANON_KEY",
        ]
    masked_data = {}
    for key, value in data.items():
        is_sensitive = any(s.lower() in key.lower() for s in keys_to_mask)
        if is_sensitive:
            if isinstance(value, str):
                masked_data[key] = (
                    mask_sensitive_url(value) if "://" in value else "****"
                )
            else:
                masked_data[key] = "****"
        else:
            masked_data[key] = (
                mask_dict_secrets(value, keys_to_mask)
                if isinstance(value, dict)
                else value
            )
    return masked_data


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token using settings.SECURITY_SECRET_KEY and settings.SECURITY_ALGORITHM."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": int(expire.timestamp()), "type": "access"})
    return jwt.encode(
        to_encode, settings.SECURITY_SECRET_KEY, algorithm=settings.SECURITY_ALGORITHM
    )


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create JWT refresh token with REFRESH_TOKEN_EXPIRE_DAYS."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.AUTH_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})
    return jwt.encode(
        to_encode, settings.SECURITY_SECRET_KEY, algorithm=settings.SECURITY_ALGORITHM
    )


def verify_token(token: str, token_type: str = "access") -> Optional[Any]:
    """Verify and decode JWT token and return TokenData if valid, else None."""
    try:
        payload = jwt.decode(
            token,
            settings.SECURITY_SECRET_KEY,
            algorithms=[settings.SECURITY_ALGORITHM],
        )
        if payload.get("type") != token_type:
            return None
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            return None
        from app.schemas.auth import TokenData

        email = payload.get("sub")
        if not email:
            return None
        return TokenData(email=email)
    except JWTError:
        return None


def validate_password_strength(password: str) -> dict[str, Union[bool, List[str]]]:
    """Validate password strength and return {'is_valid': bool, 'issues': List[str]}"""
    issues: List[str] = []
    if len(password) < 8:
        issues.append("Password must be at least 8 characters long")
    if len(password) > 128:
        issues.append("Password must be less than 128 characters long")
    if not re.search(r"[a-z]", password):
        issues.append("Password must contain at least one lowercase letter")
    if not re.search(r"[A-Z]", password):
        issues.append("Password must contain at least one uppercase letter")
    if not re.search(r"\d", password):
        issues.append("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        issues.append("Password must contain at least one special character")
    common_patterns = [
        r"(.)\1{2,}",
        r"(012|123|234|345|456|567|678|789|890)",
        r"(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)",
    ]
    for pattern in common_patterns:
        if re.search(pattern, password.lower()):
            issues.append("Password contains common patterns and may be easily guessed")
            break
    return {"is_valid": len(issues) == 0, "issues": issues}


# ==============================================================================
# PUBLIC ENDPOINT SECURITY FUNCTIONS
# ==============================================================================


async def validate_public_request(request: Request) -> None:
    """
    Validate public API request for security threats.

    Args:
        request: FastAPI Request object

    Raises:
        HTTPException: If request is deemed suspicious
    """
    # Check User-Agent for known scanners/bots
    user_agent = request.headers.get("user-agent", "").lower()
    for blocked_agent in BLOCKED_USER_AGENTS:
        if blocked_agent in user_agent:
            logger.warning(
                f"Blocked request from suspicious user agent: {user_agent}",
                extra={"event_type": "security_block", "reason": "blocked_user_agent"},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    # Check for suspicious headers
    await _check_suspicious_headers(request)

    # Check request size
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1024 * 1024:  # 1MB limit
        logger.warning(
            f"Blocked oversized request: {content_length} bytes",
            extra={"event_type": "security_block", "reason": "oversized_request"},
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request too large",
        )


async def _check_suspicious_headers(request: Request) -> None:
    """
    Check for suspicious header values.
    """
    suspicious_headers = ["x-original-url", "x-rewrite-url", "x-forwarded-host"]

    for header_name in suspicious_headers:
        if header_name in request.headers:
            header_value = request.headers[header_name]
            if _contains_suspicious_patterns(header_value):
                logger.warning(
                    f"Suspicious header detected: {header_name}={header_value}",
                    extra={
                        "event_type": "security_block",
                        "reason": "suspicious_header",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request headers",
                )


def sanitize_input(value: Any, max_length: int = 1000) -> str:
    """
    Sanitize input string for safe processing.

    Args:
        value: Input value to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Raises:
        HTTPException: If input is too long or contains suspicious patterns
    """
    if value is None:
        return ""

    # Convert to string
    str_value = str(value)

    # Check length
    if len(str_value) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input too long (max {max_length} characters)",
        )

    # Check for suspicious patterns
    if _contains_suspicious_patterns(str_value):
        logger.warning(
            f"Suspicious input detected: {str_value[:100]}...",
            extra={"event_type": "security_block", "reason": "suspicious_input"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input format"
        )

    # HTML escape and URL decode
    sanitized = html.escape(str_value)
    sanitized = urllib.parse.unquote(sanitized)

    # Remove null bytes and control characters
    sanitized = "".join(
        char for char in sanitized if ord(char) >= 32 or char in "\t\n\r"
    )

    return sanitized.strip()


def validate_token_format(token: str) -> bool:
    """
    Validate token format (basic structure check).

    Args:
        token: Token string to validate

    Returns:
        True if format is valid
    """
    if not token or len(token) < 10 or len(token) > 2048:
        return False

    return bool(TOKEN_PATTERN.match(token))


def validate_uuid_format(uuid_str: str) -> bool:
    """
    Validate UUID format.

    Args:
        uuid_str: UUID string to validate

    Returns:
        True if format is valid
    """
    if not uuid_str:
        return False

    return bool(UUID_PATTERN.match(uuid_str))


def _contains_suspicious_patterns(text: str) -> bool:
    """
    Check if text contains suspicious patterns.

    Args:
        text: Text to check

    Returns:
        True if suspicious patterns found
    """
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            return True
    return False


def mask_sensitive_url_simple(url: str) -> str:
    """
    Simple mask for sensitive parts of URL for logging.
    Note: For more comprehensive masking with query params, use mask_sensitive_url().

    Args:
        url: URL to mask

    Returns:
        Masked URL
    """
    if not url:
        return "[no url]"

    try:
        # Parse URL
        parsed = urllib.parse.urlparse(url)

        # Mask password if present
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
        else:
            netloc = parsed.netloc

        # Reconstruct URL
        masked_url = urllib.parse.urlunparse(
            (
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                "" if parsed.query else "",  # Remove query parameters
                "",
            )
        )

        return masked_url

    except Exception:
        # If parsing fails, return a safe placeholder
        return "[invalid url]"


def generate_security_headers() -> dict:
    """
    Generate security headers for public endpoints.

    Returns:
        Dictionary of security headers
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'self'",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }
