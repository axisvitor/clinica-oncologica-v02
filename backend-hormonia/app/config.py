"""
Configuration settings for Hormonia Backend System using Pydantic Settings.
Adapted for Supabase Cloud database.
"""
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os
import json


class Settings(BaseSettings):
    """Application settings with Supabase Cloud integration."""
    
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
    
    # Supabase Configuration
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(..., description="Supabase anonymous key")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(..., description="Supabase service role key")
    # Supabase User Auto-Provisioning
    AUTO_PROVISION_SUPABASE_USERS: bool = Field(
        default=False,
        description="Automatically create a local user when a valid Supabase user authenticates"
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

    @field_validator('SECRET_KEY', 'JWT_SECRET_KEY', 'ENCRYPTION_KEY', mode='after')
    @classmethod
    def validate_not_placeholder(cls, v, info):
        """Validate that security keys are not using placeholder values."""
        if v and ('CHANGE_THIS' in v.upper() or 'YOUR_' in v.upper()):
            raise ValueError(
                f"{info.field_name} must be changed from placeholder value. "
                f"Never use default/example values in production."
            )
        return v

    @field_validator('FIREBASE_ALLOWED_DOMAINS', mode='before')
    @classmethod
    def parse_allowed_domains(cls, v):
        """Parse FIREBASE_ALLOWED_DOMAINS from JSON string or return empty list for empty string."""
        if v is None or v == '':
            return []
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v

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

    # Supabase RLS Configuration
    SUPABASE_USE_SERVICE_ROLE: bool = Field(
        default=False,
        description="Use service_role key (bypass RLS) or user JWT tokens for RLS"
    )
    SUPABASE_BYPASS_RLS: bool = Field(
        default=False,
        description="Whether to bypass Row Level Security policies"
    )
    SUPABASE_JWT_HEADER_NAME: str = Field(
        default="Authorization",
        description="Header name for JWT token"
    )
    SUPABASE_JWT_PREFIX: str = Field(
        default="Bearer",
        description="Prefix for JWT token in header"
    )

    # RLS Context Settings
    RLS_OPERATION_TIMEOUT: int = Field(
        default=30,
        description="Timeout for RLS operations in seconds"
    )
    RLS_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retries for RLS operations"
    )
    RLS_ENABLE_AUDIT_LOGGING: bool = Field(
        default=True,
        description="Enable audit logging for RLS operations"
    )
    RLS_DEFAULT_ROLE: str = Field(
        default="authenticated",
        description="Default role for RLS context"
    )

    # Connection Pool Settings for RLS
    RLS_POOL_SIZE: int = Field(
        default=30,  # SECURITY FIX: Increased from 15
        description="Database pool size for RLS connections"
    )
    RLS_POOL_MAX_OVERFLOW: int = Field(
        default=50,  # SECURITY FIX: Increased from 25
        description="Maximum overflow connections for RLS pool"
    )
    
    # Database (Supabase PostgreSQL)
    DATABASE_URL: str = Field(..., description="Supabase PostgreSQL connection string")
    
    # Redis (for caching and Celery)
    REDIS_URL: str = Field(default="rediss://localhost:6379", description="Redis connection URL")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_SSL: bool = Field(default=True, description="SECURITY FIX: Redis SSL enabled")
    REDIS_SSL_CERT_REQS: str = Field(default="required", description="Redis SSL certificate requirements")
    REDIS_MAX_CONNECTIONS: int = Field(default=10, description="Redis maximum connections")
    REDIS_SOCKET_TIMEOUT: float = Field(default=30.0, description="Redis socket timeout in seconds")
    REDIS_DECODE_RESPONSES: bool = Field(default=True, description="Redis decode responses to strings")

    # Redis Database Isolation (optional, for production)
    REDIS_CACHE_DB: int = Field(default=1, description="Redis database number for cache (0-15)")
    REDIS_BROKER_DB: int = Field(default=0, description="Redis database number for Celery broker (0-15)")
    REDIS_ENABLE_DB_ISOLATION: bool = Field(default=True, description="Enable separate DBs for cache vs broker")

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
    
    # CORS
    # Includes origins for:
    # - Main frontend (3000, 5173) + Railway production
    # - Monthly quiz interface (3001, 5174) + Railway production
    # - Evolution API (8080)
    # - Quiz domain patterns for Railway deployments
    ALLOWED_ORIGINS: List[str] | str = Field(
        default=[
            # Local development - localhost (all common ports)
            "http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:5177", "http://localhost:5178", "http://localhost:5179",  # Main frontend + all Vite ports
            "http://localhost:3001",  # Monthly quiz interface
            "http://localhost:8080",  # Evolution API
            # Local development - 127.0.0.1 (needed for Frontend-v2/config.ts)
            "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175", "http://127.0.0.1:5176", "http://127.0.0.1:5177", "http://127.0.0.1:5178", "http://127.0.0.1:5179",  # Main frontend + all Vite ports
            "http://127.0.0.1:3001", "http://127.0.0.1:5174",  # Monthly quiz interface
            "http://127.0.0.1:8000",  # Backend self-reference
            "http://127.0.0.1:8080",  # Evolution API
            # Production Railway URLs - explicit URLs only (no wildcards for security)
            "https://clinica-oncologica-v02-production.up.railway.app",  # Main production deployment
            "https://interface-quiz-production.up.railway.app",  # Quiz interface production
            "https://quiz-mensal-interface.railway.app",  # Quiz interface production (alt)
            "https://hormonia-frontend.railway.app",  # Frontend production
            "https://frontend-v2.railway.app"  # Main frontend production
        ],
        description="Allowed CORS origins with Railway production support, localhost and 127.0.0.1 development URLs (includes port 5179)"
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, v):
        """
        Allow JSON array or comma-separated string for ALLOWED_ORIGINS.
        Supports wildcard patterns for Railway deployments.
        """
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            # Try JSON array
            if s.startswith("["):
                try:
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        return arr
                except Exception:
                    pass
            # Fallback: comma-separated
            return [item.strip() for item in s.split(",") if item.strip()]
        # Default fallback with quiz interface support
        return [
            "http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:5177", "http://localhost:5178", "http://localhost:5179",  # Main frontend + all Vite ports
            "http://localhost:3001",  # Quiz interface
            "http://localhost:8080",  # Evolution API
            "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175", "http://127.0.0.1:5176", "http://127.0.0.1:5177", "http://127.0.0.1:5178", "http://127.0.0.1:5179",  # Main frontend 127.0.0.1 + all Vite ports
            "http://127.0.0.1:3001", "http://127.0.0.1:5174",  # Quiz interface 127.0.0.1
            "http://127.0.0.1:8000", "http://127.0.0.1:8080",  # Backend + Evolution 127.0.0.1
            "https://clinica-oncologica-v02-production.up.railway.app",  # Main production deployment
            "https://interface-quiz-production.up.railway.app",  # Quiz interface production
            "https://quiz-mensal-interface.railway.app",  # Quiz production (alt)
            "https://hormonia-frontend.railway.app",  # Frontend production
            "https://frontend-v2.railway.app"  # Frontend production
        ]
    
    # File Storage
    UPLOAD_DIR: str = Field(default="uploads", description="Upload directory for files")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, description="Max file size in bytes (10MB)")
    
    # Localization
    DEFAULT_LOCALE: str = Field(default="pt-BR", description="Default language locale")
    SUPPORTED_LOCALES: List[str] = Field(
        default=["en", "pt-BR", "es"],
        description="Supported language locales"
    )
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
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
    
    @field_validator("AI_HUMANIZATION_CRITICAL_KEYWORDS", mode="before")
    @classmethod
    def _parse_critical_keywords(cls, v):
        """Allow JSON array or comma-separated string for critical keywords."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            # Try JSON array
            if s.startswith("["):
                try:
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        return arr
                except Exception:
                    pass
            # Fallback: comma-separated
            return [item.strip() for item in s.split(",") if item.strip()]
        return [
            "medicação", "remédio", "dosagem", "mg", "ml", "emergência", "urgente",
            "hospital", "médico", "consulta", "exame", "resultado", "tratamento",
            "quimioterapia", "radioterapia", "cirurgia", "efeito colateral",
            "reação adversa", "contraindicação", "suspender", "parar", "não tome"
        ]

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
        if not self.ALLOWED_ORIGINS:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "⚠️  ALLOWED_ORIGINS is empty! CORS will block all cross-origin requests. "
                "Add your frontend URL to ALLOWED_ORIGINS in .env"
            )
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ CORS configured with {len(self.ALLOWED_ORIGINS)} allowed origins")

    def _validate_production_config(self):
        """Validate production environment has secure configurations."""
        if self.ENVIRONMENT.lower() == 'production':
            errors = []

            # DEBUG must be False in production
            if self.DEBUG:
                errors.append("DEBUG must be False in production environment")

            # Redis SSL must be enabled in production
            if not self.REDIS_SSL:
                errors.append("REDIS_SSL must be True in production environment")

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


# Supabase client configuration
def get_supabase_config():
    """Get Supabase configuration for client initialization."""
    return {
        "url": settings.SUPABASE_URL,
        "key": settings.SUPABASE_ANON_KEY,
        "service_role_key": settings.SUPABASE_SERVICE_ROLE_KEY
    }


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

