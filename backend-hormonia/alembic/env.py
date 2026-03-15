"""Alembic environment configuration for Hormonia backend."""

from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Add the backend root to the Python path.
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.append(BACKEND_ROOT)

from app.db.migrations import get_migration_metadata, resolve_migration_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models through a settings-free path so Alembic can traverse metadata
# without bootstrapping the full application runtime.
target_metadata = get_migration_metadata()


def get_url() -> str:
    """Resolve the database URL for Alembic without importing runtime settings."""
    return resolve_migration_database_url(
        fallback_url=config.get_main_option("sqlalchemy.url")
    )


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    url = get_url()
    autocommit = os.getenv("ALEMBIC_AUTOCOMMIT", "1").lower() in (
        "1",
        "true",
        "yes",
    )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
        transactional_ddl=not autocommit,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    autocommit = os.getenv("ALEMBIC_AUTOCOMMIT", "1").lower() in (
        "1",
        "true",
        "yes",
    )
    engine_kwargs = {"poolclass": pool.NullPool}
    if autocommit:
        engine_kwargs["isolation_level"] = "AUTOCOMMIT"

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        **engine_kwargs,
    )

    with connectable.connect() as connection:
        # Some historical revisions use IDs longer than Alembic's default
        # version table width (VARCHAR(32)). Ensure enough capacity before
        # Alembic starts writing revision values.
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(255) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(255)"
            )
        )

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,
            transactional_ddl=not autocommit,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
