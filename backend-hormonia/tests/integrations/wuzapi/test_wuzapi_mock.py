import os
from unittest.mock import patch

import pytest

from app.integrations.wuzapi import WuzAPIClient, get_wuzapi_client
from app.integrations.wuzapi.mock import MockWuzAPIClient


@pytest.mark.asyncio
async def test_mock_send_text_returns_id():
    client = MockWuzAPIClient()

    response = await client.send_text("5511999999999", "hello")

    assert response["data"]["Id"]


@pytest.mark.asyncio
async def test_mock_send_text_stores_message():
    client = MockWuzAPIClient()

    await client.send_text("5511999999999", "hello")

    assert client.sent_messages[0]["phone"] == "5511999999999"
    assert client.sent_messages[0]["body"] == "hello"


@pytest.mark.asyncio
async def test_mock_send_media_returns_id():
    client = MockWuzAPIClient()

    response = await client.send_media(
        media_type="image",
        phone="5511999999999",
        data_uri="data:image/png;base64,AAAA",
    )

    assert response["data"]["Id"]


@pytest.mark.asyncio
async def test_mock_send_media_stores_message():
    client = MockWuzAPIClient()

    await client.send_media(
        media_type="image",
        phone="5511999999999",
        data_uri="data:image/png;base64,AAAA",
    )

    assert client.sent_messages[0]["type"] == "image"
    assert client.sent_messages[0]["phone"] == "5511999999999"


@pytest.mark.asyncio
async def test_mock_connect_disconnect_noop():
    client = MockWuzAPIClient()

    await client.connect()
    await client.disconnect()


@pytest.mark.asyncio
async def test_mock_context_manager():
    async with MockWuzAPIClient() as client:
        assert client.connected is True


def test_factory_returns_mock_when_env_true():
    with patch.dict(os.environ, {"WHATSAPP_WUZAPI_USE_MOCK": "true"}, clear=False):
        client = get_wuzapi_client()

    assert isinstance(client, MockWuzAPIClient)


def test_factory_returns_real_when_env_false():
    with patch.dict(os.environ, {}, clear=True):
        client = get_wuzapi_client(base_url="http://wuzapi.test", token="token-123")

    assert isinstance(client, WuzAPIClient)


@pytest.mark.asyncio
async def test_mock_response_structure():
    client = MockWuzAPIClient()

    response = await client.send_text("5511999999999", "hello")

    assert response["code"] == 200
    assert response["success"] is True
    assert response["data"]["Id"]
    assert response["data"]["Details"] == "Sent"


def test_circuit_breaker_name_is_wuzapi():
    client = WuzAPIClient(base_url="http://wuzapi.test", token="token-123")
    assert client._circuit_breaker.name == "wuzapi"
