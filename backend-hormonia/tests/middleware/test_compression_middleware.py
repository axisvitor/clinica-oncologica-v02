"""
Integration tests for Compression Middleware.

Tests response compression functionality.
"""

import pytest
import gzip
import brotli
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders
import json


class CompressionMiddleware(BaseHTTPMiddleware):
    """Response compression middleware."""

    def __init__(
        self,
        app,
        minimum_size: int = 1000,
        gzip_level: int = 6,
        exclude_paths: list = None,
        exclude_mediatype: list = None
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.gzip_level = gzip_level
        self.exclude_paths = exclude_paths or []
        self.exclude_mediatype = exclude_mediatype or ["image/", "video/", "audio/"]

    async def dispatch(self, request, call_next):
        """Apply compression to responses."""
        # Check if path is excluded
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Get accepted encodings
        accept_encoding = request.headers.get("Accept-Encoding", "")

        # Process request
        response = await call_next(request)

        # Check if response should be compressed
        content_type = response.headers.get("Content-Type", "")
        if any(content_type.startswith(mt) for mt in self.exclude_mediatype):
            return response

        # Check content length
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) < self.minimum_size:
            return response

        # Try to compress
        if "br" in accept_encoding:
            return await self._compress_brotli(response)
        elif "gzip" in accept_encoding:
            return await self._compress_gzip(response)

        return response

    async def _compress_gzip(self, response):
        """Compress response with gzip."""
        # Read response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # Compress
        compressed = gzip.compress(body, compresslevel=self.gzip_level)

        # Create new response
        headers = MutableHeaders(response.headers)
        headers["Content-Encoding"] = "gzip"
        headers["Content-Length"] = str(len(compressed))
        headers.setdefault("Vary", "Accept-Encoding")

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=dict(headers),
            media_type=response.media_type
        )

    async def _compress_brotli(self, response):
        """Compress response with brotli."""
        # Read response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # Compress
        compressed = brotli.compress(body, quality=4)

        # Create new response
        headers = MutableHeaders(response.headers)
        headers["Content-Encoding"] = "br"
        headers["Content-Length"] = str(len(compressed))
        headers.setdefault("Vary", "Accept-Encoding")

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=dict(headers),
            media_type=response.media_type
        )


@pytest.fixture
def app_with_compression():
    """Create FastAPI app with compression middleware."""
    app = FastAPI()

    # Add compression middleware
    app.add_middleware(
        CompressionMiddleware,
        minimum_size=100,  # Lower threshold for testing
        gzip_level=6,
        exclude_paths=["/health", "/metrics"],
        exclude_mediatype=["image/", "video/"]
    )

    @app.get("/small")
    async def small_response():
        return {"status": "ok"}

    @app.get("/large")
    async def large_response():
        # Generate large response
        data = {
            f"field_{i}": f"value_{i}" * 10
            for i in range(100)
        }
        return data

    @app.get("/text")
    async def text_response():
        return Response(
            content="This is a text response " * 50,
            media_type="text/plain"
        )

    @app.get("/json")
    async def json_response():
        data = [{"id": i, "data": f"item_{i}" * 10} for i in range(50)]
        return data

    @app.get("/image")
    async def image_response():
        # Simulate image response
        return Response(
            content=b"\x89PNG\r\n" + b"fake image data" * 100,
            media_type="image/png"
        )

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


@pytest.fixture
def client(app_with_compression):
    """Create test client."""
    return TestClient(app_with_compression)


