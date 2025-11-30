"""
Base configuration module with shared imports and base settings.
All configuration modules inherit from this base.
"""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, ClassVar, Any
import os
import json


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
    APP_ENVIRONMENT: str = Field(
        default="development",
        description="Environment name"
    )
    APP_ENABLE_DEBUG: bool = Field(
        default=True,
        description="Debug mode"
    )

    # API Versioning (System is 100% V2)
    API_V2_STR: str = Field(
        default="/api/v2",
        description="API v2 prefix (system is 100% V2, V1 has been deprecated)"
    )

    # Admin Dashboard
    APP_ADMIN_DASHBOARD_URL: str = Field(
        default="http://localhost:5173/admin",
        description="Admin dashboard base URL for links in notifications"
    )

    @model_validator(mode="before")
    @classmethod
    def parse_boolean_fields(cls, data: Any) -> Any:
        """Parse boolean fields from string environment variables."""
        boolean_fields = ["APP_ENABLE_DEBUG"]

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
