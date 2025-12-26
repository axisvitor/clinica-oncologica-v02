"""
Utility modules for the application.

This module provides a comprehensive set of utility functions and classes
organized by functionality categories.
"""

# =============================================================================
# Template & Input Sanitization
# =============================================================================
from app.utils.template_sanitizer import (
    TemplateSanitizer,
    get_template_sanitizer,
)
from app.utils.input_sanitizer import InputSanitizer
from app.utils.input_sanitization import sanitize_input, get_sanitizer
from app.utils.pii_masking import (
    mask_cpf,
    mask_phone,
    mask_email,
    mask_name,
    mask_pii_in_log_message,
    safe_patient_log_context,
)

# =============================================================================
# Version Management
# =============================================================================
from app.utils.version_utils import (
    VersionError,
    parse_version,
    normalize_version,
    to_int_version,
    compare_versions,
    is_valid_version,
    is_semantic_version,
    get_major_version,
    get_minor_version,
    get_patch_version,
    increment_major,
    increment_minor,
    increment_patch,
    version_to_dict,
)

# =============================================================================
# Database & Transaction Management
# =============================================================================
from app.utils.transaction_manager import (
    async_transaction,
    sync_transaction,
    with_transaction,
)
from app.utils.db_retry import with_db_retry, reset_circuit_breaker
from app.utils.database_optimization import (
    DatabaseOptimizer,
    QueryOptimizer,
    get_db_optimizer,
)

# =============================================================================
# Audit & Logging
# =============================================================================
from app.utils.audit_logger import (
    AuditLogger,
    AuditAction,
)
from app.utils.logging import get_logger, setup_logging
from app.utils.structured_logger import StructuredLogger

# =============================================================================
# Security & Rate Limiting
# =============================================================================
from app.utils.rate_limiter import limiter
from app.utils.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    verify_token,
)
from app.utils.security_validation import (
    validate_csrf_secret,
    validate_secret_key,
    validate_key_strength,
)

# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    # Template & Input Sanitization
    "TemplateSanitizer",
    "get_template_sanitizer",
    "InputSanitizer",
    "sanitize_input",
    "get_sanitizer",
    "mask_cpf",
    "mask_phone",
    "mask_email",
    "mask_name",
    "mask_pii_in_log_message",
    "safe_patient_log_context",

    # Version Management
    "VersionError",
    "parse_version",
    "normalize_version",
    "to_int_version",
    "compare_versions",
    "is_valid_version",
    "is_semantic_version",
    "get_major_version",
    "get_minor_version",
    "get_patch_version",
    "increment_major",
    "increment_minor",
    "increment_patch",
    "version_to_dict",

    # Database & Transaction Management
    "async_transaction",
    "sync_transaction",
    "with_transaction",
    "with_db_retry",
    "reset_circuit_breaker",
    "DatabaseOptimizer",
    "QueryOptimizer",
    "get_db_optimizer",

    # Audit & Logging
    "AuditLogger",
    "AuditAction",
    "get_logger",
    "setup_logging",
    "StructuredLogger",

    # Security & Rate Limiting
    "limiter",
    "get_password_hash",
    "verify_password",
    "create_access_token",
    "verify_token",
    "validate_csrf_secret",
    "validate_secret_key",
    "validate_key_strength",
]

# =============================================================================
# Module Metadata
# =============================================================================
__version__ = "2.0.0"
__author__ = "Backend Team"
__description__ = "Core utility module with commonly used functions and classes"
