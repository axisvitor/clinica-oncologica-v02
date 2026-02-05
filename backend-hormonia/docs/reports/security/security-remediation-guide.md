# Security Remediation Guide

Complete step-by-step guide for fixing all identified security vulnerabilities.

---

## Overview

- **Total Issues**: 7 (3 MEDIUM + 4 LOW)
- **Est. Effort**: 8-10 hours
- **Priority**: Medium (No critical vulnerabilities)

---

## Medium Priority Issues (Fix This Sprint)

### Issue M1: MD5 Hashing for File Checksums

**Severity**: MEDIUM | **File**: `app/api/v2/routers/upload/storage.py` | **Effort**: 30 mins

#### Step 1: Update the checksum function

**Replace**:
```python
# OLD CODE - Lines 54-68
def calculate_checksum(file_path: Path) -> str:
    """
    Calculate MD5 checksum of file.

    Args:
        file_path: Path to file

    Returns:
        MD5 checksum hex string
    """
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()
```

**With**:
```python
# NEW CODE - SHA-256 instead
def calculate_checksum(file_path: Path) -> str:
    """
    Calculate SHA-256 checksum of file.

    Args:
        file_path: Path to file

    Returns:
        SHA-256 checksum hex string

    Note:
        Uses SHA-256 (256-bit hash) instead of deprecated MD5.
        Provides better security for file integrity verification.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Increased buffer to 8KB for better performance
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()
```

#### Step 2: Update any database schema if storing checksums

If the checksum column has a fixed length constraint, verify it supports 64-character hex strings:
- MD5 hash: 32 characters
- SHA-256 hash: 64 characters

```sql
-- If needed, update schema (backup first!)
ALTER TABLE uploads MODIFY COLUMN checksum VARCHAR(64);
```

#### Step 3: Update documentation

Add migration note in docstring:
```python
"""
SECURITY UPDATE (2025-12-25):
Changed from MD5 to SHA-256 for file integrity verification.
Existing checksums will remain as-is; new uploads use SHA-256.

Migration:
  - No action required for existing files
  - New checksums use stronger algorithm
  - Database column supports both lengths
"""
```

#### Step 4: Test the change

```python
# Test in shell
from pathlib import Path
from app.api.v2.routers.upload.storage import calculate_checksum

test_file = Path("/tmp/test.txt")
test_file.write_text("test content")

checksum = calculate_checksum(test_file)
print(f"SHA-256 checksum: {checksum}")
print(f"Length: {len(checksum)}")  # Should be 64

# Cleanup
test_file.unlink()
```

---

### Issue M2: Sensitive Data Logging in Firebase Service

**Severity**: MEDIUM | **File**: `app/services/firebase_auth_service.py` | **Effort**: 1 hour

#### Step 1: Create a logging filter for sensitive data

Create new file: `app/utils/logging_filters.py`

```python
"""
Logging filters to prevent sensitive data exposure.

Redacts passwords, tokens, API keys, and other secrets from log messages.
"""

import logging
import re
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """
    Filter that redacts sensitive information from log records.

    Redacts:
    - API keys and tokens
    - Passwords and credentials
    - Secret keys
    - Private keys
    - Database URLs with credentials
    """

    # Pattern to match sensitive key=value pairs
    SENSITIVE_PATTERNS = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', 'password=***REDACTED***'),
        (r'api_key["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', 'api_key=***REDACTED***'),
        (r'apikey["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', 'apikey=***REDACTED***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', 'token=***REDACTED***'),
        (r'secret["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', 'secret=***REDACTED***'),
        (r'private_key["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', 'private_key=***REDACTED***'),
        (r'auth["\']?\s*[:=]\s*["\']?[^"\'\s,}]+', 'auth=***REDACTED***'),
        # Database URLs
        (r'(?:postgresql|mysql|mongodb)://[^@]+@', 'DB_URL://***:***@'),
        # Firebase keys in JSON
        (r'"private_key"\s*:\s*"[^"]*"', '"private_key": "***REDACTED***"'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and redact sensitive data from log record.

        Args:
            record: LogRecord to filter

        Returns:
            True to allow record, False to skip
        """
        # Redact message
        if record.msg and isinstance(record.msg, str):
            record.msg = self._redact(record.msg)

        # Redact formatted message
        if record.getMessage():
            record.msg = self._redact(record.getMessage())

        # Redact exception info
        if record.exc_text:
            record.exc_text = self._redact(record.exc_text)

        return True

    @staticmethod
    def _redact(text: str) -> str:
        """
        Redact sensitive patterns from text.

        Args:
            text: Text to redact

        Returns:
            Text with sensitive patterns replaced
        """
        if not text or not isinstance(text, str):
            return text

        for pattern, replacement in SensitiveDataFilter.SENSITIVE_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text


def setup_sensitive_data_filter(logger: Optional[logging.Logger] = None) -> None:
    """
    Setup sensitive data filter on logger.

    Args:
        logger: Logger to setup (uses root logger if None)
    """
    if logger is None:
        logger = logging.getLogger()

    # Remove existing filters to avoid duplicates
    logger.filters = [f for f in logger.filters if not isinstance(f, SensitiveDataFilter)]

    # Add new filter
    logger.addFilter(SensitiveDataFilter())
```

