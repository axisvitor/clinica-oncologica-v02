from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa

from app.db.migrations import MigrationBootstrapError, resolve_migration_database_url

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRUBBED_GRAPH_DATABASE_URL = "postgresql://graph-walk:graph-walk@localhost:5432/hormonia_graph_walk"
FORBIDDEN_GRAPH_MODULES = (
    "app.database",
    "app.config",
    "app.config.settings",
    "app.utils",
    "app.utils.timezone",
    "app.utils.jsonb_validator",
)
TARGET_GRAPH_REVISIONS = (
    "016_validate_patient_metadata",
    "018_seed_flow_templates",
    "019_seed_welcome_message_template",
    "c9a6d2f7b3e1",
)
TARGET_HEAD_REVISIONS = ("m005_s03_t02_align_audit_history_head",)


def _scrubbed_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": str(REPO_ROOT),
    }
    if extra_env:
        env.update(extra_env)
    return env



def _run_scrubbed_python(
    snippet: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(snippet)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_scrubbed_env(extra_env),
        check=False,
    )



def _run_scrubbed_alembic_command(
    command: str,
    *,
    database_url: str = SCRUBBED_GRAPH_DATABASE_URL,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *command.split()],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_scrubbed_env({"DATABASE_URL": database_url}),
        check=False,
    )



def _mask_database_urls(text: str) -> str:
    return re.sub(
        r"(postgres(?:ql)?(?:\+[^:]+)?://)([^:/@\s]+)(?::[^@\s]*)?@",
        r"\1***:***@",
        text,
    )



def _extract_failure_details(output: str) -> tuple[str, str]:
    revision_match = re.search(r"alembic/versions/([^/\s:]+\.py)", output)
    import_patterns = (
        re.compile(r"No module named ['\"](app(?:\.[\w_]+)+)['\"]"),
        re.compile(r"from (app(?:\.[\w_]+)+) import"),
        re.compile(r"import (app(?:\.[\w_]+)+)"),
    )

    import_path = "unknown"
    for pattern in import_patterns:
        match = pattern.search(output)
        if match:
            import_path = match.group(1)
            break

    return (
        revision_match.group(1) if revision_match else "unknown",
        import_path,
    )



def _alembic_command_failure_message(
    command: str,
    phase: str,
    result: subprocess.CompletedProcess[str],
) -> str:
    stdout = _mask_database_urls(result.stdout)
    stderr = _mask_database_urls(result.stderr)
    offending_revision, offending_import_path = _extract_failure_details(
        f"{stdout}\n{stderr}"
    )
    return (
        f"command={command} phase={phase} returncode={result.returncode} "
        f"offending_revision={offending_revision} "
        f"offending_import_path={offending_import_path}\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}"
    )



def _get_test_database_url() -> str | None:
    return os.getenv("TEST_DATABASE_URL")



def _is_local_postgres(db_url: str) -> bool:
    parsed = urlparse(db_url)
    if not parsed.scheme.startswith("postgres"):
        return False
    return parsed.hostname in {"localhost", "127.0.0.1", "::1"}



