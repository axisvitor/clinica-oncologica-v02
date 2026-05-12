"""Regression tests for the private upload serving boundary.

These tests intentionally exercise the FastAPI app surface instead of upload helper
functions.  They document the S04 security contract: private files may be stored
locally, but must not be exposed through the public `/uploads` static mount and
must be retrieved only through an authenticated, authorization-checked download
route.
"""

from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy import text

from app.api.v2.routers.upload import handlers as upload_handlers
from app.api.v2.routers.upload import storage as upload_storage
from app.api.v2.routers.upload import config as upload_config
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
from app.utils.security import get_password_hash


PRIVATE_BYTES = b"private clinical upload bytes - never public"
PRIVATE_TEXT = b"owner-only text upload - never public"
# Valid 1x1 RGB PNG; thumbnail generation keeps derivative URL coverage real.
PRIVATE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1Pe"
    "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


AUTH_OVERRIDE_DEPENDENCIES = (
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_current_user,
    get_optional_user,
    get_request_context,
)


def _route_path(method: str, candidates: list[str]) -> str:
    """Return the first registered route among candidates, or the desired path.

    The current app has a legacy double `/upload/upload/` mount.  The test keeps
    using whichever POST/metadata route is registered so URL-prefix drift does
    not hide the private-serving assertions.  The gated download URL remains the
    desired contract path and is asserted exactly.
    """

    for route in app.routes:
        route_methods = getattr(route, "methods", set()) or set()
        route_path = getattr(route, "path", "")
        if method.upper() in route_methods and route_path in candidates:
            return route_path
    return candidates[0]


def _upload_create_path() -> str:
    return _route_path("POST", ["/api/v2/upload/", "/api/v2/upload/upload/"])


def _upload_info_path(upload_id) -> str:
    template = _route_path(
        "GET",
        ["/api/v2/upload/{upload_id}", "/api/v2/upload/upload/{upload_id}"],
    )
    return template.replace("{upload_id}", str(upload_id))


def _download_path(upload_id) -> str:
    return f"/api/v2/upload/{upload_id}/download"


def _role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


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


def _assert_no_public_upload_url(url: str | None) -> None:
    if not url:
        return
    assert not url.startswith("/uploads/"), f"private URL leaked through public mount: {url}"


def _assert_no_private_leak(response, *, private_bytes: bytes, forbidden_terms=()) -> None:
    assert private_bytes not in response.content
    body = response.text.lower()
    assert "traceback" not in body
    for term in forbidden_terms:
        assert str(term).lower() not in body


@pytest.fixture(autouse=True)
def upload_table_schema_guard(db_session):
    """Align local Postgres test schemas with the Upload ORM used by the API.

    Some developer databases still have an older placeholder `uploads` table with
    only `upload_metadata`.  The route contract under test is DB-backed private
    serving, so the setup must fail on auth/storage behavior rather than stale
    local schema shape.  The DDL is transactional under the `db_session` fixture.
    """

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
        "UPDATE uploads SET storage_provider = 'local' WHERE storage_provider IS NULL",
        "UPDATE uploads SET is_public = false WHERE is_public IS NULL",
        "UPDATE uploads SET virus_scanned = false WHERE virus_scanned IS NULL",
    ]
    for statement in ddl_statements:
        db_session.execute(text(statement))
    db_session.flush()


@pytest.fixture(autouse=True)
def disable_expensive_upload_scanners(monkeypatch: pytest.MonkeyPatch):
    """Keep route tests focused on serving/authz, not external scan/quota services."""

    async def _ok(*args, **kwargs):
        return True

    monkeypatch.setattr(upload_handlers, "validate_mime_type", _ok)
    monkeypatch.setattr(upload_handlers, "scan_file_security", _ok)
    monkeypatch.setattr(upload_handlers, "scan_virus", _ok)
    monkeypatch.setattr(upload_handlers, "check_rate_limit", _ok)
    monkeypatch.setattr(upload_handlers, "check_user_quota", _ok)