#### Step 2: Update Firebase service logging

**File**: `app/services/firebase_auth_service.py`

```python
# Add to imports at top
from app.utils.logging_filters import setup_sensitive_data_filter, SensitiveDataFilter
from app.utils.security import mask_dict_secrets

# In _initialize_firebase() method, replace:
# OLD:
logger.info(
    f"Firebase Admin SDK initialized successfully for project: {self.project_id}"
)

# NEW:
logger.info(
    "Firebase Admin SDK initialized successfully for project: [MASKED]"
)

# If logging cred_dict anywhere, mask it first:
safe_cred = mask_dict_secrets({
    "type": "service_account",
    "project_id": self.project_id,
    "client_email": self.client_email,
    # Don't include private_key
})
logger.debug(f"Credentials loaded: {safe_cred}")
```

#### Step 3: Setup filter in application startup

**File**: `app/core/lifespan.py` or `app/core/application_factory.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler."""
    # Startup
    try:
        # Setup security logging filters
        from app.utils.logging_filters import setup_sensitive_data_filter
        setup_sensitive_data_filter()
        logger.info("Security logging filters initialized")

        # ... rest of startup code
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("Application shutting down")
```

#### Step 4: Update application factory

**File**: `app/core/application_factory.py`

```python
def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="Clínica Oncológica Backend",
        lifespan=lifespan,
    )

    # Setup security logging before other middleware
    from app.utils.logging_filters import setup_sensitive_data_filter
    setup_sensitive_data_filter()

    # ... rest of configuration
    return app
```

#### Step 5: Test the filter

```python
# Test script
import logging
from app.utils.logging_filters import SensitiveDataFilter

# Setup test logger
logger = logging.getLogger("test")
logger.addFilter(SensitiveDataFilter())
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Test messages
logger.info("User login with password=supersecret123")
logger.info("API call with api_key=sk_live_1234567890")
logger.error("Database error: postgresql://user:pass@localhost/db")

# Should output:
# test - User login with password=***REDACTED***
# test - API call with api_key=***REDACTED***
# test - Database error: DB_URL://***:***@localhost/db
```

---

### Issue M3: Weak Session Cookie Configuration in Development

**Severity**: MEDIUM | **File**: `app/config/settings/security.py` | **Effort**: 1 hour

#### Step 1: Add validation method to SecuritySettings

**File**: `app/config/settings/security.py`

Add this method to the `SecuritySettings` class:

