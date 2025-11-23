"""
Centralized template loader for flow configurations.
Provides unified access to flow template configurations and mappings.
"""
import os
import yaml
import json
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache
from datetime import datetime, timedelta

from pydantic import BaseModel, Field, validator
from app.schemas.jsonb_validators import validate_flow_template_data

logger = logging.getLogger(__name__)


@dataclass
class FlowTypeConfig:
    """Configuration for a specific flow type."""
    name: str
    description: str
    duration_days: int
    frequency: str
    priority: str
    tags: List[str]
    template_mapping: Dict[str, Any]
    timing: Dict[str, Any]
    personalization: Dict[str, Any]
    enum_value: Optional[str] = None


@dataclass
class TemplateDirectories:
    """Template directory structure configuration."""
    base_path: str
    flows: str
    quiz: str
    fallbacks: str
    ai_prompts: str


@dataclass
class DefaultConfig:
    """Default configuration settings."""
    timing: Dict[str, Any]
    personalization: Dict[str, Any]
    caching: Dict[str, Any]
    retry: Dict[str, Any]


class FlowTemplateConfigLoader:
    """
    Centralized loader for flow template configurations.
    Provides access to flow type mappings, template directories, and default settings.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the template configuration loader.

        Args:
            config_path: Path to the flow_templates.yaml file
        """
        self.config_path = config_path or self._get_default_config_path()
        self._config: Optional[Dict[str, Any]] = None
        self._last_loaded: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=30)  # Cache config for 30 minutes

    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        current_dir = Path(__file__).parent
        return str(current_dir / "flow_templates.yaml")

    @property
    def config(self) -> Dict[str, Any]:
        """
        Get the configuration dictionary with automatic reloading.

        Returns:
            Configuration dictionary
        """
        now = datetime.now()

        # Load if not cached or cache expired
        if (self._config is None or
            self._last_loaded is None or
            (now - self._last_loaded) > self._cache_ttl):
            self._load_config()

        return self._config or {}

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(self.config_path):
                logger.error(f"Configuration file not found: {self.config_path}")
                self._config = self._get_fallback_config()
                return

            with open(self.config_path, 'r', encoding='utf-8') as file:
                self._config = yaml.safe_load(file)
                self._last_loaded = datetime.now()

            logger.info(f"Loaded flow template configuration from {self.config_path}")

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self._config = self._get_fallback_config()

    def _get_fallback_config(self) -> Dict[str, Any]:
        """Get fallback configuration if main config fails to load."""
        return {
            "flow_types": {
                "day_1_15": {
                    "name": "Early Treatment Support",
                    "description": "Initial treatment phase",
                    "duration_days": 15,
                    "frequency": "daily",
                    "priority": "high",
                    "tags": ["initial", "support"],
                    "template_mapping": {
                        "file_path": "templates/flows/day_1_15.yaml",
                        "fallback_template": "basic_support",
                        "version": "1.0.0"
                    },
                    "timing": {
                        "start_hour": 9,
                        "end_hour": 18,
                        "timezone": "America/Sao_Paulo"
                    },
                    "personalization": {
                        "ai_optimization": True,
                        "sentiment_analysis": True
                    },
                    "enum_value": "initial_15_days"
                }
            },
            "defaults": {
                "timing": {
                    "timezone": "America/Sao_Paulo",
                    "business_hours_start": 9,
                    "business_hours_end": 18
                },
                "personalization": {
                    "ai_optimization": True,
                    "sentiment_analysis": True
                },
                "caching": {
                    "template_cache_ttl": 3600
                }
            }
        }

    @lru_cache(maxsize=128)
    def get_flow_type_config(self, flow_type: str) -> Optional[FlowTypeConfig]:
        """
        Get configuration for a specific flow type.

        Args:
            flow_type: The flow type identifier (e.g., 'day_1_15', 'monthly')

        Returns:
            FlowTypeConfig object or None if not found
        """
        flow_types = self.config.get("flow_types", {})

        if flow_type not in flow_types:
            logger.warning(f"Flow type '{flow_type}' not found in configuration")
            return None

        config_data = flow_types[flow_type]

        try:
            return FlowTypeConfig(
                name=config_data.get("name", ""),
                description=config_data.get("description", ""),
                duration_days=config_data.get("duration_days", 1),
                frequency=config_data.get("frequency", "daily"),
                priority=config_data.get("priority", "medium"),
                tags=config_data.get("tags", []),
                template_mapping=config_data.get("template_mapping", {}),
                timing=config_data.get("timing", {}),
                personalization=config_data.get("personalization", {}),
                enum_value=config_data.get("enum_value")
            )
        except Exception as e:
            logger.error(f"Error creating FlowTypeConfig for {flow_type}: {e}")
            return None

    def get_template_directories(self) -> TemplateDirectories:
        """
        Get template directory configuration.

        Returns:
            TemplateDirectories object
        """
        directories = self.config.get("template_directories", {})

        return TemplateDirectories(
            base_path=directories.get("base_path", "templates"),
            flows=directories.get("flows", "templates/flows"),
            quiz=directories.get("quiz", "templates/quiz"),
            fallbacks=directories.get("fallbacks", "templates/fallbacks"),
            ai_prompts=directories.get("ai_prompts", "templates/ai")
        )

    def get_default_config(self) -> DefaultConfig:
        """
        Get default configuration settings.

        Returns:
            DefaultConfig object
        """
        defaults = self.config.get("defaults", {})

        return DefaultConfig(
            timing=defaults.get("timing", {
                "timezone": "America/Sao_Paulo",
                "business_hours_start": 9,
                "business_hours_end": 18
            }),
            personalization=defaults.get("personalization", {
                "ai_optimization": True,
                "sentiment_analysis": True
            }),
            caching=defaults.get("caching", {
                "template_cache_ttl": 3600
            }),
            retry=defaults.get("retry", {
                "max_attempts": 3,
                "backoff_multiplier": 2,
                "initial_delay": 60
            })
        )

    def get_available_flow_types(self) -> List[str]:
        """
        Get list of all available flow types.

        Returns:
            List of flow type identifiers
        """
        return list(self.config.get("flow_types", {}).keys())

    def get_flow_transitions(self) -> Dict[str, Any]:
        """
        Get flow transition rules.

        Returns:
            Dictionary of transition rules
        """
        return self.config.get("transitions", {})

    def get_integration_settings(self) -> Dict[str, Any]:
        """
        Get integration settings for external services.

        Returns:
            Dictionary of integration configurations
        """
        return self.config.get("integrations", {})

    def get_monitoring_config(self) -> Dict[str, Any]:
        """
        Get monitoring and analytics configuration.

        Returns:
            Dictionary of monitoring settings
        """
        return self.config.get("monitoring", {})

    def get_security_config(self) -> Dict[str, Any]:
        """
        Get security and compliance configuration.

        Returns:
            Dictionary of security settings
        """
        return self.config.get("security", {})

    def get_feature_flags(self) -> Dict[str, bool]:
        """
        Get feature flags configuration.

        Returns:
            Dictionary of feature flags
        """
        return self.config.get("feature_flags", {})

    def reload_config(self) -> bool:
        """
        Force reload of configuration from file.

        Returns:
            True if reload successful, False otherwise
        """
        try:
            self._config = None
            self._last_loaded = None
            # Clear LRU cache
            self.get_flow_type_config.cache_clear()

            # Trigger reload
            _ = self.config

            logger.info("Configuration reloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            return False

    def validate_flow_type(self, flow_type: str) -> bool:
        """
        Validate if a flow type exists and is properly configured.

        Args:
            flow_type: Flow type to validate

        Returns:
            True if valid, False otherwise
        """
        config = self.get_flow_type_config(flow_type)
        if not config:
            return False

        # Basic validation
        if not config.name or config.duration_days <= 0:
            logger.warning(f"Invalid configuration for flow type '{flow_type}'")
            return False

        return True

    def get_template_file_path(self, flow_type: str) -> Optional[str]:
        """
        Get the template file path for a flow type.

        Args:
            flow_type: Flow type identifier

        Returns:
            Template file path or None if not found
        """
        config = self.get_flow_type_config(flow_type)
        if not config:
            return None

        return config.template_mapping.get("file_path")

    def get_fallback_template(self, flow_type: str) -> Optional[str]:
        """
        Get the fallback template for a flow type.

        Args:
            flow_type: Flow type identifier

        Returns:
            Fallback template name or None if not found
        """
        config = self.get_flow_type_config(flow_type)
        if not config:
            return None

        return config.template_mapping.get("fallback_template")

    def is_ai_optimization_enabled(self, flow_type: str) -> bool:
        """
        Check if AI optimization is enabled for a flow type.

        Args:
            flow_type: Flow type identifier

        Returns:
            True if AI optimization is enabled, False otherwise
        """
        config = self.get_flow_type_config(flow_type)
        if not config:
            return self.get_default_config().personalization.get("ai_optimization", False)

        return config.personalization.get("ai_optimization", False)

    def get_cache_ttl(self, cache_type: str = "template_cache_ttl") -> int:
        """
        Get cache TTL for a specific cache type.

        Args:
            cache_type: Type of cache (template_cache_ttl, flow_state_cache_ttl, etc.)

        Returns:
            TTL in seconds
        """
        defaults = self.get_default_config()
        return defaults.caching.get(cache_type, 3600)

    def get_template_for_treatment_type(self, treatment_type: Optional[str]) -> Optional[str]:
        """
        Get flow template based on patient treatment type.

        Maps treatment type keywords to appropriate flow templates using
        the treatment_type_mapping configuration.

        Args:
            treatment_type: Patient's treatment type (e.g., "hormone therapy", "chemotherapy")

        Returns:
            Flow template identifier (e.g., "hormone_therapy_1") or default template
        """
        if not treatment_type:
            return self.config.get("default_treatment_template", "day_1_15")

        # Normalize input
        type_lower = treatment_type.lower().strip()

        # Get treatment type mapping
        treatment_mapping = self.config.get("treatment_type_mapping", {})

        # Search for matching keywords (sorted by priority)
        matched_categories = []
        for category, config in treatment_mapping.items():
            keywords = config.get("keywords", [])
            priority = config.get("priority", 0)

            # Check if any keyword matches the treatment type
            for keyword in keywords:
                if keyword.lower() in type_lower:
                    matched_categories.append((priority, config.get("template")))
                    break

        # Return highest priority match
        if matched_categories:
            matched_categories.sort(reverse=True, key=lambda x: x[0])
            template = matched_categories[0][1]
            logger.info(f"Selected template '{template}' for treatment type '{treatment_type}'")
            return template

        # Return default template
        default = self.config.get("default_treatment_template", "day_1_15")
        logger.info(f"Using default template '{default}' for treatment type '{treatment_type}'")
        return default


# Global singleton instance
_template_loader: Optional[FlowTemplateConfigLoader] = None


def get_template_loader() -> FlowTemplateConfigLoader:
    """
    Get the global template loader singleton.

    Returns:
        FlowTemplateConfigLoader instance
    """
    global _template_loader
    if _template_loader is None:
        _template_loader = FlowTemplateConfigLoader()
    return _template_loader


# Convenience functions for common operations
def get_flow_config(flow_type: str) -> Optional[FlowTypeConfig]:
    """
    Get configuration for a flow type.

    Args:
        flow_type: Flow type identifier

    Returns:
        FlowTypeConfig or None
    """
    return get_template_loader().get_flow_type_config(flow_type)


def get_flow_duration(flow_type: str) -> int:
    """
    Get duration in days for a flow type.

    Args:
        flow_type: Flow type identifier

    Returns:
        Duration in days, or 1 as default
    """
    config = get_flow_config(flow_type)
    return config.duration_days if config else 1


def is_valid_flow_type(flow_type: str) -> bool:
    """
    Check if a flow type is valid and properly configured.

    Args:
        flow_type: Flow type identifier

    Returns:
        True if valid, False otherwise
    """
    return get_template_loader().validate_flow_type(flow_type)


def get_template_path(flow_type: str) -> Optional[str]:
    """
    Get template file path for a flow type.

    Args:
        flow_type: Flow type identifier

    Returns:
        Template file path or None
    """
    return get_template_loader().get_template_file_path(flow_type)


def reload_templates() -> bool:
    """
    Reload template configuration from file.

    Returns:
        True if successful, False otherwise
    """
    return get_template_loader().reload_config()


def get_template_for_treatment(treatment_type: Optional[str]) -> Optional[str]:
    """
    Get flow template for a patient's treatment type.

    Args:
        treatment_type: Patient's treatment type

    Returns:
        Flow template identifier or None
    """
    return get_template_loader().get_template_for_treatment_type(treatment_type)


# Flow type constants for easy access
class FlowTypes:
    """Constants for flow type identifiers."""
    DAY_1_15 = "day_1_15"
    DAY_16_45 = "day_16_45"
    MONTHLY = "monthly"
    QUIZ_MONTHLY = "quiz_monthly"
    URGENT_FOLLOWUP = "urgent_followup"

    @classmethod
    def all(cls) -> List[str]:
        """Get all flow type constants."""
        return [cls.DAY_1_15, cls.DAY_16_45, cls.MONTHLY, cls.QUIZ_MONTHLY, cls.URGENT_FOLLOWUP]

    @classmethod
    def treatment_flows(cls) -> List[str]:
        """Get treatment-related flow types."""
        return [cls.DAY_1_15, cls.DAY_16_45]

    @classmethod
    def assessment_flows(cls) -> List[str]:
        """Get assessment-related flow types."""
        return [cls.MONTHLY, cls.QUIZ_MONTHLY]