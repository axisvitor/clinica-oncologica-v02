from __future__ import annotations

import os
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest

from app.config.settings import Settings
from app.dependencies.auth_dependencies import _get_user_from_db_by_session
from app.dependencies.auth_session_contract import resolve_request_session_id
from app.utils import security as security_utils
from app.utils.timezone import now_sao_paulo


class _TokenSettings:
    SECURITY_SECRET_KEY = "m014-synthetic-secret-key-not-real-48-bytes-minimum"
    SECURITY_ALGORITHM = "HS256"
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = 30
    AUTH_REFRESH_TOKEN_EXPIRE_DAYS = 7


def _strong_secret(prefix: str) -> str:
    # Synthetic deterministic-looking values are enough for posture tests and are not deployable secrets.
    return f"{prefix}-A7f3K9m2Q8r5T1v6W4x0YzB2cD4eF6gH8iJ0kL2mN4pQ6rS8tU"


def _production_env(**overrides: str) -> dict[str, str]:
    env = {
        "APP_ENVIRONMENT": "production",
        "APP_ENABLE_DEBUG": "false",
        "ALLOW_AI_SIMULATION": "false",
        "SESSION_ENABLE_COOKIE_SECURE": "true",
        "SESSION_ENABLE_COOKIE_HTTPONLY": "true",
        "SESSION_COOKIE_SAMESITE": "lax",
        "SECURITY_ENABLE_SSL_REDIRECT": "true",
        "SECURITY_SECRET_KEY": _strong_secret("security"),
        "SECURITY_CSRF_SECRET_KEY": _strong_secret("csrf"),
        "ENCRYPTION_KEY_CURRENT": _strong_secret("fernet"),
        "PHI_ENCRYPTION_KEY": _strong_secret("phi"),
        "HASH_SALT": _strong_secret("salt"),
        "DATABASE_URL": "postgresql+psycopg://user:pass@db.example.invalid/app?sslmode=require&sslminversion=TLSv1.2",
        "REDIS_URL": "redis://localhost:6379/0",
        "FIREBASE_ADMIN_PROJECT_ID": "synthetic-project",
        "FIREBASE_ADMIN_PRIVATE_KEY": "synthetic-private-key",
        "FIREBASE_ADMIN_CLIENT_EMAIL": "synthetic@example.invalid",
        "WHATSAPP_WUZAPI_TOKEN": _strong_secret("wuzapi"),
        "WHATSAPP_WUZAPI_WEBHOOK_SECRET": _strong_secret("webhook"),
        "AI_GEMINI_API_KEY": _strong_secret("gemini"),
    }
    env.update(overrides)
    return env


def test_jwt_verification_requires_signature_type_subject_and_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security_utils, "_settings_cache", _TokenSettings())

    access_token = security_utils.create_access_token({"sub": "doctor@example.invalid"})

    token_data = security_utils.verify_token(access_token, token_type="access")
    assert token_data is not None
    assert token_data.email == "doctor@example.invalid"
    assert security_utils.verify_token(access_token, token_type="refresh") is None

    expired_token = jwt.encode(
        {
            "sub": "doctor@example.invalid",
            "type": "access",
            "exp": int((now_sao_paulo() - timedelta(minutes=1)).timestamp()),
        },
        _TokenSettings.SECURITY_SECRET_KEY,
        algorithm=_TokenSettings.SECURITY_ALGORITHM,
    )
    assert security_utils.verify_token(expired_token, token_type="access") is None

    wrong_signature_token = jwt.encode(
        {
            "sub": "doctor@example.invalid",
            "type": "access",
            "exp": int((now_sao_paulo() + timedelta(minutes=5)).timestamp()),
        },
        "different-synthetic-signing-key",
        algorithm=_TokenSettings.SECURITY_ALGORITHM,
    )
    assert security_utils.verify_token(wrong_signature_token, token_type="access") is None

    missing_subject_token = jwt.encode(
        {
            "type": "access",
            "exp": int((now_sao_paulo() + timedelta(minutes=5)).timestamp()),
        },
        _TokenSettings.SECURITY_SECRET_KEY,
        algorithm=_TokenSettings.SECURITY_ALGORITHM,
    )
    assert security_utils.verify_token(missing_subject_token, token_type="access") is None


def test_staff_session_resolution_rejects_legacy_bearer_and_x_session_transports() -> None:
    session_id, source = resolve_request_session_id(
        session_cookie_id=None,
        x_session_id="legacy-session-id",
        authorization="Bearer jwt-like-token-value",
    )

    assert session_id is None
    assert source is None

    cookie_session_id, cookie_source = resolve_request_session_id(
        session_cookie_id="cookie-session-id",
        x_session_id="legacy-session-id",
        authorization="Bearer jwt-like-token-value",
    )

    assert cookie_session_id == "cookie-session-id"
    assert cookie_source == "cookie"


@pytest.mark.asyncio
async def test_db_session_fallback_filters_revoked_inactive_and_expired_sessions() -> None:
    class _Result:
        def scalar_one_or_none(self):
            return sentinel_user

    class _CaptureSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return _Result()

    sentinel_user = SimpleNamespace(id=uuid4())
    session = _CaptureSession()

    result = await _get_user_from_db_by_session(str(uuid4()), session)  # type: ignore[arg-type]

    assert result is sentinel_user
    assert session.statement is not None
    compiled = str(session.statement).lower()
    assert "sessions.is_active is true" in compiled
    assert "sessions.revoked_at is null" in compiled
    assert "sessions.expires_at >" in compiled
    assert "sessions.id =" in compiled


def test_production_default_secret_rejection_does_not_echo_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _production_env()
    env.pop("SECURITY_SECRET_KEY")

    monkeypatch.setattr(security_utils, "_settings_cache", None)
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)

    error_text = str(exc_info.value)
    assert "SECURITY_SECRET_KEY" in error_text
    assert "dev-insecure-secret-key" not in error_text
    assert "must-be-changed" not in error_text
    assert "Current key starts" not in error_text


def test_production_posture_accepts_strong_secrets_and_tls_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security_utils, "_settings_cache", None)
    with patch.dict(os.environ, _production_env(), clear=True):
        settings = Settings(_env_file=None)

    assert settings.APP_ENVIRONMENT == "production"
    assert settings.SESSION_ENABLE_COOKIE_SECURE is True
    assert settings.SECURITY_ENABLE_SSL_REDIRECT is True
    assert "sslmode=require" in settings.DATABASE_URL
    assert "sslminversion=TLSv1.2" in settings.DATABASE_URL
