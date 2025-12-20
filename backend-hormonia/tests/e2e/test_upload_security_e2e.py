"""
E2E-003: Upload de Arquivo com Security Layers
Tests: file upload → virus scan → quota check → storage
"""
import pytest
import io
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.models.patient import Patient


@pytest.mark.asyncio
class TestUploadSecurityE2E:
    """E2E tests for file upload with security validations"""

    async def test_successful_file_upload(
        self,
        async_client: AsyncClient,
        db_session: Session,
        patient_user: Patient,
        auth_headers_admin: dict,
        mock_clamav,
        cleanup_uploads
    ):
        """
        Test successful file upload flow:
        1. Upload file
        2. Virus scan (mocked)
        3. Quota check
        4. Store file
        5. Create database record
        """
        # Create test file
        file_content = b"Test medical report content"
        file_data = {
            "file": ("report.pdf", io.BytesIO(file_content), "application/pdf")
        }

        # Upload file
        response = await async_client.post(
            f"/api/v2/patients/{patient_user.id}/upload",
            files=file_data,
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        upload_data = response.json()

        # Verify response structure
        assert "file_id" in upload_data
        assert upload_data["filename"] == "report.pdf"
        assert upload_data["size"] == len(file_content)
        assert upload_data["scan_status"] == "clean"

    async def test_upload_virus_detected(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        monkeypatch
    ):
        """Test upload fails when virus detected"""
        # Mock ClamAV to detect virus
        class MockClamAVInfected:
            def scan_file(self, file_path: str):
                return {"status": "infected", "virus": "EICAR-Test-File"}

        monkeypatch.setattr(
            "app.services.security.ClamAVScanner",
            MockClamAVInfected
        )

        file_data = {
            "file": ("infected.exe", io.BytesIO(b"X5O!P%@AP[4\\PZX"), "application/octet-stream")
        }

        response = await async_client.post(
            f"/api/v2/patients/{patient_user.id}/upload",
            files=file_data,
            headers=auth_headers_admin
        )

        assert response.status_code == 400
        error = response.json()
        assert "virus" in error["detail"].lower()

    async def test_upload_quota_exceeded(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        db_session: Session,
        mock_clamav
    ):
        """Test upload fails when quota exceeded"""
        # Set patient quota to low value
        patient_user.metadata_["upload_quota_mb"] = 1  # 1MB
        db_session.commit()

        # Try to upload 2MB file
        large_file = b"X" * (2 * 1024 * 1024)  # 2MB
        file_data = {
            "file": ("large.pdf", io.BytesIO(large_file), "application/pdf")
        }

        response = await async_client.post(
            f"/api/v2/patients/{patient_user.id}/upload",
            files=file_data,
            headers=auth_headers_admin
        )

        assert response.status_code == 413  # Payload Too Large
        error = response.json()
        assert "quota" in error["detail"].lower()

    async def test_upload_invalid_file_type(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict
    ):
        """Test upload fails with invalid file type"""
        file_data = {
            "file": ("script.sh", io.BytesIO(b"#!/bin/bash\nrm -rf /"), "application/x-sh")
        }

        response = await async_client.post(
            f"/api/v2/patients/{patient_user.id}/upload",
            files=file_data,
            headers=auth_headers_admin
        )

        assert response.status_code == 415  # Unsupported Media Type

    async def test_upload_file_name_sanitization(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        mock_clamav
    ):
        """Test file name is sanitized for security"""
        # Malicious filename
        malicious_filename = "../../../etc/passwd"
        file_data = {
            "file": (malicious_filename, io.BytesIO(b"content"), "application/pdf")
        }

        response = await async_client.post(
            f"/api/v2/patients/{patient_user.id}/upload",
            files=file_data,
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        upload_data = response.json()

        # Verify filename sanitized
        assert ".." not in upload_data["filename"]
        assert "/" not in upload_data["filename"]

    async def test_upload_multiple_files(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        mock_clamav
    ):
        """Test multiple files upload in single request"""
        files = [
            ("files", ("report1.pdf", io.BytesIO(b"Report 1"), "application/pdf")),
            ("files", ("report2.pdf", io.BytesIO(b"Report 2"), "application/pdf")),
            ("files", ("xray.jpg", io.BytesIO(b"Xray image"), "image/jpeg"))
        ]

        response = await async_client.post(
            f"/api/v2/patients/{patient_user.id}/upload-multiple",
            files=files,
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        uploads = response.json()
        assert len(uploads["files"]) == 3
        assert all(f["scan_status"] == "clean" for f in uploads["files"])
