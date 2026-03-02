from __future__ import annotations

from pydantic import BaseModel


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
