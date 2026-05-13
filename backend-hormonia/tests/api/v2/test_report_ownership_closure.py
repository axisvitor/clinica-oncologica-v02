"""Regression tests for report-ID ownership closure.

These tests intentionally exercise route-level API surfaces rather than helper
functions so direct report UUID reuse, cached export URL leakage, and
normalization-derived ownership fallbacks are caught before implementation.
"""

from __future__ import annotations

import fnmatch
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request, status

from app.api.v2.routers import enhanced_reports
from app.api.v2.routers import reports as base_reports
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.main import app
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.utils.security import get_password_hash


# ---------------------------------------------------------------------------
# In-memory Redis/cache seam
# ---------------------------------------------------------------------------


class AsyncInMemoryRedis:
    """Small async Redis seam covering the report router cache operations."""

    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    def seed_json(self, key: str, value: dict[str, Any]) -> None:
        self._kv[key] = json.dumps(value, default=str)

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        _ = ttl
        self._kv[key] = value
        return True

    async def set(self, key: str, value: str, *args: Any, **kwargs: Any) -> bool:
        _ = args, kwargs
        self._kv[key] = value
        return True

    async def delete(self, key: str) -> int:
        existed = key in self._kv
        self._kv.pop(key, None)
        return int(existed)

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self._kv.get(key) for key in keys]

    async def scan_iter(self, match: str | None = None):
        for key in list(self._kv):
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        zset = self._zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if member not in zset:
                added += 1
            zset[str(member)] = float(score)
        return added

    async def zrevrange(self, key: str, start: int, end: int) -> list[str]:
        ordered = sorted(
            self._zsets.get(key, {}).items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
        if end == -1:
            selected = ordered[start:]
        else:
            selected = ordered[start : end + 1]
        return [member for member, _score in selected]


@pytest.fixture
def report_cache(monkeypatch: pytest.MonkeyPatch) -> AsyncInMemoryRedis:
    """Patch both base and enhanced report routers onto an in-memory Redis seam."""

    cache = AsyncInMemoryRedis()

    async def _get_async_redis_client() -> AsyncInMemoryRedis:
        return cache

    import app.core.redis_manager as redis_manager

    monkeypatch.setattr(redis_manager, "get_async_redis_client", _get_async_redis_client)
    monkeypatch.setattr(enhanced_reports, "get_async_redis", _get_async_redis_client)
    return cache


# ---------------------------------------------------------------------------
# Users, patients, and auth swapping helpers
# ---------------------------------------------------------------------------


@dataclass
class AuthSwitcher:
    """Mutable auth override so one test can exercise owner/admin/foreign users."""

    current_user: User | None = None

    async def dependency(self, request: Request) -> dict[str, Any]:
        if self.current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User ID not found")

        role = (
            self.current_user.role.value
            if hasattr(self.current_user.role, "value")
            else str(self.current_user.role)
        )
        request.state.user_id = str(self.current_user.id)
        request.state.user_role = role
        return {
            "id": str(self.current_user.id),
            "email": self.current_user.email,
            "role": role,
            "is_active": self.current_user.is_active,
        }

    @contextmanager
    def as_user(self, user: User | None):
        previous = self.current_user
        self.current_user = user
        try:
            yield
        finally:
            self.current_user = previous


@pytest.fixture
def auth_switcher(client) -> AuthSwitcher:
    """Install a route-compatible session auth override."""

    switcher = AuthSwitcher()
    app.dependency_overrides[get_current_user_from_session] = switcher.dependency
    return switcher


def _create_user(db_session, *, role: UserRole, label: str) -> User:
    suffix = uuid4().hex
    user = User(
        id=uuid4(),
        email=f"{label}-{suffix}@example.com",
        hashed_password=get_password_hash("ownership-pass-123"),
        full_name=f"{label.title()} User",
        display_name=f"{label.title()} User",
        role=role,
        is_active=True,
        preferences={},
    )
    db_session.add(user)
    return user


def _create_patient(db_session, *, doctor: User, name: str) -> Patient:
    patient = Patient(
        id=uuid4(),
        doctor_id=doctor.id,
        name=name,
        birth_date=date(1980, 1, 1),
        patient_data={},
    )
    db_session.add(patient)
    return patient


@pytest.fixture
def report_subjects(db_session) -> SimpleNamespace:
    """Two doctors, two patients, and one admin for owner/admin/foreign boundaries."""

    owner_doctor = _create_user(db_session, role=UserRole.DOCTOR, label="owner-doctor")
    foreign_doctor = _create_user(db_session, role=UserRole.DOCTOR, label="foreign-doctor")
    admin = _create_user(db_session, role=UserRole.ADMIN, label="admin")
    db_session.flush()

    owner_patient = _create_patient(db_session, doctor=owner_doctor, name="Owner Patient PHI")
    foreign_patient = _create_patient(db_session, doctor=foreign_doctor, name="Foreign Patient PHI")
    db_session.commit()

    return SimpleNamespace(
        owner_doctor=owner_doctor,
        foreign_doctor=foreign_doctor,
        admin=admin,
        owner_patient=owner_patient,
        foreign_patient=foreign_patient,
    )


# ---------------------------------------------------------------------------
# Fake enhanced service: downstream behavior only after route-level auth passes
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class FakeEnhancedReportsService:
    async def share_report(self, data, user_id: UUID, role: UserRole):
        _ = role
        return [
            {
                "id": str(uuid4()),
                "report_id": str(data.report_id),
                "shared_with": str(shared_with),
                "permission_level": data.permission_level.value,
                "shared_by": str(user_id),
                "shared_at": _now_iso(),
                "expires_at": data.expires_at.isoformat() if data.expires_at else None,
                "is_active": True,
            }
            for shared_with in data.user_ids
        ]

    async def create_public_link(self, data, user_id: UUID, role: UserRole):
        _ = role
        return {
            "id": str(uuid4()),
            "report_id": str(data.report_id),
            "token": "public-test-token",
            "url": f"https://reports.example.invalid/public/{data.report_id}?token=public-test-token",
            "expires_at": data.expires_at.isoformat() if data.expires_at else None,
            "password_protected": data.password_protected,
            "max_views": data.max_views,
            "view_count": 0,
            "created_at": _now_iso(),
            "created_by": str(user_id),
            "is_active": True,
        }

    async def get_report_history(self, report_id: UUID, user_id: UUID, role: UserRole):
        _ = role
        return {
            "report_id": str(report_id),
            "current_version": 1,
            "versions": [
                {
                    "version": 1,
                    "created_at": _now_iso(),
                    "created_by": str(user_id),
                    "change_summary": "Initial report version",
                    "configuration_snapshot": {"fields": ["summary"]},
                    "data_hash": "sha256:generic-report-version",
                }
            ],
            "total_versions": 1,
        }

    async def restore_report_version(self, report_id: UUID, data, user_id: UUID, role: UserRole):
        _ = data, role
        return {
            "id": str(report_id),
            "name": "Restored to v1",
            "description": "Restored report",
            "fields": [
                {
                    "field_name": "summary",
                    "display_name": "Summary",
                    "field_type": "text",
                    "data_source": "patients",
                }
            ],
            "filters": {},
            "created_at": _now_iso(),
            "created_by": str(user_id),
            "row_count": 1,
            "generation_time_seconds": 0.01,
            "download_url": f"/api/v2/enhanced-reports/builder/{report_id}/download",
        }

    async def get_export_status(self, export_id: UUID):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    async def get_builder_report(self, builder_id: UUID):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


@pytest.fixture
def fake_enhanced_service(client) -> FakeEnhancedReportsService:
    service = FakeEnhancedReportsService()

    async def _override_service() -> FakeEnhancedReportsService:
        return service

    app.dependency_overrides[enhanced_reports.get_enhanced_reports_service] = _override_service
    return service


# ---------------------------------------------------------------------------
# Cache seed and PHI-safety assertions
# ---------------------------------------------------------------------------


BUILDER_FIELDS = [
    {
        "field_name": "summary",
        "display_name": "Summary",
        "field_type": "text",
        "data_source": "patients",
    }
]
REPORT_SECRET = "DO-NOT-LEAK-REPORT-DATA"
PRIVATE_DOWNLOAD_URL = "/uploads/private/reports/export-token.pdf?token=secret-token"


def _seed_base_report(
    cache: AsyncInMemoryRedis,
    *,
    report_id: UUID,
    owner: User | None,
    patient: Patient | None,
    status_value: str = "completed",
    include_owner: bool = True,
    include_patient_ids: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "id": str(report_id),
        "title": "Ownership Closure Report",
        "type": "patient_summary",
        "format": "json",
        "status": status_value,
        "created_at": _now_iso(),
        "data": {"summary": REPORT_SECRET, "records": [{"value": REPORT_SECRET}]},
    }
    if include_owner and owner is not None:
        report["generated_by"] = str(owner.id)
        report["created_by"] = str(owner.id)
    if include_patient_ids and patient is not None:
        report["patient_ids"] = [str(patient.id)]
    if extra:
        report.update(extra)
    cache.seed_json(base_reports._get_cache_key("report", report_id=str(report_id)), report)
    return report


def _seed_enhanced_report_metadata(
    cache: AsyncInMemoryRedis,
    *,
    report_id: UUID,
    owner: User | None,
    patient: Patient | None,
    include_owner: bool = True,
    include_patient_ids: bool = True,
    data: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metadata = {
        "id": str(report_id),
        "report_id": str(report_id),
        "name": "Enhanced Ownership Report",
        "description": "Ownership metadata fixture",
        "fields": BUILDER_FIELDS,
        "filters": {},
        "created_at": _now_iso(),
        "row_count": 1,
        "generation_time_seconds": 0.01,
        "download_url": f"/api/v2/enhanced-reports/builder/{report_id}/download",
        "data": data if data is not None else [{"summary": REPORT_SECRET}],
    }
    if include_owner and owner is not None:
        metadata["created_by"] = str(owner.id)
        metadata["generated_by"] = str(owner.id)
    if include_patient_ids and patient is not None:
        metadata["patient_ids"] = [str(patient.id)]

    # Builder endpoints use the builder key. Cross-feature report checks may use
    # either the enhanced report key or the base report key, so seed both.
    cache.seed_json(enhanced_reports._build_cache_key("builder", report_id), metadata)
    cache.seed_json(enhanced_reports._build_cache_key("report", report_id), metadata)
    cache.seed_json(base_reports._get_cache_key("report", report_id=str(report_id)), metadata)
    return metadata


def _seed_export(
    cache: AsyncInMemoryRedis,
    *,
    export_id: UUID,
    report_id: UUID | None,
    owner: User | None,
    include_owner: bool = True,
    include_report_id: bool = True,
    download_urls: dict[str, str] | None = None,
) -> dict[str, Any]:
    export = {
        "export_id": str(export_id),
        "formats": ["pdf"],
        "status": "completed",
        "download_urls": download_urls or {},
        "expires_at": _future_iso(),
        "file_sizes": {"pdf": 128},
        "created_at": _now_iso(),
    }
    if include_report_id and report_id is not None:
        export["report_id"] = str(report_id)
    if include_owner and owner is not None:
        export["created_by"] = str(owner.id)
        export["generated_by"] = str(owner.id)
    cache.seed_json(enhanced_reports._build_cache_key("export", export_id), export)
    return export


def _all_response_text(response) -> str:
    parts = [response.text]
    parts.extend(str(value) for value in response.headers.values())
    for historical_response in response.history:
        parts.append(historical_response.text)
        parts.extend(str(value) for value in historical_response.headers.values())
    return "\n".join(parts)


def _assert_generic_denial(response, *, forbidden_values: list[str] | None = None) -> None:
    assert response.status_code in {
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    }

    body = response.json() if response.content else {}
    allowed_keys = {
        "detail",
        "status",
        "status_code",
        "reason",
        "report_id",
        "export_id",
        "error",
        "message",
    }
    if isinstance(body, dict):
        assert set(body.keys()) <= allowed_keys
        detail = body.get("detail")
        if isinstance(detail, dict):
            assert set(detail.keys()) <= allowed_keys
        elif detail is not None:
            assert isinstance(detail, str)
            assert detail.strip()

    text = _all_response_text(response)
    built_in_forbidden = [
        REPORT_SECRET,
        PRIVATE_DOWNLOAD_URL,
        "/uploads",
        "secret-token",
        "public-test-token",
        "download_urls",
        "Ownership metadata fixture",
    ]
    for forbidden in built_in_forbidden + (forbidden_values or []):
        assert forbidden not in text


def _assert_unauthenticated_denial(response) -> None:
    assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
    assert REPORT_SECRET not in response.text


# ---------------------------------------------------------------------------
# Base report API ownership closure
# ---------------------------------------------------------------------------


def test_base_generate_rejects_foreign_patient_ids(
    client,
    monkeypatch: pytest.MonkeyPatch,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
):
    async def _noop_generation(*args: Any, **kwargs: Any) -> None:
        _ = args, kwargs

    monkeypatch.setattr(base_reports, "_generate_report_async", _noop_generation)

    with auth_switcher.as_user(report_subjects.owner_doctor):
        response = client.post(
            "/api/v2/reports/generate",
            params={
                "title": "Foreign patient probe",
                "report_type": "patient_summary",
                "format": "json",
                "patient_ids": str(report_subjects.foreign_patient.id),
            },
        )

    _assert_generic_denial(
        response,
        forbidden_values=[
            str(report_subjects.foreign_patient.id),
            report_subjects.foreign_patient.name,
        ],
    )


def test_base_generate_allows_owner_and_admin_patient_ids(
    client,
    monkeypatch: pytest.MonkeyPatch,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
):
    async def _noop_generation(*args: Any, **kwargs: Any) -> None:
        _ = args, kwargs

    monkeypatch.setattr(base_reports, "_generate_report_async", _noop_generation)

    with auth_switcher.as_user(report_subjects.owner_doctor):
        owner_response = client.post(
            "/api/v2/reports/generate",
            params={
                "title": "Owner patient report",
                "report_type": "patient_summary",
                "format": "json",
                "patient_ids": str(report_subjects.owner_patient.id),
            },
        )

    with auth_switcher.as_user(report_subjects.admin):
        admin_response = client.post(
            "/api/v2/reports/generate",
            params={
                "title": "Admin patient report",
                "report_type": "patient_summary",
                "format": "json",
                "patient_ids": str(report_subjects.foreign_patient.id),
            },
        )

    assert owner_response.status_code == status.HTTP_202_ACCEPTED
    assert admin_response.status_code == status.HTTP_202_ACCEPTED
    assert owner_response.json()["generated_by"] == str(report_subjects.owner_doctor.id)
    assert admin_response.json()["generated_by"] == str(report_subjects.admin.id)


def test_base_generate_invalid_patient_ids_is_rejected_without_phi(
    client,
    monkeypatch: pytest.MonkeyPatch,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
):
    async def _noop_generation(*args: Any, **kwargs: Any) -> None:
        _ = args, kwargs

    monkeypatch.setattr(base_reports, "_generate_report_async", _noop_generation)

    with auth_switcher.as_user(report_subjects.owner_doctor):
        response = client.post(
            "/api/v2/reports/generate",
            params={
                "title": "Bad patient id report",
                "report_type": "patient_summary",
                "format": "json",
                "patient_ids": "not-a-uuid",
            },
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert str(report_subjects.owner_patient.id) not in response.text
    assert report_subjects.owner_patient.name not in response.text


def test_base_completed_cached_report_download_allows_owner_and_admin(
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

    with auth_switcher.as_user(report_subjects.owner_doctor):
        owner_response = client.get(f"/api/v2/reports/{report_id}/download")
    with auth_switcher.as_user(report_subjects.admin):
        admin_response = client.get(f"/api/v2/reports/{report_id}/download")

    assert owner_response.status_code == status.HTTP_200_OK
    assert admin_response.status_code == status.HTTP_200_OK
    assert REPORT_SECRET in owner_response.text
    assert REPORT_SECRET in admin_response.text


def test_base_download_denies_foreign_and_missing_raw_ownership_before_formatting(
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
):
    foreign_probe_id = uuid4()
    _seed_base_report(
        report_cache,
        report_id=foreign_probe_id,
        owner=report_subjects.owner_doctor,
        patient=report_subjects.owner_patient,
    )

    missing_owner_id = uuid4()
    _seed_base_report(
        report_cache,
        report_id=missing_owner_id,
        owner=None,
        patient=None,
        include_owner=False,
        include_patient_ids=False,
    )

    with auth_switcher.as_user(report_subjects.foreign_doctor):
        foreign_response = client.get(f"/api/v2/reports/{foreign_probe_id}/download")
    with auth_switcher.as_user(report_subjects.owner_doctor):
        missing_owner_response = client.get(f"/api/v2/reports/{missing_owner_id}/download")

    _assert_generic_denial(
        foreign_response,
        forbidden_values=[str(report_subjects.owner_patient.id), report_subjects.owner_patient.name],
    )
    _assert_generic_denial(missing_owner_response)


def test_base_download_requires_authenticated_user(
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

    with auth_switcher.as_user(None):
        response = client.get(f"/api/v2/reports/{report_id}/download")

    _assert_unauthenticated_denial(response)


# ---------------------------------------------------------------------------
# Enhanced report ownership closure
# ---------------------------------------------------------------------------


def test_builder_read_and_download_enforce_raw_cached_owner_metadata(
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
    )

    with auth_switcher.as_user(report_subjects.owner_doctor):
        owner_read = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}")
        owner_download = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}/download?format=csv")
    with auth_switcher.as_user(report_subjects.admin):
        admin_read = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}")
        admin_download = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}/download?format=csv")
    with auth_switcher.as_user(report_subjects.foreign_doctor):
        foreign_read = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}")
        foreign_download = client.get(f"/api/v2/enhanced-reports/builder/{builder_id}/download?format=csv")

    assert owner_read.status_code == status.HTTP_200_OK
    assert owner_download.status_code == status.HTTP_200_OK
    assert admin_read.status_code == status.HTTP_200_OK
    assert admin_download.status_code == status.HTTP_200_OK
    _assert_generic_denial(
        foreign_read,
        forbidden_values=[str(report_subjects.owner_patient.id), report_subjects.owner_patient.name],
    )
    _assert_generic_denial(
        foreign_download,
        forbidden_values=[str(report_subjects.owner_patient.id), report_subjects.owner_patient.name],
    )

    missing_raw_builder_id = uuid4()
    _seed_enhanced_report_metadata(
        report_cache,
        report_id=missing_raw_builder_id,
        owner=None,
        patient=None,
        include_owner=False,
        include_patient_ids=False,
    )
    with auth_switcher.as_user(report_subjects.owner_doctor):
        missing_raw_read = client.get(f"/api/v2/enhanced-reports/builder/{missing_raw_builder_id}")
        missing_raw_download = client.get(
            f"/api/v2/enhanced-reports/builder/{missing_raw_builder_id}/download?format=csv"
        )

    # Missing raw created_by/patient metadata must not be normalized to the requester.
    _assert_generic_denial(missing_raw_read)
    _assert_generic_denial(missing_raw_download)


