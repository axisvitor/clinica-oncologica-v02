"""PII redaction coverage for websocket event payloads."""

from __future__ import annotations

import importlib
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.websocket import WebSocketEventType
from app.services.websocket_events import WebSocketEventService

websocket_events_module = importlib.import_module("app.services.websocket_events")


@pytest.mark.asyncio
async def test_broadcast_message_event_redacts_sensitive_content(monkeypatch):
    fake_manager = MagicMock()
    fake_manager.broadcast_to_patient_room = AsyncMock(return_value=1)
    monkeypatch.setattr(websocket_events_module, "connection_manager", fake_manager)

    service = WebSocketEventService(redis=MagicMock())
    patient_id = uuid4()
    message_id = uuid4()

    sent_count = await service.broadcast_message_event(
        WebSocketEventType.MESSAGE_SENT,
        {
            "message_id": message_id,
            "patient_id": patient_id,
            "direction": "outbound",
            "type": "text",
            "content": (
                "CPF 12345678901 email maria@clinic.com phone +5511999998888 "
                "Authorization: Bearer token-abc-123"
            ),
            "metadata": {
                "api_key": "sk_test_123",
                "token": "plain-token",
                "email": "secret.user@clinic.com",
                "phone": "551188887777",
            },
        },
    )

    assert sent_count == 1
    assert fake_manager.broadcast_to_patient_room.await_count == 1

    room_id, payload = fake_manager.broadcast_to_patient_room.await_args.args
    assert room_id == str(patient_id)

    content = payload["data"]["content"]
    metadata = payload["data"]["metadata"]

    assert "12345678901" not in content
    assert "maria@clinic.com" not in content
    assert "+5511999998888" not in content
    assert "token-abc-123" not in content
    assert "[REDACTED_TOKEN]" in content or "[REDACTED_SECRET]" in content

    assert metadata["api_key"] == "[REDACTED_SECRET]"
    assert metadata["token"] == "[REDACTED_SECRET]"
    assert metadata["email"] == "se***@clinic.com"
    assert metadata["phone"] == "+55***7777"


@pytest.mark.asyncio
async def test_broadcast_to_all_authenticated_redacts_nested_payload(monkeypatch):
    fake_manager = MagicMock()
    fake_manager.broadcast_to_all_authenticated = AsyncMock(return_value=2)
    monkeypatch.setattr(websocket_events_module, "connection_manager", fake_manager)

    service = WebSocketEventService(redis=MagicMock())
    sent_count = await service.broadcast_to_all_authenticated(
        {
            "type": "custom",
            "data": {
                "contacts": [
                    {"email": "ana@example.com"},
                    {"phone": "11988776655"},
                ],
                "metadata": {"client_secret": "secret-value"},
            },
        }
    )

    assert sent_count == 2
    (payload,) = fake_manager.broadcast_to_all_authenticated.await_args.args
    assert payload["data"]["contacts"][0]["email"] == "an***@example.com"
    assert payload["data"]["contacts"][1]["phone"] == "***6655"
    assert payload["data"]["metadata"]["client_secret"] == "[REDACTED_SECRET]"
