"""Async database engine, session factory, and FastAPI dependency.

Canonical location for all async database infrastructure.
Separated from sync config (app/database.py) per Phase 21 architecture decision.

Usage:
    from app.core.database import get_async_db
    # or
    from app.core.database.async_engine import get_async_db
"""

import asyncio
import logging
import ssl as ssl_module
from dataclasses import dataclass
from typing import Any, AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

_async_engine = None
_async_session_factory = None

_ASYNCPG_SCHEME = "postgresql+asyncpg://"
_SCHEME_REPLACEMENTS = (
    ("postgresql+psycopg://", _ASYNCPG_SCHEME),
    ("postgresql+psycopg2://", _ASYNCPG_SCHEME),
    ("postgresql://", _ASYNCPG_SCHEME),
)
_SUPPORTED_SSLMODES = {"disable", "require", "verify-ca", "verify-full"}
_LIBPQ_SSL_QUERY_KEYS = {
    "sslmode",
    "sslrootcert",
    "sslcert",
    "sslkey",
    "sslcrl",
    "sslcrldir",
    "sslcompression",
    "sslpassword",
    "ssl_min_protocol_version",
    "ssl_max_protocol_version",
    # Historical M015 synthetic harness URLs used these shorter async-only aliases;
    # keep accepting them for runtime config while migration URLs canonicalize them.
    "sslminversion",
    "sslmaxversion",
}
_TLS_VERSION_ALIASES = {
    "tlsv1.2": ssl_module.TLSVersion.TLSv1_2,
    "tlsv1_2": ssl_module.TLSVersion.TLSv1_2,
    "tls1.2": ssl_module.TLSVersion.TLSv1_2,
    "tls12": ssl_module.TLSVersion.TLSv1_2,
    "tlsv1.3": ssl_module.TLSVersion.TLSv1_3,
    "tlsv1_3": ssl_module.TLSVersion.TLSv1_3,
    "tls1.3": ssl_module.TLSVersion.TLSv1_3,
    "tls13": ssl_module.TLSVersion.TLSv1_3,
}