def test_enhanced_sharing_public_link_and_share_listing_enforce_report_owner(
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
    fake_enhanced_service: FakeEnhancedReportsService,
):
    _ = fake_enhanced_service
    report_id = uuid4()
    _seed_enhanced_report_metadata(
        report_cache,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        patient=report_subjects.owner_patient,
    )

    share_payload = {
        "report_id": str(report_id),
        "user_ids": [str(report_subjects.foreign_doctor.id)],
        "permission_level": "view",
    }
    public_link_payload = {
        "report_id": str(report_id),
        "password_protected": False,
        "max_views": 10,
    }

    for allowed_user in (report_subjects.owner_doctor, report_subjects.admin):
        with auth_switcher.as_user(allowed_user):
            share_response = client.post("/api/v2/enhanced-reports/sharing", json=share_payload)
            public_link_response = client.post(
                "/api/v2/enhanced-reports/sharing/public-link",
                json=public_link_payload,
            )
            shares_response = client.get(f"/api/v2/enhanced-reports/sharing/{report_id}/shares")

        assert share_response.status_code == status.HTTP_201_CREATED
        assert public_link_response.status_code == status.HTTP_201_CREATED
        assert shares_response.status_code == status.HTTP_200_OK

    with auth_switcher.as_user(report_subjects.foreign_doctor):
        foreign_share = client.post("/api/v2/enhanced-reports/sharing", json=share_payload)
        foreign_public_link = client.post(
            "/api/v2/enhanced-reports/sharing/public-link",
            json=public_link_payload,
        )
        foreign_shares = client.get(f"/api/v2/enhanced-reports/sharing/{report_id}/shares")

    for denied_response in (foreign_share, foreign_public_link, foreign_shares):
        _assert_generic_denial(
            denied_response,
            forbidden_values=[str(report_subjects.owner_patient.id), report_subjects.owner_patient.name],
        )


