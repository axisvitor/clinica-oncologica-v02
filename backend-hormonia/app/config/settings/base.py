"""
Base configuration module with shared imports and base settings.
All configuration modules inherit from this base.
"""

from typing import Any
import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .parsing import strip_wrapping_quotes


class BaseAppSettings(BaseSettings):
    """Base settings class with common configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )

    # Base directory for relative paths
    BASE_DIR: str = Field(
        default_factory=lambda: os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ),
        description="Base directory of the application (backend-hormonia parent)",
    )

    # Environment - Direct ENV names (no validation_alias)
    APP_ENVIRONMENT: str = Field(default="development", description="Environment name")
    APP_ENABLE_DEBUG: bool = Field(default=True, description="Debug mode")

    # API Versioning (System is 100% V2)
    API_V2_STR: str = Field(
        default="/api/v2",
        description="API v2 prefix (system is 100% V2, V1 has been deprecated)",
    )

    # Admin Dashboard
    APP_ADMIN_DASHBOARD_URL: str = Field(
        default="http://localhost:5173/admin",
        description="Admin dashboard base URL for links in notifications",
    )

    # AI Simulation Control
    ALLOW_AI_SIMULATION: bool = Field(
        default=True,
        description="Allow AI simulation mode (mock data). Should be False in production.",
    )

    @model_validator(mode="after")
    def validate_debug_flag(self) -> "BaseAppSettings":
        """Block startup with APP_ENABLE_DEBUG=True in production/staging.

        Mirrors the validate_secret_key pattern in SecuritySettings.
        Ensures debug routes and authentication bypasses cannot be active
        in production or staging environments.
        """
        import logging

        logger = logging.getLogger(__name__)
        env = self.APP_ENVIRONMENT.lower()
        if self.APP_ENABLE_DEBUG and env in ("production", "prod", "staging"):
            raise ValueError(
                f"APP_ENABLE_DEBUG=True is not allowed in '{env}' environment.\n"
                "Set APP_ENABLE_DEBUG=False in your deployment configuration.\n"
                "This prevents debug routes and authentication bypasses in production."
            )
        if self.APP_ENABLE_DEBUG and env not in ("development", "dev", "test", "testing"):
            logger.warning(
                "APP_ENABLE_DEBUG=True in environment '%s'. "
                "This is only safe in development/test environments.",
                env,
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def parse_boolean_fields(cls, data: Any) -> Any:
        """Parse boolean fields from string environment variables."""
        if isinstance(data, dict):
            for k, v in list(data.items()):
                if isinstance(v, str):
                    data[k] = strip_wrapping_quotes(v)

        boolean_fields = ["APP_ENABLE_DEBUG", "ALLOW_AI_SIMULATION"]

        for field in boolean_fields:
            if field in data:
                v = data[field]
                if isinstance(v, bool):
                    data[field] = v
                elif isinstance(v, str):
                    data[field] = v.lower() not in ("false", "0", "no", "off", "")
                else:
                    data[field] = bool(v)

        return data
