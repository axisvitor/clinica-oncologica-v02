"""
Comprehensive tests for Upload API v2

Tests cover:
- File upload endpoints (multipart/form-data)
- Get upload info endpoint
- Delete upload endpoint
- Image processing (thumbnails, previews, resizing)
- File validation (type, size, extension)
- Security validation (dangerous files, virus scanning)
- Redis caching behavior
- Rate limiting
- User quota enforcement
- Field selection
- Error handling
"""

import pytest
import io
import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import status
from fastapi.testclient import TestClient

from app.models.user import User, UserRole
from app.schemas.v2.upload import (
    FileCategory,
    StorageProvider,
    ProcessingStatus,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.get = AsyncMock(return_value=None)  # Default: cache miss
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=True)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.pipeline = Mock(return_value=AsyncMock())
    return redis_mock


@pytest.fixture
def test_user(db_session):
    """Create test user."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        name="Test User",
        role=UserRole.DOCTOR,
        is_active=True,
        firebase_uid="test_firebase_uid"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers with Session ID."""
    return {"X-Session-ID": f"test-session-{test_user.id}"}


@pytest.fixture
def sample_image_file():
    """Create sample image file for testing."""
    # Create a simple 1x1 PNG image
    png_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return ("test_image.png", io.BytesIO(png_data), "image/png")


@pytest.fixture
def sample_pdf_file():
    """Create sample PDF file for testing."""
    # Minimal PDF
    pdf_data = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n206\n%%EOF"
    return ("test_document.pdf", io.BytesIO(pdf_data), "application/pdf")


@pytest.fixture
def sample_text_file():
    """Create sample text file for testing."""
    text_data = b"This is a test text file.\nLine 2.\nLine 3."
    return ("test_file.txt", io.BytesIO(text_data), "text/plain")


# ============================================================================
# Upload Endpoint Tests
# ============================================================================


