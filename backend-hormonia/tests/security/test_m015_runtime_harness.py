from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from psycopg.conninfo import conninfo_to_dict

from app.db.migrations import MigrationBootstrapError, resolve_migration_database_url


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
RUNNER = REPO_ROOT / "scripts" / "security" / "verify-m015-runtime-security.sh"
COMPOSE_FILE = REPO_ROOT / "scripts" / "security" / "m015-runtime" / "docker-compose.yml"


def _query_params(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def test_migration_url_canonicalizes_asyncpg_tls_aliases_for_psycopg() -> None:
    resolved = resolve_migration_database_url(
        {
            "DATABASE_URL": "postgresql+psycopg://user:secret@postgres:5432/app"
            "?sslmode=verify-full&sslrootcert=/m015-certs/ca.crt"
            "&sslminversion=TLSv1.2&application_name=m015_db_seam"
        },
        None,
    )

    query = _query_params(resolved)
    assert query["sslmode"] == "verify-full"
    assert query["sslrootcert"] == "/m015-certs/ca.crt"
    assert query["ssl_min_protocol_version"] == "TLSv1.2"
    assert query["application_name"] == "m015_db_seam"
    assert "sslminversion" not in query

    # psycopg itself parses plain libpq URIs; SQLAlchemy owns the +psycopg
    # driver token before handing options to psycopg.
    libpq_uri = resolved.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = conninfo_to_dict(libpq_uri)
    assert parsed["sslmode"] == "verify-full"
    assert parsed["sslrootcert"] == "/m015-certs/ca.crt"
    assert parsed["ssl_min_protocol_version"] == "TLSv1.2"


def test_migration_url_rejects_unknown_tls_options_without_leaking_dsn() -> None:
    secret_url = (
        "postgresql+psycopg://user:super-secret@postgres:5432/app"
        "?sslmode=verify-full&sslrootcert=/private/ca.crt&sslinvalidoption=1"
    )

    with pytest.raises(MigrationBootstrapError) as exc_info:
        resolve_migration_database_url({"DATABASE_URL": secret_url}, None)

    error_text = str(exc_info.value)
    assert "unsupported PostgreSQL TLS query option" in error_text
    assert "super-secret" not in error_text
    assert "/private/ca.crt" not in error_text
    assert secret_url not in error_text


def test_m015_harness_uses_psycopg_compatible_tls_minimum_key() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "sslminversion" not in runner_text
    assert "sslminversion" not in compose_text
    assert "ssl_min_protocol_version=TLSv1.2" in runner_text
    assert "ssl_min_protocol_version=TLSv1.2" in compose_text
    assert "sslmode=verify-full" in runner_text
    assert "sslmode=verify-full" in compose_text
    assert "sslrootcert=/m015-certs/ca.crt" in runner_text
    assert "sslrootcert=/m015-certs/ca.crt" in compose_text
