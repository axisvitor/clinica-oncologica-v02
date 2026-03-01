import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql


def _get_test_database_url() -> str | None:
    return os.getenv("TEST_DATABASE_URL")


def _is_local_postgres(db_url: str) -> bool:
    parsed = urlparse(db_url)
    if not parsed.scheme.startswith("postgres"):
        return False
    return parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def _make_alembic_config(db_url: str) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    alembic_path = repo_root / "alembic"
    config = Config()
    config.set_main_option("script_location", str(alembic_path))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def _reset_schema(engine: sa.Engine) -> None:
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))


def _create_minimal_quiz_schema(engine: sa.Engine) -> None:
    metadata = sa.MetaData()

    sa.Table(
        "users",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    sa.Table(
        "patients",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    sa.Table(
        "quiz_templates",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    sa.Table(
        "quiz_responses",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("response_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    sa.Table(
        "quiz_questions",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    sa.Table(
        "quiz_template_versions_v2",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    sa.Table(
        "quiz_sessions_v2",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    sa.Table(
        "quiz_response_migration_log",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    )

    metadata.create_all(engine)

    view_sql = """
        CREATE OR REPLACE VIEW quiz_responses_with_text AS
        SELECT
            qr.*,
            qr.response_value::text AS response_value_text,
            CASE
                WHEN jsonb_typeof(qr.response_value) = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(qr.response_value))
                ELSE NULL
            END AS response_value_array,
            CASE
                WHEN jsonb_typeof(qr.response_value) = 'number'
                THEN (qr.response_value)::numeric
                ELSE NULL
            END AS response_value_numeric
        FROM quiz_responses qr
        """
    with engine.begin() as connection:
        connection.execute(sa.text(view_sql))


@pytest.mark.integration
def test_drop_unused_quiz_tables_migration_upgrade_downgrade():
    db_url = _get_test_database_url()
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set")
    if not _is_local_postgres(db_url):
        pytest.skip("migration test requires local postgres")

    config = _make_alembic_config(db_url)
    engine = sa.create_engine(db_url)

    try:
        previous_db_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = db_url
        _reset_schema(engine)
        _create_minimal_quiz_schema(engine)

        command.stamp(config, "9139c2862e40")

        command.upgrade(config, "29016a88ebf0")

        inspector = sa.inspect(engine)
        tables = inspector.get_table_names()
        views = inspector.get_view_names()
        assert "quiz_questions" not in tables
        assert "quiz_template_versions_v2" not in tables
        assert "quiz_sessions_v2" not in tables
        assert "quiz_response_migration_log" not in tables
        assert "quiz_responses_with_text" not in views

        command.downgrade(config, "9139c2862e40")

        inspector = sa.inspect(engine)
        tables = inspector.get_table_names()
        views = inspector.get_view_names()
        assert "quiz_questions" in tables
        assert "quiz_template_versions_v2" in tables
        assert "quiz_sessions_v2" in tables
        assert "quiz_response_migration_log" in tables
        assert "quiz_responses_with_text" in views
    finally:
        if previous_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db_url
        _reset_schema(engine)
        engine.dispose()
