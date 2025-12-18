"""
Response compression utilities for performance optimization.
"""

import gzip
import zlib
from typing import List, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.logging import get_logger

logger = get_logger(__name__)


class EnhancedCompressionMiddleware(BaseHTTPMiddleware):
    """Enhanced compression middleware with configurable compression levels and content type filtering."""

    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compression_level: int = 6,
        compressible_types: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level

        # Default compressible content types
        if compressible_types is None:
            self.compressible_types = {
                "application/json",
                "application/javascript",
                "application/xml",
                "text/html",
                "text/css",
                "text/javascript",
                "text/plain",
                "text/xml",
                "text/csv",
                "image/svg+xml",
            }
        else:
            self.compressible_types = set(compressible_types)

    async def dispatch(self, request: Request, call_next):
        """Process request and compress response if appropriate."""
        response = await call_next(request)

        # Check if client accepts compression
        accept_encoding = request.headers.get("accept-encoding", "")

        # Skip compression for certain conditions
        if not self._should_compress(request, response, accept_encoding):
            return response

        # Get response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        # Check minimum size
        if len(response_body) < self.minimum_size:
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Compress based on client preference
        compressed_body, encoding = self._compress_body(response_body, accept_encoding)

        if compressed_body and encoding:
            # Calculate compression ratio
            original_size = len(response_body)
            compressed_size = len(compressed_body)
            compression_ratio = (1 - compressed_size / original_size) * 100

            logger.debug(
                f"Response compressed: {original_size} -> {compressed_size} bytes ({compression_ratio:.1f}% reduction)",
                extra={
                    "event_type": "response_compressed",
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": compression_ratio,
                    "encoding": encoding,
                },
            )

            # Create compressed response
            headers = dict(response.headers)
            headers["content-encoding"] = encoding
            headers["content-length"] = str(len(compressed_body))
            headers["vary"] = "Accept-Encoding"

            return Response(
                content=compressed_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        # Return original response if compression failed
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def _should_compress(
        self, request: Request, response: Response, accept_encoding: str
    ) -> bool:
        """Determine if response should be compressed."""
        # Skip if client doesn't accept compression
        if not any(
            encoding in accept_encoding.lower() for encoding in ["gzip", "deflate"]
        ):
            return False

        # Skip if already compressed
        if response.headers.get("content-encoding"):
            return False

        # Skip for certain status codes
        if response.status_code < 200 or response.status_code >= 300:
            return False

        # Check content type
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if content_type not in self.compressible_types:
            return False

        # Skip for certain endpoints (e.g., file downloads)
        if any(
            path in request.url.path for path in ["/download", "/export", "/stream"]
        ):
            return False

        return True

    def _compress_body(
        self, body: bytes, accept_encoding: str
    ) -> tuple[Optional[bytes], Optional[str]]:
        """Compress response body using the best available method."""
        accept_encoding_lower = accept_encoding.lower()

        try:
            # Prefer gzip if available
            if "gzip" in accept_encoding_lower:
                compressed = gzip.compress(body, compresslevel=self.compression_level)
                return compressed, "gzip"

            # Fall back to deflate
            elif "deflate" in accept_encoding_lower:
                compressed = zlib.compress(body, level=self.compression_level)
                return compressed, "deflate"

        except Exception as e:
            logger.error(f"Compression failed: {e}")

        return None, None


class StaticFileCompressionMiddleware(BaseHTTPMiddleware):
    """Middleware for pre-compressing static files."""

    def __init__(self, app: ASGIApp, static_paths: List[str] = None):
        super().__init__(app)
        self.static_paths = static_paths or ["/static", "/assets", "/public"]

    async def dispatch(self, request: Request, call_next):
        """Check for pre-compressed static files."""
        # Check if this is a static file request
        if not any(request.url.path.startswith(path) for path in self.static_paths):
            return await call_next(request)

        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)

        # Try to serve pre-compressed version
        original_path = request.url.path
        gzip_path = original_path + ".gz"

        # Modify request path to look for .gz version
        request.scope["path"] = gzip_path

        try:
            response = await call_next(request)

            # If .gz file exists, add appropriate headers
            if response.status_code == 200:
                headers = dict(response.headers)
                headers["content-encoding"] = "gzip"
                headers["vary"] = "Accept-Encoding"

                return Response(
                    content=await response.body(),
                    status_code=response.status_code,
                    headers=headers,
                    media_type=response.media_type,
                )

        except Exception as e:
            logger.warning(f"Brotli compression fallback failed: {e}", exc_info=True)

        # Fall back to original file
        request.scope["path"] = original_path
        return await call_next(request)


