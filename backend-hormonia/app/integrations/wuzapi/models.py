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