def _reset_schema(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


@pytest.fixture
def local_test_database_url() -> str:
    db_url = _get_test_database_url()
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set")
    if not _is_local_postgres(db_url):
        pytest.skip("migration operability test requires local postgres")

    _reset_schema(db_url)
    try:
        yield db_url
    finally:
        _reset_schema(db_url)


@pytest.mark.parametrize(
    ("environ", "fallback_url", "expected"),
    [
        (
            {"DATABASE_URL": "postgres://user:pass@localhost:5432/hormonia_test"},
            "postgresql://ignored:ignored@localhost:5432/ignored",
            "postgresql://user:pass@localhost:5432/hormonia_test",
        ),
        (
            {},
            "postgresql://config-user:config-pass@localhost:5432/hormonia_test",
            "postgresql://config-user:config-pass@localhost:5432/hormonia_test",
        ),
    ],
    ids=["env_wins_and_normalizes", "config_fallback"],
)
def test_db_url_resolution(environ: dict[str, str], fallback_url: str, expected: str) -> None:
    assert resolve_migration_database_url(environ, fallback_url) == expected



def test_db_url_resolution_missing_source_has_named_failure() -> None:
    with pytest.raises(MigrationBootstrapError, match="db_url_resolution failed"):
        resolve_migration_database_url({}, None)



def test_settings_free_metadata_bootstrap() -> None:
    result = _run_scrubbed_python(
        """
        import sys

        from app.db.migrations import get_migration_metadata

        metadata = get_migration_metadata()
        table_names = set(metadata.tables)
        required_tables = {"patient_deletion_audit", "whatsapp_messages", "webhook_endpoints"}
        missing_tables = sorted(required_tables - table_names)
        if missing_tables:
            raise SystemExit(
                "phase=settings_free_metadata missing_tables=" + ",".join(missing_tables)
            )

        forbidden_modules = [
            module_name
            for module_name in ("app.database", "app.config", "app.config.settings")
            if module_name in sys.modules
        ]
        if forbidden_modules:
            raise SystemExit(
                "phase=settings_free_metadata forbidden_imports="
                + ",".join(forbidden_modules)
            )

        print(
            "phase=settings_free_metadata "
            f"tables={len(table_names)} runtime_imports=clean"
        )
        """
    )

    assert result.returncode == 0, (
        "settings-free metadata bootstrap failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "phase=settings_free_metadata" in result.stdout
    assert "runtime_imports=clean" in result.stdout



def test_graph_walk_bootstrap_avoids_runtime_helpers() -> None:
    result = _run_scrubbed_python(
        """
        import sys

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config("alembic.ini")
        revisions = list(ScriptDirectory.from_config(config).walk_revisions())
        revision_ids = {revision.revision for revision in revisions}
        required_revisions = {
            "016_validate_patient_metadata",
            "018_seed_flow_templates",
            "019_seed_welcome_message_template",
            "c9a6d2f7b3e1",
        }
        missing_revisions = sorted(required_revisions - revision_ids)
        if missing_revisions:
            raise SystemExit(
                "phase=graph-load missing_revisions=" + ",".join(missing_revisions)
            )

        forbidden_modules = [
            module_name
            for module_name in (
                "app.database",
                "app.config",
                "app.config.settings",
                "app.utils",
                "app.utils.timezone",
                "app.utils.jsonb_validator",
            )
            if module_name in sys.modules
        ]
        if forbidden_modules:
            raise SystemExit(
                "phase=graph-load forbidden_imports=" + ",".join(forbidden_modules)
            )

        print(
            "phase=graph-load "
            f"revisions={len(revisions)} runtime_imports=clean"
        )
        """
    )

    assert result.returncode == 0, (
        "graph walk bootstrap loaded runtime helpers\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "phase=graph-load" in result.stdout
    assert "runtime_imports=clean" in result.stdout


@pytest.mark.parametrize(
    ("command", "expected_tokens"),
    [
        (
            "history",
            TARGET_GRAPH_REVISIONS,
        ),
        (
            "heads",
            TARGET_HEAD_REVISIONS,
        ),
    ],
    ids=["history", "heads"],
)
def test_scrubbed_graph_commands_report_offending_revision(
    command: str,
    expected_tokens: tuple[str, ...],
) -> None:
    result = _run_scrubbed_alembic_command(command)

    assert result.returncode == 0, _alembic_command_failure_message(
        command, "graph-load", result
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    for token in expected_tokens:
        assert token in combined_output, (
            f"command={command} missing_token={token}\n"
            f"stdout:\n{_mask_database_urls(result.stdout)}\n"
            f"stderr:\n{_mask_database_urls(result.stderr)}"
        )



def test_scrubbed_upgrade_head_reports_revision_on_failure(
    local_test_database_url: str,
) -> None:
    result = _run_scrubbed_alembic_command(
        "upgrade head",
        database_url=local_test_database_url,
    )

    assert result.returncode == 0, _alembic_command_failure_message(
        "upgrade head", "upgrade", result
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    for token in TARGET_HEAD_REVISIONS:
        assert token in combined_output, (
            f"command=upgrade head phase=upgrade missing_token={token}\n"
            f"stdout:\n{_mask_database_urls(result.stdout)}\n"
            f"stderr:\n{_mask_database_urls(result.stderr)}"
        )



def test_scrubbed_current_matches_head_after_upgrade(
    local_test_database_url: str,
) -> None:
    upgrade_result = _run_scrubbed_alembic_command(
        "upgrade head",
        database_url=local_test_database_url,
    )
    assert upgrade_result.returncode == 0, _alembic_command_failure_message(
        "upgrade head", "upgrade", upgrade_result
    )

    current_result = _run_scrubbed_alembic_command(
        "current",
        database_url=local_test_database_url,
    )
    assert current_result.returncode == 0, _alembic_command_failure_message(
        "current", "current", current_result
    )

    combined_output = f"{current_result.stdout}\n{current_result.stderr}"
    for token in TARGET_HEAD_REVISIONS:
        assert token in combined_output, (
            f"command=current phase=current missing_token={token}\n"
            f"stdout:\n{_mask_database_urls(current_result.stdout)}\n"
            f"stderr:\n{_mask_database_urls(current_result.stderr)}"
        )
    assert "head" in combined_output.lower(), (
        "command=current phase=current missing_head_marker\n"
        f"stdout:\n{_mask_database_urls(current_result.stdout)}\n"
        f"stderr:\n{_mask_database_urls(current_result.stderr)}"
    )
