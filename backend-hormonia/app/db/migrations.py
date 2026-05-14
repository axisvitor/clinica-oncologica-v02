"""Alembic-safe bootstrap helpers.

This module must stay importable without loading the application runtime settings.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import MetaData

from app.db.base import Base

_MIGRATION_MODEL_MODULES = (
    "app.models",
    "app.integrations.whatsapp.models.message",
)

_LIBPQ_TLS_QUERY_KEYS = {
    "sslmode",
    "sslcert",
    "sslkey",
    "sslrootcert",
    "sslcrl",
    "sslcrldir",
    "sslcompression",
    "sslpassword",
    "ssl_min_protocol_version",
    "ssl_max_protocol_version",
}
_LIBPQ_TLS_QUERY_ALIASES = {
    # asyncpg accepts these harness aliases through app.core.database.async_engine,
    # but psycopg/libpq rejects them as URI query parameters.
    "sslminversion": "ssl_min_protocol_version",
    "sslmaxversion": "ssl_max_protocol_version",
}


class MigrationBootstrapError(RuntimeError):
    """Raised when Alembic bootstrap cannot resolve metadata or database URL."""


def normalize_database_url(database_url: str) -> str:
    """Normalize supported PostgreSQL URL schemes for SQLAlchemy/Alembic."""
    normalized_url = database_url
    if normalized_url.startswith("postgres://"):
        normalized_url = normalized_url.replace("postgres://", "postgresql://", 1)
    return _normalize_migration_tls_query_options(normalized_url)


def _normalize_migration_tls_query_options(database_url: str) -> str:
    """Return a psycopg/libpq-compatible migration URL without async-only TLS keys."""
    try:
        parsed = urlsplit(database_url)
    except Exception as exc:  # pragma: no cover - urlsplit is normally permissive.
        raise MigrationBootstrapError(
            "alembic db_url_resolution failed: DATABASE_URL could not be parsed"
        ) from exc

    if not parsed.query:
        return database_url

    normalized_query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        canonical_key = _LIBPQ_TLS_QUERY_ALIASES.get(normalized_key)
        if canonical_key:
            normalized_query.append((canonical_key, value))
            continue

        if normalized_key.startswith("ssl"):
            if normalized_key not in _LIBPQ_TLS_QUERY_KEYS:
                raise MigrationBootstrapError(
                    "alembic db_url_resolution failed: unsupported PostgreSQL TLS query option for migrations"
                )
            normalized_query.append((normalized_key, value))
            continue

        normalized_query.append((key, value))

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(normalized_query, doseq=True, safe="/:"),
            parsed.fragment,
        )
    )


def resolve_migration_database_url(
    environ: Mapping[str, str] | None = None,
    fallback_url: str | None = None,
) -> str:
    """Resolve the database URL for Alembic without importing runtime settings."""
    env = os.environ if environ is None else environ
    database_url = env.get("DATABASE_URL") or fallback_url

    if not database_url:
        raise MigrationBootstrapError(
            "alembic db_url_resolution failed: set DATABASE_URL or sqlalchemy.url"
        )

    return normalize_database_url(database_url)


def get_migration_metadata() -> MetaData:
    """Load all model modules required for Alembic metadata discovery."""
    for module_name in _MIGRATION_MODEL_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - exercised via subprocess tests
            raise MigrationBootstrapError(
                "alembic graph-load metadata import failed while loading "
                f"{module_name}: {exc}"
            ) from exc

    return Base.metadata
