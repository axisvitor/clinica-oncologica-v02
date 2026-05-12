from __future__ import annotations

import base64
from collections.abc import Sequence
from unittest.mock import AsyncMock

import pytest

from app.integrations.wuzapi.client import WuzAPIClient
from app.integrations.wuzapi.errors import MediaTooLargeError, UnsafeMediaUrlError
from app.integrations.wuzapi.media import fetch_and_encode_media

PUBLIC_IPV4 = "93.184.216.34"


class MockStream:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.completed = False

    async def iter_chunked(self, _chunk_size: int):
        for chunk in self._chunks:
            yield chunk
        self.completed = True


class MockResponse:
    def __init__(
        self,
        chunks: list[bytes] | None = None,
        content_type: str | None = None,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.headers = dict(headers or {})
        if content_type is not None:
            self.headers["Content-Type"] = content_type
        self.content = MockStream(chunks or [])

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
    def __init__(self, responses: MockResponse | Sequence[MockResponse]) -> None:
        if isinstance(responses, MockResponse):
            self._responses = [responses]
        else:
            self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def __aenter__(self) -> "MockSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        _ = exc_type, exc, tb
        return False

    def get(self, url: str, timeout=None, allow_redirects=None):
        self.calls.append({"url": url, "timeout": timeout, "allow_redirects": allow_redirects})
        if not self._responses:
            raise AssertionError(f"unexpected GET for {url}")
        return MockResponseContext(self._responses.pop(0))


def make_client() -> WuzAPIClient:
    return WuzAPIClient(base_url="http://wuzapi.test", token="token-123")


def install_public_resolver(monkeypatch, mapping: dict[str, Sequence[str]] | None = None):
    calls: list[tuple[str, int]] = []

    async def resolver(host: str, port: int) -> Sequence[str]:
        calls.append((host, port))
        if mapping is not None and host in mapping:
            return list(mapping[host])
        return [PUBLIC_IPV4]

    monkeypatch.setattr("app.integrations.wuzapi.ssrf_guard.resolve_host", resolver)
    return calls


def install_session(monkeypatch, responses: MockResponse | Sequence[MockResponse]) -> MockSession:
    session = MockSession(responses)
    monkeypatch.setattr("app.integrations.wuzapi.media.aiohttp.ClientSession", lambda: session)
    return session


def assert_no_auto_redirects(session: MockSession) -> None:
    assert session.calls
    assert all(call["allow_redirects"] is False for call in session.calls)


@pytest.mark.asyncio
async def test_fetch_and_encode_small_image(monkeypatch):
    raw = b"a" * 1024
    response = MockResponse([raw], content_type="image/jpeg")
    install_public_resolver(monkeypatch)
    session = install_session(monkeypatch, response)

    result = await fetch_and_encode_media("https://example.com/file.jpg")

    assert result.startswith("data:image/jpeg;base64,")
    encoded = result.split(",", 1)[1]
    assert base64.b64decode(encoded) == raw
    assert [call["url"] for call in session.calls] == ["https://example.com/file.jpg"]
    assert_no_auto_redirects(session)


@pytest.mark.asyncio
async def test_fetch_and_encode_uses_content_type(monkeypatch):
    response = MockResponse([b"abc"], content_type="image/png; charset=utf-8")
    install_public_resolver(monkeypatch)
    session = install_session(monkeypatch, response)

    result = await fetch_and_encode_media("https://example.com/file.png")

    assert result.startswith("data:image/png;base64,")
    assert_no_auto_redirects(session)


@pytest.mark.asyncio
async def test_fetch_and_encode_follows_safe_relative_redirect_after_validation(monkeypatch):
    calls = install_public_resolver(monkeypatch)
    session = install_session(
        monkeypatch,
        [
            MockResponse(status=302, headers={"Location": "/cdn/file.png"}),
            MockResponse([b"abc"], content_type="image/png"),
        ],
    )

    result = await fetch_and_encode_media("https://example.com/file.png")

    assert result.startswith("data:image/png;base64,")
    assert [call["url"] for call in session.calls] == [
        "https://example.com/file.png",
        "https://example.com/cdn/file.png",
    ]
    assert calls == [("example.com", 443), ("example.com", 443)]
    assert_no_auto_redirects(session)


@pytest.mark.asyncio
async def test_fetch_and_encode_rejects_oversized(monkeypatch):
    chunks = [b"a" * (16 * 1024 * 1024), b"b", b"c" * 1024]
    response = MockResponse(chunks, content_type="application/pdf")
    install_public_resolver(monkeypatch)
    session = install_session(monkeypatch, response)

    with pytest.raises(MediaTooLargeError) as exc_info:
        await fetch_and_encode_media("https://example.com/huge.pdf?token=secret")

    assert "16 MB limit" in str(exc_info.value)
    assert "example.com" not in str(exc_info.value)
    assert "huge.pdf" not in str(exc_info.value)
    assert "token=secret" not in str(exc_info.value)
    assert response.content.completed is False
    assert_no_auto_redirects(session)


@pytest.mark.asyncio
async def test_fetch_and_encode_default_mime(monkeypatch):
    response = MockResponse([b"payload"])
    install_public_resolver(monkeypatch)
    session = install_session(monkeypatch, response)

    result = await fetch_and_encode_media("https://example.com/blob")

    assert result.startswith("data:application/octet-stream;base64,")
    assert_no_auto_redirects(session)


@pytest.mark.asyncio
async def test_fetch_and_encode_media_blocks_private_resolution_before_get(monkeypatch):
    calls = install_public_resolver(monkeypatch, {"attacker.test": ["127.0.0.1"]})
    session = install_session(monkeypatch, MockResponse([b"should-not-fetch"]))

    with pytest.raises(UnsafeMediaUrlError) as exc_info:
        await fetch_and_encode_media("https://attacker.test/file.jpg?token=secret")

    assert str(exc_info.value) == "Blocked media URL"
    assert "attacker.test" not in str(exc_info.value)
    assert "token=secret" not in str(exc_info.value)
    assert calls == [("attacker.test", 443)]
    assert session.calls == []


@pytest.mark.asyncio
async def test_fetch_and_encode_media_blocks_redirect_to_metadata(monkeypatch):
    install_public_resolver(monkeypatch)
    session = install_session(
        monkeypatch,
        [
            MockResponse(status=302, headers={"Location": "http://169.254.169.254/latest/meta-data"}),
            MockResponse([b"should-not-fetch"]),
        ],
    )

    with pytest.raises(UnsafeMediaUrlError) as exc_info:
        await fetch_and_encode_media("https://example.com/file.jpg?token=secret")

    assert str(exc_info.value) == "Blocked media URL"
    assert "169.254.169.254" not in str(exc_info.value)
    assert "latest/meta-data" not in str(exc_info.value)
    assert "token=secret" not in str(exc_info.value)
    assert [call["url"] for call in session.calls] == ["https://example.com/file.jpg?token=secret"]
    assert_no_auto_redirects(session)


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
