"""
Flow Configuration - Configuration settings for Flow Services (QW-021).

This module centralizes all configuration for the flow system, including
timeouts, retry policies, feature flags, and integration settings.

Migration Note:
    This consolidates configuration from:
    - enhanced_flow_engine.py (engine config)
    - flow_engine.py (legacy config)
    - flow_template.py (template config)
    - Various hardcoded values across flow services
"""

from typing import Dict, Any, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class FlowExecutionConfig(BaseSettings):
    """Configuration for flow execution engine."""

    # Timeouts
    default_step_timeout_seconds: int = Field(
        default=300,
        description="Default timeout for step execution (5 minutes)",
    )
    default_flow_timeout_minutes: int = Field(
        default=60,
        description="Default timeout for entire flow (1 hour)",
    )
    max_flow_timeout_hours: int = Field(
        default=24,
        description="Maximum allowed flow timeout (24 hours)",
    )

    # Retries
    max_step_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed steps",
    )
    retry_backoff_seconds: int = Field(
        default=5,
        description="Initial backoff time between retries",
    )
    retry_backoff_multiplier: float = Field(
        default=2.0,
        description="Backoff multiplier for exponential backoff",
    )

    # Concurrency
    max_concurrent_flows_per_patient: int = Field(
        default=5,
        description="Maximum concurrent flows per patient",
    )
    max_concurrent_steps: int = Field(
        default=10,
        description="Maximum concurrent step executions",
    )

    # Validation
    enable_strict_validation: bool = Field(
        default=True,
        description="Enable strict validation of flow data",
    )
    validate_transitions: bool = Field(
        default=True,
        description="Validate transitions between steps",
    )

    # Performance
    enable_step_caching: bool = Field(
        default=True,
        description="Enable caching of step results",
    )
    step_cache_ttl_seconds: int = Field(
        default=300,
        description="TTL for step result cache (5 minutes)",
    )

    @field_validator("max_step_retries")
    @classmethod
    def validate_max_retries(cls, v):
        """Ensure max retries is reasonable."""
        if v < 0:
            raise ValueError("max_step_retries must be >= 0")
        if v > 10:
            raise ValueError("max_step_retries must be <= 10")
        return v

    model_config = {"env_prefix": "FLOW_EXECUTION_"}


class FlowTemplateConfig(BaseSettings):
    """Configuration for flow template management."""

    # Template storage
    template_cache_enabled: bool = Field(
        default=True,
        description="Enable template caching",
    )
    template_cache_ttl_seconds: int = Field(
        default=3600,
        description="Template cache TTL (1 hour)",
    )

    # Versioning
    enable_template_versioning: bool = Field(
        default=True,
        description="Enable template versioning",
    )
    max_template_versions: int = Field(
        default=10,
        description="Maximum template versions to keep",
    )

    # Validation
    validate_template_on_load: bool = Field(
        default=True,
        description="Validate templates when loading",
    )
    strict_template_validation: bool = Field(
        default=False,
        description="Use strict validation (fail on warnings)",
    )

    model_config = {"env_prefix": "FLOW_TEMPLATE_"}


class FlowAnalyticsConfig(BaseSettings):
    """Configuration for flow analytics and monitoring."""

    # Metrics
    enable_metrics: bool = Field(
        default=True,
        description="Enable flow metrics collection",
    )
    metrics_aggregation_interval_seconds: int = Field(
        default=60,
        description="Metrics aggregation interval (1 minute)",
    )

    # Events
    enable_event_broadcasting: bool = Field(
        default=True,
        description="Enable flow event broadcasting",
    )
    event_queue_size: int = Field(
        default=1000,
        description="Maximum event queue size",
    )

    # Monitoring
    enable_health_checks: bool = Field(
        default=True,
        description="Enable flow health monitoring",
    )
    health_check_interval_seconds: int = Field(
        default=30,
        description="Health check interval (30 seconds)",
    )

    # Dashboard
    enable_dashboard: bool = Field(
        default=True,
        description="Enable flow dashboard",
    )
    dashboard_refresh_seconds: int = Field(
        default=10,
        description="Dashboard data refresh interval (10 seconds)",
    )

    model_config = {"env_prefix": "FLOW_ANALYTICS_"}


class FlowIntegrationConfig(BaseSettings):
    """Configuration for flow integrations (Quiz, AI, etc.)."""

    # Quiz Integration
    enable_quiz_integration: bool = Field(
        default=True,
        description="Enable quiz flow integration",
    )
    quiz_timeout_hours: int = Field(
        default=72,
        description="Quiz completion timeout (72 hours)",
    )
    quiz_reminder_interval_hours: int = Field(
        default=24,
        description="Quiz reminder interval (24 hours)",
    )

    # AI Integration
    enable_ai_integration: bool = Field(
        default=True,
        description="Enable AI features in flows",
    )
    ai_timeout_seconds: int = Field(
        default=30,
        description="AI request timeout (30 seconds)",
    )
    ai_max_retries: int = Field(
        default=2,
        description="AI request max retries",
    )

    # Message Integration
    enable_message_sending: bool = Field(
        default=True,
        description="Enable message sending from flows",
    )
    message_rate_limit_per_minute: int = Field(
        default=10,
        description="Message rate limit per patient (10/min)",
    )

    model_config = {"env_prefix": "FLOW_INTEGRATION_"}


