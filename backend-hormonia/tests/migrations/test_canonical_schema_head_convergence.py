from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config


pytestmark = [pytest.mark.integration, pytest.mark.migrations]

EXPECTED_HEAD_REVISION = "m006_s02_t03_drop_users_firebase_residue"
EXISTING_UPGRADE_START = "m005_s02_t01_publish_firebase_history_boundary"
TARGET_TABLES = ("users", "audit_logs", "firebase_sync_history")
TARGET_ENUMS = ("audit_event_type", "user_role")
EXPECTED_USERS_COLUMNS = (
    "id",
    "created_at",
    "updated_at",
    "email",
    "hashed_password",
    "full_name",
    "role",
    "is_active",
    "last_login",
    "auth_created_at",
    "email_verified",
    "display_name",
    "photo_url",
    "preferences",
    "specialty",
    "specialties",
    "license_number",
    "phone",
    "bio",
    "avatar_url",
    "auth_provider",
    "failed_login_attempts",
    "is_locked",
    "locked_until",
    "force_change_password",
    "last_password_change",
    "permissions",
)
EXPECTED_USERS_INDEXES = {
    "idx_users_locked": ("is_locked",),
    "idx_users_locked_until": ("locked_until",),
    "ix_users_permissions_gin": ("permissions",),
    "users_email_key": ("email",),
}
REMOVED_USERS_COLUMNS = (
    "firebase_uid",
    "firebase_last_sign_in",
    "firebase_created_at",
    "firebase_email_verified",
    "firebase_display_name",
    "firebase_photo_url",
    "firebase_custom_claims",
    "last_firebase_sync",
)
REMOVED_USERS_INDEXES = ("ix_users_firebase_uid",)


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


def _collect_head_revision(engine: sa.Engine) -> str:
    with engine.connect() as connection:
        return connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()


def _collect_columns(engine: sa.Engine, table_name: str) -> list[dict[str, object]]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                """
                SELECT
                    column_name,
                    data_type,
                    udt_name,
                    is_nullable,
                    character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                ORDER BY ordinal_position
                """
            ),
            {"table_name": table_name},
        ).mappings().all()

    return [
        {
            "name": row["column_name"],
            "data_type": row["data_type"],
            "udt_name": row["udt_name"],
            "nullable": row["is_nullable"] == "YES",
            "max_length": row["character_maximum_length"],
        }
        for row in rows
    ]


def _collect_indexes(engine: sa.Engine, table_name: str) -> list[dict[str, object]]:
    inspector = sa.inspect(engine)
    indexes = []
    for index in inspector.get_indexes(table_name):
        indexes.append(
            {
                "name": index["name"],
                "columns": tuple(index.get("column_names") or ()),
                "unique": bool(index.get("unique", False)),
            }
        )
    return sorted(indexes, key=lambda item: item["name"])


def _collect_enums(engine: sa.Engine) -> dict[str, list[str]]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                """
                SELECT t.typname, e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = ANY(:enum_names)
                ORDER BY t.typname, e.enumsortorder
                """
            ),
            {"enum_names": list(TARGET_ENUMS)},
        ).mappings().all()

    enums: dict[str, list[str]] = {name: [] for name in TARGET_ENUMS}
    for row in rows:
        enums[row["typname"]].append(row["enumlabel"])
    return enums


def _collect_fingerprint(engine: sa.Engine) -> dict[str, object]:
    return {
        "head": _collect_head_revision(engine),
        "tables": {
            table_name: {
                "columns": _collect_columns(engine, table_name),
                "indexes": _collect_indexes(engine, table_name),
            }
            for table_name in TARGET_TABLES
        },
        "enums": _collect_enums(engine),
    }


def _fingerprint_diff(
    left: dict[str, object],
    right: dict[str, object],
) -> dict[str, object]:
    diff: dict[str, object] = {}
    if left.get("head") != right.get("head"):
        diff["head"] = {"left": left.get("head"), "right": right.get("head")}

    table_diffs: dict[str, object] = {}
    left_tables = left.get("tables", {})
    right_tables = right.get("tables", {})
    for table_name in TARGET_TABLES:
        left_table = left_tables.get(table_name)
        right_table = right_tables.get(table_name)
        if left_table != right_table:
            table_diffs[table_name] = {"left": left_table, "right": right_table}
    if table_diffs:
        diff["tables"] = table_diffs

    if left.get("enums") != right.get("enums"):
        diff["enums"] = {"left": left.get("enums"), "right": right.get("enums")}

    return diff


