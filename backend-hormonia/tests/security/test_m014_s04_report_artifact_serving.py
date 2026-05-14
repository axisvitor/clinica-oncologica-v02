"""M014/S04 proof for report and export artifact serving.

The tests exercise route-level report/export downloads with cache-backed fixtures only.
They prove generated artifacts are served as non-executable attachments after
owner/admin checks and that unsafe legacy artifact URLs are withheld fail-closed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import status

from app.api.v2.routers import enhanced_reports
from app.api.v2.routers import reports as base_reports
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.main import app
from app.models.user import UserRole
from tests.api.v2.test_report_ownership_closure import (
    AsyncInMemoryRedis,
    AuthSwitcher,
    FakeEnhancedReportsService,
    PRIVATE_DOWNLOAD_URL,
    REPORT_SECRET,
    _all_response_text,
    _assert_generic_denial,
    _create_patient,
    _create_user,
    _seed_base_report,
    _seed_enhanced_report_metadata,
    _seed_export,
)


@pytest.fixture
def report_cache(monkeypatch: pytest.MonkeyPatch) -> AsyncInMemoryRedis:
    """Patch both report routers onto an in-memory Redis seam."""

    cache = AsyncInMemoryRedis()

    async def _get_async_redis_client() -> AsyncInMemoryRedis:
        return cache

    import app.core.redis_manager as redis_manager

    monkeypatch.setattr(redis_manager, "get_async_redis_client", _get_async_redis_client)
    monkeypatch.setattr(enhanced_reports, "get_async_redis", _get_async_redis_client)
    return cache


@pytest.fixture
def auth_switcher(client) -> AuthSwitcher:
    """Install a route-compatible mutable session auth override."""

    switcher = AuthSwitcher()
    app.dependency_overrides[get_current_user_from_session] = switcher.dependency
    return switcher


@pytest.fixture
def report_subjects(db_session) -> SimpleNamespace:
    """Users and one owner patient for owner/admin/foreign boundaries."""

    owner_doctor = _create_user(db_session, role=UserRole.DOCTOR, label="artifact-owner")
    foreign_doctor = _create_user(db_session, role=UserRole.DOCTOR, label="artifact-foreign")
    admin = _create_user(db_session, role=UserRole.ADMIN, label="artifact-admin")
    db_session.flush()

    owner_patient = _create_patient(db_session, doctor=owner_doctor, name="Artifact Patient PHI")
    db_session.commit()

    return SimpleNamespace(
        owner_doctor=owner_doctor,
        foreign_doctor=foreign_doctor,
        admin=admin,
        owner_patient=owner_patient,
    )


@pytest.fixture
def fake_enhanced_service(client) -> FakeEnhancedReportsService:
    """Patch enhanced report service so tests use cache fixtures only."""

    service = FakeEnhancedReportsService()

    async def _override_service() -> FakeEnhancedReportsService:
        return service

    app.dependency_overrides[enhanced_reports.get_enhanced_reports_service] = _override_service
    return service


def _assert_attachment_security_headers(
    response,
    *,
    content_type_contains: str | None = None,
    filename_suffix: str | None = None,
) -> None:
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in response.headers["cache-control"].lower()

    disposition = response.headers["content-disposition"].lower()
    assert disposition.startswith("attachment")
    if filename_suffix:
        assert filename_suffix.lower() in disposition
    if content_type_contains:
        assert content_type_contains in response.headers["content-type"]


def _seed_malformed_export(
    cache: AsyncInMemoryRedis,
    *,
    export_id: UUID,
    report_id: UUID,
    owner_id: UUID,
    download_urls: Any,
) -> None:
    cache.seed_json(
        enhanced_reports._build_cache_key("export", export_id),
        {
            "export_id": str(export_id),
            "report_id": str(report_id),
            "created_by": str(owner_id),
            "generated_by": str(owner_id),
            "formats": ["pdf"],
            "status": "completed",
            "download_urls": download_urls,
            "file_sizes": {"pdf": 128},
        },
    )


def test_base_report_downloads_are_safe_attachments_for_generated_formats(
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
):
    report_id = uuid4()
    _seed_base_report(
        report_cache,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        patient=report_subjects.owner_patient,
    )

    expected_types = {
        "json": "application/json",
        "csv": "text/csv",
        "pdf": "application/pdf",
    }

    with auth_switcher.as_user(report_subjects.owner_doctor):
        responses = {
            format_name: client.get(
                f"/api/v2/reports/{report_id}/download",
                params={"format_override": format_name},
            )
            for format_name in expected_types
        }

    for format_name, response in responses.items():
        _assert_attachment_security_headers(
            response,
            content_type_contains=expected_types[format_name],
            filename_suffix=f".{format_name}",
        )
        assert REPORT_SECRET in response.text


def test_builder_downloads_preserve_owner_checks_and_safe_attachment_headers(
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
):
    builder_id = uuid4()
    _seed_enhanced_report_metadata(
        report_cache,
        report_id=builder_id,
        owner=report_subjects.owner_doctor,
        patient=report_subjects.owner_patient,
        data=[{"summary": REPORT_SECRET, "count": 1}],
    )

    with auth_switcher.as_user(report_subjects.owner_doctor):
        csv_response = client.get(
            f"/api/v2/enhanced-reports/builder/{builder_id}/download?format=csv"
        )
        json_response = client.get(
            f"/api/v2/enhanced-reports/builder/{builder_id}/download?format=json"
        )
    with auth_switcher.as_user(report_subjects.foreign_doctor):
        foreign_response = client.get(
            f"/api/v2/enhanced-reports/builder/{builder_id}/download?format=csv"
        )

    _assert_attachment_security_headers(
        csv_response,
        content_type_contains="text/csv",
        filename_suffix=".csv",
    )
    _assert_attachment_security_headers(
        json_response,
        content_type_contains="application/json",
        filename_suffix=".json",
    )
    assert REPORT_SECRET in csv_response.text
    assert REPORT_SECRET in json_response.text
    _assert_generic_denial(foreign_response, forbidden_values=[REPORT_SECRET])


def test_export_fallback_downloads_are_non_executable_attachments(
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
    fake_enhanced_service: FakeEnhancedReportsService,
):
    _ = fake_enhanced_service
    report_id = uuid4()
    export_id = uuid4()
    _seed_enhanced_report_metadata(
        report_cache,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        patient=report_subjects.owner_patient,
    )
    _seed_export(
        report_cache,
        export_id=export_id,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        download_urls={},
    )
    # Add HTML to the normalized fallback formats without creating a real file.
    export_record = report_cache._kv[enhanced_reports._build_cache_key("export", export_id)]
    import json

    export_payload = json.loads(export_record)
    export_payload["formats"] = ["pdf", "html"]
    report_cache.seed_json(enhanced_reports._build_cache_key("export", export_id), export_payload)

    with auth_switcher.as_user(report_subjects.owner_doctor):
        pdf_response = client.get(
            f"/api/v2/enhanced-reports/export/{export_id}/download?format=pdf"
        )
        html_response = client.get(
            f"/api/v2/enhanced-reports/export/{export_id}/download?format=html"
        )

    _assert_attachment_security_headers(
        pdf_response,
        content_type_contains="application/pdf",
        filename_suffix=".pdf",
    )
    _assert_attachment_security_headers(
        html_response,
        content_type_contains="application/octet-stream",
        filename_suffix=".html",
    )
    assert "text/html" not in html_response.headers["content-type"].lower()


@pytest.mark.parametrize(
    "unsafe_url",
    [
        PRIVATE_DOWNLOAD_URL,
        "uploads/private/report.pdf",
        "/safe/prefix/uploads/report.pdf",
        "%2Fuploads/private/report.pdf",
        "uploads%2Fprivate%2Freport.pdf",
        "/safe/prefix/%75ploads/report.pdf",
        "%252Fuploads/private/report.pdf",
        "https://evil.example.invalid/report.pdf",
        "http://evil.example.invalid/report.pdf",
        "//evil.example.invalid/report.pdf",
        "https://reports.example.invalid/%2Fuploads/private/report.pdf",
        "file:///etc/passwd",
        "data:text/html,<script>alert(1)</script>",
        "javascript:alert(1)",
        "C:/private/report.pdf",
        "C:%5Cprivate%5Creport.pdf",
        "/mnt/c/private/report.pdf",
    ],
)
def test_unsafe_export_urls_are_withheld_and_never_redirect(
    unsafe_url: str,
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
    fake_enhanced_service: FakeEnhancedReportsService,
):
    _ = fake_enhanced_service
    report_id = uuid4()
    export_id = uuid4()
    _seed_enhanced_report_metadata(
        report_cache,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        patient=report_subjects.owner_patient,
    )
    _seed_export(
        report_cache,
        export_id=export_id,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        download_urls={"pdf": unsafe_url},
    )

    with auth_switcher.as_user(report_subjects.owner_doctor):
        status_response = client.get(f"/api/v2/enhanced-reports/export/{export_id}")
        download_response = client.get(
            f"/api/v2/enhanced-reports/export/{export_id}/download?format=pdf"
        )

    assert status_response.status_code == status.HTTP_200_OK
    assert status_response.json()["download_urls"] == {}
    assert unsafe_url not in _all_response_text(status_response)

    assert download_response.status_code == status.HTTP_404_NOT_FOUND
    assert download_response.history == []
    assert "location" not in {header.lower() for header in download_response.headers}
    assert unsafe_url not in _all_response_text(download_response)


def test_malformed_export_download_urls_are_withheld_and_never_redirect(
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
    fake_enhanced_service: FakeEnhancedReportsService,
):
    _ = fake_enhanced_service
    report_id = uuid4()
    export_id = uuid4()
    _seed_enhanced_report_metadata(
        report_cache,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        patient=report_subjects.owner_patient,
    )
    _seed_malformed_export(
        report_cache,
        export_id=export_id,
        report_id=report_id,
        owner_id=report_subjects.owner_doctor.id,
        download_urls=[PRIVATE_DOWNLOAD_URL],
    )

    with auth_switcher.as_user(report_subjects.owner_doctor):
        status_response = client.get(f"/api/v2/enhanced-reports/export/{export_id}")
        download_response = client.get(
            f"/api/v2/enhanced-reports/export/{export_id}/download?format=pdf"
        )

    assert status_response.status_code == status.HTTP_200_OK
    assert status_response.json()["download_urls"] == {}
    assert PRIVATE_DOWNLOAD_URL not in _all_response_text(status_response)

    assert download_response.status_code == status.HTTP_404_NOT_FOUND
    assert download_response.history == []
    assert "location" not in {header.lower() for header in download_response.headers}
    assert PRIVATE_DOWNLOAD_URL not in _all_response_text(download_response)