class AsyncDatabaseConfigError(RuntimeError):
    """Sanitized async database initialization failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class AsyncPostgresConnectionConfig:
    """Prepared asyncpg connection details plus PHI/secret-safe TLS posture."""

    async_url: str
    sanitized_async_url: str
    connect_args: dict[str, Any]
    sslmode: str | None
    tls_enabled: bool
    tls_certificate_verified: bool
    tls_hostname_verified: bool
    client_certificate_configured: bool


class _AsyncSessionFactoryProxy:
    """Lazy proxy that defers async session factory initialization."""

    def __call__(self, *args, **kwargs):
        return get_async_session_factory()(*args, **kwargs)


def _raise_config_error(code: str, message: str) -> None:
    """Raise a named configuration error whose text never includes DSNs or paths."""
    raise AsyncDatabaseConfigError(code, message)


def _convert_postgres_url_scheme(database_url: str) -> str:
    """Convert supported PostgreSQL sync driver URLs to SQLAlchemy asyncpg URLs."""
    if not isinstance(database_url, str) or not database_url.strip():
        _raise_config_error(
            "async_postgres_url_invalid",
            "DATABASE_URL must be a non-empty PostgreSQL URL.",
        )

    stripped_url = database_url.strip()
    for source_scheme, target_scheme in _SCHEME_REPLACEMENTS:
        if stripped_url.startswith(source_scheme):
            return target_scheme + stripped_url[len(source_scheme) :]

    if stripped_url.startswith(_ASYNCPG_SCHEME):
        return stripped_url

    _raise_config_error(
        "async_postgres_url_invalid",
        "DATABASE_URL must use a supported PostgreSQL scheme.",
    )
    raise AssertionError("unreachable")


def _sanitize_url_password(url: str) -> str:
    """Hide any password in a URL string before diagnostics use."""
    parsed = urlsplit(url)
    netloc = parsed.netloc
    if "@" in netloc:
        userinfo, hostinfo = netloc.rsplit("@", 1)
        if ":" in userinfo:
            username, _password = userinfo.split(":", 1)
            userinfo = f"{username}:***"
        netloc = f"{userinfo}@{hostinfo}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _parse_asyncpg_url_and_ssl_options(
    async_url: str,
) -> tuple[str, str, dict[str, str]]:
    """Strip libpq SSL params from the async URL and return sanitized options."""
    try:
        parsed = urlsplit(async_url)
    except Exception as exc:  # pragma: no cover - defensive; urlsplit is permissive.
        raise AsyncDatabaseConfigError(
            "async_postgres_url_invalid",
            "DATABASE_URL could not be parsed as a PostgreSQL URL.",
        ) from exc

    if parsed.scheme != "postgresql+asyncpg" or not parsed.netloc:
        _raise_config_error(
            "async_postgres_url_invalid",
            "DATABASE_URL must resolve to a PostgreSQL asyncpg URL.",
        )

    preserved_query: list[tuple[str, str]] = []
    ssl_options: dict[str, str] = {}

    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key in _LIBPQ_SSL_QUERY_KEYS:
            ssl_options[normalized_key] = value
        else:
            preserved_query.append((key, value))

    stripped_query = urlencode(preserved_query, doseq=True)
    stripped_url = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, stripped_query, parsed.fragment)
    )
    sanitized_url = _sanitize_url_password(stripped_url)
    return stripped_url, sanitized_url, ssl_options


def _normalize_sslmode(ssl_options: dict[str, str]) -> str | None:
    raw_sslmode = ssl_options.get("sslmode")
    if raw_sslmode is None or raw_sslmode == "":
        return None

    sslmode = raw_sslmode.lower().strip()
    if sslmode not in _SUPPORTED_SSLMODES:
        _raise_config_error(
            "async_postgres_sslmode_unsupported",
            "Unsupported PostgreSQL sslmode for async engine initialization.",
        )
    return sslmode


def _lookup_tls_version(raw_value: str | None, *, code: str) -> ssl_module.TLSVersion | None:
    if raw_value is None or raw_value == "":
        return None
    version = _TLS_VERSION_ALIASES.get(raw_value.lower().strip())
    if version is None:
        _raise_config_error(
            code,
            "Unsupported PostgreSQL TLS protocol version for async engine initialization.",
        )
    return version


def _apply_tls_protocol_versions(
    context: ssl_module.SSLContext,
    ssl_options: dict[str, str],
) -> None:
    minimum_version = _lookup_tls_version(
        ssl_options.get("sslminversion")
        or ssl_options.get("ssl_min_protocol_version"),
        code="async_postgres_ssl_min_version_unsupported",
    )
    if minimum_version is not None:
        context.minimum_version = minimum_version

    maximum_version = _lookup_tls_version(
        ssl_options.get("sslmaxversion")
        or ssl_options.get("ssl_max_protocol_version"),
        code="async_postgres_ssl_max_version_unsupported",
    )
    if maximum_version is not None:
        context.maximum_version = maximum_version


def _load_client_certificate_if_configured(
    context: ssl_module.SSLContext,
    ssl_options: dict[str, str],
) -> bool:
    certfile = ssl_options.get("sslcert")
    keyfile = ssl_options.get("sslkey")

    if keyfile and not certfile:
        _raise_config_error(
            "async_postgres_ssl_client_cert_invalid",
            "sslkey requires sslcert for async engine initialization.",
        )

    if not certfile:
        return False

    context.load_cert_chain(certfile=certfile, keyfile=keyfile or None)
    return True


def _build_ssl_context(
    sslmode: str | None,
    ssl_options: dict[str, str],
) -> tuple[ssl_module.SSLContext | None, bool]:
    """Build an asyncpg SSLContext from libpq-style options, fail closed."""
    if sslmode is None or sslmode == "disable":
        return None, False

    try:
        if sslmode == "require":
            context = ssl_module.SSLContext(ssl_module.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl_module.CERT_NONE
        else:
            sslrootcert = ssl_options.get("sslrootcert")
            if not sslrootcert:
                _raise_config_error(
                    "async_postgres_sslrootcert_required",
                    "sslrootcert is required for verified async PostgreSQL TLS modes.",
                )
            context = ssl_module.create_default_context(cafile=sslrootcert)
            context.check_hostname = sslmode == "verify-full"
            context.verify_mode = ssl_module.CERT_REQUIRED

        _apply_tls_protocol_versions(context, ssl_options)
        client_cert_configured = _load_client_certificate_if_configured(
            context,
            ssl_options,
        )
        return context, client_cert_configured
    except AsyncDatabaseConfigError:
        raise
    except Exception as exc:
        raise AsyncDatabaseConfigError(
            "async_postgres_ssl_context_invalid",
            "Failed to build async PostgreSQL SSL context from sanitized configuration.",
        ) from exc


def _prepare_asyncpg_connection_config(database_url: str) -> AsyncPostgresConnectionConfig:
    """Convert DATABASE_URL to asyncpg URL/connect_args with strict TLS semantics."""
    async_url = _convert_postgres_url_scheme(database_url)
    stripped_async_url, sanitized_async_url, ssl_options = _parse_asyncpg_url_and_ssl_options(
        async_url
    )
    sslmode = _normalize_sslmode(ssl_options)
    ssl_context, client_cert_configured = _build_ssl_context(sslmode, ssl_options)

    connect_args: dict[str, Any] = {}
    if ssl_context is not None:
        connect_args["ssl"] = ssl_context

    return AsyncPostgresConnectionConfig(
        async_url=stripped_async_url,
        sanitized_async_url=sanitized_async_url,
        connect_args=connect_args,
        sslmode=sslmode,
        tls_enabled=ssl_context is not None,
        tls_certificate_verified=sslmode in {"verify-ca", "verify-full"},
        tls_hostname_verified=sslmode == "verify-full",
        client_certificate_configured=client_cert_configured,
    )


def get_async_engine():
    """Get or create an AsyncEngine for async database operations."""
    global _async_engine

    if _async_engine is None:
        try:
            connection_config = _prepare_asyncpg_connection_config(settings.DATABASE_URL)
        except AsyncDatabaseConfigError as exc:
            logger.error("AsyncEngine initialization failed (%s)", exc.code)
            raise

        logger.info(
            "Initializing AsyncEngine (mode=%s tls_enabled=%s "
            "certificate_verified=%s hostname_verified=%s client_certificate=%s)",
            connection_config.sslmode or "absent",
            connection_config.tls_enabled,
            connection_config.tls_certificate_verified,
            connection_config.tls_hostname_verified,
            connection_config.client_certificate_configured,
        )

        _async_engine = create_async_engine(
            connection_config.async_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=settings.APP_ENABLE_DEBUG,
            connect_args=connection_config.connect_args,
        )

    return _async_engine


def get_async_session_factory():
    """Get or create an async session factory."""
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    return _async_session_factory


AsyncSessionLocal = _AsyncSessionFactoryProxy()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session."""
    try:
        asyncio.get_running_loop()
    except RuntimeError as exc:
        raise RuntimeError(
            "get_async_db() must be called from an async context. "
            "Celery tasks should use get_db() or get_scoped_session() instead."
        ) from exc

    async_session_factory = get_async_session_factory()
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error("Async database session error: %s", e)
            await session.rollback()
            raise
        finally:
            await session.close()
