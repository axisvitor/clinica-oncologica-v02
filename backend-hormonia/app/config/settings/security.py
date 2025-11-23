"""
Security configuration module: JWT, Firebase Auth, CSRF, CORS, and encryption settings.
"""

from pydantic import Field, model_validator
from typing import List, Optional, Any
import json
from .base import BaseAppSettings


class SecuritySettings(BaseAppSettings):
    """Security configuration for authentication, authorization, and protection."""

    # ============================================================================
    # JWT Configuration
    # ============================================================================
    SECRET_KEY: str = Field(..., description="Secret key for JWT signing")
    JWT_SECRET_KEY: Optional[str] = Field(
        default=None, description="JWT secret key (fallback to SECRET_KEY if not set)"
    )
    ENCRYPTION_KEY: Optional[str] = Field(
        default=None, description="Encryption key for sensitive data"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, description="JWT expiration time"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7, description="Refresh token expiration time in days"
    )
    BCRYPT_ROUNDS: int = Field(
        default=12,
        description="Bcrypt hashing rounds for password security (12-15 recommended for production)",
    )

    # ============================================================================
    # Session and Cookie Configuration
    # ============================================================================
    SESSION_COOKIE_SECURE: bool = Field(
        default=False, description="Require HTTPS for session cookies (must be True in production)"
    )
    SESSION_COOKIE_HTTPONLY: bool = Field(
        default=True, description="Prevent JavaScript access to session cookies (XSS protection)"
    )
    SESSION_COOKIE_SAMESITE: str = Field(
        default="lax", description="SameSite cookie attribute: 'strict', 'lax', or 'none' (CSRF protection)"
    )
    SESSION_COOKIE_NAME: str = Field(
        default="session_id", description="Name of the session cookie"
    )
    SESSION_COOKIE_PATH: str = Field(
        default="/", description="Path for session cookie"
    )
    SESSION_COOKIE_DOMAIN: Optional[str] = Field(
        default=None, description="Domain for session cookie (None = current domain only)"
    )
    SESSION_COOKIE_MAX_AGE: int = Field(
        default=28800, description="Session cookie max age in seconds (default: 8 hours)"
    )
    SECURE_SSL_REDIRECT: bool = Field(default=False, description="Force HTTPS redirect")

    # ============================================================================
    # CSRF Protection
    # ============================================================================
    CSRF_SECRET_KEY: Optional[str] = Field(
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

    # Firebase Security Configuration
    FIREBASE_ALLOWED_DOMAINS: List[str] = Field(
        default_factory=list,
        description="Authorized email domains for Firebase user creation (no public domains allowed)",
    )
    FIREBASE_REQUIRE_CUSTOM_CLAIMS: bool = Field(
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
    FIREBASE_BLOCK_PUBLIC_DOMAINS: bool = Field(
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

    # Firebase Redis Cache Configuration (3-Layer Architecture)
    FIREBASE_TOKEN_CACHE_TTL: int = Field(
        default=3600,
        description="Firebase token validation cache TTL in seconds (Layer 1 - Default: 1 hour)",
    )
    FIREBASE_USER_CACHE_TTL: int = Field(
        default=7200,
        description="Firebase user object cache TTL in seconds (Layer 2 - Default: 2 hours)",
    )
    FIREBASE_SESSION_TTL: int = Field(
        default=86400,
        description="Firebase session management TTL in seconds (Layer 3 - Default: 24 hours)",
    )

    # ============================================================================
    # Rate Limiting Configuration
    # ============================================================================
    RATE_LIMIT_ENABLED: bool = Field(
        default=True, description="Enable rate limiting on authentication endpoints"
    )
    RATE_LIMIT_REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis URL for rate limiting storage (uses REDIS_URL if not set, in-memory if Redis unavailable)",
    )

    # ============================================================================
    # CORS Configuration
    # ============================================================================
    FRONTEND_URL: str = Field(
        default="http://localhost:5173",
        description="Frontend URL (used for CORS in production)",
    )
    QUIZ_URL: str = Field(
        default="http://localhost:3001",
        description="Quiz interface URL (used for CORS in production)",
    )
    ALLOWED_ORIGINS: List[str] | str = Field(
        default=[],
        description="Allowed CORS origins (auto-constructed from FRONTEND_URL + QUIZ_URL in production, empty in dev for regex)",
    )

    # ============================================================================
    # Validators
    # ============================================================================

    @model_validator(mode="before")
    @classmethod
    def parse_security_values(cls, data: Any) -> Any:
        """Parse security-related environment variable values."""
        # Parse boolean fields
        boolean_fields = [
            "SESSION_COOKIE_SECURE",
            "SESSION_COOKIE_HTTPONLY",
            "SECURE_SSL_REDIRECT",
            "FIREBASE_REQUIRE_CUSTOM_CLAIMS",
            "FIREBASE_ENABLE_AUDIT_LOGGING",
            "FIREBASE_BLOCK_PUBLIC_DOMAINS",
            "RATE_LIMIT_ENABLED",
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

        # Parse ALLOWED_ORIGINS
        if "ALLOWED_ORIGINS" in data:
            v = data["ALLOWED_ORIGINS"]
            if isinstance(v, list) and len(v) > 0:
                pass  # Already a list
            elif isinstance(v, str) and v.strip():
                s = v.strip()
                if s.startswith("["):
                    try:
                        data["ALLOWED_ORIGINS"] = json.loads(s)
                    except:
                        data["ALLOWED_ORIGINS"] = [
                            item.strip() for item in s.split(",") if item.strip()
                        ]
                else:
                    data["ALLOWED_ORIGINS"] = [
                        item.strip() for item in s.split(",") if item.strip()
                    ]
            else:
                data["ALLOWED_ORIGINS"] = []

        # Validate security keys are not placeholders
        for field in ["SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY"]:
            if field in data:
                v = data[field]
                if v and ("CHANGE_THIS" in v.upper() or "YOUR_" in v.upper()):
                    raise ValueError(
                        f"{field} must be changed from placeholder value. "
                        f"Never use default/example values in production."
                    )

        return data

    def validate_firebase_config(self):
        """Validate Firebase configuration at runtime."""
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
            missing_fields = []
            if not self.FIREBASE_ADMIN_PROJECT_ID:
                missing_fields.append("FIREBASE_ADMIN_PROJECT_ID")
            if not self.FIREBASE_ADMIN_PRIVATE_KEY:
                missing_fields.append("FIREBASE_ADMIN_PRIVATE_KEY")
            if not self.FIREBASE_ADMIN_CLIENT_EMAIL:
                missing_fields.append("FIREBASE_ADMIN_CLIENT_EMAIL")

            if missing_fields:
                raise ValueError(
                    f"Firebase Admin SDK requires all credentials. Missing: {', '.join(missing_fields)}"
                )

    def validate_cors_config(self):
        """Validate CORS configuration to ensure frontend URL is included."""
        import logging

        logger = logging.getLogger(__name__)

        if not self.ALLOWED_ORIGINS:
            # Check if fallback URLs are configured
            has_fallback = bool(self.FRONTEND_URL or self.QUIZ_URL)
            if has_fallback and self.ENVIRONMENT.lower() != "production":
                # Dev mode: empty ALLOWED_ORIGINS is OK (regex is used)
                logger.info(
                    "✅ CORS using regex pattern (dev mode) - ALLOWED_ORIGINS empty by design"
                )
            elif has_fallback:
                # Production with fallback: build from FRONTEND_URL/QUIZ_URL
                logger.info(
                    f"✅ CORS will use fallback: {self.FRONTEND_URL}, {self.QUIZ_URL}"
                )
            else:
                # No origins and no fallback: actual problem
                logger.warning(
                    "⚠️  ALLOWED_ORIGINS is empty! CORS will block all cross-origin requests. "
                    "Add your frontend URL to ALLOWED_ORIGINS in .env"
                )
        else:
            logger.info(
                f"✅ CORS configured with {len(self.ALLOWED_ORIGINS)} allowed origins"
            )

    def validate_csrf_config(self):
        """Validate CSRF secret key strength at application startup."""
        import logging

        logger = logging.getLogger(__name__)

        if self.CSRF_SECRET_KEY:
            try:
                # Import validation function
                from app.utils.security_validation import validate_csrf_secret

                # Validate CSRF secret with entropy checking
                # log_validation=True will log metrics without exposing the secret
                validate_csrf_secret(self.CSRF_SECRET_KEY, log_validation=True)
                logger.info("✅ CSRF secret validation passed")

            except ValueError as e:
                logger.error(f"❌ CSRF secret validation failed: {e}")

                # In production, weak CSRF secrets should prevent application startup
                if self.ENVIRONMENT.lower() == "production":
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
                "⚠️  CSRF_SECRET_KEY not configured. "
                "CSRF protection will be disabled. "
                "For production, generate a secret with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

    def validate_production_config(self):
        """Validate production environment has secure configurations."""
        if self.ENVIRONMENT.lower() == "production":
            errors = []

            # DEBUG must be False in production
            if self.DEBUG:
                errors.append("DEBUG must be False in production environment")

            # Session cookies must be secure in production
            if not self.SESSION_COOKIE_SECURE:
                errors.append(
                    "SESSION_COOKIE_SECURE must be True in production environment"
                )

            # HttpOnly should always be true for security
            if not self.SESSION_COOKIE_HTTPONLY:
                errors.append(
                    "SESSION_COOKIE_HTTPONLY must be True to prevent XSS attacks"
                )

            # SameSite should be strict or lax in production
            if self.SESSION_COOKIE_SAMESITE.lower() not in ['strict', 'lax']:
                errors.append(
                    f"SESSION_COOKIE_SAMESITE must be 'strict' or 'lax' in production (got: {self.SESSION_COOKIE_SAMESITE})"
                )

            # SSL redirect should be enabled in production
            if not self.SECURE_SSL_REDIRECT:
                errors.append(
                    "SECURE_SSL_REDIRECT must be True in production environment"
                )

            if errors:
                raise ValueError(
                    f"Production environment security validation failed:\n"
                    + "\n".join(f"  - {error}" for error in errors)
                )

    def get_cors_origins(self) -> List[str]:
        """
        Returns CORS origins based on environment.
        Production: FRONTEND_URL + QUIZ_URL
        Dev: empty list (uses regex)
        """
        if self.ENVIRONMENT.lower() == "production":
            origins = []
            if self.FRONTEND_URL:
                origins.append(self.FRONTEND_URL.rstrip("/"))
            if self.QUIZ_URL:
                origins.append(self.QUIZ_URL.rstrip("/"))
            # If ALLOWED_ORIGINS was explicitly set, use it
            if self.ALLOWED_ORIGINS:
                return self.ALLOWED_ORIGINS
            return origins
        else:
            # Dev: return empty, middleware will use regex
            return []

    def get_firebase_security_config(self) -> dict:
        """Get Firebase security configuration for user provisioning."""
        return {
            "allowed_domains": self.FIREBASE_ALLOWED_DOMAINS,
            "require_custom_claims": self.FIREBASE_REQUIRE_CUSTOM_CLAIMS,
            "allowed_roles": self.FIREBASE_ALLOWED_ROLES,
            "enable_audit_logging": self.FIREBASE_ENABLE_AUDIT_LOGGING,
            "block_public_domains": self.FIREBASE_BLOCK_PUBLIC_DOMAINS,
            "public_domains_blocklist": self.FIREBASE_PUBLIC_DOMAINS_BLOCKLIST,
        }
