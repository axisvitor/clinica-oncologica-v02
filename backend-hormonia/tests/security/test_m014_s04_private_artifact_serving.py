"""Proof for M014/S04 private legacy artifact download hardening.

Legacy upload rows can point at active-looking files that predate upload-time XSS
rejection.  The authenticated owner/admin download route must keep continuity by
serving those bytes, but only as non-executable attachments with path-safe
failure and scanner diagnostics.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, status
from sqlalchemy import text

from app.api.v2.routers.upload import config as upload_config
from app.api.v2.routers.upload import handlers as upload_handlers
from app.api.v2.routers.upload import storage as upload_storage
from app.api.v2.routers.upload.security import scan_file_security, scan_virus
from app.dependencies import RequestContext, get_request_context
from app.dependencies.auth_dependencies import (
    get_current_user,
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_optional_user,
    get_permissions_for_role,
)
from app.main import app
from app.models.upload import Upload
from app.models.user import User, UserRole
from app.services.file_security import FileSecurityService
from app.services.mime_validator import MimeTypeValidator
from app.services.virus_scanner import ScanResult
from app.utils.security import get_password_hash


ACTIVE_HTML_BYTES = b"<!doctype html><html><script>alert('legacy')</script></html>"
ACTIVE_SVG_BYTES = b"<svg><script>alert('legacy')</script></svg>"
UNKNOWN_BYTES = b"legacy bytes with no reliable MIME metadata"

AUTH_OVERRIDE_DEPENDENCIES = (
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_current_user,
    get_optional_user,
    get_request_context,
)


def _download_path(upload_id) -> str:
    return f"/api/v2/upload/{upload_id}/download"


def _role_value(user: User) -> str:
    role = user.role
    return role.value if hasattr(role, "value") else str(role)


def _session_payload(user: User) -> dict:
    role = _role_value(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
        "is_active": user.is_active,
        "firebase_uid": user.firebase_uid,
        "permissions": get_permissions_for_role(role),
    }


def _assert_no_private_leak(response, *, private_bytes: bytes, forbidden_terms=()) -> None:
    assert private_bytes not in response.content
    body = response.text.lower()
    assert "traceback" not in body
    assert "script" not in body
    for term in forbidden_terms:
        assert str(term).lower() not in body


def _assert_attachment_headers(response) -> None:
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert response.headers["content-disposition"].lower().startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def _assert_path_safe_records(caplog, *, private_path) -> None:
    log_text = "\n".join(str(record.__dict__) for record in caplog.records).lower()
    assert str(private_path).lower() not in log_text
    assert private_path.name.lower() not in log_text
    assert "traceback" not in log_text


@pytest.fixture(autouse=True)
def upload_table_schema_guard(db_session):
    """Keep route tests independent of older local placeholder upload schemas."""

    bind = db_session.get_bind()
    if bind.dialect.name != "postgresql":
        return

    ddl_statements = [
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS file_name VARCHAR(500)",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS file_size INTEGER",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS file_type VARCHAR(100)",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS storage_path VARCHAR(1000)",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS storage_provider VARCHAR(50) DEFAULT 'local'",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS file_metadata JSONB DEFAULT '{}'::jsonb",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT false",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS virus_scanned BOOLEAN DEFAULT false",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS virus_clean BOOLEAN",
        "ALTER TABLE uploads ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
        "UPDATE uploads SET storage_provider = 'local' WHERE storage_provider IS NULL",
        "UPDATE uploads SET is_public = false WHERE is_public IS NULL",
        "UPDATE uploads SET virus_scanned = false WHERE virus_scanned IS NULL",
    ]
    for statement in ddl_statements:
        db_session.execute(text(statement))
    db_session.flush()


@pytest.fixture
def temp_upload_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Point upload storage and /uploads StaticFiles at the public-only root."""

    root = tmp_path / "uploads"
    root.mkdir()

    monkeypatch.setattr(upload_config, "UPLOAD_DIR", root)
    monkeypatch.setattr(upload_storage, "UPLOAD_DIR", root)
    monkeypatch.setattr(upload_handlers, "UPLOAD_DIR", root)

    public_root = upload_config.get_public_upload_root(create=True)
    for route in app.routes:
        if getattr(route, "path", "") == "/uploads":
            static_files = route.app
            monkeypatch.setattr(static_files, "directory", str(public_root), raising=False)
            monkeypatch.setattr(static_files, "all_directories", [str(public_root)], raising=False)
            monkeypatch.setattr(static_files, "config_checked", False, raising=False)
            break

    return root