def test_enhanced_history_and_restore_enforce_report_owner(
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
    fake_enhanced_service: FakeEnhancedReportsService,
):
    _ = fake_enhanced_service
    report_id = uuid4()
    _seed_enhanced_report_metadata(
        report_cache,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        patient=report_subjects.owner_patient,
    )
    restore_payload = {"report_id": str(report_id), "version": 1, "create_backup": True}

    for allowed_user in (report_subjects.owner_doctor, report_subjects.admin):
        with auth_switcher.as_user(allowed_user):
            history_response = client.get(f"/api/v2/enhanced-reports/reports/{report_id}/history")
            restore_response = client.post(
                f"/api/v2/enhanced-reports/reports/{report_id}/restore",
                json=restore_payload,
            )

        assert history_response.status_code == status.HTTP_200_OK
        assert restore_response.status_code == status.HTTP_200_OK

    with auth_switcher.as_user(report_subjects.foreign_doctor):
        foreign_history = client.get(f"/api/v2/enhanced-reports/reports/{report_id}/history")
        foreign_restore = client.post(
            f"/api/v2/enhanced-reports/reports/{report_id}/restore",
            json=restore_payload,
        )

    _assert_generic_denial(
        foreign_history,
        forbidden_values=[str(report_subjects.owner_patient.id), report_subjects.owner_patient.name],
    )
    _assert_generic_denial(
        foreign_restore,
        forbidden_values=[str(report_subjects.owner_patient.id), report_subjects.owner_patient.name],
    )


