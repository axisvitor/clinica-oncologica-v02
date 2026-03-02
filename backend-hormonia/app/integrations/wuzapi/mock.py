from __future__ import annotations

from typing import Any
from uuid import uuid4


class MockWuzAPIClient:
    """Drop-in mock for WuzAPIClient controlled by env-based factory."""

    def __init__(self, **kwargs: Any) -> None:
        _ = kwargs
        self.sent_messages: list[dict[str, Any]] = []
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def __aenter__(self) -> "MockWuzAPIClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        _ = exc_type, exc_value, traceback
        await self.disconnect()

    def _make_response(self) -> dict[str, Any]:
        msg_id = f"mock_{uuid4().hex[:16]}"
        return {"code": 200, "data": {"Id": msg_id, "Details": "Sent"}, "success": True}

    async def send_text(self, phone: str, message: str) -> dict[str, Any]:
        self.sent_messages.append({"type": "text", "phone": phone, "body": message})
        return self._make_response()

    async def send_media(
        self,
        media_type: str,
        phone: str,
        data_uri: str,
        caption: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        self.sent_messages.append(
            {
                "type": media_type,
                "phone": phone,
                "data_uri": data_uri,
                "caption": caption,
                "filename": filename,
            }
        )
        return self._make_response()

    async def session_connect(
        self,
        subscribe: list[str] | None = None,
        immediate: bool = False,
    ) -> dict[str, Any]:
        """Mock session connect."""
        _ = subscribe, immediate
        self.connected = True
        return {
            "code": 200,
            "data": {"details": "Connected (mock)", "jid": "mock@s.whatsapp.net"},
            "success": True,
        }

    async def get_session_status(self) -> dict[str, Any]:
        """Mock session status."""
        return {
            "code": 200,
            "data": {"Connected": self.connected, "LoggedIn": self.connected},
            "success": True,
        }

    async def get_qr(self) -> dict[str, Any]:
        """Mock QR code."""
        return {
            "code": 200,
            "data": "data:image/png;base64,mockQRbase64data==",
            "success": True,
        }
