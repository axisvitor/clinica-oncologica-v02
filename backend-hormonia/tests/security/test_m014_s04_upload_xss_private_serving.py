"""Route-level proof for M014/S04 upload XSS ingress hardening.

These tests exercise the FastAPI surfaces that can persist attacker-controlled
bytes.  They assert active HTML/SVG/script upload shapes are rejected before any
DB row, storage file, cache metadata, or avatar URL side effect is created.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest
from fastapi import Request, status
from sqlalchemy import text

from app.api.v2.routers.upload import config as upload_config
from app.api.v2.routers.upload import handlers as upload_handlers
from app.api.v2.routers.upload import storage as upload_storage
from app.dependencies import RequestContext, get_request_context
from app.dependencies.auth_dependencies import (
    get_current_user,
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_optional_user,
    get_permissions_for_role,
)
from app.main import app
from app.middleware.csrf import get_csrf_token
from app.models.upload import Upload
from app.models.user import User


SAFE_PNG = base64.b64decode(
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
    for route in app.routes:
        route_methods = getattr(route, "methods", set()) or set()
        route_path = getattr(route, "path", "")
        if method.upper() in route_methods and route_path in candidates:
            return route_path
    return candidates[0]


def _upload_create_path() -> str:
    return _route_path("POST", ["/api/v2/upload/", "/api/v2/upload/upload/"])


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


def _file_snapshot(root) -> set[str]:
    return {
        path.relative_to(root.parent).as_posix()
        for path in root.parent.rglob("*")
        if path.is_file()
    }


def _assert_denial_body_is_safe(response, *, payload: bytes, upload_root, filename: str | None = None) -> None:
    if payload:
        assert payload not in response.content
    body = response.text.lower()
    assert "traceback" not in body
    assert str(upload_root).lower() not in body
    assert str(upload_root.parent).lower() not in body
    if filename:
        assert filename.lower() not in body


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


@pytest.fixture(autouse=True)
def disable_expensive_upload_scanners(monkeypatch: pytest.MonkeyPatch):
    """Keep ingress tests focused on active-content denial, not external services."""

    async def _ok(*args, **kwargs):
        return True

    monkeypatch.setattr(upload_handlers, "validate_mime_type", _ok)
    monkeypatch.setattr(upload_handlers, "scan_file_security", _ok)
    monkeypatch.setattr(upload_handlers, "scan_virus", _ok)
    monkeypatch.setattr(upload_handlers, "check_rate_limit", _ok)
    monkeypatch.setattr(upload_handlers, "check_user_quota", _ok)


@pytest.fixture
def redis_spy(monkeypatch: pytest.MonkeyPatch):
    class RedisSpy:
        def __init__(self):
            self.setex_calls: list[tuple] = []
            self.delete_calls: list[tuple] = []

        async def setex(self, *args):
            self.setex_calls.append(args)

        async def delete(self, *args):
            self.delete_calls.append(args)

    spy = RedisSpy()

    async def _get_redis_client():
        return spy

    monkeypatch.setattr(upload_handlers, "get_redis_client", _get_redis_client)
    return spy


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
    """Switch auth dependency overrides between a concrete user and anonymous."""

    def as_user(user: User):
        session = _session_payload(user)
        session_id = f"m014-s04-upload-xss-{user.id}"
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
                user_agent="pytest-m014-s04-upload-xss",
                user_id=user.id,
                session_id=session_id,
            )

        app.dependency_overrides[get_current_user_from_session] = _override_session
        app.dependency_overrides[get_current_user_object_from_session] = _override_current_user_object
        app.dependency_overrides[get_current_user] = _override_current_user
        app.dependency_overrides[get_optional_user] = _override_optional_user
        app.dependency_overrides[get_request_context] = _override_request_context
        client.headers["Authorization"] = f"Bearer m014-s04-upload-xss-{user.id}"
        client.headers["X-Session-ID"] = session_id
        csrf_token = get_csrf_token()
        client.headers["X-CSRF-Token"] = csrf_token
        client.headers["Cookie"] = f"csrf_token={csrf_token}"

    def clear():
        for dependency in AUTH_OVERRIDE_DEPENDENCIES:
            app.dependency_overrides.pop(dependency, None)
        client.headers.pop("Authorization", None)
        client.headers.pop("X-Session-ID", None)
        client.headers.pop("X-CSRF-Token", None)
        client.headers.pop("Cookie", None)

    return SimpleNamespace(as_user=as_user, clear=clear)


@pytest.mark.parametrize(
    ("filename", "payload", "content_type"),
    [
        ("spoofed-svg.png", b"<svg><script>alert(1)</script></svg>", "image/png"),
        ("clinical-note.txt", b"clinical note\n<script>alert(1)</script>", "text/plain"),
        ("diagram.svg", b"not even markup", "image/png"),
        ("payload.html", b"<!doctype html><title>xss</title>", "text/plain"),
    ],
)
def test_upload_active_content_denied_before_db_storage_cache_or_url_side_effects(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    redis_spy,
    test_user_obj,
    caplog,
    filename: str,
    payload: bytes,
    content_type: str,
):
    auth_context.as_user(test_user_obj)
    rows_before = db_session.query(Upload).count()
    files_before = _file_snapshot(temp_upload_root)

    with caplog.at_level("WARNING"):
        response = client.post(
            f"{_upload_create_path()}?scan_virus=false",
            files={"file": (filename, payload, content_type)},
        )

    assert response.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE}
    assert response.json()["detail"] == "File type is not allowed for security reasons"
    _assert_denial_body_is_safe(response, payload=payload, upload_root=temp_upload_root, filename=filename)

    db_session.expire_all()
    assert db_session.query(Upload).count() == rows_before
    assert _file_snapshot(temp_upload_root) == files_before
    assert redis_spy.setex_calls == []

    denial_records = [record for record in caplog.records if record.getMessage() == "upload_active_content_denied"]
    assert denial_records
    for record in denial_records:
        assert getattr(record, "upload_id")
        assert getattr(record, "user_id") == str(test_user_obj.id)
        assert getattr(record, "reason")
        assert getattr(record, "status") in {status.HTTP_400_BAD_REQUEST, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE}
        assert hasattr(record, "duration_ms")
        log_text = str(record.__dict__).lower()
        assert payload.decode("latin-1", errors="ignore").lower() not in log_text
        assert str(temp_upload_root).lower() not in log_text
        assert filename.lower() not in log_text


def test_upload_missing_file_returns_validation_error_without_side_effects(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    redis_spy,
    test_user_obj,
):
    auth_context.as_user(test_user_obj)
    rows_before = db_session.query(Upload).count()
    files_before = _file_snapshot(temp_upload_root)

    response = client.post(f"{_upload_create_path()}?scan_virus=false")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    _assert_denial_body_is_safe(response, payload=b"", upload_root=temp_upload_root)
    db_session.expire_all()
    assert db_session.query(Upload).count() == rows_before
    assert _file_snapshot(temp_upload_root) == files_before
    assert redis_spy.setex_calls == []


def test_safe_png_upload_still_persists_through_intended_private_route(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    test_user_obj,
):
    auth_context.as_user(test_user_obj)
    rows_before = db_session.query(Upload).count()

    response = client.post(
        f"{_upload_create_path()}?scan_virus=false",
        files={"file": ("avatar-control.png", SAFE_PNG, "image/png")},
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    payload = response.json()
    assert payload["is_public"] is False
    assert payload["url"] == payload["download_url"]
    assert payload["url"].startswith("/api/v2/upload/")
    assert not payload["url"].startswith("/uploads/")

    db_session.expire_all()
    assert db_session.query(Upload).count() == rows_before + 1
    stored = db_session.query(Upload).filter(Upload.id == payload["id"]).one()
    assert stored.storage_path.startswith("private/")
    stored_path = upload_config.resolve_local_upload_path(stored.storage_path, public=False, require_exists=True).path
    assert stored_path.read_bytes() == SAFE_PNG


def test_avatar_spoofed_active_content_denied_before_file_or_user_update(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    test_user_obj,
    caplog,
):
    original_avatar_url = "/uploads/avatars/original-safe.png"
    if hasattr(test_user_obj, "set_avatar_url"):
        test_user_obj.set_avatar_url(original_avatar_url)
    else:
        test_user_obj.avatar_url = original_avatar_url
    db_session.commit()
    db_session.refresh(test_user_obj)

    auth_context.as_user(test_user_obj)
    payload = b"<svg><script>alert('avatar')</script></svg>"
    files_before = _file_snapshot(temp_upload_root)

    with caplog.at_level("WARNING"):
        response = client.post(
            "/api/v2/auth/avatar",
            files={"file": ("avatar.png", payload, "image/png")},
        )

    assert response.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE}
    assert response.json()["detail"] == "File type is not allowed for security reasons"
    _assert_denial_body_is_safe(response, payload=payload, upload_root=temp_upload_root, filename="avatar.png")
    assert _file_snapshot(temp_upload_root) == files_before

    db_session.refresh(test_user_obj)
    assert test_user_obj.get_avatar_url() == original_avatar_url

    denial_records = [record for record in caplog.records if record.getMessage() == "avatar_active_content_denied"]
    assert denial_records
    for record in denial_records:
        assert getattr(record, "user_id") == str(test_user_obj.id)
        assert getattr(record, "reason")
        assert getattr(record, "status") in {status.HTTP_400_BAD_REQUEST, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE}
        assert hasattr(record, "duration_ms")
        log_text = str(record.__dict__).lower()
        assert "<svg" not in log_text
        assert str(temp_upload_root).lower() not in log_text
        assert "avatar.png" not in log_text


def test_safe_png_avatar_stores_under_public_upload_root_and_updates_user(
    client,
    db_session,
    temp_upload_root,
    auth_context,
    test_user_obj,
):
    original_avatar_url = test_user_obj.get_avatar_url()
    auth_context.as_user(test_user_obj)

    response = client.post(
        "/api/v2/auth/avatar",
        files={"file": ("safe-avatar.png", SAFE_PNG, "image/png")},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    payload = response.json()
    assert payload["success"] is True
    avatar_url = payload["avatar_url"]
    assert avatar_url.startswith("/uploads/avatars/avatar_")
    assert str(test_user_obj.id) not in avatar_url

    public_root = upload_config.get_public_upload_root(create=False)
    stored_file = public_root / avatar_url.removeprefix("/uploads/")
    assert stored_file.is_file()
    assert stored_file.read_bytes() == SAFE_PNG
    assert stored_file.parent == public_root / "avatars"
    assert not (temp_upload_root / "avatars" / stored_file.name).exists()

    db_session.refresh(test_user_obj)
    assert test_user_obj.get_avatar_url() == avatar_url
    assert test_user_obj.get_avatar_url() != original_avatar_url
