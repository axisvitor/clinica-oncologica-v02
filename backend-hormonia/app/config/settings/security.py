"""
Security configuration module: JWT, Firebase Auth, CSRF, CORS, and encryption settings.
ENV Variable Naming Convention: {CATEGORY}_{SUBCATEGORY}_{ATTRIBUTE}_{UNIT}
"""

from pydantic import Field, model_validator, field_validator
from typing import List, Optional, Any
import json
from .base import BaseAppSettings


class SecuritySettings(BaseAppSettings):
    """Security configuration for authentication, authorization, and protection."""

    # ============================================================================
    # Security Keys - Direct ENV names
    # ============================================================================
    SECURITY_SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-must-be-changed-in-production-railway",
        description="Secret key for JWT signing. MUST be set via environment variable in production.",
    )
    SECURITY_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ENCRYPTION_KEY_CURRENT: Optional[str] = Field(
        default=None,
        description="Fernet key for legacy field encryption (base64)",
    )
    PHI_ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Base64-encoded 32-byte key for PHI/PII encryption (AES-GCM)",
    )
    HASH_SALT: Optional[str] = Field(
        default=None,
        description="Hex-encoded salt for searchable hash generation",
    )
    SECURITY_ENCRYPTION_KEY: Optional[str] = Field(
        default=None, description="Legacy fallback for ENCRYPTION_KEY_CURRENT"
    )

    # ============================================================================
    # Authentication - Direct ENV names
    # ============================================================================
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, description="JWT expiration time"
    )
    AUTH_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7, description="Refresh token expiration time in days"
    )
    AUTH_BCRYPT_ROUNDS: int = Field(
        default=12,
        description="Bcrypt hashing rounds for password security (12-15 recommended for production)",
    )

    # Token Rotation & Blacklist - Direct ENV names
    AUTH_ENABLE_TOKEN_ROTATION: bool = Field(
        default=False,
        description="Enable automatic token rotation for enhanced security",
    )
    AUTH_ENABLE_TOKEN_BLACKLIST: bool = Field(
        default=True, description="Enable token blacklist for logout/revocation support"
    )

    # ============================================================================
    # Session and Cookie Configuration - Direct ENV names
    # ============================================================================
    SESSION_ENABLE_COOKIE_SECURE: bool = Field(
        default=False,
        description="Require HTTPS for session cookies (must be True in production)",
    )
    SESSION_ENABLE_COOKIE_HTTPONLY: bool = Field(
        default=True,
        description="Prevent JavaScript access to session cookies (XSS protection)",
    )
    SESSION_COOKIE_SAMESITE: str = Field(
        default="lax",
        description="SameSite cookie attribute: 'strict', 'lax', or 'none' (CSRF protection)",
    )
    SESSION_COOKIE_NAME: str = Field(
        default="session_id", description="Name of the session cookie"
    )
    SESSION_COOKIE_PATH: str = Field(default="/", description="Path for session cookie")
    SESSION_COOKIE_DOMAIN: Optional[str] = Field(
        default=None,
        description="Domain for session cookie (None = current domain only)",
    )
    SESSION_COOKIE_MAX_AGE_SECONDS: int = Field(
        default=28800,
        description="Session cookie max age in seconds (default: 8 hours)",
    )

    # ========================================================================
    # Authentication Feature Flags
    # ========================================================================
    ENABLE_STRICT_UID_VALIDATION: bool = Field(
        default=True,
        description="Enable strict Firebase UID validation (28 chars)",
    )
    ENABLE_COOKIE_PRIORITY: bool = Field(
        default=True,
        description="Prioritize cookie over header for session ID",
    )

    # ============================================================================
    # Security Features - Direct ENV names
    # ============================================================================
    SECURITY_ENABLE_SSL_REDIRECT: bool = Field(
        default=False, description="Force HTTPS redirect"
    )
    SECURITY_ENABLE_CONTENT_TYPE_NOSNIFF: bool = Field(
        default=True, description="Enable X-Content-Type-Options: nosniff header"
    )
    SECURITY_ENABLE_BROWSER_XSS_FILTER: bool = Field(
        default=True, description="Enable X-XSS-Protection header"
    )
    SECURITY_ENABLE_FIELD_ENCRYPTION: bool = Field(
        default=True, description="Enable field-level encryption for sensitive data"
    )

    # ============================================================================
    # CSRF Protection - Direct ENV name
    # ============================================================================
    SECURITY_CSRF_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Secret key for CSRF token generation (generate with secrets.token_urlsafe(32))",
    )

    # ============================================================================
    # Firebase Admin SDK Configuration
    # ============================================================================
    FIREBASE_ADMIN_PROJECT_ID: Optional[str] = Field(
        default=None, description="Firebase Admin SDK project ID"
    )
    FIREBASE_ADMIN_PRIVATE_KEY: Optional[str] = Field(
        default=None, description="Firebase Admin SDK service account private key"
    )
    FIREBASE_ADMIN_CLIENT_EMAIL: Optional[str] = Field(
        default=None, description="Firebase Admin SDK service account email"
    )
    FIREBASE_ADMIN_SDK_TIMEOUT: int = Field(
        default=10, description="Timeout in seconds for Firebase Admin SDK calls"
    )

    # Firebase Security Configuration - Direct ENV names
    FIREBASE_ALLOWED_DOMAINS: List[str] = Field(
        default_factory=list,
        description="Authorized email domains for Firebase user creation (no public domains allowed)",
    )
    FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS: bool = Field(
        default=True,
        description="Require valid custom claims (role) before creating user",
    )
    FIREBASE_ALLOWED_ROLES: List[str] = Field(
        default=["admin", "doctor", "medico"],
        description="Allowed roles in Firebase custom claims",
    )
    FIREBASE_ENABLE_AUDIT_LOGGING: bool = Field(
        default=True,
        description="Enable comprehensive audit logging for user provisioning",
    )
    FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS: bool = Field(
        default=True,
        description="Block public email domains (gmail.com, yahoo.com, etc.)",
    )
    FIREBASE_PUBLIC_DOMAINS_BLOCKLIST: List[str] = Field(
        default=[
            "gmail.com",
            "yahoo.com",
            "hotmail.com",
            "outlook.com",
            "icloud.com",
        ],
        description="Public email domains that are explicitly blocked",
    )

    # Firebase Redis Cache Configuration - Direct ENV names
    FIREBASE_TOKEN_CACHE_TTL_SECONDS: int = Field(
        default=3600,
        description="Firebase token validation cache TTL in seconds (Layer 1 - Default: 1 hour)",
    )
    FIREBASE_USER_CACHE_TTL_SECONDS: int = Field(
        default=7200,
        description="Firebase user object cache TTL in seconds (Layer 2 - Default: 2 hours)",
    )
    FIREBASE_SESSION_TTL_SECONDS: int = Field(
        default=86400,
        description="Firebase session management TTL in seconds (Layer 3 - Default: 24 hours)",
    )
    SESSION_MAX_AGE_SECONDS: int = Field(
        default=604800,  # 7 days
        description="Maximum absolute session lifetime in seconds regardless of activity (Default: 7 days)",
    )

    # ============================================================================
    # Rate Limiting Configuration - Direct ENV name
    # ============================================================================
    RATE_LIMIT_ENABLE_SERVICE: bool = Field(
        default=True, description="Enable rate limiting on authentication endpoints"
    )
    RATE_LIMIT_REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis URL for rate limiting storage (uses REDIS_URL if not set, in-memory if Redis unavailable)",
    )

    # ============================================================================
    # CORS Configuration - Direct ENV names
    # ============================================================================
    CORS_FRONTEND_URL: str = Field(
        default="http://localhost:5173",
        description="Frontend URL (used for CORS in production)",
    )
    CORS_QUIZ_URL: str = Field(
        default="http://localhost:3001",
        description="Quiz interface URL (used for CORS in production)",
    )
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default=[],
        description="Allowed CORS origins (combined with CORS_FRONTEND_URL + CORS_QUIZ_URL)",
    )
    CORS_ALLOWED_HEADERS: List[str] = Field(
        default=[
            "Content-Type",
            "Authorization",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-CSRF-Token",
            "X-CSRFToken",
            "X-XSRF-Token",
        ],
        description="Allowed CORS headers (validated against safe headers whitelist)",
    )

    # ============================================================================
    # Validators
    # ============================================================================

    @model_validator(mode="after")
    def validate_secret_key(self) -> "SecuritySettings":
        """
        Validate SECRET_KEY is secure and not using default/development values.

        CRITICAL SECURITY: Prevents deployment with insecure default SECRET_KEY.

        Rules:
        - Production: MUST NOT contain "dev-insecure" and MUST be at least 32 characters
        - Development: Warns if using weak keys but allows startup
        """
        import logging

        logger = logging.getLogger(__name__)
        is_production = self.APP_ENVIRONMENT.lower() == "production"

        # Check if SECRET_KEY is set
        if not self.SECURITY_SECRET_KEY:
            if is_production:
                raise ValueError(
                    "SECURITY_SECRET_KEY must be set in production environment.\n"
                    "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
                )
            else:
                logger.warning(
                    "⚠️  SECURITY_SECRET_KEY not set. Using empty key is UNSAFE even in development!"
                )
                return self

        # Check for insecure patterns
        insecure_patterns = ["dev-insecure", "must-be-changed", "change-this", "your-secret"]
        key_lower = self.SECURITY_SECRET_KEY.lower()

        if any(pattern in key_lower for pattern in insecure_patterns):
            if is_production:
                raise ValueError(
                    f"SECURITY_SECRET_KEY contains insecure default value and CANNOT be used in production.\n"
                    f"Current key starts with: {self.SECURITY_SECRET_KEY[:20]}...\n"
                    f"Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
                )
            else:
                logger.warning(
                    f"⚠️  SECURITY_SECRET_KEY contains development/default value: {self.SECURITY_SECRET_KEY[:20]}...\n"
                    "This is UNSAFE for production. Generate a secure key with:\n"
                    "python -c 'import secrets; print(secrets.token_urlsafe(64))'"
                )

        # Check minimum length (32 characters is minimum, 64+ recommended)
        if len(self.SECURITY_SECRET_KEY) < 32:
            if is_production:
                raise ValueError(
                    f"SECURITY_SECRET_KEY must be at least 32 characters (current: {len(self.SECURITY_SECRET_KEY)}).\n"
                    "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
                )
            else:
                logger.warning(
                    f"⚠️  SECURITY_SECRET_KEY is too short ({len(self.SECURITY_SECRET_KEY)} characters). "
                    "Minimum 32 characters required, 64+ recommended for production."
                )

        return self

    @model_validator(mode="after")
    def validate_required_environment_variables(self) -> "SecuritySettings":
        """
        Validate that all required environment variables are set at startup.

        This validator runs AFTER model initialization to ensure the app fails fast
        with clear error messages if critical environment variables are missing.

        In production, all security-critical variables must be set.
        In development, only Firebase variables are validated (if Firebase is in use).
        """
        import os

        is_production = self.APP_ENVIRONMENT.lower() == "production"
        missing_vars = []

        # ============================================================================
        # Production-Only Required Variables
        # ============================================================================
        if is_production:
            # CSRF Protection
            if not self.SECURITY_CSRF_SECRET_KEY:
                missing_vars.append(
                    "SECURITY_CSRF_SECRET_KEY - Required for CSRF token generation\n"
                    "  Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            # Encryption Keys
            encryption_key = self.ENCRYPTION_KEY_CURRENT or self.SECURITY_ENCRYPTION_KEY
            if not encryption_key:
                missing_vars.append(
                    "ENCRYPTION_KEY_CURRENT - Required for field-level encryption (PHI/PII)\n"
                    "  Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )

            phi_encryption_key = self.PHI_ENCRYPTION_KEY or os.getenv(
                "COMPLIANCE_PHI_ENCRYPTION_KEY"
            )
            if not phi_encryption_key:
                missing_vars.append(
                    "PHI_ENCRYPTION_KEY - Required for AES-GCM encryption\n"
                    "  Generate with: python -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'"
                )

            # Hash Salt for searchable encryption
            hash_salt = self.HASH_SALT or os.getenv("COMPLIANCE_HASH_SALT")
            if not hash_salt:
                missing_vars.append(
                    "HASH_SALT - Required for searchable hash generation\n"
                    "  Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
                )

        # ============================================================================
        # Firebase Validation (All Environments if Firebase is in use)
        # ============================================================================
        # Check if Firebase is being used (any Firebase field is set)
        firebase_in_use = any(
            [
                self.FIREBASE_ADMIN_PROJECT_ID,
                self.FIREBASE_ADMIN_PRIVATE_KEY,
                self.FIREBASE_ADMIN_CLIENT_EMAIL,
            ]
        )

        if firebase_in_use:
            # If any Firebase field is set, all must be set
            if not self.FIREBASE_ADMIN_PROJECT_ID:
                missing_vars.append(
                    "FIREBASE_ADMIN_PROJECT_ID - Required when using Firebase Admin SDK\n"
                    "  Get from Firebase Console > Project Settings > Service Accounts"
                )

            if not self.FIREBASE_ADMIN_PRIVATE_KEY:
                missing_vars.append(
                    "FIREBASE_ADMIN_PRIVATE_KEY - Required when using Firebase Admin SDK\n"
                    "  Get from Firebase Console > Project Settings > Service Accounts > Generate New Private Key"
                )

            if not self.FIREBASE_ADMIN_CLIENT_EMAIL:
                missing_vars.append(
                    "FIREBASE_ADMIN_CLIENT_EMAIL - Required when using Firebase Admin SDK\n"
                    "  Get from Firebase Console > Project Settings > Service Accounts"
                )

        # ============================================================================
        # Fail Fast with Clear Error Message
        # ============================================================================
        if missing_vars:
            error_header = (
                "\n" + "=" * 80 + "\n"
                "❌ STARTUP VALIDATION FAILED: Missing Required Environment Variables\n"
                "=" * 80 + "\n"
            )

            error_body = "\nThe following environment variables are missing:\n\n"
            for i, var_msg in enumerate(missing_vars, 1):
                error_body += f"{i}. {var_msg}\n\n"

            error_footer = (
                "=" * 80 + "\n"
                f"Environment: {self.APP_ENVIRONMENT}\n"
                "Please set these variables in your .env file or environment configuration.\n"
                "=" * 80 + "\n"
            )

            raise ValueError(error_header + error_body + error_footer)

        return self

    @field_validator("CORS_ALLOWED_HEADERS")
    @classmethod
    def validate_cors_headers(cls, v: List[str]) -> List[str]:
        """
        Validate CORS allowed headers against security whitelist.

        Prevents runtime modification with unsafe headers that could
        expose sensitive data or enable attacks.

        Security Issue: HIGH-002 - CORS Wildcard Headers Vulnerability
        """
        # Whitelist of safe CORS headers
        SAFE_HEADERS = {
            "Content-Type",
            "Authorization",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-CSRF-Token",
            "X-CSRFToken",
            "X-XSRF-Token",
            "X-API-Key",
            "Cache-Control",
            "Pragma",
        }

        # Check for wildcard (critical security issue)
        if "*" in v:
            raise ValueError(
                "CORS wildcard headers cannot be used with credentials. "
                "This violates CORS specification and exposes all request headers."
            )

        # Check for unsafe headers
        unsafe_headers = set(v) - SAFE_HEADERS
        if unsafe_headers:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Non-standard CORS headers detected: {unsafe_headers}. "
                f"Only whitelisted headers are recommended for security: {SAFE_HEADERS}"
            )

        return v

    @model_validator(mode="before")
    @classmethod
    def parse_security_values(cls, data: Any) -> Any:
        """Parse security-related environment variable values."""
        # Parse boolean fields - Using new field names
        boolean_fields = [
            "SESSION_ENABLE_COOKIE_SECURE",
            "SESSION_ENABLE_COOKIE_HTTPONLY",
            "SECURITY_ENABLE_SSL_REDIRECT",
            "FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS",
            "FIREBASE_ENABLE_AUDIT_LOGGING",
            "FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS",
            "RATE_LIMIT_ENABLE_SERVICE",
        ]

        for field in boolean_fields:
            if field in data:
                v = data[field]
                if isinstance(v, bool):
                    data[field] = v
                elif isinstance(v, str):
                    data[field] = v.lower() not in ("false", "0", "no", "off", "")
                else:
                    data[field] = bool(v)

        # Parse FIREBASE_ALLOWED_DOMAINS from JSON string
        if "FIREBASE_ALLOWED_DOMAINS" in data:
            v = data["FIREBASE_ALLOWED_DOMAINS"]
            if v is None or v == "":
                data["FIREBASE_ALLOWED_DOMAINS"] = []
            elif isinstance(v, str):
                try:
                    data["FIREBASE_ALLOWED_DOMAINS"] = json.loads(v)
                except json.JSONDecodeError:
                    data["FIREBASE_ALLOWED_DOMAINS"] = []

        # Parse CORS_ALLOWED_ORIGINS
        if "CORS_ALLOWED_ORIGINS" in data:
            v = data["CORS_ALLOWED_ORIGINS"]
            if isinstance(v, list) and len(v) > 0:
                pass  # Already a list
            elif isinstance(v, str) and v.strip():
                s = v.strip()
                if s.startswith("["):
                    try:
                        data["CORS_ALLOWED_ORIGINS"] = json.loads(s)
                    except (json.JSONDecodeError, ValueError):
                        data["CORS_ALLOWED_ORIGINS"] = [
                            item.strip() for item in s.split(",") if item.strip()
                        ]
                else:
                    data["CORS_ALLOWED_ORIGINS"] = [
                        item.strip() for item in s.split(",") if item.strip()
                    ]
            else:
                data["CORS_ALLOWED_ORIGINS"] = []

        # Validate security keys are not placeholders (only in production)
        # In development, default insecure keys are allowed for local testing
        import os

        is_production = (
            os.environ.get("APP_ENVIRONMENT", "development").lower() == "production"
        )

        if is_production:
            placeholder_patterns = [
                "CHANGE_THIS",
                "YOUR_",
                "INSECURE",
                "DEV-",
                "MUST-BE-CHANGED",
            ]
            generation_commands = {
                "SECURITY_SECRET_KEY": "python -c 'import secrets; print(secrets.token_urlsafe(64))'",
                "SECURITY_CSRF_SECRET_KEY": "python -c 'import secrets; print(secrets.token_urlsafe(32))'",
                "ENCRYPTION_KEY_CURRENT": "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'",
                "PHI_ENCRYPTION_KEY": "python -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'",
                "HASH_SALT": "python -c 'import secrets; print(secrets.token_hex(32))'",
                "SECURITY_ENCRYPTION_KEY": "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'",
            }
            for field in [
                "SECURITY_SECRET_KEY",
                "SECURITY_CSRF_SECRET_KEY",
                "ENCRYPTION_KEY_CURRENT",
                "PHI_ENCRYPTION_KEY",
                "HASH_SALT",
                "SECURITY_ENCRYPTION_KEY",
            ]:
                if field in data:
                    v = data[field]
                    if v and any(
                        pattern in v.upper() for pattern in placeholder_patterns
                    ):
                        command = generation_commands.get(
                            field,
                            "python -c 'import secrets; print(secrets.token_urlsafe(64))'",
                        )
                        raise ValueError(
                            f"{field} must be changed from placeholder/default value in production. "
                            f"Generate a secure key with: {command}"
                        )

        return data

    def validate_csrf_config(self):
        """Validate CSRF secret key strength at application startup."""
        import logging

        logger = logging.getLogger(__name__)

        if self.SECURITY_CSRF_SECRET_KEY:
            try:
                # Import validation function
                from app.utils.security_validation import validate_csrf_secret

                # Validate CSRF secret with entropy checking
                # log_validation=True will log metrics without exposing the secret
                validate_csrf_secret(self.SECURITY_CSRF_SECRET_KEY, log_validation=True)
                logger.info("✅ CSRF secret validation passed")

            except ValueError as e:
                logger.error(f"❌ CSRF secret validation failed: {e}")

                # In production, weak CSRF secrets should prevent application startup
                if self.APP_ENVIRONMENT.lower() == "production":
                    raise ValueError(
                        f"CSRF secret validation failed in production: {e}\n"
                        "Generate a secure secret with: "
                        "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                    )
                else:
                    # In development, just warn but allow startup
                    logger.warning(
                        "⚠️  Continuing in development mode with weak CSRF secret. "
                        "This is NOT SAFE for production! "
                        "Generate a secure secret with: "
                        "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                    )
        else:
            logger.warning(
                "⚠️  SECURITY_CSRF_SECRET_KEY not configured. "
                "CSRF protection will be disabled. "
                "For production, generate a secret with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

    def validate_production_config(self):
        """
        Validate production environment has secure configurations.

        Security Issue: AUTH-001
        Validates that all security keys have sufficient entropy to prevent
        weak/placeholder keys in production.
        """
        if self.APP_ENVIRONMENT.lower() == "production":
            errors = []

            # DEBUG must be False in production
            if self.APP_ENABLE_DEBUG:
                errors.append(
                    "APP_ENABLE_DEBUG must be False in production environment"
                )

            # Session cookies must be secure in production
            if not self.SESSION_ENABLE_COOKIE_SECURE:
                errors.append(
                    "SESSION_ENABLE_COOKIE_SECURE must be True in production environment"
                )

            # HttpOnly should always be true for security
            if not self.SESSION_ENABLE_COOKIE_HTTPONLY:
                errors.append(
                    "SESSION_ENABLE_COOKIE_HTTPONLY must be True to prevent XSS attacks"
                )

            # SameSite should be strict, lax, or none in production
            if self.SESSION_COOKIE_SAMESITE.lower() not in ["strict", "lax", "none"]:
                errors.append(
                    f"SESSION_COOKIE_SAMESITE must be 'strict', 'lax', or 'none' in production (got: {self.SESSION_COOKIE_SAMESITE})"
                )

            # SSL redirect should be enabled in production
            if not self.SECURITY_ENABLE_SSL_REDIRECT:
                errors.append(
                    "SECURITY_ENABLE_SSL_REDIRECT must be True in production environment"
                )

            # ===================================================================
            # AUTH-001: Validate entropy of security keys (NEW)
            # ===================================================================
            try:
                from app.utils.security_validation import (
                    validate_all_secrets,
                    mask_secret_for_logging,
                )

                import logging

                logger = logging.getLogger(__name__)

                # Collect all security keys that need validation
                secrets_to_validate = {}

                if self.SECURITY_SECRET_KEY:
                    secrets_to_validate["SECURITY_SECRET_KEY"] = (
                        self.SECURITY_SECRET_KEY
                    )

                encryption_key_current = (
                    self.ENCRYPTION_KEY_CURRENT or self.SECURITY_ENCRYPTION_KEY
                )
                if encryption_key_current:
                    secrets_to_validate["ENCRYPTION_KEY_CURRENT"] = (
                        encryption_key_current
                    )

                if self.SECURITY_CSRF_SECRET_KEY:
                    secrets_to_validate["SECURITY_CSRF_SECRET_KEY"] = (
                        self.SECURITY_CSRF_SECRET_KEY
                    )

                if self.PHI_ENCRYPTION_KEY:
                    secrets_to_validate["PHI_ENCRYPTION_KEY"] = (
                        self.PHI_ENCRYPTION_KEY
                    )

                if self.HASH_SALT:
                    secrets_to_validate["HASH_SALT"] = self.HASH_SALT

                # Validate all secrets
                validation_results = validate_all_secrets(
                    secrets_to_validate, environment="production"
                )

                # Check for any invalid keys
                for key_name, result in validation_results.items():
                    if not result.is_valid:
                        masked_key = mask_secret_for_logging(
                            secrets_to_validate[key_name]
                        )

                        error_msg = (
                            f"{key_name} has insufficient entropy:\n"
                            f"  - Masked value: {masked_key}\n"
                            f"  - Entropy: {result.entropy_bits:.1f} bits (minimum: 128)\n"
                            f"  - Strength: {result.strength_level}\n"
                            f"  - Issues: {', '.join(result.issues)}\n"
                            f"  - Recommendation: {result.recommendations[0] if result.recommendations else 'Generate secure key'}"
                        )
                        errors.append(error_msg)
                        logger.error(f"❌ {key_name} validation failed: {error_msg}")
                    else:
                        # Log successful validation (with masked key)
                        masked_key = mask_secret_for_logging(
                            secrets_to_validate[key_name]
                        )
                        logger.info(
                            f"✅ {key_name} validation passed: "
                            f"entropy={result.entropy_bits:.1f} bits, "
                            f"strength={result.strength_level}, "
                            f"masked={masked_key}"
                        )

            except ImportError as e:
                errors.append(
                    f"Could not import security validation module: {e}\n"
                    "Ensure app.utils.security_validation is available"
                )

            if errors:
                raise ValueError(
                    "Production environment security validation failed:\n"
                    + "\n".join(f"  - {error}" for error in errors)
                )

    def _normalize_cors_origin(self, origin: str, is_production: bool) -> str:
        """
        Normalize a CORS origin URL.

        - Strips whitespace, quotes, and trailing slashes
        - Adds https:// prefix if missing and in production
        - Adds http:// prefix if missing and in development (for localhost)

        Args:
            origin: The origin URL to normalize
            is_production: Whether running in production mode

        Returns:
            Normalized origin URL with proper protocol
        """
        normalized = origin.strip().strip('"').strip("'").rstrip("/")
        if not normalized:
            return ""

        # If already has protocol, return as-is
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return normalized

        # Add appropriate protocol based on environment
        if is_production:
            # Production: always use HTTPS
            return f"https://{normalized}"
        else:
            # Development: use HTTP for localhost, HTTPS for others
            if "localhost" in normalized or "127.0.0.1" in normalized:
                return f"http://{normalized}"
            else:
                return f"https://{normalized}"

    def get_cors_origins(self) -> List[str]:
        """
        Returns CORS origins from environment configuration only.

        Logic:
        1. Start with any explicitly configured CORS_ALLOWED_ORIGINS
        2. Add CORS_FRONTEND_URL and CORS_QUIZ_URL if set
        3. Normalize all origins (strip whitespace, remove trailing slashes)
        4. Auto-add https:// prefix if missing in production

        All origins must come from environment variables.
        """
        origins = set()
        is_production = self.APP_ENVIRONMENT.lower() == "production"

        # 1. Explicitly configured origins
        if self.CORS_ALLOWED_ORIGINS:
            for origin in self.CORS_ALLOWED_ORIGINS:
                normalized = self._normalize_cors_origin(origin, is_production)
                if normalized:
                    origins.add(normalized)

        # 2. Configured Frontend/Quiz URLs (only if not localhost in production)
        if self.CORS_FRONTEND_URL:
            normalized = self._normalize_cors_origin(self.CORS_FRONTEND_URL, is_production)
            # Skip localhost URLs in production
            if normalized and not (is_production and "localhost" in normalized):
                origins.add(normalized)

        if self.CORS_QUIZ_URL:
            normalized = self._normalize_cors_origin(self.CORS_QUIZ_URL, is_production)
            # Skip localhost URLs in production
            if normalized and not (is_production and "localhost" in normalized):
                origins.add(normalized)

        return list(origins)

    def get_firebase_security_config(self) -> dict:
        """Get Firebase security configuration for user provisioning."""
        return {
            "allowed_domains": self.FIREBASE_ALLOWED_DOMAINS,
            "require_custom_claims": self.FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS,
            "allowed_roles": self.FIREBASE_ALLOWED_ROLES,
            "enable_audit_logging": self.FIREBASE_ENABLE_AUDIT_LOGGING,
            "block_public_domains": self.FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS,
            "public_domains_blocklist": self.FIREBASE_PUBLIC_DOMAINS_BLOCKLIST,
        }