@pytest.fixture
def auth_context(client):
    """Switch auth dependency overrides between users and anonymous."""

    def as_user(user: User):
        session = _session_payload(user)
        session_id = f"m014-s04-private-artifact-{user.id}"
        role = _role_value(user)

        async def _override_session(request: Request):
            request.state.user_id = session["id"]
            request.state.user_role = role
            request.state.session_id = session_id
            return session

        async def _override_current_user(request: Request):
            request.state.user = user
            request.state.user_id = str(user.id)
            request.state.user_role = role
            request.state.session_id = session_id
            return user

        async def _override_current_user_object():
            return user

        async def _override_optional_user(credentials=None, services=None):
            return user

        async def _override_request_context(request: Request):
            return RequestContext(
                ip_address="127.0.0.1",
                user_agent="pytest-m014-s04-private-artifact",
                user_id=user.id,
                session_id=session_id,
            )

        app.dependency_overrides[get_current_user_from_session] = _override_session
        app.dependency_overrides[get_current_user_object_from_session] = _override_current_user_object
        app.dependency_overrides[get_current_user] = _override_current_user
        app.dependency_overrides[get_optional_user] = _override_optional_user
        app.dependency_overrides[get_request_context] = _override_request_context
        client.headers["Authorization"] = f"Bearer m014-s04-private-artifact-{user.id}"
        client.headers["X-Session-ID"] = session_id

    def clear():
        for dependency in AUTH_OVERRIDE_DEPENDENCIES:
            app.dependency_overrides.pop(dependency, None)
        client.headers.pop("Authorization", None)
        client.headers.pop("X-Session-ID", None)

    return SimpleNamespace(as_user=as_user, clear=clear)


@pytest.fixture
def other_doctor_user(db_session) -> User:
    doctor = User(
        id=uuid4(),
        email="m014-private-foreign@example.com",
        firebase_uid="M014PRIVATEFOREIGN123456789012",
        hashed_password=get_password_hash("doctorpass123"),
        full_name="M014 Foreign Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


@pytest.fixture
def admin_user(db_session) -> User:
    admin = User(
        id=uuid4(),
        email="m014-private-admin@example.com",
        firebase_uid="M014PRIVATEADMIN1234567890123",
        hashed_password=get_password_hash("adminpass123"),
        full_name="M014 Private Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _seed_private_upload(
    db_session,
    upload_root,
    owner: User,
    *,
    storage_path: str,
    content: bytes,
    file_name: str,
    file_type: str | None,
) -> Upload:
    file_path = upload_root / storage_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)

    upload = Upload(
        id=uuid4(),
        user_id=owner.id,
        file_name=file_name,
        file_size=len(content),
        file_type=file_type,
        storage_path=storage_path,
        storage_provider="local",
        content_hash=hashlib.sha256(content).hexdigest(),
        file_metadata={"category": "document"},
        is_public=False,
        virus_scanned=True,
        virus_clean=True,
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    return upload


@pytest.mark.parametrize(
    ("storage_path", "file_name", "file_type", "content"),
    [
        ("legacy/html-report.html", "patient-report.html", "text/html", ACTIVE_HTML_BYTES),
        ("legacy/vector.svg", "diagram.svg", "image/svg+xml", ACTIVE_SVG_BYTES),
        ("legacy/unknown-download", "unknown-download", "application/x-legacy-unknown", UNKNOWN_BYTES),
        ("legacy/malicious-name.html", 'bad"\r\nX-Evil: yes.html', "text/html", ACTIVE_HTML_BYTES),
    ],
)
def test_owner_receives_legacy_active_or_unknown_private_artifacts_only_as_attachment(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    test_user_obj,
    storage_path: str,
    file_name: str,
    file_type: str | None,
    content: bytes,
):
    upload = _seed_private_upload(
        db_session,
        temp_upload_root,
        test_user_obj,
        storage_path=storage_path,
        content=content,
        file_name=file_name,
        file_type=file_type,
    )

    auth_context.as_user(test_user_obj)
    response = client.get(_download_path(upload.id))

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.content == content
    _assert_attachment_headers(response)
    disposition = response.headers["content-disposition"].lower()
    assert "x-evil" not in disposition
    assert "patient-report" not in disposition
    assert "bad_" not in disposition
    assert "yes.html" not in disposition


def test_admin_receives_legacy_active_private_artifact_only_as_attachment(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    test_user_obj,
    admin_user,
):
    upload = _seed_private_upload(
        db_session,
        temp_upload_root,
        test_user_obj,
        storage_path="legacy/admin-report.html",
        content=ACTIVE_HTML_BYTES,
        file_name="admin-visible-report.html",
        file_type="text/html",
    )

    auth_context.as_user(admin_user)
    response = client.get(_download_path(upload.id))

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.content == ACTIVE_HTML_BYTES
    _assert_attachment_headers(response)


def test_anonymous_and_foreign_download_denials_do_not_expose_private_bytes_or_paths(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    test_user_obj,
    other_doctor_user,
    monkeypatch: pytest.MonkeyPatch,
):
    storage_path = "legacy/denied-active.html"
    upload = _seed_private_upload(
        db_session,
        temp_upload_root,
        test_user_obj,
        storage_path=storage_path,
        content=ACTIVE_HTML_BYTES,
        file_name="denied-active.html",
        file_type="text/html",
    )
    download_url = _download_path(upload.id)

    auth_context.clear()
    anonymous_response = client.get(download_url)
    assert anonymous_response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    }
    _assert_no_private_leak(
        anonymous_response,
        private_bytes=ACTIVE_HTML_BYTES,
        forbidden_terms=(str(temp_upload_root), storage_path),
    )

    def _fail_if_storage_is_resolved(*args, **kwargs):
        raise AssertionError("foreign owner should be rejected before file IO")

    monkeypatch.setattr(upload_handlers, "resolve_local_upload_path", _fail_if_storage_is_resolved)
    auth_context.as_user(other_doctor_user)
    foreign_response = client.get(download_url)

    assert foreign_response.status_code == status.HTTP_403_FORBIDDEN
    _assert_no_private_leak(
        foreign_response,
        private_bytes=ACTIVE_HTML_BYTES,
        forbidden_terms=(str(temp_upload_root), storage_path),
    )