```python
@model_validator(mode="after")
def validate_session_cookie_security(self) -> "SecuritySettings":
    """
    Validate session cookie security settings match environment.

    Production environment must enforce secure cookies.
    """
    import logging
    logger = logging.getLogger(__name__)

    if self.APP_ENVIRONMENT.lower() == "production":
        errors = []

        # Check Secure flag
        if not self.SESSION_ENABLE_COOKIE_SECURE:
            errors.append(
                "SESSION_ENABLE_COOKIE_SECURE must be True in production\n"
                "  This requires HTTPS for all cookies\n"
                "  Set: SESSION_ENABLE_COOKIE_SECURE=true"
            )

        # Check HttpOnly flag
        if not self.SESSION_ENABLE_COOKIE_HTTPONLY:
            errors.append(
                "SESSION_ENABLE_COOKIE_HTTPONLY must be True in production\n"
                "  This prevents JavaScript access to cookies (XSS protection)\n"
                "  Set: SESSION_ENABLE_COOKIE_HTTPONLY=true"
            )

        # Check SameSite policy
        samesite_lower = self.SESSION_COOKIE_SAMESITE.lower()
        if samesite_lower not in ["strict", "lax"]:
            errors.append(
                f"SESSION_COOKIE_SAMESITE must be 'strict' or 'lax' in production (got: {self.SESSION_COOKIE_SAMESITE})\n"
                "  - 'strict': Recommended for healthcare systems\n"
                "  - 'lax': Allows same-site GET navigation\n"
                "  Set: SESSION_COOKIE_SAMESITE=strict"
            )

        # Raise error with all violations
        if errors:
            error_msg = (
                "\n❌ SESSION COOKIE SECURITY VALIDATION FAILED IN PRODUCTION\n"
                + "=" * 70 + "\n"
                + "\n".join(f"{i}. {err}" for i, err in enumerate(errors, 1))
                + "\n" + "=" * 70
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Log successful validation in production
        logger.info(
            "✅ Session cookie security validated for production:\n"
            f"  - Secure: {self.SESSION_ENABLE_COOKIE_SECURE}\n"
            f"  - HttpOnly: {self.SESSION_ENABLE_COOKIE_HTTPONLY}\n"
            f"  - SameSite: {self.SESSION_COOKIE_SAMESITE}"
        )

    else:
        # Development mode warnings
        if not self.SESSION_ENABLE_COOKIE_SECURE:
            logger.warning(
                "⚠️  SESSION_ENABLE_COOKIE_SECURE is False in development\n"
                "  This is OK for localhost testing but MUST be True in production"
            )

        if self.SESSION_COOKIE_SAMESITE.lower() not in ["strict", "lax"]:
            logger.warning(
                f"⚠️  SESSION_COOKIE_SAMESITE is '{self.SESSION_COOKIE_SAMESITE}' in development\n"
                "  Should be 'strict' or 'lax' in production"
            )

    return self
```

#### Step 2: Update middleware to use validated settings

**File**: `app/core/middleware_setup.py` or similar

Ensure session middleware gets configuration from settings:

```python
from fastapi.middleware.sessions import SessionMiddleware
from app.config import settings

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECURITY_SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_COOKIE_MAX_AGE_SECONDS,
    same_site=settings.SESSION_COOKIE_SAMESITE,
    https_only=settings.SESSION_ENABLE_COOKIE_SECURE,  # Enforced in production
    domain=settings.SESSION_COOKIE_DOMAIN,
)
```

#### Step 3: Create production environment template

Create `.env.production.example`:

```bash
# Session Cookie Security - REQUIRED FOR PRODUCTION
SESSION_ENABLE_COOKIE_SECURE=true
SESSION_ENABLE_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=strict
SESSION_COOKIE_MAX_AGE_SECONDS=28800

# Security - REQUIRED FOR PRODUCTION
SECURITY_ENABLE_SSL_REDIRECT=true
SECURITY_SECRET_KEY=<generate-with-secrets.token_urlsafe(64)>
SECURITY_CSRF_SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>

# Application
APP_ENVIRONMENT=production
APP_ENABLE_DEBUG=false
```

#### Step 4: Test the validation

