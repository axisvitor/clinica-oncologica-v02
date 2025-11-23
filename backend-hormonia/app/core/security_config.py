"""
Security Configuration Management for Hormonia Backend.

Centralized configuration for security settings including rate limiting,
authentication, and role-based access control.
"""
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from datetime import timedelta
import os

logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY CONFIGURATION MODELS
# =============================================================================

class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    enabled: bool = True
    requests_per_minute: int = Field(default=60, ge=1, le=1000)
    requests_per_hour: int = Field(default=1000, ge=1, le=10000)
    burst_size: int = Field(default=10, ge=1, le=100)

    # Endpoint-specific limits
    auth_login_per_minute: int = Field(default=5, ge=1, le=30)
    auth_signup_per_minute: int = Field(default=3, ge=1, le=10)
    password_reset_per_hour: int = Field(default=3, ge=1, le=10)

    # Privileged endpoint limits
    admin_requests_per_minute: int = Field(default=100, ge=1, le=500)

    @validator('requests_per_hour')
    def validate_hourly_limit(cls, v, values):
        if 'requests_per_minute' in values and v < values['requests_per_minute']:
            raise ValueError('Hourly limit must be >= minute limit')
        return v


class AuthenticationConfig(BaseModel):
    """Authentication security configuration."""
    require_email_verification: bool = True
    password_min_length: int = Field(default=8, ge=6, le=128)
    password_require_special_chars: bool = True
    password_require_numbers: bool = True
    password_require_uppercase: bool = True

    # Session configuration
    session_timeout_minutes: int = Field(default=480, ge=30, le=1440)  # 8 hours default
    refresh_token_lifetime_days: int = Field(default=30, ge=1, le=90)

    # Multi-factor authentication
    mfa_enabled: bool = False
    mfa_required_for_admin: bool = True

    # Account lockout
    max_failed_attempts: int = Field(default=5, ge=3, le=10)
    lockout_duration_minutes: int = Field(default=15, ge=5, le=60)


class DomainSecurityConfig(BaseModel):
    """Domain-based security configuration."""
    # Trusted domains for automatic role assignment
    trusted_domains: List[str] = [
        "hormonia.io",
        "admin.local",
        "clinica.med.br"
    ]

    # High-security domains requiring additional verification
    high_security_domains: List[str] = [
        "med.br",
        "saude.gov.br",
        "crm.org.br"
    ]

    # Blocked domains
    blocked_domains: List[str] = [
        "tempmail.org",
        "10minutemail.com",
        "guerrillamail.com"
    ]

    # Domain validation patterns
    medical_domain_patterns: List[str] = [
        r".*\.med\.br$",
        r".*\.saude\.gov\.br$",
        r".*\.crm\.org\.br$",
        r".*hospital.*\.com\.br$"
    ]