def test_export_status_and_download_enforce_owner_and_hide_private_urls(
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
    )

    for allowed_user in (report_subjects.owner_doctor, report_subjects.admin):
        with auth_switcher.as_user(allowed_user):
            status_response = client.get(f"/api/v2/enhanced-reports/export/{export_id}")
            download_response = client.get(
                f"/api/v2/enhanced-reports/export/{export_id}/download?format=pdf"
            )

        assert status_response.status_code == status.HTTP_200_OK
        assert download_response.status_code == status.HTTP_200_OK
        assert "application/pdf" in download_response.headers["content-type"]

    with auth_switcher.as_user(report_subjects.foreign_doctor):
        foreign_status = client.get(f"/api/v2/enhanced-reports/export/{export_id}")

    _assert_generic_denial(
        foreign_status,
        forbidden_values=[str(report_subjects.owner_patient.id), report_subjects.owner_patient.name],
    )

    private_export_id = uuid4()
    _seed_export(
        report_cache,
        export_id=private_export_id,
        report_id=report_id,
        owner=report_subjects.owner_doctor,
        download_urls={"pdf": PRIVATE_DOWNLOAD_URL},
    )

    with auth_switcher.as_user(report_subjects.foreign_doctor):
        private_download_probe = client.get(
            f"/api/v2/enhanced-reports/export/{private_export_id}/download?format=pdf"
        )

    _assert_generic_denial(
        private_download_probe,
        forbidden_values=[PRIVATE_DOWNLOAD_URL, str(report_subjects.owner_patient.id)],
    )
    assert private_download_probe.history == []
    assert "location" not in {header.lower() for header in private_download_probe.headers}

    missing_raw_export_id = uuid4()
    _seed_export(
        report_cache,
        export_id=missing_raw_export_id,
        report_id=None,
        owner=None,
        include_owner=False,
        include_report_id=False,
    )

    with auth_switcher.as_user(report_subjects.owner_doctor):
        missing_raw_status = client.get(f"/api/v2/enhanced-reports/export/{missing_raw_export_id}")
        missing_raw_download = client.get(
            f"/api/v2/enhanced-reports/export/{missing_raw_export_id}/download?format=pdf"
        )

    _assert_generic_denial(missing_raw_status)
    _assert_generic_denial(missing_raw_download)


def test_unknown_export_id_returns_generic_not_found(
    client,
    report_cache: AsyncInMemoryRedis,
    auth_switcher: AuthSwitcher,
    report_subjects: SimpleNamespace,
    fake_enhanced_service: FakeEnhancedReportsService,
):
    _ = report_cache, fake_enhanced_service
    unknown_export_id = uuid4()

    with auth_switcher.as_user(report_subjects.owner_doctor):
        response = client.get(f"/api/v2/enhanced-reports/export/{unknown_export_id}")

    _assert_generic_denial(response)
