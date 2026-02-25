"""
Application Constants - Centralized Magic Numbers and Configuration Values.

This module consolidates all magic numbers and hardcoded values found throughout
the codebase to improve maintainability and comply with DRY principles.

Addresses:
- MEDIUM-003: Magic Numbers consolidation
- LOW-003: Hardcoded regex patterns

File: backend-hormonia/app/config/constants.py
Created: 2025-11-16
Compliance: DRY 95%+
"""

import re
from typing import Final

# ============================================================================
# SAGA CONFIGURATION
# ============================================================================


class SagaConfig:
    """Configuration for Saga orchestration and retry logic."""

    # Retry settings
    MAX_RETRIES: Final[int] = 3
    """Maximum number of retry attempts for failed saga steps"""

    TIMEOUT_SECONDS: Final[int] = 300
    """Maximum timeout for saga step execution (5 minutes)"""

    RETRY_BASE_DELAY: Final[int] = 5
    """Base delay in seconds for exponential backoff retry strategy"""

    RETRY_INITIAL_DELAY: Final[int] = 1
    """Initial retry delay in seconds"""

    RETRY_MAX_DELAY: Final[int] = 30
    """Maximum retry delay in seconds"""

    # Monitoring settings
    METRICS_COLLECTION_INTERVAL: Final[int] = 3600
    """Interval for collecting saga metrics (1 hour)"""


# ============================================================================
# CACHE CONFIGURATION
# ============================================================================


class CacheConfig:
    """Configuration for Redis cache TTL values."""

    # General cache TTLs
    TTL_SECONDS: Final[int] = 3600
    """Default cache TTL (1 hour)"""

    TEMPLATE_TTL: Final[int] = 3600
    """Template cache TTL (1 hour)"""

    USER_DATA_TTL: Final[int] = 900
    """User data cache TTL (15 minutes)"""

    USER_PROFILE_TTL: Final[int] = 3600
    """User profile cache TTL (1 hour)"""

    # Quiz-specific cache
    QUIZ_RESPONSE_TTL: Final[int] = 300
    """Quiz response cache TTL (5 minutes)"""

    PUBLIC_QUIZ_TTL: Final[int] = 900
    """Public quiz cache TTL (15 minutes)"""

    # Connection and pool settings
    POOL_RECYCLE_SECONDS: Final[int] = 3600
    """Database connection pool recycle interval (1 hour)"""


# ============================================================================
# PAGINATION CONFIGURATION
# ============================================================================


class PaginationConfig:
    """Configuration for API pagination limits."""

    DEFAULT_PAGE_SIZE: Final[int] = 50
    """Default number of items per page"""

    MAX_PAGE_SIZE: Final[int] = 100
    """Maximum number of items per page"""

    ADMIN_LIMIT_MAX: Final[int] = 200
    """Maximum items for admin endpoints"""

    BATCH_PROCESS_LIMIT: Final[int] = 50
    """Limit for batch processing operations"""


# ============================================================================
# RATE LIMITING CONFIGURATION
# ============================================================================


class RateLimitConfig:
    """Configuration for rate limiting and throttling."""

    # WhatsApp rate limiting
    WHATSAPP_MAX_REQUESTS: Final[int] = 50
    """Maximum WhatsApp requests per time window"""

    WHATSAPP_TIME_WINDOW: Final[int] = 60
    """WhatsApp rate limit time window (seconds)"""

    # Password change rate limiting
    PASSWORD_CHANGE_MAX_ATTEMPTS: Final[int] = 3
    """Maximum password change attempts"""

    PASSWORD_CHANGE_WINDOW_SECONDS: Final[int] = 3600
    """Password change rate limit window (1 hour)"""

    # Webhook processing
    WEBHOOK_RETRY_MAX_DELAY: Final[int] = 300
    """Maximum delay for webhook retry (5 minutes)"""


# ============================================================================
# TIMEOUT CONFIGURATION
# ============================================================================


class TimeoutConfig:
    """Configuration for various timeout values."""

    RECOVERY_TIMEOUT: Final[int] = 300
    """Recovery timeout for services (5 minutes)"""

    MESSAGE_TIME_DIFF_THRESHOLD: Final[int] = 300
    """Time difference threshold for message deduplication (5 minutes)"""

    TASK_RETRY_COUNTDOWN: Final[int] = 300
    """Countdown for task retry (5 minutes)"""

    QUIZ_SESSION_24H: Final[int] = 24 * 3600
    """Quiz session timeout (24 hours)"""

    QUIZ_SESSION_18H: Final[int] = 18 * 3600
    """Quiz session warning threshold (18 hours)"""


# ============================================================================
# TOKEN/STRING LENGTH LIMITS
# ============================================================================


