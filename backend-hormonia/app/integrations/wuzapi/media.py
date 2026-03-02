from __future__ import annotations

import base64

import aiohttp

from app.integrations.wuzapi.errors import MediaTooLargeError


MAX_MEDIA_BYTES = 16 * 1024 * 1024


async def fetch_and_encode_media(url: str, timeout: int = 30) -> str:
    """Download URL content and encode it as a base64 data URI."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "application/octet-stream")
            mime_type = content_type.split(";", 1)[0].strip()

            chunks: list[bytes] = []
            total = 0

            async for chunk in response.content.iter_chunked(64 * 1024):
                total += len(chunk)
                if total > MAX_MEDIA_BYTES:
                    raise MediaTooLargeError(
                        f"Media at {url!r} exceeds 16 MB limit ({total} bytes so far)",
                        status=None,
                        response=None,
                    )
                chunks.append(chunk)

            data = b"".join(chunks)
            encoded = base64.b64encode(data).decode("ascii")
            return f"data:{mime_type};base64,{encoded}"