```python
# Test invalid production config
import pytest
from app.config.settings.security import SecuritySettings

def test_production_session_security_validation():
    """Test that invalid session configs fail in production."""

    # Should fail: Secure=False in production
    with pytest.raises(ValueError) as exc_info:
        SecuritySettings(
            APP_ENVIRONMENT="production",
            SESSION_ENABLE_COOKIE_SECURE=False,  # Invalid!
        )
    assert "SESSION_ENABLE_COOKIE_SECURE must be True" in str(exc_info.value)

    # Should succeed: All secure in production
    settings = SecuritySettings(
        APP_ENVIRONMENT="production",
        SESSION_ENABLE_COOKIE_SECURE=True,
        SESSION_ENABLE_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="strict",
    )
    assert settings.SESSION_ENABLE_COOKIE_SECURE is True
```

---

## Low Priority Issues (Next Sprint)

### Issue L1: Test Token Registry in Production Code

**Severity**: LOW | **File**: `app/dependencies/auth_dependencies.py` | **Effort**: 2 hours

#### Step 1: Create testing module

Create new file: `app/testing/auth_fixtures.py`

```python
"""
Test authentication fixtures for development/testing only.

NEVER use in production. This module is only imported by test suites
when APP_ENVIRONMENT is not 'production'.
"""

from typing import Dict, Optional
from app.models.user import User

# In-memory registry for test tokens (development/testing only)
TEST_TOKEN_REGISTRY: Dict[str, User] = {}


def register_test_token(token: str, user: User) -> None:
    """
    Register a test token for use in test fixtures.

    Args:
        token: Test token string
        user: User object to associate with token

    Example:
        >>> test_user = User(email="test@example.com", role="doctor")
        >>> register_test_token("test_token_123", test_user)
    """
    TEST_TOKEN_REGISTRY[token] = user


def get_test_token(token: str) -> Optional[User]:
    """
    Get test user by token.

    Args:
        token: Test token string

    Returns:
        User object if found, None otherwise
    """
    return TEST_TOKEN_REGISTRY.get(token)


def clear_test_tokens() -> None:
    """Clear all registered test tokens."""
    TEST_TOKEN_REGISTRY.clear()
```

#### Step 2: Update auth_dependencies.py

**File**: `app/dependencies/auth_dependencies.py`

Remove the in-memory registry and import from testing module instead:

```python
# OLD CODE - Remove this:
"""
# In-memory registry used by test fixtures to bypass Firebase validation.
# SECURITY: This registry is ONLY used when APP_ENABLE_DEBUG=True
# In production, test tokens are NEVER accepted
"""
TEST_TOKEN_REGISTRY: Optional[Dict[str, User]] = (
    {} if _app_environment in ("development", "test", "dev", "testing") else None
)

# NEW CODE - Replace with:
# Import test fixtures only in non-production environments
_TEST_TOKEN_REGISTRY: Optional[Dict[str, User]] = None

if _app_environment not in ("production", "prod"):
    try:
        from app.testing.auth_fixtures import TEST_TOKEN_REGISTRY as _imported_registry
        _TEST_TOKEN_REGISTRY = _imported_registry
    except ImportError:
        _TEST_TOKEN_REGISTRY = {}
else:
    _TEST_TOKEN_REGISTRY = None


def _get_test_token_registry() -> Optional[Dict[str, User]]:
    """
    Get test token registry (development/testing only).

    SECURITY: Returns None in production environments.
    This method enforces the environment-based separation of test infrastructure.
    """
    if _app_environment in ("production", "prod"):
        return None
    return _TEST_TOKEN_REGISTRY
```

#### Step 3: Update get_current_user function

Update references to use the getter:

```python
# In get_current_user():

# OLD:
cached_local = None
if allow_test_tokens and TEST_TOKEN_REGISTRY is not None:
    cached_local = TEST_TOKEN_REGISTRY.get(token_value)

# NEW:
cached_local = None
test_registry = _get_test_token_registry()
if allow_test_tokens and test_registry is not None:
    cached_local = test_registry.get(token_value)
```

#### Step 4: Update tests to use fixture module

**File**: `tests/conftest.py` or test files

```python
import pytest
import os

# Only import test fixtures in non-production environments
if os.getenv("APP_ENVIRONMENT") not in ("production", "prod"):
    from app.testing.auth_fixtures import register_test_token, clear_test_tokens


@pytest.fixture
def test_user_token(test_user):
    """Fixture to register test user token."""
    token = "test_token_doctor_123"
    register_test_token(token, test_user)
    yield token
    clear_test_tokens()


def test_authenticated_endpoint(client, test_user_token):
    """Test endpoint with test token."""
    response = client.get(
        "/api/v2/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == 200
```

