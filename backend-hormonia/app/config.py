"""
Configuration settings for Hormonia Backend System using Pydantic Settings.
Using AWS RDS PostgreSQL database.
"""
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, ClassVar, Any
import os
import json


class Settings(BaseSettings):
    """Application settings with AWS RDS PostgreSQL integration."""

    # Application
    DEBUG: bool = Field(default=True, description="Debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment name")
    SECRET_KEY: str = Field(..., description="Secret key for JWT signing")
    JWT_SECRET_KEY: Optional[str] = Field(default=None, description="JWT secret key (fallback to SECRET_KEY if not set)")
    ENCRYPTION_KEY: Optional[str] = Field(default=None, description="Encryption key for sensitive data")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT expiration time")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiration time in days")
    BCRYPT_ROUNDS: int = Field(default=12, description="Bcrypt hashing rounds for password security (12-15 recommended for production)")

    # Security: Session and Cookie Configuration
    SESSION_COOKIE_SECURE: bool = Field(default=False, description="Require HTTPS for session cookies")
    SECURE_SSL_REDIRECT: bool = Field(default=False, description="Force HTTPS redirect")

    # Security: CSRF Protection
    CSRF_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Secret key for CSRF token generation (generate with secrets.token_urlsafe(32))"
    )

    # Firebase Admin SDK Configuration
    FIREBASE_ADMIN_PROJECT_ID: Optional[str] = Field(
        default=None,
        description="Firebase Admin SDK project ID"
    )
    FIREBASE_ADMIN_PRIVATE_KEY: Optional[str] = Field(
        default=None,
        description="Firebase Admin SDK service account private key"
    )
    FIREBASE_ADMIN_CLIENT_EMAIL: Optional[str] = Field(
        default=None,
        description="Firebase Admin SDK service account email"
    )

    # Firebase Security Configuration
    FIREBASE_ALLOWED_DOMAINS: List[str] = Field(
        default_factory=list,
        description="Authorized email domains for Firebase user creation (no public domains allowed)"
    )

    FIREBASE_REQUIRE_CUSTOM_CLAIMS: bool = Field(
        default=True,
        description="Require valid custom claims (role) before creating user"
    )
    FIREBASE_ALLOWED_ROLES: List[str] = Field(
        default=['admin', 'super_admin', 'doctor', 'medico'],
        description="Allowed roles in Firebase custom claims"
    )
    FIREBASE_ENABLE_AUDIT_LOGGING: bool = Field(
        default=True,
        description="Enable comprehensive audit logging for user provisioning"
    )
    FIREBASE_BLOCK_PUBLIC_DOMAINS: bool = Field(
        default=True,
        description="Block public email domains (gmail.com, yahoo.com, etc.)"
    )
    FIREBASE_PUBLIC_DOMAINS_BLOCKLIST: List[str] = Field(
        default=['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com'],
        description="Public email domains that are explicitly blocked"
    )

    # Database (AWS RDS PostgreSQL)
    DATABASE_URL: str = Field(..., description="AWS RDS PostgreSQL connection string")

    # Redis (for caching and Celery)
    # Redis Connection Settings (redis-py 6.0.0 compatible)
    REDIS_URL: str = Field(default="redis://localhost:6379", description="Redis connection URL (use redis:// or rediss:// for SSL)")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")

    # SSL/TLS Configuration
    REDIS_SSL: bool = Field(default=False, description="Enable SSL/TLS for Redis connection (use rediss:// URL or set to True)")
    REDIS_SSL_CERT_REQS: str = Field(
        default="required",
        description="Redis SSL certificate requirements: none, optional, required (SECURITY: Use 'required' for production)"
    )
    REDIS_SSL_MIN_VERSION: Optional[str] = Field(
        default=None,
        description="Minimum TLS version: 'TLSV1_2' or 'TLSV1_3'. Leave empty for auto-negotiation."
    )
    REDIS_SSL_CA_CERTS: Optional[str] = Field(
        default=None,
        description="Path to CA certificate bundle (absolute or relative to BASE_DIR). If not specified with CERT_REQUIRED, will use certifi."
    )

    # Base directory for relative paths
    BASE_DIR: str = Field(
        default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        description="Base directory of the application (backend-hormonia/app parent)"
    )

    # Connection Pool Settings
    REDIS_MAX_CONNECTIONS: int = Field(default=50, description="Redis maximum connections in pool")
    REDIS_SOCKET_TIMEOUT: float = Field(default=10.0, description="Redis socket timeout in seconds")
    REDIS_SOCKET_CONNECT_TIMEOUT: float = Field(default=5.0, description="Redis connection timeout in seconds")
    REDIS_RETRY_ON_TIMEOUT: bool = Field(default=True, description="Retry Redis operations on timeout")
    REDIS_HEALTH_CHECK_INTERVAL: int = Field(default=30, description="Redis connection health check interval in seconds")
    REDIS_DECODE_RESPONSES: bool = Field(default=True, description="Redis decode responses to strings")

    # Redis Database Isolation (optional, for production)
    REDIS_CACHE_DB: int = Field(default=1, description="Redis database number for cache (0-15)")
    REDIS_BROKER_DB: int = Field(default=0, description="Redis database number for Celery broker (0-15)")
    REDIS_SESSION_DB: int = Field(default=2, description="Redis database number for sessions (0-15)")
    REDIS_RATE_LIMIT_DB: int = Field(default=3, description="Redis database number for rate limiting (0-15)")
    REDIS_ENABLE_DB_ISOLATION: bool = Field(default=True, description="Enable separate DBs for cache vs broker")

    # Firebase Redis Cache Configuration (3-Layer Architecture)
    FIREBASE_TOKEN_CACHE_TTL: int = Field(
        default=3600,
        description="Firebase token validation cache TTL in seconds (Layer 1 - Default: 1 hour)"
    )
    FIREBASE_USER_CACHE_TTL: int = Field(
        default=7200,
        description="Firebase user object cache TTL in seconds (Layer 2 - Default: 2 hours)"
    )
    FIREBASE_SESSION_TTL: int = Field(
        default=86400,
        description="Firebase session management TTL in seconds (Layer 3 - Default: 24 hours)"
    )

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting on authentication endpoints")
    RATE_LIMIT_REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis URL for rate limiting storage (uses REDIS_URL if not set, in-memory if Redis unavailable)"
    )

    # Evolution API (WhatsApp)
    ENABLE_EVOLUTION: bool = Field(default=True, description="Enable Evolution API WhatsApp integration")
    EVOLUTION_API_URL: str = Field(default="http://localhost:8080", description="Evolution API base URL")
    EVOLUTION_INSTANCE_NAME: str = Field(default="clinica_oncologica", description="Evolution instance name")
    EVOLUTION_API_KEY: str = Field(default="your-evolution-api-key-here", description="Evolution API key")
    EVOLUTION_WEBHOOK_SECRET: Optional[str] = Field(default=None, description="Evolution webhook secret for signature validation")
    EVOLUTION_WEBHOOK_URL: Optional[str] = Field(default=None, description="Webhook URL for receiving Evolution API events")

    # AI Services (Gemini/LangChain)
    LANGCHAIN_TRACING_V2: bool = Field(default=False, description="Enable LangChain tracing")
    LANGCHAIN_API_KEY: Optional[str] = Field(default=None, description="LangChain API key")

    # Google Gemini AI
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-2.0-flash-exp", description="Gemini model to use")
    GEMINI_TEMPERATURE: float = Field(default=0.7, description="Gemini generation temperature")
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=500, description="Gemini max output tokens")
    GEMINI_TOP_P: float = Field(default=0.8, description="Gemini top-p parameter")
    GEMINI_TOP_K: int = Field(default=40, description="Gemini top-k parameter")
    GEMINI_TIMEOUT: int = Field(default=30, description="Gemini API timeout in seconds")
    GEMINI_MAX_RETRIES: int = Field(default=3, description="Gemini API max retries")

    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="rediss://localhost:6379/0", description="Celery broker URL")
    CELERY_RESULT_BACKEND: str = Field(default="rediss://localhost:6379/1", description="Celery result backend (use different DB)")
    CELERY_TASK_SERIALIZER: str = Field(default="json", description="Celery task serializer")
    CELERY_ACCEPT_CONTENT: List[str] = Field(default=["json"], description="Celery accepted content types")
    CELERY_RESULT_SERIALIZER: str = Field(default="json", description="Celery result serializer")
    CELERY_TIMEZONE: str = Field(default="UTC", description="Celery timezone")
    CELERY_ENABLE_UTC: bool = Field(default=True, description="Enable UTC in Celery")
    CELERY_TASK_TRACK_STARTED: bool = Field(default=True, description="Track task start events")
    CELERY_TASK_TIME_LIMIT: int = Field(default=300, description="Task time limit in seconds")
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=240, description="Task soft time limit in seconds")
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(default=1000, description="Max tasks per worker child")
    CELERY_WORKER_DISABLE_RATE_LIMITS: bool = Field(default=True, description="Disable rate limits for workers")

    # CORS - Dynamic configuration (domain-only in production, regex in dev)
    FRONTEND_URL: str = Field(
        default="http://localhost:5173",
        description="Frontend URL (used for CORS in production)"
    )
    QUIZ_URL: str = Field(
        default="http://localhost:3001",
        description="Quiz interface URL (used for CORS in production)"
    )
    ALLOWED_ORIGINS: List[str] | str = Field(
        default=[],
        description="Allowed CORS origins (auto-constructed from FRONTEND_URL + QUIZ_URL in production, empty in dev for regex)"
    )

    # File Storage
    UPLOAD_DIR: str = Field(default="uploads", description="Upload directory for files")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, description="Max file size in bytes (10MB)")

    # Localization
    DEFAULT_LOCALE: str = Field(default="pt-BR", description="Default language locale")
    SUPPORTED_LOCALES: List[str] = Field(
        default=["en", "pt-BR", "es"],
        description="Supported language locales"
    )

    # Logging Configuration (Enhanced for Critical Bug Fixes)
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    MAX_LOGS_PER_SECOND: int = Field(
        default=100, 
        description="Maximum logs per second to prevent rate limiting (Railway limit: 500/sec)"
    )
    ENABLE_REQUEST_LOGGING: bool = Field(
        default=True, 
        description="Enable request logging middleware (uses DEBUG level for routine operations)"
    )
    LOG_STACK_TRACES: bool = Field(
        default=True, 
        description="Enable stack trace logging for errors"
    )
    LOG_DEDUPLICATION_WINDOW: int = Field(
        default=300, 
        description="Time window in seconds for log deduplication (5 minutes)"
    )
    
    # Error Tracking Configuration (Critical Bug Fixes)
    ENABLE_ERROR_TRACKING: bool = Field(
        default=True, 
        description="Enable centralized error tracking and logging"
    )
    MAX_ERROR_LOGS: int = Field(
        default=1000, 
        description="Maximum number of error logs to store in database"
    )
    ERROR_DEDUPLICATION_WINDOW: int = Field(
        default=3600, 
        description="Time window in seconds for error deduplication (1 hour)"
    )
    ERROR_TRACKING_RATE_LIMIT: int = Field(
        default=10, 
        description="Maximum error logs per minute for same error type"
    )
    CRITICAL_ERROR_NOTIFICATION: bool = Field(
        default=True, 
        description="Enable notifications for critical errors (DI, role enum, schema issues)"
    )

    # Monthly Quiz Configuration
    MONTHLY_QUIZ_VIA_LINK: bool = Field(
        default=True,
        description="Enable monthly quiz via secure link (True) or WhatsApp conversational (False)"
    )
    MONTHLY_QUIZ_BASE_URL: str = Field(
        default="http://localhost:3001",
        description="Base URL for monthly quiz access links"
    )
    MONTHLY_QUIZ_TOKEN_SECRET: str = Field(
        default="your-monthly-quiz-token-secret-change-this",
        description="Secret key for generating quiz tokens (should be different from main SECRET_KEY)"
    )
    MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS: int = Field(
        default=72,
        description="Monthly quiz link expiry time in hours (default: 72 hours = 3 days)"
    )

    # Monitoring Configuration
    MONITORING_ENABLED: bool = Field(default=True, description="Enable comprehensive monitoring system")
    MONITORING_DEBUG: bool = Field(default=False, description="Enable monitoring debug mode")
    MONITORING_REDIS_HOST: str = Field(default="localhost", description="Redis host for monitoring")
    MONITORING_REDIS_PORT: int = Field(default=6379, description="Redis port for monitoring")
    MONITORING_REDIS_DB: int = Field(default=1, description="Redis database for monitoring")
    MONITORING_REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password for monitoring")

    # APM Configuration
    APM_APDEX_THRESHOLD: float = Field(default=0.5, description="APM Apdex threshold in seconds")
    APM_SLOW_REQUEST_THRESHOLD: float = Field(default=1.0, description="Slow request threshold in seconds")

    # Database Monitoring
    DB_SLOW_QUERY_THRESHOLD: float = Field(default=1.0, description="Database slow query threshold in seconds")

    # Resource Monitoring
    RESOURCE_SAMPLE_INTERVAL: float = Field(default=10.0, description="Resource monitoring sample interval")
    RESOURCE_CPU_THRESHOLD: float = Field(default=80.0, description="CPU usage threshold percentage")
    RESOURCE_MEMORY_THRESHOLD: float = Field(default=85.0, description="Memory usage threshold percentage")

    # Dashboard Configuration
    DASHBOARD_UPDATE_INTERVAL: float = Field(default=5.0, description="Dashboard update interval in seconds")

    # AI Humanization Configuration
    AI_HUMANIZATION_ENABLED: bool = Field(default=True, description="Enable AI message humanization in flow engine")
    AI_HUMANIZATION_SAFETY_MODE: bool = Field(default=True, description="Enable safety checks for critical message types")
    AI_HUMANIZATION_MAX_RETRIES: int = Field(default=2, description="Maximum retries for AI humanization failures")
    AI_HUMANIZATION_TIMEOUT: float = Field(default=10.0, description="Timeout for AI humanization requests in seconds")
    AI_HUMANIZATION_FALLBACK_ENABLED: bool = Field(default=True, description="Enable fallback to original message on AI failure")
    AI_HUMANIZATION_CRITICAL_KEYWORDS: List[str] = Field(
        default=[
            "medicação", "remédio", "dosagem", "mg", "ml", "emergência", "urgente",
            "hospital", "médico", "consulta", "exame", "resultado", "tratamento",
            "quimioterapia", "radioterapia", "cirurgia", "efeito colateral",
            "reação adversa", "contraindicação", "suspender", "parar", "não tome"
        ],
        description="Keywords that prevent AI humanization for safety"
    )

    # WhatsApp Integration Configuration
    ENABLE_WHATSAPP_ON_REGISTRATION: bool = Field(
        default=True,
        description="Enable automatic WhatsApp welcome message on patient registration"
    )
    WHATSAPP_WELCOME_MESSAGE_ENABLED: bool = Field(
        default=True,
        description="Enable welcome message feature (can be disabled for testing)"
    )
    WHATSAPP_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts for failed WhatsApp messages"
    )
    WHATSAPP_RETRY_DELAY_SECONDS: int = Field(
        default=60,
        description="Initial delay in seconds before retrying failed messages (uses exponential backoff)"
    )
    CLINIC_NAME: str = Field(
        default="Clínica Oncológica Hormonia",
        description="Clinic name for WhatsApp messages"
    )
    CLINIC_SUPPORT_PHONE: Optional[str] = Field(
        default=None,
        description="Support phone number for emergencies (shown in welcome message)"
    )

    # Pydantic v2.9.2 + Python 3.13: model_validator requires special handling
    @model_validator(mode='before')
    @classmethod
    def parse_env_values(cls, data: Any) -> Any:
        """Parse all environment variable values before model validation (Pydantic v2 compatible)."""
        # Parse boolean fields from string
        for field in ['DEBUG', 'SESSION_COOKIE_SECURE', 'SECURE_SSL_REDIRECT']:
            if field in data:
                v = data[field]
                if isinstance(v, bool):
                    data[field] = v
                elif isinstance(v, str):
                    data[field] = v.lower() not in ('false', '0', 'no', 'off', '')
                else:
                    data[field] = bool(v)

        # Parse FIREBASE_ALLOWED_DOMAINS from JSON string
        if 'FIREBASE_ALLOWED_DOMAINS' in data:
            v = data['FIREBASE_ALLOWED_DOMAINS']
            if v is None or v == '':
                data['FIREBASE_ALLOWED_DOMAINS'] = []
            elif isinstance(v, str):
                try:
                    data['FIREBASE_ALLOWED_DOMAINS'] = json.loads(v)
                except json.JSONDecodeError:
                    data['FIREBASE_ALLOWED_DOMAINS'] = []

        # Parse ALLOWED_ORIGINS
        if 'ALLOWED_ORIGINS' in data:
            v = data['ALLOWED_ORIGINS']
            if isinstance(v, list) and len(v) > 0:
                pass  # Already a list
            elif isinstance(v, str) and v.strip():
                s = v.strip()
                if s.startswith("["):
                    try:
                        data['ALLOWED_ORIGINS'] = json.loads(s)
                    except:
                        data['ALLOWED_ORIGINS'] = [item.strip() for item in s.split(",") if item.strip()]
                else:
                    data['ALLOWED_ORIGINS'] = [item.strip() for item in s.split(",") if item.strip()]
            else:
                data['ALLOWED_ORIGINS'] = []

        # Parse AI_HUMANIZATION_CRITICAL_KEYWORDS
        if 'AI_HUMANIZATION_CRITICAL_KEYWORDS' in data:
            v = data['AI_HUMANIZATION_CRITICAL_KEYWORDS']
            if isinstance(v, list):
                pass  # Already a list
            elif isinstance(v, str):
                s = v.strip()
                if s.startswith("["):
                    try:
                        arr = json.loads(s)
                        if isinstance(arr, list):
                            data['AI_HUMANIZATION_CRITICAL_KEYWORDS'] = arr
                        else:
                            data['AI_HUMANIZATION_CRITICAL_KEYWORDS'] = [item.strip() for item in s.split(",") if item.strip()]
                    except Exception:
                        data['AI_HUMANIZATION_CRITICAL_KEYWORDS'] = [item.strip() for item in s.split(",") if item.strip()]
                else:
                    data['AI_HUMANIZATION_CRITICAL_KEYWORDS'] = [item.strip() for item in s.split(",") if item.strip()]

        # Validate security keys are not placeholders
        for field in ['SECRET_KEY', 'JWT_SECRET_KEY', 'ENCRYPTION_KEY']:
            if field in data:
                v = data[field]
                if v and ('CHANGE_THIS' in v.upper() or 'YOUR_' in v.upper()):
                    raise ValueError(
                        f"{field} must be changed from placeholder value. "
                        f"Never use default/example values in production."
                    )

        return data

    # Pydantic v2: model_config MUST be declared AFTER all validators
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra='ignore'
    )

    def __init__(self, **kwargs):
        """Initialize settings with validation."""
        super().__init__(**kwargs)
        self._validate_firebase_config()
        self._validate_cors_config()
        self._validate_production_config()
        self._validate_csrf_config()

    def _validate_firebase_config(self):
        """Validate Firebase configuration at runtime."""
        # Check if Firebase is being used (any Firebase field is set)
        firebase_in_use = any([
            self.FIREBASE_ADMIN_PROJECT_ID,
            self.FIREBASE_ADMIN_PRIVATE_KEY,
            self.FIREBASE_ADMIN_CLIENT_EMAIL
        ])

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

    def _validate_cors_config(self):
        """Validate CORS configuration to ensure frontend URL is included."""
        import logging
        logger = logging.getLogger(__name__)

        if not self.ALLOWED_ORIGINS:
            # Check if fallback URLs are configured
            has_fallback = bool(self.FRONTEND_URL or self.QUIZ_URL)
            if has_fallback and self.ENVIRONMENT.lower() != 'production':
                # Dev mode: empty ALLOWED_ORIGINS is OK (regex is used)
                logger.info("✅ CORS using regex pattern (dev mode) - ALLOWED_ORIGINS empty by design")
            elif has_fallback:
                # Production with fallback: build from FRONTEND_URL/QUIZ_URL
                logger.info(f"✅ CORS will use fallback: {self.FRONTEND_URL}, {self.QUIZ_URL}")
            else:
                # No origins and no fallback: actual problem
                logger.warning(
                    "⚠️  ALLOWED_ORIGINS is empty! CORS will block all cross-origin requests. "
                    "Add your frontend URL to ALLOWED_ORIGINS in .env"
                )
        else:
            logger.info(f"✅ CORS configured with {len(self.ALLOWED_ORIGINS)} allowed origins")

    def _validate_csrf_config(self):
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
                if self.ENVIRONMENT.lower() == 'production':
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

    def _validate_production_config(self):
        """Validate production environment has secure configurations."""
        if self.ENVIRONMENT.lower() == 'production':
            errors = []

            # DEBUG must be False in production
            if self.DEBUG:
                errors.append("DEBUG must be False in production environment")

            # Redis SSL validation (optional - some Redis Cloud instances don't use SSL)
            # Note: Redis Cloud port 14149 does NOT use SSL/TLS
            # Validate URL scheme matches SSL setting
            if self.REDIS_SSL and not self.REDIS_URL.startswith('rediss://'):
                print("⚠️  WARNING: REDIS_SSL=True but URL doesn't use rediss:// scheme - SSL may not work correctly")
            elif not self.REDIS_SSL and self.REDIS_URL.startswith('rediss://'):
                errors.append("REDIS_SSL=False but URL uses rediss:// scheme - configuration mismatch")

            # Session cookies must be secure in production
            if not self.SESSION_COOKIE_SECURE:
                errors.append("SESSION_COOKIE_SECURE must be True in production environment")

            # SSL redirect should be enabled in production
            if not self.SECURE_SSL_REDIRECT:
                errors.append("SECURE_SSL_REDIRECT must be True in production environment")

            if errors:
                raise ValueError(
                    f"Production environment security validation failed:\n" +
                    "\n".join(f"  - {error}" for error in errors)
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
                origins.append(self.FRONTEND_URL.rstrip('/'))
            if self.QUIZ_URL:
                origins.append(self.QUIZ_URL.rstrip('/'))
            # If ALLOWED_ORIGINS was explicitly set, use it
            if self.ALLOWED_ORIGINS:
                return self.ALLOWED_ORIGINS
            return origins
        else:
            # Dev: return empty, middleware will use regex
            return []


# Global settings instance
settings = Settings()


# AI Humanization helper functions
def is_ai_humanization_enabled() -> bool:
    """Check if AI humanization is enabled."""
    return settings.AI_HUMANIZATION_ENABLED


def should_humanize_message(content: str) -> bool:
    """Check if message content is safe for AI humanization."""
    if not settings.AI_HUMANIZATION_SAFETY_MODE:
        return True

    content_lower = content.lower()
    return not any(
        keyword in content_lower
        for keyword in settings.AI_HUMANIZATION_CRITICAL_KEYWORDS
    )


def get_humanization_config() -> dict:
    """Get AI humanization configuration."""
    return {
        "enabled": settings.AI_HUMANIZATION_ENABLED,
        "safety_mode": settings.AI_HUMANIZATION_SAFETY_MODE,
        "max_retries": settings.AI_HUMANIZATION_MAX_RETRIES,
        "timeout": settings.AI_HUMANIZATION_TIMEOUT,
        "fallback_enabled": settings.AI_HUMANIZATION_FALLBACK_ENABLED,
        "critical_keywords": settings.AI_HUMANIZATION_CRITICAL_KEYWORDS
    }


def get_settings():
    """Get settings instance."""
    return settings


def get_firebase_security_config():
    """Get Firebase security configuration for user provisioning."""
    return {
        "allowed_domains": settings.FIREBASE_ALLOWED_DOMAINS,
        "require_custom_claims": settings.FIREBASE_REQUIRE_CUSTOM_CLAIMS,
        "allowed_roles": settings.FIREBASE_ALLOWED_ROLES,
        "enable_audit_logging": settings.FIREBASE_ENABLE_AUDIT_LOGGING,
        "block_public_domains": settings.FIREBASE_BLOCK_PUBLIC_DOMAINS,
        "public_domains_blocklist": settings.FIREBASE_PUBLIC_DOMAINS_BLOCKLIST
    }
