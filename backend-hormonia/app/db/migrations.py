"""Alembic-safe bootstrap helpers.

This module must stay importable without loading the application runtime settings.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping

from sqlalchemy import MetaData

from app.db.base import Base

_MIGRATION_MODEL_MODULES = (
    "app.models",
    "app.integrations.whatsapp.models.message",
)


class MigrationBootstrapError(RuntimeError):
    """Raised when Alembic bootstrap cannot resolve metadata or database URL."""


def normalize_database_url(database_url: str) -> str:
    """Normalize supported PostgreSQL URL schemes for SQLAlchemy/Alembic."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


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
