from __future__ import annotations

import base64
from urllib.parse import urljoin

import aiohttp

from app.integrations.wuzapi.errors import MediaTooLargeError, UnsafeMediaUrlError
from app.integrations.wuzapi.ssrf_guard import validate_media_url


MAX_MEDIA_BYTES = 16 * 1024 * 1024
MAX_MEDIA_REDIRECTS = 3


async def fetch_and_encode_media(url: str, timeout: int = 30) -> str:
    """Download URL content and encode it as a base64 data URI."""
    current_url = await validate_media_url(url)
    request_timeout = aiohttp.ClientTimeout(total=timeout)
    redirects_followed = 0

    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(current_url, timeout=request_timeout, allow_redirects=False) as response:
                if _is_redirect_response(response):
                    if redirects_followed >= MAX_MEDIA_REDIRECTS:
                        raise UnsafeMediaUrlError()

                    location = response.headers.get("Location")
                    if location is None or not location.strip():
                        raise UnsafeMediaUrlError()

                    redirect_url = urljoin(current_url, location)
                    current_url = await validate_media_url(redirect_url)
                    redirects_followed += 1
                    continue

                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "application/octet-stream")
                mime_type = content_type.split(";", 1)[0].strip()

                chunks: list[bytes] = []
                total = 0

                async for chunk in response.content.iter_chunked(64 * 1024):
                    total += len(chunk)
                    if total > MAX_MEDIA_BYTES:
                        raise MediaTooLargeError(
                            f"Media exceeds 16 MB limit ({total} bytes read)",
                            status=None,
                            response=None,
                        )
                    chunks.append(chunk)

                data = b"".join(chunks)
                encoded = base64.b64encode(data).decode("ascii")
                return f"data:{mime_type};base64,{encoded}"


def _is_redirect_response(response: aiohttp.ClientResponse) -> bool:
    return 300 <= response.status < 400