def _assert_users_contract(fingerprint: dict[str, object], *, phase: str) -> None:
    users_table = fingerprint["tables"]["users"]
    actual_columns = [column["name"] for column in users_table["columns"]]
    actual_column_set = set(actual_columns)
    expected_column_set = set(EXPECTED_USERS_COLUMNS)
    removed_column_set = set(REMOVED_USERS_COLUMNS)

    column_diff = {
        "missing": sorted(expected_column_set - actual_column_set),
        "unexpected": sorted(actual_column_set - expected_column_set),
        "removed_present": sorted(actual_column_set & removed_column_set),
    }
    assert not any(column_diff.values()), (
        f"canonical_head phase={phase} users_column_diff={json.dumps(column_diff, sort_keys=True)}"
    )

    actual_index_map = {
        index["name"]: tuple(index.get("columns") or ())
        for index in users_table["indexes"]
    }
    expected_index_names = set(EXPECTED_USERS_INDEXES)
    actual_index_names = set(actual_index_map)
    removed_index_names = set(REMOVED_USERS_INDEXES)

    wrong_index_columns = {
        name: {
            "expected": EXPECTED_USERS_INDEXES[name],
            "actual": actual_index_map.get(name),
        }
        for name in sorted(expected_index_names & actual_index_names)
        if tuple(actual_index_map.get(name, ())) != tuple(EXPECTED_USERS_INDEXES[name])
    }
    index_diff = {
        "missing": sorted(expected_index_names - actual_index_names),
        "unexpected": sorted(actual_index_names - expected_index_names),
        "removed_present": sorted(actual_index_names & removed_index_names),
        "wrong_columns": wrong_index_columns,
    }
    assert not index_diff["missing"] and not index_diff["unexpected"] and not index_diff["removed_present"] and not index_diff["wrong_columns"], (
        f"canonical_head phase={phase} users_index_diff={json.dumps(index_diff, sort_keys=True)}"
    )


def _run_phase(config: Config, engine: sa.Engine, *, phase: str, seed_revision: str | None) -> dict[str, object]:
    previous_db_url = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = config.get_main_option("sqlalchemy.url")
        _reset_schema(engine)
        if seed_revision:
            command.upgrade(config, seed_revision)
        command.upgrade(config, "head")
        fingerprint = _collect_fingerprint(engine)
    finally:
        if previous_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db_url

    assert fingerprint["head"] == EXPECTED_HEAD_REVISION, (
        f"canonical_head phase={phase} head={fingerprint['head']} "
        f"expected_head={EXPECTED_HEAD_REVISION}"
    )

    missing_enums = [enum_name for enum_name in TARGET_ENUMS if not fingerprint["enums"].get(enum_name)]
    assert not missing_enums, (
        f"canonical_head phase={phase} head={fingerprint['head']} "
        f"enum_missing={','.join(missing_enums)}"
    )

    _assert_users_contract(fingerprint, phase=phase)
    return fingerprint


@pytest.mark.integration
def test_canonical_head_convergence_clean_replay_matches_existing_upgrade():
    db_url = _get_test_database_url()
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set")
    if not _is_local_postgres(db_url):
        pytest.skip("migration test requires local postgres")

    config = _make_alembic_config(db_url)
    engine = sa.create_engine(db_url)

    try:
        clean_fingerprint = _run_phase(
            config,
            engine,
            phase="clean_replay",
            seed_revision=None,
        )
        existing_fingerprint = _run_phase(
            config,
            engine,
            phase="existing_upgrade",
            seed_revision=EXISTING_UPGRADE_START,
        )

        diff = _fingerprint_diff(clean_fingerprint, existing_fingerprint)
        assert not diff, (
            f"canonical_head phase=compare head={EXPECTED_HEAD_REVISION} "
            f"fingerprint_diff={json.dumps(diff, sort_keys=True)}"
        )
    finally:
        _reset_schema(engine)
        engine.dispose()
