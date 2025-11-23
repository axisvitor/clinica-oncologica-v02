"""
Cache TTL Configuration Settings

Centralized TTL (Time-To-Live) configuration for all caching operations.
All values are in seconds and can be overridden via environment variables.

Environment variables use the prefix CACHE_ followed by the setting name.
Example: CACHE_FLOW_TEMPLATE_TTL=7200

MEDIUM-008: Extracted from hardcoded values throughout the codebase.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class CacheSettings(BaseSettings):
    """
    Cache TTL configuration for all application components.

    All TTL values are in seconds and can be overridden via environment variables
    using the CACHE_ prefix.

    Examples:
        CACHE_FLOW_TEMPLATE_TTL=7200
        CACHE_AUTH_TOKEN_TTL=86400
    """

    # ========================================================================
    # FLOW & TEMPLATES
    # ========================================================================

    FLOW_TEMPLATE_TTL: int = 3600  # 1 hour
    """TTL for cached flow templates"""

    TEMPLATE_CACHE_TTL: int = 3600  # 1 hour
    """TTL for general template cache"""

    FLOW_STATE_TTL: int = 1800  # 30 minutes
    """TTL for flow state cache"""

    # ========================================================================
    # USER & AUTHENTICATION
    # ========================================================================

    USER_SESSION_TTL: int = 1800  # 30 minutes
    """TTL for user session data"""

    AUTH_TOKEN_TTL: int = 86400  # 24 hours
    """TTL for authentication tokens"""

    REFRESH_TOKEN_TTL: int = 604800  # 7 days
    """TTL for refresh tokens"""

    USER_PROFILE_TTL: int = 1800  # 30 minutes
    """TTL for cached user profiles"""

    # ========================================================================
    # PATIENT DATA
    # ========================================================================

    PATIENT_CACHE_TTL: int = 900  # 15 minutes
    """TTL for patient data cache"""

    PATIENT_LIST_TTL: int = 300  # 5 minutes
    """TTL for patient list cache"""

    PATIENT_DETAIL_TTL: int = 600  # 10 minutes
    """TTL for patient detail cache"""

    DOCTOR_CACHE_TTL: int = 1800  # 30 minutes
    """TTL for doctor/physician data cache"""

    # ========================================================================
    # QUIZ & SESSIONS
    # ========================================================================

    QUIZ_SESSION_TTL: int = 7200  # 2 hours
    """TTL for active quiz sessions"""

    QUIZ_TEMPLATES_TTL: int = 3600  # 1 hour
    """TTL for quiz template cache"""

    QUIZ_CACHE_TTL: int = 1800  # 30 minutes
    """TTL for general quiz data cache"""

    # ========================================================================
    # MESSAGES & COMMUNICATION
    # ========================================================================

    MESSAGE_CACHE_TTL: int = 3600  # 1 hour
    """TTL for message cache"""

    MESSAGE_STATS_TTL: int = 300  # 5 minutes
    """TTL for message statistics"""

    WHATSAPP_METRICS_TTL: int = 604800  # 7 days
    """TTL for WhatsApp metrics (long-term)"""

    # ========================================================================
    # WEBHOOK & IDEMPOTENCY
    # ========================================================================

    WEBHOOK_IDEMPOTENCY_TTL: int = 3600  # 1 hour
    """TTL for webhook idempotency keys"""

    WEBHOOK_CACHE_TTL: int = 300  # 5 minutes
    """TTL for webhook data cache"""

    # ========================================================================
    # RATE LIMITING
    # ========================================================================

    RATE_LIMIT_WINDOW_TTL: int = 60  # 1 minute
    """TTL for rate limit windows"""

    RATE_LIMIT_BUCKET_TTL: int = 3600  # 1 hour
    """TTL for rate limit bucket tracking"""

    # ========================================================================
    # REPORTS & ANALYTICS
    # ========================================================================

    REPORT_CACHE_TTL: int = 1800  # 30 minutes
    """TTL for report data cache"""

    REPORT_DATA_TTL: int = 1800  # 30 minutes
    """TTL for report data (alias)"""

    ANALYTICS_CACHE_TTL: int = 300  # 5 minutes
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

    DISTRIBUTED_LOCK_TTL: int = 30  # 30 seconds
    """TTL for distributed locks (short-lived)"""

    SAGA_STATE_TTL: int = 3600  # 1 hour
    """TTL for Saga orchestration state"""

    CIRCUIT_BREAKER_STATE_TTL: int = 300  # 5 minutes
    """TTL for circuit breaker state"""

    # ========================================================================
    # MONITORING & METRICS
    # ========================================================================

    SYSTEM_METRICS_TTL: int = 60  # 1 minute
    """TTL for system metrics cache"""

    RESOURCE_MONITOR_TTL: int = 300  # 5 minutes
    """TTL for resource monitoring data"""

    PERFORMANCE_METRICS_TTL: int = 300  # 5 minutes
    """TTL for performance metrics"""

    # ========================================================================
    # SESSION & STATE MANAGEMENT
    # ========================================================================

    SESSION_DATA_TTL: int = 1800  # 30 minutes
    """TTL for session data"""

    CONNECTION_STATE_TTL: int = 300  # 5 minutes
    """TTL for connection state (WhatsApp, etc.)"""

    QRCODE_TTL: int = 300  # 5 minutes
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
    # REDIS CONNECTION SETTINGS
    # ========================================================================

    REDIS_MAX_CONNECTIONS: int = 50
    """Maximum number of Redis connections in pool"""

    REDIS_SOCKET_TIMEOUT: int = 5
    """Socket timeout for Redis operations (seconds)"""

    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    """Socket connect timeout for Redis (seconds)"""

    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
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
        key: Setting key name (e.g., 'FLOW_TEMPLATE_TTL')
        default: Default value if key not found

    Returns:
        TTL value in seconds

    Example:
        >>> ttl = get_ttl('PATIENT_CACHE_TTL')
        >>> 900
    """
    settings = get_cache_settings()
    return getattr(settings, key, default)
