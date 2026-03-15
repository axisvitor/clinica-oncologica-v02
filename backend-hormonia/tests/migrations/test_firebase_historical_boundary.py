from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from tests import conftest as shared_test_conftest
from tests.api.critical import conftest as critical_test_conftest

PRE_BOUNDARY_REVISION = "lgpd03_add_ai_audit_event_types"
BOUNDARY_HEAD_REVISION = "m005_s03_t02_align_audit_history_head"
LEGACY_TABLE = "user_sync_log"
HISTORY_TABLE = "firebase_sync_history"
AUDIT_TABLE = "audit_logs"
AUDIT_FIXTURE_GUARDS = (
    ("shared", shared_test_conftest._ensure_audit_logs_live_columns),
    ("critical", critical_test_conftest._ensure_audit_logs_live_columns),
)


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


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _create_stripped_audit_logs_table(engine: sa.Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE audit_logs ("
                "id UUID PRIMARY KEY, "
                "event_type VARCHAR(50) NOT NULL, "
                "event_status VARCHAR(50), "
                "event_metadata JSONB, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                ")"
            )
        )


def _assert_sync_history_surface(engine: sa.Engine, *, phase: str) -> None:
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())

    assert HISTORY_TABLE in tables, (
        f"sync_history_surface phase={phase} "
        f"missing_table={HISTORY_TABLE} tables={sorted(tables)}"
    )
    assert LEGACY_TABLE not in tables, (
        f"sync_history_surface phase={phase} "
        f"legacy_table_still_present={LEGACY_TABLE} tables={sorted(tables)}"
    )

    columns = _column_names(inspector, HISTORY_TABLE)
    expected_columns = {
        "id",
        "firebase_uid",
        "user_id",
        "operation",
        "sync_direction",
        "changes",
        "success",
        "error_message",
        "created_at",
    }
    missing_columns = sorted(expected_columns - columns)
    unexpected_columns = sorted(
        {"supabase_user_id", "sync_action", "sync_status"} & columns
    )
    assert not missing_columns, (
        f"sync_history_surface phase={phase} missing_columns={missing_columns}"
    )
    assert not unexpected_columns, (
        f"sync_history_surface phase={phase} historical_shape_live_columns={unexpected_columns}"
    )

    index_names = {index["name"] for index in inspector.get_indexes(HISTORY_TABLE)}
    expected_indexes = {
        "ix_firebase_sync_history_created_at",
        "ix_firebase_sync_history_firebase_uid",
        "ix_firebase_sync_history_user_id",
    }
    missing_indexes = sorted(expected_indexes - index_names)
    assert not missing_indexes, (
        f"sync_history_surface phase={phase} missing_indexes={missing_indexes}"
    )

    foreign_key_names = {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys(HISTORY_TABLE)
        if foreign_key.get("name")
    }
    assert "fk_firebase_sync_history_user_id" in foreign_key_names, (
        f"sync_history_surface phase={phase} foreign_keys={sorted(foreign_key_names)}"
    )

    primary_key_name = inspector.get_pk_constraint(HISTORY_TABLE).get("name")
    assert primary_key_name == "firebase_sync_history_pkey", (
        f"sync_history_surface phase={phase} primary_key={primary_key_name}"
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("suite_name", "guard_fn"),
    AUDIT_FIXTURE_GUARDS,
    ids=lambda case: case if isinstance(case, str) else None,
)
def test_named_failure_audit_fixture_guards_do_not_revive_historical_firebase_residue(
    suite_name: str,
    guard_fn,
):
    db_url = _get_test_database_url()
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set")
    if not _is_local_postgres(db_url):
        pytest.skip("migration test requires local postgres")

    engine = sa.create_engine(db_url)

    try:
        _reset_schema(engine)
        _create_stripped_audit_logs_table(engine)

        guard_fn(engine)

        inspector = sa.inspect(engine)
        columns = _column_names(inspector, AUDIT_TABLE)
        assert "event_category" in columns, (
            f"named_failure suite={suite_name} live_column_missing=event_category columns={sorted(columns)}"
        )
        assert "firebase_uid" not in columns, (
            f"named_failure suite={suite_name} resurrected_historical_audit_firebase_uid=true columns={sorted(columns)}"
        )

        index_names = {index["name"] for index in inspector.get_indexes(AUDIT_TABLE)}
        assert "idx_audit_firebase_time" not in index_names, (
            f"named_failure suite={suite_name} resurrected_historical_audit_firebase_index=true indexes={sorted(index_names)}"
        )
    finally:
        _reset_schema(engine)
        engine.dispose()