---

### Issue L2: Information Disclosure in Error Messages

**Severity**: LOW | **File**: `app/dependencies/auth_dependencies.py` | **Effort**: 1 hour

#### Step 1: Create error response helper

Create new file: `app/utils/error_messages.py`

```python
"""
Safe error message utilities for external API responses.

All error messages returned to clients are generic to prevent
information disclosure about internal systems.
"""

import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class SafeErrorResponse:
    """Generate safe error messages for API responses."""

    # Mapping of error types to generic public messages
    ERROR_MESSAGES: Dict[str, str] = {
        "authentication": "Authentication failed. Please check your credentials.",
        "authorization": "You do not have permission to access this resource.",
        "token_invalid": "Invalid authentication credentials.",
        "token_expired": "Your session has expired. Please log in again.",
        "not_found": "The requested resource was not found.",
        "validation": "Invalid request data provided.",
        "server_error": "An unexpected error occurred. Please try again later.",
    }

    @staticmethod
    def get_message(error_type: str, default: str = "An error occurred") -> str:
        """
        Get safe error message for error type.

        Args:
            error_type: Type of error (authentication, authorization, etc.)
            default: Default message if type not found

        Returns:
            Safe, generic error message
        """
        return SafeErrorResponse.ERROR_MESSAGES.get(error_type, default)

    @staticmethod
    def log_error_internally(
        error_type: str,
        exc: Exception,
        context: Optional[Dict[str, Any]] = None,
        **extra_data
    ) -> None:
        """
        Log full error details internally while returning generic message to client.

        Args:
            error_type: Type of error
            exc: Exception that occurred
            context: Additional context (user email, endpoint, etc.)
            **extra_data: Additional data to log
        """
        logger.error(
            f"Error ({error_type}): {exc}",
            exc_info=True,
            extra={
                "error_type": error_type,
                "exception_type": type(exc).__name__,
                **(context or {}),
                **extra_data,
            }
        )
```

#### Step 2: Update auth_dependencies.py

Replace generic exception handling with safe messages:

```python
# OLD CODE:
except Exception as e:
    logger.error(f"Firebase token verification failed: {str(e)}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Invalid Firebase token: {str(e)}",  # Exposes error details!
        headers={"WWW-Authenticate": "Bearer"},
    )

# NEW CODE:
except Exception as e:
    from app.utils.error_messages import SafeErrorResponse

    # Log full details internally
    SafeErrorResponse.log_error_internally(
        error_type="firebase_verification",
        exc=e,
        context={"endpoint": "verify_firebase_token"}
    )

    # Return generic message to client
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=SafeErrorResponse.get_message("token_invalid"),
        headers={"WWW-Authenticate": "Bearer"},
    )
```

#### Step 3: Update all exception handlers

Apply the same pattern to other exception handlers:

```python
# In get_current_user():
except HTTPException:
    raise  # Re-raise HTTP exceptions as-is
except Exception as e:
    SafeErrorResponse.log_error_internally(
        error_type="authentication",
        exc=e,
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=SafeErrorResponse.get_message("authentication"),
        headers={"WWW-Authenticate": "Bearer"},
    )
```

#### Step 4: Test safe errors

```python
def test_safe_error_messages():
    """Test that error messages don't leak details."""
    from app.utils.error_messages import SafeErrorResponse

    # Generic message for auth failure
    msg = SafeErrorResponse.get_message("token_invalid")
    assert "Invalid Firebase token" not in msg  # No tech details
    assert "firebase" not in msg.lower()

    # Generic message for server error
    msg = SafeErrorResponse.get_message("server_error")
    assert len(msg) < 100  # Short, non-technical message
```

---

### Issue L3: Explicit Path Traversal Validation

**Severity**: LOW | **File**: `app/api/v2/routers/upload/storage.py` | **Effort**: 1.5 hours