@pytest.fixture
def temp_upload_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Point upload storage and the `/uploads` StaticFiles mount at tmp_path."""

    root = tmp_path / "uploads"
    root.mkdir()

    monkeypatch.setattr(upload_config, "UPLOAD_DIR", root)
    monkeypatch.setattr(upload_storage, "UPLOAD_DIR", root)
    monkeypatch.setattr(upload_handlers, "UPLOAD_DIR", root)

    for route in app.routes:
        if getattr(route, "path", "") == "/uploads":
            static_files = route.app
            monkeypatch.setattr(static_files, "directory", str(root), raising=False)
            monkeypatch.setattr(
                static_files,
                "all_directories",
                [str(root)],
                raising=False,
            )
            monkeypatch.setattr(static_files, "config_checked", False, raising=False)
            break

    return root


@pytest.fixture
def auth_context(client):
    """Switch the app's auth dependency overrides between users and anonymous."""

    def as_user(user: User):
        session = _session_payload(user)
        session_id = f"private-upload-test-{user.id}"
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
                user_agent="pytest-private-upload-serving",
                user_id=user.id,
                session_id=session_id,
            )

        app.dependency_overrides[get_current_user_from_session] = _override_session
        app.dependency_overrides[get_current_user_object_from_session] = (
            _override_current_user_object
        )
        app.dependency_overrides[get_current_user] = _override_current_user
        app.dependency_overrides[get_optional_user] = _override_optional_user
        app.dependency_overrides[get_request_context] = _override_request_context
        client.headers["Authorization"] = f"Bearer private-upload-test-{user.id}"
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
        email="private-upload-other-doctor@example.com",
        firebase_uid="PRIVATEUPLOADOTHERDOCTOR1234567890",
        hashed_password=get_password_hash("doctorpass123"),
        full_name="Other Private Upload Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _seed_private_upload(
    db_session,
    upload_root,
    owner: User,
    *,
    storage_path: str = "document/private-note.txt",
    content: bytes = PRIVATE_BYTES,
    file_type: str = "text/plain",
) -> Upload:
    file_path = upload_root / storage_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)

    upload = Upload(
        id=uuid4(),
        user_id=owner.id,
        file_name="private-note.txt",
        file_size=len(content),
        file_type=file_type,
        storage_path=storage_path,
        storage_provider="local",
        content_hash=hashlib.sha256(content).hexdigest(),
        file_metadata={"category": "text"},
        is_public=False,
        virus_scanned=True,
        virus_clean=True,
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    return upload


def test_private_upload_defaults_to_gated_urls_and_never_public_derivatives(
    client,
    temp_upload_root,
    auth_context,
    test_doctor_user,
):
    auth_context.as_user(test_doctor_user)

    response = client.post(
        f"{_upload_create_path()}?scan_virus=false&generate_thumbnail=true",
        files={"file": ("private-image.png", PRIVATE_PNG, "image/png")},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    expected_download_url = _download_path(payload["id"])

    assert payload["is_public"] is False
    assert payload["download_url"] == expected_download_url
    _assert_no_public_upload_url(payload.get("url"))

    processing = payload.get("processing") or {}
    for key in ("thumbnail_url", "preview_url", "resized_url"):
        derivative_url = processing.get(key)
        _assert_no_public_upload_url(derivative_url)
        if derivative_url:
            assert derivative_url.startswith("/api/v2/upload/")


def test_private_upload_storage_path_is_not_publicly_served(
    client,
    temp_upload_root,
    auth_context,
    test_doctor_user,
):
    auth_context.as_user(test_doctor_user)

    response = client.post(
        f"{_upload_create_path()}?scan_virus=false",
        files={"file": ("private-note.txt", PRIVATE_TEXT, "text/plain")},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["is_public"] is False

    auth_context.clear()
    static_response = client.get(f"/uploads/{payload['storage_path']}")

    assert static_response.status_code in {403, 404}
    _assert_no_private_leak(
        static_response,
        private_bytes=PRIVATE_TEXT,
        forbidden_terms=(str(temp_upload_root), payload["storage_path"]),
    )


def test_gated_download_authorizes_owner_admin_and_rejects_anonymous_foreign_user(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    test_doctor_user,
    other_doctor_user,
    test_admin_user,
):
    upload = _seed_private_upload(db_session, temp_upload_root, test_doctor_user)
    download_url = _download_path(upload.id)

    auth_context.clear()
    anonymous_response = client.get(download_url)
    assert anonymous_response.status_code in {401, 403, 404}
    _assert_no_private_leak(anonymous_response, private_bytes=PRIVATE_BYTES)

    auth_context.as_user(test_doctor_user)
    owner_response = client.get(download_url)
    assert owner_response.status_code == 200, owner_response.text
    assert owner_response.content == PRIVATE_BYTES
    assert owner_response.headers["content-type"].startswith("text/plain")

    auth_context.as_user(other_doctor_user)
    foreign_response = client.get(download_url)
    assert foreign_response.status_code == 403
    _assert_no_private_leak(foreign_response, private_bytes=PRIVATE_BYTES)

    auth_context.as_user(test_admin_user)
    admin_response = client.get(download_url)
    assert admin_response.status_code == 200, admin_response.text
    assert admin_response.content == PRIVATE_BYTES


def test_private_upload_metadata_cache_miss_uses_database_without_public_url(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    test_doctor_user,
):
    upload = _seed_private_upload(db_session, temp_upload_root, test_doctor_user)
    auth_context.as_user(test_doctor_user)

    response = client.get(_upload_info_path(upload.id))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == str(upload.id)
    assert payload["is_public"] is False
    assert payload["download_url"] == _download_path(upload.id)
    _assert_no_public_upload_url(payload.get("url"))


def test_missing_upload_id_returns_generic_not_found_without_filesystem_details(
    client,
    temp_upload_root,
    auth_context,
    test_doctor_user,
):
    auth_context.as_user(test_doctor_user)

    response = client.get(_download_path(uuid4()))

    assert response.status_code == 404
    _assert_no_private_leak(
        response,
        private_bytes=PRIVATE_BYTES,
        forbidden_terms=(str(temp_upload_root), "private-note.txt"),
    )


@pytest.mark.parametrize("storage_path_builder", ["relative_escape", "absolute"])
def test_unsafe_persisted_storage_path_fails_closed_without_private_bytes_or_paths(
    client,
    db_session,
    tmp_path,
    temp_upload_root,
    auth_context,
    test_doctor_user,
    storage_path_builder,
):
    outside_secret = tmp_path / f"outside-{storage_path_builder}.txt"
    outside_secret.write_bytes(PRIVATE_BYTES)

    if storage_path_builder == "relative_escape":
        storage_path = f"../{outside_secret.name}"
    else:
        storage_path = str(outside_secret)

    upload = Upload(
        id=uuid4(),
        user_id=test_doctor_user.id,
        file_name="private-note.txt",
        file_size=len(PRIVATE_BYTES),
        file_type="text/plain",
        storage_path=storage_path,
        storage_provider="local",
        content_hash=hashlib.sha256(PRIVATE_BYTES).hexdigest(),
        file_metadata={"category": "text"},
        is_public=False,
        virus_scanned=True,
        virus_clean=True,
    )
    db_session.add(upload)
    db_session.commit()

    auth_context.as_user(test_doctor_user)
    response = client.get(_download_path(upload.id))

    assert response.status_code in {400, 403, 404}
    _assert_no_private_leak(
        response,
        private_bytes=PRIVATE_BYTES,
        forbidden_terms=(str(temp_upload_root), str(outside_secret), storage_path),
    )
