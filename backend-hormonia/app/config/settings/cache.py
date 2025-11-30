"""
Cache TTL Configuration Settings

Centralized TTL (Time-To-Live) configuration for all caching operations.
All values are in seconds and can be overridden via environment variables.

Environment variables use the prefix CACHE_ followed by the setting name.
Example: CACHE_FLOW_TEMPLATE_TTL_SECONDS=7200

ENV Variable Naming Convention: CACHE_{CATEGORY}_{ATTRIBUTE}_TTL_SECONDS
MEDIUM-008: Extracted from hardcoded values throughout the codebase.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class CacheSettings(BaseSettings):
    """
    Cache TTL configuration for all application components.

    All TTL values are in seconds and can be overridden via environment variables
    using the CACHE_ prefix with _TTL_SECONDS suffix.

    Examples:
        CACHE_FLOW_TEMPLATE_TTL_SECONDS=7200
        CACHE_AUTH_TOKEN_TTL_SECONDS=86400
    """

    # ========================================================================
    # FLOW & TEMPLATES - Direct ENV names
    # ========================================================================

    CACHE_FLOW_TEMPLATE_TTL_SECONDS: int = Field(default=3600)
    """TTL for cached flow templates"""

    CACHE_TEMPLATE_CACHE_TTL_SECONDS: int = Field(default=3600)
    """TTL for general template cache"""

    FLOW_STATE_TTL: int = 1800  # 30 minutes
    """TTL for flow state cache"""

    # ========================================================================
    # USER & AUTHENTICATION
    # ========================================================================

    CACHE_USER_SESSION_TTL_SECONDS: int = Field(default=1800)
    """TTL for user session data"""

    CACHE_AUTH_TOKEN_TTL_SECONDS: int = Field(default=86400)
    """TTL for authentication tokens"""

    CACHE_REFRESH_TOKEN_TTL_SECONDS: int = Field(default=604800)
    """TTL for refresh tokens"""

    USER_PROFILE_TTL: int = 1800  # 30 minutes
    """TTL for cached user profiles"""

    # ========================================================================
    # PATIENT DATA
    # ========================================================================

    CACHE_PATIENT_CACHE_TTL_SECONDS: int = Field(default=900)
    """TTL for patient data cache"""

    PATIENT_LIST_TTL: int = 300  # 5 minutes
    """TTL for patient list cache"""

    PATIENT_DETAIL_TTL: int = 600  # 10 minutes
    """TTL for patient detail cache"""

    CACHE_DOCTOR_CACHE_TTL_SECONDS: int = Field(default=1800)
    """TTL for doctor/physician data cache"""

    # ========================================================================
    # QUIZ & SESSIONS
    # ========================================================================

    CACHE_QUIZ_SESSION_TTL_SECONDS: int = Field(default=7200)
    """TTL for active quiz sessions"""

    CACHE_QUIZ_TEMPLATES_TTL_SECONDS: int = Field(default=3600)
    """TTL for quiz template cache"""

    QUIZ_CACHE_TTL: int = 1800  # 30 minutes
    """TTL for general quiz data cache"""

    # ========================================================================
    # MESSAGES & COMMUNICATION
    # ========================================================================

    CACHE_MESSAGE_CACHE_TTL_SECONDS: int = Field(default=3600)
    """TTL for message cache"""

    CACHE_MESSAGE_STATS_TTL_SECONDS: int = Field(default=300)
    """TTL for message statistics"""

    CACHE_WHATSAPP_METRICS_TTL_SECONDS: int = Field(default=604800)
    """TTL for WhatsApp metrics (long-term)"""

    # ========================================================================
    # WEBHOOK & IDEMPOTENCY
    # ========================================================================

    CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS: int = Field(default=3600)
    """TTL for webhook idempotency keys"""

    CACHE_WEBHOOK_CACHE_TTL_SECONDS: int = Field(default=300)
    """TTL for webhook data cache"""

    # ========================================================================
    # RATE LIMITING
    # ========================================================================

    CACHE_RATE_LIMIT_WINDOW_TTL_SECONDS: int = Field(default=60)
    """TTL for rate limit windows"""

    RATE_LIMIT_BUCKET_TTL: int = 3600  # 1 hour
    """TTL for rate limit bucket tracking"""

    # ========================================================================
    # REPORTS & ANALYTICS
    # ========================================================================

    CACHE_REPORT_CACHE_TTL_SECONDS: int = Field(default=1800)
    """TTL for report data cache"""

    REPORT_DATA_TTL: int = 1800  # 30 minutes
    """TTL for report data (alias)"""

    CACHE_ANALYTICS_CACHE_TTL_SECONDS: int = Field(default=300)
    """TTL for analytics data cache"""

    ANALYTICS_DASHBOARD_TTL: int = 300  # 5 minutes
    """TTL for analytics dashboard cache"""

    # ========================================================================
    # AI & RESPONSES
    # ========================================================================

    AI_RESPONSES_TTL: int = 7200  # 2 hours
    """TTL for cached AI responses"""

    AI_CONTEXT_TTL: int = 3600  # 1 hour
    """TTL for AI context cache"""

    # ========================================================================
    # DISTRIBUTED SYSTEMS
    # ========================================================================

    CACHE_DISTRIBUTED_LOCK_TTL_SECONDS: int = Field(default=30)
    """TTL for distributed locks (short-lived)"""

    CACHE_SAGA_STATE_TTL_SECONDS: int = Field(default=3600)
    """TTL for Saga orchestration state"""

    CACHE_CIRCUIT_BREAKER_STATE_TTL_SECONDS: int = Field(default=300)
    """TTL for circuit breaker state"""

    # ========================================================================
    # MONITORING & METRICS
    # ========================================================================

    CACHE_SYSTEM_METRICS_TTL_SECONDS: int = Field(default=60)
    """TTL for system metrics cache"""

    CACHE_RESOURCE_MONITOR_TTL_SECONDS: int = Field(default=300)
    """TTL for resource monitoring data"""

    PERFORMANCE_METRICS_TTL: int = 300  # 5 minutes
    """TTL for performance metrics"""

    # ========================================================================
    # SESSION & STATE MANAGEMENT
    # ========================================================================

    SESSION_DATA_TTL: int = 1800  # 30 minutes
    """TTL for session data"""

    CACHE_CONNECTION_STATE_TTL_SECONDS: int = Field(default=300)
    """TTL for connection state (WhatsApp, etc.)"""

    CACHE_QRCODE_TTL_SECONDS: int = Field(default=300)
    """TTL for QR code data"""

    # ========================================================================
    # SEARCH & INDEXING
    # ========================================================================

    SEARCH_CACHE_TTL: int = 600  # 10 minutes
    """TTL for search results cache"""

    INDEX_CACHE_TTL: int = 1800  # 30 minutes
    """TTL for index cache"""

    # ========================================================================
    # GENERAL PURPOSE
    # ========================================================================

    SHORT_CACHE_TTL: int = 300  # 5 minutes
    """TTL for short-lived cache (default)"""

    MEDIUM_CACHE_TTL: int = 1800  # 30 minutes
    """TTL for medium-lived cache (default)"""

    LONG_CACHE_TTL: int = 86400  # 24 hours
    """TTL for long-lived cache (default)"""

    # ========================================================================
    # REDIS CONNECTION SETTINGS (Legacy - kept for compatibility)
    # ========================================================================

    REDIS_MAX_CONNECTIONS: int = 50
    """Maximum number of Redis connections in pool"""

    REDIS_SOCKET_TIMEOUT: int = 5
    """Socket timeout for Redis operations (seconds)"""

    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    """Socket connect timeout for Redis (seconds)"""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # CRITICAL FIX: Ignore extra environment variables not defined in model
    )


# Singleton instance
_cache_settings: Optional[CacheSettings] = None


def get_cache_settings() -> CacheSettings:
    """
    Get the cache settings singleton instance.

    Returns:
        CacheSettings instance
    """
    global _cache_settings
    if _cache_settings is None:
        _cache_settings = CacheSettings()
    return _cache_settings


# Export singleton for direct import
cache_settings = get_cache_settings()


# Helper function for backward compatibility
def get_ttl(key: str, default: int = 300) -> int:
    """
    Get TTL value by key name.

    Args:
        key: Setting key name (e.g., 'CACHE_FLOW_TEMPLATE_TTL_SECONDS')
        default: Default value if key not found

    Returns:
        TTL value in seconds

    Example:
        >>> ttl = get_ttl('CACHE_PATIENT_CACHE_TTL_SECONDS')
        >>> 900
    """
    settings = get_cache_settings()
    return getattr(settings, key, default)
