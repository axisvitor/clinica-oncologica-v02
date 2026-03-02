from __future__ import annotations

from pydantic import BaseModel


MEDIA_FIELD_MAP = {
    "image": "Image",
    "audio": "Audio",
    "video": "Video",
    "document": "Document",
}
MEDIA_ENDPOINT_MAP = {media_type: f"/chat/send/{media_type}" for media_type in MEDIA_FIELD_MAP}


class WuzAPISendData(BaseModel):
    Id: str
    Details: str
    Timestamp: str | None = None


class WuzAPISendResponse(BaseModel):
    code: int
    data: WuzAPISendData
    success: bool


class WuzAPITextRequest(BaseModel):
    Phone: str
    Body: str


class WuzAPIMediaRequest(BaseModel):
    Phone: str


class WuzAPIMessageInfo(BaseModel):
    """Info block from WuzAPI webhook event (whatsmeow MessageInfo)."""

    ID: str = ""
    Sender: str = ""
    Chat: str = ""
    Timestamp: str | None = None
    PushName: str | None = None
    IsFromMe: bool = False


class WuzAPIWebhookEvent(BaseModel):
    """Top-level WuzAPI webhook envelope."""

    type: str = "unknown"
    token: str | None = None
    event: dict | None = None

    model_config = {"extra": "allow"}