def get_compression_stats(responses: List[dict]) -> dict:
    """Calculate compression statistics from response data."""
    if not responses:
        return {
            "total_responses": 0,
            "compressed_responses": 0,
            "compression_ratio": 0,
            "bytes_saved": 0,
        }

    total_responses = len(responses)
    compressed_responses = sum(1 for r in responses if r.get("compressed", False))

    total_original_size = sum(r.get("original_size", 0) for r in responses)
    total_compressed_size = sum(
        r.get("compressed_size", r.get("original_size", 0)) for r in responses
    )

    bytes_saved = total_original_size - total_compressed_size
    compression_ratio = (
        (bytes_saved / total_original_size * 100) if total_original_size > 0 else 0
    )

    return {
        "total_responses": total_responses,
        "compressed_responses": compressed_responses,
        "compression_percentage": round(
            (compressed_responses / total_responses) * 100, 2
        ),
        "compression_ratio": round(compression_ratio, 2),
        "bytes_saved": bytes_saved,
        "total_original_size": total_original_size,
        "total_compressed_size": total_compressed_size,
    }


def should_precompress_file(file_path: str, file_size: int) -> bool:
    """Determine if a static file should be pre-compressed."""
    # File size threshold (compress files larger than 1KB)
    if file_size < 1024:
        return False

    # File extension whitelist
    compressible_extensions = {
        ".js",
        ".css",
        ".html",
        ".htm",
        ".xml",
        ".json",
        ".svg",
        ".txt",
        ".csv",
        ".md",
        ".yaml",
        ".yml",
    }

    file_extension = file_path.lower().split(".")[-1] if "." in file_path else ""
    return f".{file_extension}" in compressible_extensions


def precompress_static_files(static_dir: str, compression_level: int = 6) -> dict:
    """Pre-compress static files for faster serving."""
    import os
    import gzip

    stats = {
        "files_processed": 0,
        "files_compressed": 0,
        "bytes_saved": 0,
        "errors": [],
    }

    if not os.path.exists(static_dir):
        stats["errors"].append(f"Static directory not found: {static_dir}")
        return stats

    for root, dirs, files in os.walk(static_dir):
        for file in files:
            file_path = os.path.join(root, file)

            # Skip already compressed files
            if file.endswith(".gz"):
                continue

            try:
                file_size = os.path.getsize(file_path)
                stats["files_processed"] += 1

                if should_precompress_file(file, file_size):
                    # Compress file
                    with open(file_path, "rb") as f_in:
                        with gzip.open(
                            file_path + ".gz", "wb", compresslevel=compression_level
                        ) as f_out:
                            f_out.writelines(f_in)

                    compressed_size = os.path.getsize(file_path + ".gz")
                    bytes_saved = file_size - compressed_size

                    stats["files_compressed"] += 1
                    stats["bytes_saved"] += bytes_saved

                    logger.info(
                        f"Pre-compressed {file}: {file_size} -> {compressed_size} bytes",
                        extra={
                            "event_type": "file_precompressed",
                            "file": file,
                            "original_size": file_size,
                            "compressed_size": compressed_size,
                            "bytes_saved": bytes_saved,
                        },
                    )

            except Exception as e:
                stats["errors"].append(f"Error compressing {file_path}: {str(e)}")
                logger.error(f"Error pre-compressing {file_path}: {e}")

    return stats
