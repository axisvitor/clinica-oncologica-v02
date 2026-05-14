from __future__ import annotations

import logging
import ssl
from types import SimpleNamespace

import pytest

from app.core.database import async_engine
from app.core.database.async_engine import (
    AsyncDatabaseConfigError,
    _prepare_asyncpg_connection_config,
)


class _FakeSSLContext:
    def __init__(self) -> None:
        self.check_hostname = True
        self.verify_mode = ssl.CERT_REQUIRED
        self.cert_chain: tuple[str, str | None] | None = None
        self.minimum_version = None

    def load_cert_chain(self, certfile: str, keyfile: str | None = None) -> None:
        self.cert_chain = (certfile, keyfile)


def _stub_default_context(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_create_default_context(*, cafile: str | None = None, **_: object) -> _FakeSSLContext:
        context = _FakeSSLContext()
        calls.append({"cafile": cafile, "context": context})
        return context

    monkeypatch.setattr(async_engine.ssl_module, "create_default_context", fake_create_default_context)
    return calls


def test_verify_full_loads_ca_keeps_hostname_verification_and_strips_libpq_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stub_default_context(monkeypatch)

    config = _prepare_asyncpg_connection_config(
        "postgresql+psycopg://user:secret@postgres:5432/app"
        "?sslmode=verify-full&sslrootcert=/runtime/ca.crt&sslcert=/runtime/client.crt"
        "&sslkey=/runtime/client.key&sslminversion=TLSv1.2&command_timeout=5"
    )

    assert config.async_url == "postgresql+asyncpg://user:secret@postgres:5432/app?command_timeout=5"
    assert config.sanitized_async_url == "postgresql+asyncpg://user:***@postgres:5432/app?command_timeout=5"
    assert calls[0]["cafile"] == "/runtime/ca.crt"
    context = config.connect_args["ssl"]
    assert isinstance(context, _FakeSSLContext)
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.cert_chain == ("/runtime/client.crt", "/runtime/client.key")
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    assert config.sslmode == "verify-full"
    assert config.tls_enabled is True
    assert config.tls_certificate_verified is True
    assert config.tls_hostname_verified is True
    assert config.client_certificate_configured is True
    assert "sslmode" not in config.async_url
    assert "sslrootcert" not in config.async_url
    assert "sslcert" not in config.async_url
    assert "sslkey" not in config.async_url
    assert "sslminversion" not in config.async_url


def test_verify_ca_loads_ca_but_disables_hostname_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stub_default_context(monkeypatch)

    config = _prepare_asyncpg_connection_config(
        "postgresql+psycopg2://user:secret@postgres/app?sslmode=verify-ca&sslrootcert=/runtime/ca.crt"
    )

    assert config.async_url == "postgresql+asyncpg://user:secret@postgres/app"
    assert calls[0]["cafile"] == "/runtime/ca.crt"
    context = config.connect_args["ssl"]
    assert isinstance(context, _FakeSSLContext)
    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert config.tls_certificate_verified is True
    assert config.tls_hostname_verified is False


def test_require_mode_enables_tls_without_certificate_verification() -> None:
    config = _prepare_asyncpg_connection_config(
        "postgresql://user:secret@postgres/app?sslmode=require&application_name=hormonia"
    )

    assert config.async_url == "postgresql+asyncpg://user:secret@postgres/app?application_name=hormonia"
    context = config.connect_args["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE
    assert config.sslmode == "require"
    assert config.tls_enabled is True
    assert config.tls_certificate_verified is False
    assert config.tls_hostname_verified is False


def test_disable_mode_strips_sslmode_and_creates_no_ssl_context() -> None:
    config = _prepare_asyncpg_connection_config(
        "postgresql://user:secret@postgres/app?sslmode=disable&command_timeout=7"
    )

    assert config.async_url == "postgresql+asyncpg://user:secret@postgres/app?command_timeout=7"
    assert config.connect_args == {}
    assert config.sslmode == "disable"
    assert config.tls_enabled is False


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:super-secret@postgres/app?sslmode=prefer&sslrootcert=/private/ca.crt",
        "postgresql://user:super-secret@postgres/app?sslmode=verify-full",
        "not-a-postgresql-url",
    ],
)
def test_invalid_tls_configuration_fails_closed_without_dsn_secret_or_private_path(database_url: str) -> None:
    with pytest.raises(AsyncDatabaseConfigError) as exc_info:
        _prepare_asyncpg_connection_config(database_url)

    error_text = str(exc_info.value)
    assert "super-secret" not in error_text
    assert "/private/ca.crt" not in error_text
    assert database_url not in error_text


def test_context_construction_failure_is_named_and_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_create_default_context(*, cafile: str | None = None, **_: object) -> _FakeSSLContext:
        raise OSError(f"could not read {cafile} with password=super-secret")

    monkeypatch.setattr(async_engine.ssl_module, "create_default_context", fail_create_default_context)

    with pytest.raises(AsyncDatabaseConfigError) as exc_info:
        _prepare_asyncpg_connection_config(
            "postgresql://user:super-secret@postgres/app?sslmode=verify-full&sslrootcert=/private/ca.crt"
        )

    error_text = str(exc_info.value)
    assert "async_postgres_ssl_context_invalid" in error_text
    assert "super-secret" not in error_text
    assert "/private/ca.crt" not in error_text


def test_engine_initialization_logs_only_sanitized_tls_posture(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_async_engine(url: str, **kwargs: object) -> object:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(
        async_engine,
        "settings",
        SimpleNamespace(
            DATABASE_URL="postgresql://user:super-secret@postgres/app?sslmode=require&sslrootcert=/private/ca.crt",
            APP_ENABLE_DEBUG=False,
        ),
    )
    monkeypatch.setattr(async_engine, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(async_engine, "_async_engine", None)
    monkeypatch.setattr(async_engine, "_async_session_factory", None)

    with caplog.at_level(logging.INFO, logger=async_engine.__name__):
        engine = async_engine.get_async_engine()

    assert engine is not None
    assert captured["url"] == "postgresql+asyncpg://user:super-secret@postgres/app"
    assert "connect_args" in captured["kwargs"]
    log_text = caplog.text
    assert "super-secret" not in log_text
    assert "/private/ca.crt" not in log_text
    assert "postgresql://" not in log_text
    assert "mode=require" in log_text
    assert "tls_enabled=True" in log_text
    assert "certificate_verified=False" in log_text
