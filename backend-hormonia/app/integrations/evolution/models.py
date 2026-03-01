"""
Evolution API data models and enums.
Defines message types, status enums, and webhook event structures.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

from app.exceptions import ExternalServiceError
from app.utils.timezone import now_sao_paulo_naive


class MessageType(str, Enum):
    """Supported message types for Evolution API."""

    TEXT = "text"
    BUTTON = "button"
    LIST = "list"
    MEDIA = "media"
    LOCATION = "location"


class TextMessage(BaseModel):
    """Text message payload."""

    text: str = Field(..., description="Message text content")


class ButtonMessage(BaseModel):
    """Button message payload."""

    text: str = Field(..., description="Message text")
    buttons: List[Dict[str, str]] = Field(..., description="Button definitions")


class ListMessage(BaseModel):
    """List message payload."""

    text: str = Field(..., description="Message text")
    title: str = Field(..., description="List title")
    sections: List[Dict[str, Any]] = Field(..., description="List sections")


class MediaMessage(BaseModel):
    """Media message payload."""

    media_url: str = Field(..., description="Media file URL")
    caption: Optional[str] = Field(None, description="Media caption")
    media_type: str = Field(
        ..., description="Media type (image, video, audio, document)"
    )


class WebhookEvent(BaseModel):
    """Webhook event from Evolution API."""

    event: str = Field(..., description="Event type")
    instance: str = Field(..., description="Instance name")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: datetime = Field(default_factory=now_sao_paulo_naive)


class EvolutionAPIError(ExternalServiceError):
    """Evolution API specific error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict] = None,
    ):
        super().__init__(f"Evolution API Error: {message}")
        self.status_code = status_code
        self.response_data = response_data