#### Step 1: Create path security utilities

Create new file: `app/utils/path_security.py`

```python
"""
Path security utilities for file operations.

Prevents path traversal attacks and validates file paths.
"""

import os
from pathlib import Path
from typing import Optional, Tuple


class PathSecurityValidator:
    """Validate file paths to prevent traversal attacks."""

    @staticmethod
    def validate_path_within_directory(
        file_path: Path,
        allowed_directory: Path,
        raise_error: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that a path is within an allowed directory.

        Uses path.resolve() to handle .. sequences and symlinks.

        Args:
            file_path: Path to validate
            allowed_directory: Root directory that should contain file
            raise_error: Raise ValueError if path is outside directory

        Returns:
            Tuple of (is_valid, error_message)

        Raises:
            ValueError: If raise_error=True and path is invalid
        """
        try:
            # Resolve both paths to absolute paths
            resolved_file = file_path.resolve()
            resolved_allowed = allowed_directory.resolve()

            # Check if resolved file path starts with allowed directory
            try:
                resolved_file.relative_to(resolved_allowed)
                return True, None

            except ValueError:
                # Path is outside allowed directory
                error = f"Path {file_path} is outside allowed directory {allowed_directory}"

                if raise_error:
                    raise ValueError(error)
                return False, error

        except (OSError, RuntimeError) as e:
            error = f"Failed to resolve path: {e}"
            if raise_error:
                raise ValueError(error)
            return False, error

    @staticmethod
    def validate_filename(
        filename: str,
        max_length: int = 255,
        raise_error: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate filename for path traversal and null bytes.

        Args:
            filename: Filename to validate
            max_length: Maximum allowed filename length
            raise_error: Raise ValueError if validation fails

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not filename:
            error = "Filename cannot be empty"
            if raise_error:
                raise ValueError(error)
            return False, error

        if len(filename) > max_length:
            error = f"Filename exceeds maximum length of {max_length}"
            if raise_error:
                raise ValueError(error)
            return False, error

        # Check for path traversal attempts
        dangerous_sequences = ["..", "/", "\\", "\x00"]
        for seq in dangerous_sequences:
            if seq in filename:
                error = f"Filename contains invalid sequence: {repr(seq)}"
                if raise_error:
                    raise ValueError(error)
                return False, error

        return True, None

    @staticmethod
    def secure_join_path(
        base_directory: Path,
        *path_components: str,
        validate: bool = True
    ) -> Path:
        """
        Safely join path components and optionally validate.

        Args:
            base_directory: Base directory (must exist)
            *path_components: Path components to join
            validate: Validate result is within base directory

        Returns:
            Resulting path

        Raises:
            ValueError: If path is invalid
        """
        # Build path
        result_path = base_directory
        for component in path_components:
            result_path = result_path / component

        # Validate if requested
        if validate:
            PathSecurityValidator.validate_path_within_directory(
                result_path, base_directory, raise_error=True
            )

        return result_path
```

#### Step 2: Update storage.py with path validation

**File**: `app/api/v2/routers/upload/storage.py`