@pytest.mark.integration
def test_sync_history_surface_clean_replay_promotes_explicit_firebase_history():
    db_url = _get_test_database_url()
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set")
    if not _is_local_postgres(db_url):
        pytest.skip("migration test requires local postgres")

    config = _make_alembic_config(db_url)
    engine = sa.create_engine(db_url)

    previous_db_url = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = db_url
        _reset_schema(engine)
        command.upgrade(config, "head")

        _assert_sync_history_surface(engine, phase="clean_replay")

        with engine.connect() as connection:
            current_revision = connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert current_revision == BOUNDARY_HEAD_REVISION, (
            "sync_history_surface phase=clean_replay "
            f"expected_head={BOUNDARY_HEAD_REVISION} current_revision={current_revision}"
        )
    finally:
        if previous_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db_url
        _reset_schema(engine)
        engine.dispose()


@pytest.mark.integration
def test_sync_history_named_failure_preserves_rows_on_existing_db_upgrade():
    db_url = _get_test_database_url()
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set")
    if not _is_local_postgres(db_url):
        pytest.skip("migration test requires local postgres")

    config = _make_alembic_config(db_url)
    engine = sa.create_engine(db_url)

    previous_db_url = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = db_url
        _reset_schema(engine)
        command.upgrade(config, PRE_BOUNDARY_REVISION)

        legacy_history = sa.Table(LEGACY_TABLE, sa.MetaData(), autoload_with=engine)
        masked_row_id = uuid.uuid4()
        masked_supabase_user_id = uuid.uuid4()
        masked_firebase_uid = "masked-firebase-uid-001"
        with engine.begin() as connection:
            connection.execute(
                legacy_history.insert().values(
                    id=masked_row_id,
                    firebase_uid=masked_firebase_uid,
                    supabase_user_id=masked_supabase_user_id,
                    sync_action="legacy_sync",
                    sync_status="completed",
                    error_message=None,
                    user_id=None,
                    operation="sync",
                    sync_direction="firebase_to_pg",
                    changes={"source": "existing-db-upgrade"},
                    success=True,
                )
            )

        command.upgrade(config, "head")

        _assert_sync_history_surface(engine, phase="existing_upgrade")

        history_table = sa.Table(HISTORY_TABLE, sa.MetaData(), autoload_with=engine)
        with engine.connect() as connection:
            rows = connection.execute(
                sa.select(
                    history_table.c.id,
                    history_table.c.firebase_uid,
                    history_table.c.operation,
                    history_table.c.sync_direction,
                    history_table.c.success,
                    history_table.c.changes,
                ).order_by(history_table.c.created_at.asc())
            ).mappings().all()

        assert len(rows) == 1, (
            f"named_failure phase=existing_upgrade preserved_rows={len(rows)}"
        )

        row = rows[0]
        assert row["id"] == masked_row_id, (
            "named_failure phase=existing_upgrade preserved_primary_key_changed=true"
        )
        assert row["firebase_uid"] == masked_firebase_uid, (
            "named_failure phase=existing_upgrade preserved_firebase_uid_missing=true"
        )
        assert row["operation"] == "sync", (
            "named_failure phase=existing_upgrade operation_changed=true"
        )
        assert row["sync_direction"] == "firebase_to_pg", (
            "named_failure phase=existing_upgrade sync_direction_changed=true"
        )
        assert row["success"] is True, (
            "named_failure phase=existing_upgrade success_changed=true"
        )

        historical_shape = (row["changes"] or {}).get("historical_shape") or {}
        assert historical_shape.get("supabase_user_id") == str(masked_supabase_user_id), (
            "historical_shape phase=existing_upgrade preserved_legacy_supabase_link_missing=true"
        )
        assert historical_shape.get("sync_action") == "legacy_sync", (
            "historical_shape phase=existing_upgrade preserved_sync_action_missing=true"
        )
        assert historical_shape.get("sync_status") == "completed", (
            "historical_shape phase=existing_upgrade preserved_sync_status_missing=true"
        )
    finally:
        if previous_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db_url
        _reset_schema(engine)
        engine.dispose()
