"""Utility package exports.

Keep package import side effects minimal so submodule imports such as
`app.utils.timezone` do not bootstrap unrelated runtime configuration.
"""

from __future__ import annotations

from importlib import import_module

_EXPORTS: dict[str, tuple[str, str]] = {
    # Template & Input Sanitization
    "TemplateSanitizer": ("app.utils.template_sanitizer", "TemplateSanitizer"),
    "get_template_sanitizer": (
        "app.utils.template_sanitizer",
        "get_template_sanitizer",
    ),
    "InputSanitizer": ("app.utils.input_sanitization", "InputSanitizer"),
    "sanitize_input": ("app.utils.input_sanitization", "sanitize_input"),
    "get_sanitizer": ("app.utils.input_sanitization", "get_sanitizer"),
    "mask_cpf": ("app.utils.pii_redaction", "mask_cpf"),
    "mask_phone": ("app.utils.pii_redaction", "mask_phone"),
    "mask_email": ("app.utils.pii_redaction", "mask_email"),
    "mask_name": ("app.utils.pii_redaction", "mask_name"),
    "mask_pii_in_log_message": (
        "app.utils.pii_redaction",
        "mask_pii_in_log_message",
    ),
    "safe_patient_log_context": (
        "app.utils.pii_redaction",
        "safe_patient_log_context",
    ),
    # Version Management
    "VersionError": ("app.utils.version_utils", "VersionError"),
    "parse_version": ("app.utils.version_utils", "parse_version"),
    "normalize_version": ("app.utils.version_utils", "normalize_version"),
    "to_int_version": ("app.utils.version_utils", "to_int_version"),
    "compare_versions": ("app.utils.version_utils", "compare_versions"),
    "is_valid_version": ("app.utils.version_utils", "is_valid_version"),
    "is_semantic_version": ("app.utils.version_utils", "is_semantic_version"),
    "get_major_version": ("app.utils.version_utils", "get_major_version"),
    "get_minor_version": ("app.utils.version_utils", "get_minor_version"),
    "get_patch_version": ("app.utils.version_utils", "get_patch_version"),
    "increment_major": ("app.utils.version_utils", "increment_major"),
    "increment_minor": ("app.utils.version_utils", "increment_minor"),
    "increment_patch": ("app.utils.version_utils", "increment_patch"),
    "version_to_dict": ("app.utils.version_utils", "version_to_dict"),
    # Database & Transaction Management
    "async_transaction": ("app.utils.transaction_manager", "async_transaction"),
    "sync_transaction": ("app.utils.transaction_manager", "sync_transaction"),
    "with_transaction": ("app.utils.transaction_manager", "with_transaction"),
    "with_db_retry": ("app.utils.db_retry", "with_db_retry"),
    "reset_circuit_breaker": ("app.utils.db_retry", "reset_circuit_breaker"),
    "DatabaseOptimizer": (
        "app.utils.database_optimization",
        "DatabaseOptimizer",
    ),
    "QueryOptimizer": ("app.utils.database_optimization", "QueryOptimizer"),
    "get_db_optimizer": ("app.utils.database_optimization", "get_db_optimizer"),
    # Audit & Logging
    "get_logger": ("app.utils.logging", "get_logger"),
    "setup_logging": ("app.utils.logging", "setup_logging"),
    "StructuredLogger": ("app.utils.structured_logger", "StructuredLogger"),
    "AuditLogger": ("app.monitoring.audit_logger", "TemplateAuditLogger"),
    "AuditAction": ("app.monitoring.audit_logger", "TemplateAuditAction"),
    # Security & Rate Limiting
    "limiter": ("app.utils.rate_limiter", "limiter"),
    "get_password_hash": ("app.utils.security", "get_password_hash"),
    "verify_password": ("app.utils.security", "verify_password"),
    "create_access_token": ("app.utils.security", "create_access_token"),
    "verify_token": ("app.utils.security", "verify_token"),
    "validate_csrf_secret": (
        "app.utils.key_validation",
        "validate_csrf_secret",
    ),
    "validate_secret_key": ("app.utils.key_validation", "validate_secret_key"),
    "validate_key_strength": ("app.utils.key_validation", "validate_key_strength"),
}

__all__ = list(_EXPORTS)

__version__ = "2.0.0"
__author__ = "Backend Team"
__description__ = "Core utility module with commonly used functions and classes"


def __getattr__(name: str):
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