class LimitsConfig:
    """Configuration for string and token limits."""

    # Token limits
    CONTEXT_MAX_TOKENS: Final[int] = 300
    """Maximum tokens for patient context"""

    MESSAGE_MAX_TOKENS: Final[int] = 100
    """Maximum tokens for individual messages"""

    METADATA_TOKENS: Final[int] = 100
    """Tokens reserved for patient metadata"""

    QUIZ_TOKENS: Final[int] = 100
    """Tokens reserved for quiz responses"""

    FLOW_TOKENS: Final[int] = 100
    """Tokens reserved for flow data"""

    TOKEN_BUFFER: Final[int] = 50
    """Token buffer reservation"""

    MINIMUM_CONTEXT_BUDGET: Final[int] = 100
    """Minimum context budget after reservations"""

    # Database field lengths
    STRING_SHORT: Final[int] = 50
    """Short string field length (e.g., operation type, status)"""

    STRING_MEDIUM: Final[int] = 100
    """Medium string field length (e.g., file type, treatment sessions)"""

    STRING_LONG: Final[int] = 500
    """Long string field length (e.g., diagnosis)"""

    # Content truncation
    CONTENT_PREVIEW_LENGTH: Final[int] = 100
    """Length for content preview in logs"""


# ============================================================================
# PERCENTAGE THRESHOLDS
# ============================================================================


class ThresholdConfig:
    """Configuration for percentage-based thresholds."""

    QUIZ_COMPLETION_FOLLOW_UP: Final[int] = 50
    """Quiz completion percentage requiring follow-up"""

    PROGRESS_MAX_PERCENT: Final[int] = 100
    """Maximum progress percentage"""

    TREATMENT_DAYS_TOTAL: Final[int] = 180
    """Total days for treatment progress calculation"""


# ============================================================================
# RETRY SCHEDULE CONFIGURATION
# ============================================================================


class RetryScheduleConfig:
    """Configuration for retry scheduling."""

    QUIZ_LINK_RETRY_DELAYS: Final[list[int]] = [3600, 7200, 14400]
    """Quiz link retry delays: 1h, 2h, 4h"""


# ============================================================================
# REGEX PATTERNS
# ============================================================================


class RegexPatterns:
    """Centralized regex patterns for validation."""

    CPF_REGEX: Final[re.Pattern] = re.compile(r"^\d{11}$")
    """Brazilian CPF pattern (11 digits)"""

    CPF_CLEAN_REGEX: Final[re.Pattern] = re.compile(r"[^0-9]")
    """Pattern to remove non-digits from CPF"""

    PHONE_REGEX: Final[re.Pattern] = re.compile(r"^\+?[1-9]\d{1,14}$")
    """International phone number pattern (E.164 format)"""

    EMAIL_REGEX: Final[re.Pattern] = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )
    """Email validation pattern"""

    # Brazilian phone patterns
    BR_PHONE_DIGITS_ONLY: Final[re.Pattern] = re.compile(r"\D")
    """Pattern to extract only digits from phone numbers"""


# ============================================================================
# CPF VALIDATION CONSTANTS
# ============================================================================


class CPFConstants:
    """Constants for CPF validation."""

    LENGTH: Final[int] = 11
    """Valid CPF length"""

    INVALID_SEQUENCES: Final[set[str]] = {
        "00000000000",
        "11111111111",
        "22222222222",
        "33333333333",
        "44444444444",
        "55555555555",
        "66666666666",
        "77777777777",
        "88888888888",
        "99999999999",
    }
    """Known invalid CPF sequences (all same digit)"""


# ============================================================================
# TREATMENT PHASE CONSTANTS
# ============================================================================


class TreatmentPhase:
    """Valid treatment phase values."""

    ONBOARDING: Final[str] = "onboarding"
    INITIAL: Final[str] = "initial"
    ADJUSTMENT: Final[str] = "adjustment"
    MAINTENANCE: Final[str] = "maintenance"
    MONITORING: Final[str] = "monitoring"
    FOLLOWUP: Final[str] = "followup"
    COMPLETED: Final[str] = "completed"

    ALL_PHASES: Final[set[str]] = {
        ONBOARDING,
        INITIAL,
        ADJUSTMENT,
        MAINTENANCE,
        MONITORING,
        FOLLOWUP,
        COMPLETED,
    }


# ============================================================================
# IDEMPOTENCY CONFIGURATION
# ============================================================================


class IdempotencyConfig:
    """Configuration for idempotency keys and TTL."""

    WEBHOOK_MESSAGE_TTL: Final[int] = 3600
    """TTL for webhook message idempotency keys (1 hour)"""

    REDIS_KEY_PREFIX_WEBHOOK: Final[str] = "webhook:message:"
    """Prefix for webhook idempotency keys in Redis"""


# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================


class SecurityConfig:
    """Security-related constants."""

    UNAUTHORIZED_MAX_ATTEMPTS: Final[int] = 3
    """Maximum unauthorized access attempts before blocking"""

    CONTENT_LOG_MAX_LENGTH: Final[int] = 100
    """Maximum content length for security logs"""

    SECURITY_EVENT_TTL: Final[int] = 86400
    """TTL for security event tracking (24 hours)"""


# ============================================================================
# EXPORT ALL CONFIGURATIONS
# ============================================================================

__all__ = [
    "SagaConfig",
    "CacheConfig",
    "PaginationConfig",
    "RateLimitConfig",
    "TimeoutConfig",
    "LimitsConfig",
    "ThresholdConfig",
    "RetryScheduleConfig",
    "RegexPatterns",
    "CPFConstants",
    "TreatmentPhase",
    "IdempotencyConfig",
    "SecurityConfig",
]