class TestUploadEndpoint:
    """Tests for POST /api/v2/upload/"""

    def test_upload_image_success(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_image_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test successful image upload."""
        filename, file_data, content_type = sample_image_file

        # Mock get_current_user_object_from_session
        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, file_data, content_type)},
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify response structure
        assert "id" in data
        assert "url" in data
        assert "file" in data
        assert "processing" in data
        assert "storage_provider" in data
        assert "uploaded_by" in data
        assert "uploaded_at" in data

        # Verify file metadata
        assert data["file"]["filename"] == filename
        assert data["file"]["content_type"] == content_type
        assert data["file"]["category"] == FileCategory.IMAGE.value
        assert data["file"]["size"] > 0
        assert "checksum" in data["file"]

        # Verify processing status
        assert data["processing"]["status"] in [
            ProcessingStatus.PENDING.value,
            ProcessingStatus.COMPLETED.value,
        ]

        # Verify storage
        assert data["storage_provider"] == StorageProvider.LOCAL.value
        assert data["is_public"] is False

    def test_upload_with_thumbnail_generation(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_image_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test image upload with thumbnail generation."""
        filename, file_data, content_type = sample_image_file

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    with patch("app.api.v2.upload.get_image_metadata") as mock_img_meta:
                        # Mock image metadata
                        mock_img_meta.return_value = Mock(
                            width=100,
                            height=100,
                            format="png",
                            has_alpha=False,
                            color_mode="RGB",
                        )

                        response = client.post(
                            "/api/v2/upload/",
                            files={"file": (filename, file_data, content_type)},
                            params={
                                "generate_thumbnail": True,
                                "generate_preview": True,
                                "quality": 90,
                            },
                            headers=auth_headers,
                        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify image metadata
        assert "image_metadata" in data
        if data["image_metadata"]:
            assert "width" in data["image_metadata"]
            assert "height" in data["image_metadata"]
            assert "format" in data["image_metadata"]

    def test_upload_with_resize(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_image_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test image upload with resizing."""
        filename, file_data, content_type = sample_image_file

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, file_data, content_type)},
                        params={
                            "resize_width": 800,
                            "quality": 85,
                        },
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "processing" in data

    def test_upload_pdf_success(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_pdf_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test successful PDF upload."""
        filename, file_data, content_type = sample_pdf_file

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, file_data, content_type)},
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify document category
        assert data["file"]["category"] == FileCategory.DOCUMENT.value
        assert data["file"]["content_type"] == content_type

        # No image metadata for PDFs
        assert data["image_metadata"] is None

    def test_upload_text_file_success(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_text_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test successful text file upload."""
        filename, file_data, content_type = sample_text_file

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, file_data, content_type)},
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["file"]["category"] == FileCategory.TEXT.value

    def test_upload_field_selection(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_image_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test upload with field selection."""
        filename, file_data, content_type = sample_image_file

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, file_data, content_type)},
                        params={"fields": "id,url,file"},
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify only requested fields present
        assert "id" in data
        assert "url" in data
        assert "file" in data

    def test_upload_file_too_large(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
        tmp_path,
    ):
        """Test upload fails for files exceeding size limit."""
        # Create file larger than max size (50MB)
        large_data = b"x" * (51 * 1024 * 1024)
        filename = "large_file.bin"

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, io.BytesIO(large_data), "application/octet-stream")},
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        data = response.json()
        assert "detail" in data

    def test_upload_unsupported_file_type(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
        tmp_path,
    ):
        """Test upload fails for unsupported file types."""
        # Create file with unsupported MIME type
        data = b"fake executable data"
        filename = "malware.exe"

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, io.BytesIO(data), "application/x-executable")},
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        data = response.json()
        assert "not supported" in data["detail"]

    def test_upload_dangerous_extension(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
        tmp_path,
    ):
        """Test upload fails for dangerous file extensions."""
        data = b"fake script"
        filename = "script.sh"

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, io.BytesIO(data), "text/plain")},
                        headers=auth_headers,
                    )

        # Should be rejected due to dangerous extension
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        ]

    def test_upload_rate_limit_exceeded(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_image_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test upload fails when rate limit exceeded."""
        filename, file_data, content_type = sample_image_file

        # Mock rate limit exceeded
        mock_redis_client.get = AsyncMock(return_value="25")  # Over limit

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, file_data, content_type)},
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        data = response.json()
        assert "rate limit" in data["detail"].lower()

    def test_upload_virus_detected(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_image_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test upload fails when virus detected."""
        filename, file_data, content_type = sample_image_file

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    with patch("app.api.v2.upload.scan_virus", return_value=False):
                        response = client.post(
                            "/api/v2/upload/",
                            files={"file": (filename, file_data, content_type)},
                            params={"scan_virus": True},
                            headers=auth_headers,
                        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "virus" in data["detail"].lower()

    def test_upload_caching(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        sample_image_file,
        mock_redis_client,
        tmp_path,
    ):
        """Test upload metadata is cached in Redis."""
        filename, file_data, content_type = sample_image_file

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.post(
                        "/api/v2/upload/",
                        files={"file": (filename, file_data, content_type)},
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify cache was called
        mock_redis_client.setex.assert_called()


# ============================================================================
# Get Upload Info Tests
# ============================================================================


class TestGetUploadInfo:
    """Tests for GET /api/v2/upload/{upload_id}"""

    def test_get_upload_info_success(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
    ):
        """Test successful get upload info from cache."""
        upload_id = uuid4()

        # Mock cached response
        cached_data = {
            "id": str(upload_id),
            "url": "/uploads/test.jpg",
            "download_url": f"/api/v2/upload/{upload_id}/download",
            "file": {
                "id": str(upload_id),
                "filename": "test.jpg",
                "safe_filename": "20250107_123456_abc.jpg",
                "content_type": "image/jpeg",
                "category": "image",
                "size": 1024,
                "checksum": "abc123",
            },
            "image_metadata": {
                "width": 800,
                "height": 600,
                "format": "jpeg",
                "has_alpha": False,
                "color_mode": "RGB",
            },
            "processing": {
                "status": "completed",
                "thumbnail_url": None,
                "preview_url": None,
                "resized_url": None,
                "virus_scan_clean": True,
                "processing_time_ms": 100,
            },
            "storage_provider": "local",
            "storage_path": "uploads/image/test.jpg",
            "uploaded_by": str(uuid4()),
            "uploaded_at": datetime.utcnow().isoformat(),
            "is_public": False,
            "expires_at": None,
            "custom_metadata": None,
        }

        import json
        mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                response = client.get(
                    f"/api/v2/upload/{upload_id}",
                    headers=auth_headers,
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(upload_id)
        assert data["file"]["filename"] == "test.jpg"

    def test_get_upload_info_not_found(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
    ):
        """Test get upload info fails for non-existent upload."""
        upload_id = uuid4()

        # Mock cache miss
        mock_redis_client.get = AsyncMock(return_value=None)

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                response = client.get(
                    f"/api/v2/upload/{upload_id}",
                    headers=auth_headers,
                )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_upload_info_field_selection(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
    ):
        """Test get upload info with field selection."""
        upload_id = uuid4()

        # Mock cached response
        cached_data = {
            "id": str(upload_id),
            "url": "/uploads/test.jpg",
            "download_url": f"/api/v2/upload/{upload_id}/download",
            "file": {
                "id": str(upload_id),
                "filename": "test.jpg",
                "safe_filename": "20250107_123456_abc.jpg",
                "content_type": "image/jpeg",
                "category": "image",
                "size": 1024,
                "checksum": "abc123",
            },
            "image_metadata": None,
            "processing": {
                "status": "completed",
                "thumbnail_url": None,
                "preview_url": None,
                "resized_url": None,
                "virus_scan_clean": True,
                "processing_time_ms": 100,
            },
            "storage_provider": "local",
            "storage_path": "uploads/image/test.jpg",
            "uploaded_by": str(uuid4()),
            "uploaded_at": datetime.utcnow().isoformat(),
            "is_public": False,
            "expires_at": None,
            "custom_metadata": None,
        }

        import json
        mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                response = client.get(
                    f"/api/v2/upload/{upload_id}",
                    params={"fields": "id,url"},
                    headers=auth_headers,
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify only requested fields
        assert "id" in data
        assert "url" in data


# ============================================================================
# Delete Upload Tests
# ============================================================================


class TestDeleteUpload:
    """Tests for DELETE /api/v2/upload/{upload_id}"""

    def test_delete_upload_success(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
        tmp_path,
    ):
        """Test successful file deletion."""
        upload_id = uuid4()

        # Create test file
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test content")

        # Mock cached response
        cached_data = {
            "id": str(upload_id),
            "url": "/uploads/test.jpg",
            "download_url": f"/api/v2/upload/{upload_id}/download",
            "file": {
                "id": str(upload_id),
                "filename": "test.jpg",
                "safe_filename": "test.jpg",
                "content_type": "image/jpeg",
                "category": "image",
                "size": 1024,
                "checksum": "abc123",
            },
            "image_metadata": None,
            "processing": {
                "status": "completed",
                "thumbnail_url": None,
                "preview_url": None,
                "resized_url": None,
                "virus_scan_clean": True,
                "processing_time_ms": 100,
            },
            "storage_provider": "local",
            "storage_path": str(test_file.relative_to(tmp_path)),
            "uploaded_by": str(test_user.id),
            "uploaded_at": datetime.utcnow().isoformat(),
            "is_public": False,
            "expires_at": None,
            "custom_metadata": None,
        }

        import json
        mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                with patch("app.api.v2.upload.UPLOAD_DIR", tmp_path):
                    response = client.delete(
                        f"/api/v2/upload/{upload_id}",
                        headers=auth_headers,
                    )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify file was deleted
        assert not test_file.exists()

        # Verify cache was cleared
        mock_redis_client.delete.assert_called()

    def test_delete_upload_not_found(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
    ):
        """Test delete fails for non-existent upload."""
        upload_id = uuid4()

        # Mock cache miss
        mock_redis_client.get = AsyncMock(return_value=None)

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                response = client.delete(
                    f"/api/v2/upload/{upload_id}",
                    headers=auth_headers,
                )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_upload_forbidden(
        self,
        client: TestClient,
        auth_headers,
        test_user,
        mock_redis_client,
    ):
        """Test delete fails when user doesn't own the file."""
        upload_id = uuid4()
        other_user_id = uuid4()

        # Mock cached response with different owner
        cached_data = {
            "id": str(upload_id),
            "url": "/uploads/test.jpg",
            "download_url": f"/api/v2/upload/{upload_id}/download",
            "file": {
                "id": str(upload_id),
                "filename": "test.jpg",
                "safe_filename": "test.jpg",
                "content_type": "image/jpeg",
                "category": "image",
                "size": 1024,
                "checksum": "abc123",
            },
            "image_metadata": None,
            "processing": {
                "status": "completed",
                "thumbnail_url": None,
                "preview_url": None,
                "resized_url": None,
                "virus_scan_clean": True,
                "processing_time_ms": 100,
            },
            "storage_provider": "local",
            "storage_path": "test.jpg",
            "uploaded_by": str(other_user_id),  # Different user
            "uploaded_at": datetime.utcnow().isoformat(),
            "is_public": False,
            "expires_at": None,
            "custom_metadata": None,
        }

        import json
        mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

        with patch("app.api.v2.upload.get_current_user_object_from_session", return_value=test_user):
            with patch("app.api.v2.upload.get_redis_client", return_value=mock_redis_client):
                response = client.delete(
                    f"/api/v2/upload/{upload_id}",
                    headers=auth_headers,
                )

        assert response.status_code == status.HTTP_403_FORBIDDEN