@pytest.mark.asyncio
async def test_file_security_denial_logs_exclude_tmp_private_paths_and_keep_safe_metadata(
    tmp_path,
    caplog,
):
    private_path = tmp_path / ".uploads_private" / "legacy-active.html"
    private_path.parent.mkdir(parents=True)
    private_path.write_bytes(ACTIVE_HTML_BYTES)

    with caplog.at_level("ERROR"):
        with pytest.raises(HTTPException):
            await scan_file_security(private_path)

    denial_records = [
        record
        for record in caplog.records
        if record.getMessage() == "File security threats detected"
        and record.name == "app.api.v2.routers.upload.security"
    ]
    assert denial_records
    _assert_path_safe_records(caplog, private_path=private_path)
    for record in denial_records:
        assert getattr(record, "extension") == ".html"
        assert getattr(record, "status") == status.HTTP_400_BAD_REQUEST
        assert getattr(record, "scan_time_ms") >= 0
        assert getattr(record, "reason")


@pytest.mark.asyncio
async def test_virus_denial_logs_exclude_tmp_private_paths_and_keep_scanner_metadata(
    tmp_path,
    caplog,
    monkeypatch: pytest.MonkeyPatch,
):
    private_path = tmp_path / ".uploads_private" / "infected.bin"
    private_path.parent.mkdir(parents=True)
    private_path.write_bytes(b"EICAR")

    class FakeScanner:
        async def scan_file(self, path):
            return ScanResult(
                clean=False,
                threat_found="Eicar-Test-Signature",
                scanner_used="fake-clamav",
                scan_time_ms=7,
            )

    import app.services.virus_scanner as virus_scanner_module

    monkeypatch.setattr(virus_scanner_module, "get_virus_scanner", lambda: FakeScanner())

    with caplog.at_level("ERROR"):
        with pytest.raises(HTTPException):
            await scan_virus(private_path)

    denial_records = [record for record in caplog.records if record.getMessage() == "Virus detected in uploaded file"]
    assert denial_records
    _assert_path_safe_records(caplog, private_path=private_path)
    for record in denial_records:
        assert getattr(record, "extension") == ".bin"
        assert getattr(record, "scanner") == "fake-clamav"
        assert getattr(record, "status") == status.HTTP_400_BAD_REQUEST
        assert getattr(record, "scan_time_ms") == 7
        assert getattr(record, "reason") == "malware_detected"


@pytest.mark.asyncio
async def test_mime_validator_denial_logs_exclude_tmp_private_paths_and_keep_safe_metadata(
    tmp_path,
    caplog,
    monkeypatch: pytest.MonkeyPatch,
):
    private_path = tmp_path / ".uploads_private" / "spoofed.pdf"
    private_path.parent.mkdir(parents=True)
    private_path.write_bytes(b"MZ executable bytes")
    validator = MimeTypeValidator(enabled=True)
    validator._magic_available = True
    validator.magic = SimpleNamespace(from_file=lambda *args, **kwargs: "application/x-msdownload")

    with caplog.at_level("ERROR"):
        result = await validator.validate_file(private_path, "application/pdf")

    assert result.is_valid is False
    denial_records = [record for record in caplog.records if record.getMessage() == "Dangerous MIME type detected"]
    assert denial_records
    _assert_path_safe_records(caplog, private_path=private_path)
    for record in denial_records:
        assert getattr(record, "extension") == ".pdf"
        assert getattr(record, "status") == status.HTTP_400_BAD_REQUEST
        assert getattr(record, "reason") == "dangerous_mime"
        assert getattr(record, "actual_mime") == "application/x-msdownload"


@pytest.mark.asyncio
async def test_file_security_service_logs_are_path_safe_for_direct_scans(tmp_path, caplog):
    private_path = tmp_path / ".uploads_private" / "direct-active.svg"
    private_path.parent.mkdir(parents=True)
    private_path.write_bytes(ACTIVE_SVG_BYTES)
    scanner = FileSecurityService(enabled=True)

    with caplog.at_level("ERROR"):
        result = await scanner.scan_file(private_path)

    assert result.is_safe is False
    service_records = [record for record in caplog.records if record.getMessage() == "File security threats detected"]
    assert service_records
    _assert_path_safe_records(caplog, private_path=private_path)
    for record in service_records:
        assert getattr(record, "extension") == ".svg"
        assert getattr(record, "status") == "denied"
        assert getattr(record, "scan_time_ms") >= 0