```python
# Add import
from app.utils.path_security import PathSecurityValidator

# Update save_upload_file function
async def save_upload_file(
    file: UploadFile,
    category: FileCategory,
    user_id: UUID,
) -> Tuple[Path, str, str]:
    """
    Save uploaded file to disk with security validation.

    Args:
        file: Uploaded file
        category: File category
        user_id: User ID

    Returns:
        Tuple of (file_path, safe_filename, checksum)

    Raises:
        HTTPException: If path is invalid or file save fails
    """
    from fastapi import HTTPException, status

    try:
        # Create directory structure: uploads/{category}/{user_id}/
        category_dir = UPLOAD_DIR / category.value / str(user_id)

        # SECURITY: Validate path is within UPLOAD_DIR (defense-in-depth)
        # Even though we're using enum and UUID, explicit validation is safer
        is_valid, error_msg = PathSecurityValidator.validate_path_within_directory(
            category_dir,
            UPLOAD_DIR,
            raise_error=False
        )

        if not is_valid:
            logger.error(f"Path traversal attempt detected: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path"
            )

        # Create directory with proper error handling
        try:
            category_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, RuntimeError) as e:
            logger.error(f"Failed to create upload directory: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process upload"
            )

        # Generate safe filename
        safe_filename = generate_safe_filename(
            file.filename or "upload",
            file.content_type or "application/octet-stream"
        )

        # Validate filename (additional defense-in-depth)
        is_valid, error_msg = PathSecurityValidator.validate_filename(
            safe_filename, raise_error=False
        )

        if not is_valid:
            logger.error(f"Generated filename failed validation: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to generate safe filename"
            )

        # Construct final path
        file_path = category_dir / safe_filename

        # Final validation: ensure file path is within upload directory
        is_valid, error_msg = PathSecurityValidator.validate_path_within_directory(
            file_path,
            UPLOAD_DIR,
            raise_error=False
        )

        if not is_valid:
            logger.error(f"Final path validation failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path"
            )

        # Save file
        try:
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        finally:
            file.file.close()

        # Calculate checksum (now using SHA-256)
        checksum = calculate_checksum(file_path)

        return file_path, safe_filename, checksum

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process upload"
        )
```

#### Step 3: Test path security

```python
import pytest
from pathlib import Path
from app.utils.path_security import PathSecurityValidator


def test_path_traversal_prevention():
    """Test path traversal prevention."""
    base_dir = Path("/tmp/uploads")
    base_dir.mkdir(exist_ok=True)

    # Should fail: Path traversal
    malicious_path = base_dir / ".." / ".." / "etc" / "passwd"
    is_valid, error = PathSecurityValidator.validate_path_within_directory(
        malicious_path, base_dir, raise_error=False
    )
    assert not is_valid, "Should reject path traversal"

    # Should succeed: Normal path
    safe_path = base_dir / "user123" / "file.txt"
    is_valid, error = PathSecurityValidator.validate_path_within_directory(
        safe_path, base_dir, raise_error=False
    )
    assert is_valid, "Should accept safe path"


def test_filename_validation():
    """Test filename validation."""
    # Should fail: Contains ..
    is_valid, _ = PathSecurityValidator.validate_filename(
        "../malicious.txt", raise_error=False
    )
    assert not is_valid

    # Should fail: Contains /
    is_valid, _ = PathSecurityValidator.validate_filename(
        "dir/file.txt", raise_error=False
    )
    assert not is_valid

    # Should succeed: Normal filename
    is_valid, _ = PathSecurityValidator.validate_filename(
        "safe_filename.txt", raise_error=False
    )
    assert is_valid
```

---

### Issue L4: Add HTTPS Security Headers

**Severity**: LOW | **File**: `app/utils/security.py` | **Effort**: 30 mins

#### Step 1: Update security headers function

**File**: `app/utils/security.py`

```python
# OLD CODE - Replace:
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

# NEW CODE:
def generate_security_headers(is_production: bool = False) -> dict:
    """
    Generate security headers for public endpoints.

    Args:
        is_production: Whether running in production (enables HSTS, etc.)

    Returns:
        Dictionary of security headers
    """
    headers = {
        # Content Type Protection
        "X-Content-Type-Options": "nosniff",

        # Frame Protection (clickjacking)
        "X-Frame-Options": "DENY",

        # XSS Protection (older browsers)
        "X-XSS-Protection": "1; mode=block",

        # Referrer Policy
        "Referrer-Policy": "strict-origin-when-cross-origin",

        # Content Security Policy
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        ),

        # Permissions Policy (formerly Feature Policy)
        "Permissions-Policy": (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "usb=(), "
            "accelerometer=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "payment=()"
        ),
    }

    # Production-specific headers
    if is_production:
        # HSTS: Force HTTPS for 1 year, include subdomains, preload
        headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Upgrade insecure requests to HTTPS
        headers["Upgrade-Insecure-Requests"] = "1"

        # Deny embedding in frames
        headers["X-Frame-Options"] = "DENY"

        # Remove inline scripts in CSP for production
        headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "  # No unsafe-inline
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )

    return headers
```