class TestCompressionMiddleware:
    """Test compression middleware functionality."""

    def test_gzip_compression(self, client):
        """Test gzip compression is applied."""
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )
        assert response.status_code == 200
        assert response.headers.get("Content-Encoding") == "gzip"
        assert "Vary" in response.headers

        # Decompress and verify content
        content = gzip.decompress(response.content)
        data = json.loads(content)
        assert "field_0" in data

    def test_brotli_compression(self, client):
        """Test brotli compression is applied."""
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "br"}
        )
        assert response.status_code == 200
        assert response.headers.get("Content-Encoding") == "br"

        # Decompress and verify content
        content = brotli.decompress(response.content)
        data = json.loads(content)
        assert "field_0" in data

    def test_no_compression_small_response(self, client):
        """Test small responses are not compressed."""
        response = client.get(
            "/small",
            headers={"Accept-Encoding": "gzip"}
        )
        assert response.status_code == 200
        assert "Content-Encoding" not in response.headers

    def test_no_compression_without_accept_encoding(self, client):
        """Test no compression without Accept-Encoding header."""
        response = client.get("/large")
        assert response.status_code == 200
        assert "Content-Encoding" not in response.headers

    def test_excluded_paths(self, client):
        """Test excluded paths are not compressed."""
        response = client.get(
            "/health",
            headers={"Accept-Encoding": "gzip"}
        )
        assert response.status_code == 200
        assert "Content-Encoding" not in response.headers

    def test_excluded_media_types(self, client):
        """Test excluded media types are not compressed."""
        response = client.get(
            "/image",
            headers={"Accept-Encoding": "gzip"}
        )
        assert response.status_code == 200
        assert "Content-Encoding" not in response.headers

    def test_text_response_compression(self, client):
        """Test text responses are compressed."""
        response = client.get(
            "/text",
            headers={"Accept-Encoding": "gzip"}
        )
        assert response.status_code == 200
        assert response.headers.get("Content-Encoding") == "gzip"

    def test_json_response_compression(self, client):
        """Test JSON responses are compressed."""
        response = client.get(
            "/json",
            headers={"Accept-Encoding": "gzip"}
        )
        assert response.status_code == 200
        assert response.headers.get("Content-Encoding") == "gzip"

        # Verify content integrity
        content = gzip.decompress(response.content)
        data = json.loads(content)
        assert len(data) == 50
        assert data[0]["id"] == 0

    def test_compression_preference(self, client):
        """Test brotli is preferred over gzip."""
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip, br"}
        )
        assert response.status_code == 200
        # Should prefer brotli
        assert response.headers.get("Content-Encoding") == "br"

    def test_vary_header(self, client):
        """Test Vary header is set correctly."""
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )
        assert response.status_code == 200
        assert response.headers.get("Vary") == "Accept-Encoding"

    def test_content_length_updated(self, client):
        """Test Content-Length is updated after compression."""
        # Get uncompressed size
        response_uncompressed = client.get("/large")
        uncompressed_size = len(response_uncompressed.content)

        # Get compressed size
        response_compressed = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )
        compressed_size = int(response_compressed.headers.get("Content-Length", 0))

        # Compressed should be smaller
        assert compressed_size < uncompressed_size
        assert compressed_size > 0


class TestCompressionQuality:
    """Test compression quality and ratios."""

    def test_compression_ratio(self, client):
        """Test compression achieves good ratio."""
        # Get uncompressed
        response_uncompressed = client.get("/large")
        uncompressed_size = len(response_uncompressed.content)

        # Get compressed
        response_compressed = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )
        compressed_size = len(response_compressed.content)

        # Calculate ratio
        ratio = compressed_size / uncompressed_size

        # Should achieve reasonable compression for JSON
        assert ratio < 0.5  # At least 50% compression

    def test_brotli_vs_gzip_compression(self, client):
        """Test brotli achieves better compression than gzip."""
        # Get gzip compressed
        response_gzip = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )
        gzip_size = len(response_gzip.content)

        # Get brotli compressed
        response_br = client.get(
            "/large",
            headers={"Accept-Encoding": "br"}
        )
        br_size = len(response_br.content)

        # Brotli usually achieves better compression
        # Allow some margin as it depends on data
        assert br_size <= gzip_size * 1.1


class TestCompressionPerformance:
    """Test compression performance impact."""

    def test_compression_overhead(self, client):
        """Test compression overhead is acceptable."""
        import time

        # Warm up
        client.get("/large")

        # Measure without compression
        start = time.time()
        for _ in range(10):
            response = client.get("/large")
            assert response.status_code == 200
        no_compression_time = time.time() - start

        # Measure with compression
        start = time.time()
        for _ in range(10):
            response = client.get(
                "/large",
                headers={"Accept-Encoding": "gzip"}
            )
            assert response.status_code == 200
        compression_time = time.time() - start

        # Compression overhead should be reasonable
        # Allow up to 3x time for compression
        assert compression_time < no_compression_time * 3

    def test_concurrent_compression(self, client):
        """Test concurrent requests are compressed correctly."""
        import concurrent.futures

        def make_request(use_compression):
            headers = {"Accept-Encoding": "gzip"} if use_compression else {}
            response = client.get("/large", headers=headers)
            return response.status_code, "Content-Encoding" in response.headers

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(10):
                use_compression = i % 2 == 0
                futures.append(executor.submit(make_request, use_compression))

            results = [f.result() for f in futures]

        # All requests should succeed
        for status, compressed in results:
            assert status == 200

        # Half should be compressed
        compressed_count = sum(1 for _, compressed in results if compressed)
        assert compressed_count == 5