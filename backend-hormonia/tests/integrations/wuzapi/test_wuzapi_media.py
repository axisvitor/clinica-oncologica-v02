import base64
from unittest.mock import AsyncMock

import pytest

from app.integrations.wuzapi.client import WuzAPIClient
from app.integrations.wuzapi.errors import MediaTooLargeError
from app.integrations.wuzapi.media import fetch_and_encode_media


class MockStream:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.completed = False

    async def iter_chunked(self, _chunk_size: int):
        for chunk in self._chunks:
            yield chunk
        self.completed = True


class MockResponse:
    def __init__(self, chunks: list[bytes], content_type: str | None = None) -> None:
        self.headers = {}
        if content_type is not None:
            self.headers["Content-Type"] = content_type
        self.content = MockStream(chunks)

    def raise_for_status(self) -> None:
        return None


class MockResponseContext:
    def __init__(self, response: MockResponse) -> None:
        self._response = response

    async def __aenter__(self) -> MockResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        _ = exc_type, exc, tb
        return False


class MockSession:
    def __init__(self, response: MockResponse) -> None:
        self._response = response

    async def __aenter__(self) -> "MockSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        _ = exc_type, exc, tb
        return False

    def get(self, _url: str, timeout=None):
        _ = timeout
        return MockResponseContext(self._response)


def make_client() -> WuzAPIClient:
    return WuzAPIClient(base_url="http://wuzapi.test", token="token-123")


@pytest.mark.asyncio
async def test_fetch_and_encode_small_image(monkeypatch):
    raw = b"a" * 1024
    response = MockResponse([raw], content_type="image/jpeg")
    monkeypatch.setattr("app.integrations.wuzapi.media.aiohttp.ClientSession", lambda: MockSession(response))

    result = await fetch_and_encode_media("https://example.com/file.jpg")

    assert result.startswith("data:image/jpeg;base64,")
    encoded = result.split(",", 1)[1]
    assert base64.b64decode(encoded) == raw


@pytest.mark.asyncio
async def test_fetch_and_encode_uses_content_type(monkeypatch):
    response = MockResponse([b"abc"], content_type="image/png; charset=utf-8")
    monkeypatch.setattr("app.integrations.wuzapi.media.aiohttp.ClientSession", lambda: MockSession(response))

    result = await fetch_and_encode_media("https://example.com/file.png")

    assert result.startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_fetch_and_encode_rejects_oversized(monkeypatch):
    chunks = [b"a" * (16 * 1024 * 1024), b"b", b"c" * 1024]
    response = MockResponse(chunks, content_type="application/pdf")
    monkeypatch.setattr("app.integrations.wuzapi.media.aiohttp.ClientSession", lambda: MockSession(response))

    with pytest.raises(MediaTooLargeError):
        await fetch_and_encode_media("https://example.com/huge.pdf")

    assert response.content.completed is False


@pytest.mark.asyncio
async def test_fetch_and_encode_default_mime(monkeypatch):
    response = MockResponse([b"payload"])
    monkeypatch.setattr("app.integrations.wuzapi.media.aiohttp.ClientSession", lambda: MockSession(response))

    result = await fetch_and_encode_media("https://example.com/blob")

    assert result.startswith("data:application/octet-stream;base64,")


@pytest.mark.asyncio
async def test_send_media_image():
    client = make_client()
    client._make_request = AsyncMock(return_value={"data": {"Id": "img-1"}, "success": True})

    await client.send_media("image", "5511987654321", "data:image/png;base64,AAAA", caption="Test")

    client._make_request.assert_awaited_once_with(
        "POST",
        "/chat/send/image",
        data={"Phone": "5511987654321", "Image": "data:image/png;base64,AAAA", "Caption": "Test"},
    )


@pytest.mark.asyncio
async def test_send_media_audio():
    client = make_client()
    client._make_request = AsyncMock(return_value={"data": {"Id": "aud-1"}, "success": True})

    await client.send_media("audio", "5511987654321", "data:audio/ogg;base64,BBBB")

    client._make_request.assert_awaited_once_with(
        "POST",
        "/chat/send/audio",
        data={"Phone": "5511987654321", "Audio": "data:audio/ogg;base64,BBBB"},
    )


@pytest.mark.asyncio
async def test_send_media_video_with_caption():
    client = make_client()
    client._make_request = AsyncMock(return_value={"data": {"Id": "vid-1"}, "success": True})

    await client.send_media("video", "5511987654321", "data:video/mp4;base64,CCCC", caption="Vid")

    client._make_request.assert_awaited_once_with(
        "POST",
        "/chat/send/video",
        data={"Phone": "5511987654321", "Video": "data:video/mp4;base64,CCCC", "Caption": "Vid"},
    )


@pytest.mark.asyncio
async def test_send_media_document_with_filename():
    client = make_client()
    client._make_request = AsyncMock(return_value={"data": {"Id": "doc-1"}, "success": True})

    await client.send_media(
        "document",
        "5511987654321",
        "data:application/pdf;base64,DDDD",
        filename="report.pdf",
    )

    client._make_request.assert_awaited_once_with(
        "POST",
        "/chat/send/document",
        data={
            "Phone": "5511987654321",
            "Document": "data:application/pdf;base64,DDDD",
            "FileName": "report.pdf",
        },
    )


@pytest.mark.asyncio
async def test_send_media_invalid_type():
    client = make_client()

    with pytest.raises(ValueError):
        await client.send_media("gif", "5511987654321", "data:image/gif;base64,EEEE")


@pytest.mark.asyncio
async def test_send_media_caption_ignored_for_audio():
    client = make_client()
    client._make_request = AsyncMock(return_value={"data": {"Id": "aud-2"}, "success": True})

    await client.send_media("audio", "5511987654321", "data:audio/ogg;base64,FFFF", caption="X")

    client._make_request.assert_awaited_once_with(
        "POST",
        "/chat/send/audio",
        data={"Phone": "5511987654321", "Audio": "data:audio/ogg;base64,FFFF"},
    )