class APISecurityConfig(BaseModel):
    """API security configuration."""
    # CORS settings
    cors_allow_origins: List[str] = ["https://app.hormonia.io"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    # SECURITY: Explicit header whitelist - NEVER use ["*"] with credentials
    # Using wildcard headers with allow_credentials=True violates CORS security
    # and can expose all request headers to cross-origin requests
    cors_allow_headers: List[str] = [
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token",
        "Accept",
        "Origin"
    ]

    # API key settings
    require_api_key_for_public_endpoints: bool = False
    api_key_header_name: str = "X-API-Key"

    # Request validation
    max_request_size_mb: int = Field(default=10, ge=1, le=100)
    max_json_depth: int = Field(default=10, ge=5, le=50)

    # Security headers
    enable_security_headers: bool = True
    hsts_max_age: int = 31536000  # 1 year
    content_security_policy: str = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"


class WhatsAppSecurityConfig(BaseModel):
    """WhatsApp-specific security configuration."""
    # Access control
    enable_patient_validation: bool = True
    enable_phone_blocking: bool = True
    enable_unauthorized_logging: bool = True

    # Rate limiting for unauthorized attempts
    max_unauthorized_attempts_per_hour: int = Field(default=5, ge=1, le=20)
    max_unauthorized_attempts_per_day: int = Field(default=15, ge=5, le=50)

    # Blocking configuration
    block_duration_hours: int = Field(default=24, ge=1, le=168)  # Max 1 week
    escalating_responses: bool = True

    # Security monitoring
    high_risk_threshold: int = Field(default=7, ge=1, le=10)
    alert_after_attempts: int = Field(default=10, ge=5, le=50)

    # Feature flags for gradual rollout
    enable_enhanced_validation: bool = True
    enable_security_alerts: bool = True
    enable_risk_scoring: bool = True


class LoggingSecurityConfig(BaseModel):
    """Security logging configuration."""
    # Authentication events
    log_successful_logins: bool = True
    log_failed_logins: bool = True
    log_password_changes: bool = True
    log_role_changes: bool = True

    # API access
    log_api_access: bool = True
    log_privileged_operations: bool = True
    log_data_access: bool = True

    # Security events
    log_rate_limit_violations: bool = True
    log_permission_denials: bool = True
    log_suspicious_activity: bool = True

    # WhatsApp security events
    log_whatsapp_unauthorized_access: bool = True
    log_whatsapp_authorized_access: bool = True
    log_phone_blocking_events: bool = True

    # Log retention
    security_log_retention_days: int = Field(default=90, ge=30, le=365)

    # Alert thresholds
    failed_login_alert_threshold: int = Field(default=10, ge=5, le=50)
    suspicious_activity_alert_threshold: int = Field(default=5, ge=1, le=20)
    whatsapp_security_alert_threshold: int = Field(default=10, ge=5, le=30)


class SecurityConfig(BaseModel):
    """Master security configuration."""
    rate_limiting: RateLimitConfig = RateLimitConfig()
    authentication: AuthenticationConfig = AuthenticationConfig()
    domain_security: DomainSecurityConfig = DomainSecurityConfig()
    api_security: APISecurityConfig = APISecurityConfig()
    whatsapp_security: WhatsAppSecurityConfig = WhatsAppSecurityConfig()
    logging: LoggingSecurityConfig = LoggingSecurityConfig()

    # Environment-specific settings
    environment: str = Field(default="production")
    debug_mode: bool = Field(default=False)

    # Feature flags
    enable_auto_provisioning: bool = True
    enable_domain_validation: bool = True
    enable_role_hierarchies: bool = True
    enable_audit_logging: bool = True
    enable_whatsapp_security_monitoring: bool = True

    @validator('environment')
    def validate_environment(cls, v):
        allowed_envs = ['development', 'testing', 'staging', 'production']
        if v not in allowed_envs:
            raise ValueError(f'Environment must be one of: {allowed_envs}')
        return v

    @validator('debug_mode')
    def validate_debug_mode(cls, v, values):
        if v and values.get('environment') == 'production':
            logger.warning("Debug mode should not be enabled in production")
        return v


# =============================================================================
# SECURITY CONFIGURATION LOADER
# =============================================================================

class SecurityConfigLoader:
    """Load and validate security configuration from environment."""

    def __init__(self):
        self._config: Optional[SecurityConfig] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from environment variables."""
        try:
            # Base configuration
            config_dict = {
                "environment": os.getenv("ENVIRONMENT", "production"),
                "debug_mode": os.getenv("DEBUG", "false").lower() == "true",
            }

            # Rate limiting configuration
            rate_limit_config = {}
            if os.getenv("RATE_LIMIT_ENABLED") is not None:
                rate_limit_config["enabled"] = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
            if os.getenv("RATE_LIMIT_PER_MINUTE"):
                rate_limit_config["requests_per_minute"] = int(os.getenv("RATE_LIMIT_PER_MINUTE"))
            if os.getenv("AUTH_LOGIN_RATE_LIMIT"):
                rate_limit_config["auth_login_per_minute"] = int(os.getenv("AUTH_LOGIN_RATE_LIMIT"))

            if rate_limit_config:
                config_dict["rate_limiting"] = rate_limit_config

            # Authentication configuration
            auth_config = {}
            if os.getenv("REQUIRE_EMAIL_VERIFICATION") is not None:
                auth_config["require_email_verification"] = os.getenv("REQUIRE_EMAIL_VERIFICATION", "true").lower() == "true"
            if os.getenv("PASSWORD_MIN_LENGTH"):
                auth_config["password_min_length"] = int(os.getenv("PASSWORD_MIN_LENGTH"))
            if os.getenv("SESSION_TIMEOUT_MINUTES"):
                auth_config["session_timeout_minutes"] = int(os.getenv("SESSION_TIMEOUT_MINUTES"))
            if os.getenv("MFA_ENABLED") is not None:
                auth_config["mfa_enabled"] = os.getenv("MFA_ENABLED", "false").lower() == "true"

            if auth_config:
                config_dict["authentication"] = auth_config

            # Domain security configuration
            domain_config = {}
            if os.getenv("TRUSTED_DOMAINS"):
                domain_config["trusted_domains"] = os.getenv("TRUSTED_DOMAINS").split(",")
            if os.getenv("BLOCKED_DOMAINS"):
                domain_config["blocked_domains"] = os.getenv("BLOCKED_DOMAINS").split(",")

            if domain_config:
                config_dict["domain_security"] = domain_config

            # API security configuration
            api_config = {}
            if os.getenv("CORS_ALLOW_ORIGINS"):
                api_config["cors_allow_origins"] = os.getenv("CORS_ALLOW_ORIGINS").split(",")
            if os.getenv("MAX_REQUEST_SIZE_MB"):
                api_config["max_request_size_mb"] = int(os.getenv("MAX_REQUEST_SIZE_MB"))

            if api_config:
                config_dict["api_security"] = api_config

            # WhatsApp security configuration
            whatsapp_config = {}
            if os.getenv("WHATSAPP_ENABLE_PATIENT_VALIDATION") is not None:
                whatsapp_config["enable_patient_validation"] = os.getenv("WHATSAPP_ENABLE_PATIENT_VALIDATION", "true").lower() == "true"
            if os.getenv("WHATSAPP_ENABLE_PHONE_BLOCKING") is not None:
                whatsapp_config["enable_phone_blocking"] = os.getenv("WHATSAPP_ENABLE_PHONE_BLOCKING", "true").lower() == "true"
            if os.getenv("WHATSAPP_MAX_ATTEMPTS_PER_HOUR"):
                whatsapp_config["max_unauthorized_attempts_per_hour"] = int(os.getenv("WHATSAPP_MAX_ATTEMPTS_PER_HOUR"))
            if os.getenv("WHATSAPP_BLOCK_DURATION_HOURS"):
                whatsapp_config["block_duration_hours"] = int(os.getenv("WHATSAPP_BLOCK_DURATION_HOURS"))
            if os.getenv("WHATSAPP_ENABLE_ENHANCED_VALIDATION") is not None:
                whatsapp_config["enable_enhanced_validation"] = os.getenv("WHATSAPP_ENABLE_ENHANCED_VALIDATION", "true").lower() == "true"

            if whatsapp_config:
                config_dict["whatsapp_security"] = whatsapp_config

            # Feature flags
            if os.getenv("ENABLE_AUTO_PROVISIONING") is not None:
                config_dict["enable_auto_provisioning"] = os.getenv("ENABLE_AUTO_PROVISIONING", "true").lower() == "true"
            if os.getenv("ENABLE_AUDIT_LOGGING") is not None:
                config_dict["enable_audit_logging"] = os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true"
            if os.getenv("ENABLE_WHATSAPP_SECURITY_MONITORING") is not None:
                config_dict["enable_whatsapp_security_monitoring"] = os.getenv("ENABLE_WHATSAPP_SECURITY_MONITORING", "true").lower() == "true"

            # Create configuration object
            self._config = SecurityConfig(**config_dict)

            logger.info(f"Security configuration loaded for environment: {self._config.environment}")

        except Exception as e:
            logger.error(f"Failed to load security configuration: {e}")
            # Fall back to default configuration
            self._config = SecurityConfig()

    @property
    def config(self) -> SecurityConfig:
        """Get the current security configuration."""
        if self._config is None:
            self._load_config()
        return self._config

    def reload_config(self) -> None:
        """Reload configuration from environment."""
        self._load_config()

    def validate_config(self) -> List[str]:
        """Validate current configuration and return any warnings."""
        warnings = []

        if self._config is None:
            return ["Configuration not loaded"]

        # Check for insecure settings in production
        if self._config.environment == "production":
            if self._config.debug_mode:
                warnings.append("Debug mode should not be enabled in production")

            if not self._config.authentication.require_email_verification:
                warnings.append("Email verification should be required in production")

            if self._config.authentication.password_min_length < 8:
                warnings.append("Password minimum length should be at least 8 characters")

            if not self._config.logging.log_failed_logins:
                warnings.append("Failed login logging should be enabled in production")

            if not self._config.enable_audit_logging:
                warnings.append("Audit logging should be enabled in production")

        # Check rate limiting
        if not self._config.rate_limiting.enabled:
            warnings.append("Rate limiting should be enabled for security")

        if self._config.rate_limiting.auth_login_per_minute > 10:
            warnings.append("Authentication rate limit seems high - consider reducing")

        # Check CORS settings
        if "*" in self._config.api_security.cors_allow_origins:
            warnings.append("CORS allow origins should not include wildcard in production")

        # SECURITY: Check for wildcard headers with credentials
        if (self._config.api_security.cors_allow_credentials and
            "*" in self._config.api_security.cors_allow_headers):
            warnings.append(
                "CRITICAL: CORS wildcard headers with credentials enabled - "
                "this exposes all request headers to cross-origin requests and "
                "can lead to credential leakage"
            )

        return warnings

    def get_environment_template(self) -> str:
        """Get environment variable template for configuration."""
        template = """
# Security Configuration Environment Variables

# Environment
ENVIRONMENT=production
DEBUG=false

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
AUTH_LOGIN_RATE_LIMIT=5

# Authentication
REQUIRE_EMAIL_VERIFICATION=true
PASSWORD_MIN_LENGTH=8
SESSION_TIMEOUT_MINUTES=480
MFA_ENABLED=false

# Domain Security
TRUSTED_DOMAINS=hormonia.io,admin.local,clinica.med.br
BLOCKED_DOMAINS=tempmail.org,10minutemail.com

# API Security
CORS_ALLOW_ORIGINS=https://app.hormonia.io
MAX_REQUEST_SIZE_MB=10

# WhatsApp Security
WHATSAPP_ENABLE_PATIENT_VALIDATION=true
WHATSAPP_ENABLE_PHONE_BLOCKING=true
WHATSAPP_MAX_ATTEMPTS_PER_HOUR=5
WHATSAPP_BLOCK_DURATION_HOURS=24
WHATSAPP_ENABLE_ENHANCED_VALIDATION=true

# Feature Flags
ENABLE_AUTO_PROVISIONING=true
ENABLE_AUDIT_LOGGING=true
ENABLE_WHATSAPP_SECURITY_MONITORING=true
"""
        return template.strip()


# =============================================================================
# GLOBAL CONFIGURATION INSTANCE
# =============================================================================

# Create global configuration loader
_config_loader = SecurityConfigLoader()

def get_security_config() -> SecurityConfig:
    """Get the current security configuration."""
    return _config_loader.config

def reload_security_config() -> None:
    """Reload security configuration from environment."""
    _config_loader.reload_config()

def validate_security_config() -> List[str]:
    """Validate security configuration and return warnings."""
    return _config_loader.validate_config()

# Export the config for direct access
security_config = get_security_config()