#### Step 2: Apply headers in middleware

**File**: `app/core/middleware_setup.py` or `app/core/application_factory.py`

```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

def setup_middleware(app: FastAPI, settings) -> None:
    """Setup application middleware with security headers."""

    # Trust headers from reverse proxy (Cloudflare, nginx, etc.)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Allow all, but we validate CORS separately
    )

    # Add security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)

        # Generate headers based on environment
        is_prod = settings.APP_ENVIRONMENT.lower() == "production"
        security_headers = generate_security_headers(is_production=is_prod)

        # Add all security headers
        for header_name, header_value in security_headers.items():
            response.headers[header_name] = header_value

        return response

    # ... rest of middleware setup
```

#### Step 3: Test headers in production

```python
def test_security_headers_production():
    """Test security headers are set correctly in production."""
    from app.utils.security import generate_security_headers

    headers = generate_security_headers(is_production=True)

    # Should include HSTS
    assert "Strict-Transport-Security" in headers
    assert "max-age=31536000" in headers["Strict-Transport-Security"]
    assert "includeSubDomains" in headers["Strict-Transport-Security"]

    # Should upgrade insecure
    assert headers.get("Upgrade-Insecure-Requests") == "1"

    # Should have CSP without inline scripts
    assert "'unsafe-inline'" not in headers["Content-Security-Policy"]
```

---

## Validation Checklist

After implementing all fixes:

- [ ] MD5 → SHA-256 migration complete
- [ ] Logging filter blocks all sensitive patterns
- [ ] Session cookies validated in production config
- [ ] Test token registry moved to separate module
- [ ] Error messages are generic (no tech details)
- [ ] Path traversal validation in place
- [ ] Security headers include HSTS in production
- [ ] All tests pass: `pytest tests/security/`
- [ ] No sensitive data in logs: `grep -r "password\|token\|secret" logs/`
- [ ] Code review completed

---

## Rollout Plan

### Phase 1: Development (Week 1)
- [ ] Implement all fixes locally
- [ ] Run security tests
- [ ] Code review with team

### Phase 2: Staging (Week 2)
- [ ] Deploy to staging environment
- [ ] Run full security test suite
- [ ] Manual security testing
- [ ] Performance validation

### Phase 3: Production (Week 3)
- [ ] Deploy fixes in non-breaking order
- [ ] Monitor logs for issues
- [ ] Validate all systems operational
- [ ] Document changes for compliance

---

## Testing Commands

```bash
# Run all security tests
pytest tests/security/ -v

# Check for hardcoded secrets
grep -r "password\|secret\|api_key\|token" app/ --include="*.py" | grep -v "# SECURITY:" | grep -v ".md"

# Validate no SQL injection
grep -r "f\".*select\|f\".*where\|f\".*insert" app/ --include="*.py"

# Test path security
python -c "from tests.utils.test_path_security import test_path_traversal_prevention; test_path_traversal_prevention()"

# Check for eval usage
grep -r "eval(\|exec(" app/ --include="*.py"

# Validate logging doesn't expose secrets
grep -r "logger.*password\|logger.*token\|logger.*secret" app/ --include="*.py"
```

---

## Estimated Timeline

| Task | Effort | Timeline |
|------|--------|----------|
| M1: MD5 → SHA-256 | 0.5h | Day 1 AM |
| M2: Logging filter | 1h | Day 1 PM |
| M3: Session validation | 1h | Day 2 AM |
| L1: Test fixtures | 2h | Day 2 PM |
| L2: Safe errors | 1h | Day 3 AM |
| L3: Path security | 1.5h | Day 3 AM-PM |
| L4: Security headers | 0.5h | Day 3 PM |
| Testing | 2h | Day 4 |
| Code review | 1h | Day 4-5 |
| **Total** | **10h** | **1 week** |

---

## Support & Questions

For questions about these fixes:
1. Check the SECURITY_AUDIT_REPORT.md for full context
2. Review the code comments in each fix
3. Run test suites to validate behavior
4. Consult OWASP guidelines for standards

---

**End of Remediation Guide**
