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

    # Environment
    ENVIRONMENT: str = Field(default="development", description="Environment name")
    DEBUG: bool = Field(default=True, description="Debug mode")

    @model_validator(mode="before")
    @classmethod
    def parse_boolean_fields(cls, data: Any) -> Any:
        """Parse boolean fields from string environment variables."""
        boolean_fields = ["DEBUG"]

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