class FlowErrorHandlingConfig(BaseSettings):
    """Configuration for error handling and recovery."""

    # Error handling
    enable_auto_recovery: bool = Field(
        default=True,
        description="Enable automatic error recovery",
    )
    max_recovery_attempts: int = Field(
        default=3,
        description="Maximum automatic recovery attempts",
    )

    # Error escalation
    escalate_after_failures: int = Field(
        default=5,
        description="Escalate to admin after N failures",
    )
    enable_error_notifications: bool = Field(
        default=True,
        description="Enable error notifications",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Log level for flow operations",
    )
    log_detailed_errors: bool = Field(
        default=True,
        description="Log detailed error information",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Ensure log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    model_config = {"env_prefix": "FLOW_ERROR_"}


class FlowFeatureFlags(BaseSettings):
    """
    Feature flags for the canonical production flow system.

    Controls routing behavior of the FlowDispatcher facade.
    Canonical system: production (flow_core.py / EnhancedFlowEngine).
    """

    # Canonical system identifier (informational)
    canonical_system: str = Field(
        default="production",
        description="Canonical flow system: 'production' (flat files: flow_core.py / EnhancedFlowEngine)",
    )

    # Patient-type routing flags
    route_new_patients_to_canonical: bool = Field(
        default=True,
        description="Route new patients to the canonical production system immediately",
    )
    route_existing_patients_to_canonical: bool = Field(
        default=True,
        description="Route existing patients to the canonical production system",
    )

    # Audit / transition logging
    log_dispatcher_routing: bool = Field(
        default=True,
        description="Log FlowDispatcher routing decisions for audit during migration",
    )

    model_config = {"env_prefix": "FLOW_FEATURE_"}


class FlowConfig:
    """
    Main configuration container for Flow Services.

    Aggregates all flow-related configuration into a single access point.
    """

    def __init__(self):
        """Initialize all configuration sections."""
        self.execution = FlowExecutionConfig()
        self.templates = FlowTemplateConfig()
        self.analytics = FlowAnalyticsConfig()
        self.integrations = FlowIntegrationConfig()
        self.error_handling = FlowErrorHandlingConfig()
        self.feature_flags = FlowFeatureFlags()

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        Export all configuration as dictionary.

        Returns:
            Dictionary with all configuration values.
        """
        return {
            "execution": self.execution.model_dump(),
            "templates": self.templates.model_dump(),
            "analytics": self.analytics.model_dump(),
            "integrations": self.integrations.model_dump(),
            "error_handling": self.error_handling.model_dump(),
            "feature_flags": self.feature_flags.model_dump(),
        }

    def update_from_dict(self, config_dict: Dict[str, Dict[str, Any]]) -> None:
        """
        Update configuration from dictionary.

        Args:
            config_dict: Dictionary with configuration updates.
        """
        if "execution" in config_dict:
            self.execution = FlowExecutionConfig(**config_dict["execution"])
        if "templates" in config_dict:
            self.templates = FlowTemplateConfig(**config_dict["templates"])
        if "analytics" in config_dict:
            self.analytics = FlowAnalyticsConfig(**config_dict["analytics"])
        if "integrations" in config_dict:
            self.integrations = FlowIntegrationConfig(**config_dict["integrations"])
        if "error_handling" in config_dict:
            self.error_handling = FlowErrorHandlingConfig(
                **config_dict["error_handling"]
            )
        if "feature_flags" in config_dict:
            self.feature_flags = FlowFeatureFlags(**config_dict["feature_flags"])

    def is_canonical_system_production(self) -> bool:
        """
        Check if the canonical system is set to production.

        Returns:
            True if canonical_system == "production" (always True post-QW-021 deletion).
        """
        return self.feature_flags.canonical_system == "production"


# ============================================================================
# Global Configuration Instance
# ============================================================================

# Global config instance (singleton pattern)
_flow_config: Optional[FlowConfig] = None


def get_flow_config() -> FlowConfig:
    """
    Get global flow configuration instance.

    Returns:
        Global FlowConfig instance (singleton).
    """
    global _flow_config
    if _flow_config is None:
        _flow_config = FlowConfig()
    return _flow_config


def reset_flow_config() -> None:
    """
    Reset global flow configuration.

    Useful for testing.
    """
    global _flow_config
    _flow_config = None


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "FlowExecutionConfig",
    "FlowTemplateConfig",
    "FlowAnalyticsConfig",
    "FlowIntegrationConfig",
    "FlowErrorHandlingConfig",
    "FlowFeatureFlags",
    "FlowConfig",
    "get_flow_config",
    "reset_flow_config",
]
