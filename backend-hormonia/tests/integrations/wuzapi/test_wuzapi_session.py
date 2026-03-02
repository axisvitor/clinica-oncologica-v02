"""Tests for WuzAPI session methods and monitoring endpoints (Phase 35)."""

from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

from app.api.v2.monitoring.wuzapi import router
from app.integrations.wuzapi.mock import MockWuzAPIClient


@pytest.fixture
def mock_client():
    return MockWuzAPIClient()


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/monitoring/wuzapi")
    return app


class TestMockWuzAPIClientSession:
    """Test MockWuzAPIClient session methods."""

    @pytest.mark.asyncio
    async def test_session_connect(self, mock_client):
        result = await mock_client.session_connect(subscribe=["Message"])
        assert result["success"] is True
        assert result["data"]["details"] == "Connected (mock)"
        assert mock_client.connected is True

    @pytest.mark.asyncio
    async def test_get_session_status_disconnected(self, mock_client):
        result = await mock_client.get_session_status()
        assert result["data"]["Connected"] is False

    @pytest.mark.asyncio
    async def test_get_session_status_connected(self, mock_client):
        await mock_client.connect()
        result = await mock_client.get_session_status()
        assert result["data"]["Connected"] is True
        assert result["data"]["LoggedIn"] is True

    @pytest.mark.asyncio
    async def test_get_qr(self, mock_client):
        result = await mock_client.get_qr()
        assert result["success"] is True
        assert result["data"].startswith("data:image/png;base64,")


class TestWuzAPIMonitoringEndpoints:
    """Test monitoring router endpoints via ASGI test client."""

    @pytest.mark.asyncio
    async def test_session_status_with_mock(self, app):
        with (
            patch("app.api.v2.monitoring.wuzapi.settings") as mock_settings,
            patch("app.api.v2.monitoring.wuzapi.get_wuzapi_client") as mock_factory,
        ):
            mock_settings.WHATSAPP_WUZAPI_TOKEN = "test-token"
            mock_settings.WHATSAPP_WUZAPI_BASE_URL = "http://localhost:8080"
            mock_settings.WHATSAPP_WUZAPI_USE_MOCK = True

            client_instance = MockWuzAPIClient()
            await client_instance.connect()
            mock_factory.return_value = client_instance

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/monitoring/wuzapi/session/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True
            assert data["logged_in"] is True
            assert data.get("mock") is True

    @pytest.mark.asyncio
    async def test_session_status_no_token(self, app):
        with patch("app.api.v2.monitoring.wuzapi.settings") as mock_settings:
            mock_settings.WHATSAPP_WUZAPI_TOKEN = None
            mock_settings.WHATSAPP_WUZAPI_BASE_URL = ""
            mock_settings.WHATSAPP_WUZAPI_USE_MOCK = False

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/monitoring/wuzapi/session/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            assert "error" in data

    @pytest.mark.asyncio
    async def test_qr_with_mock(self, app):
        with (
            patch("app.api.v2.monitoring.wuzapi.settings") as mock_settings,
            patch("app.api.v2.monitoring.wuzapi.get_wuzapi_client") as mock_factory,
        ):
            mock_settings.WHATSAPP_WUZAPI_TOKEN = "test-token"
            mock_settings.WHATSAPP_WUZAPI_BASE_URL = "http://localhost:8080"
            mock_settings.WHATSAPP_WUZAPI_USE_MOCK = True

            mock_factory.return_value = MockWuzAPIClient()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/monitoring/wuzapi/session/qr")
            assert resp.status_code == 200
            data = resp.json()
            assert data["qr"] is not None
            assert data["qr"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_qr_no_token(self, app):
        with patch("app.api.v2.monitoring.wuzapi.settings") as mock_settings:
            mock_settings.WHATSAPP_WUZAPI_TOKEN = None
            mock_settings.WHATSAPP_WUZAPI_BASE_URL = ""
            mock_settings.WHATSAPP_WUZAPI_USE_MOCK = False

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/monitoring/wuzapi/session/qr")
            assert resp.status_code == 200
            data = resp.json()
            assert data["qr"] is None
            assert "error" in data
