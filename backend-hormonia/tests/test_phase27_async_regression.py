"""Regression guards for Phase 27 async migration stability."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path


def _iter_router_module_sources():
    routers_pkg = importlib.import_module("app.api.v2.routers")
    router_dir = list(routers_pkg.__path__)

    for _importer, modname, _ispkg in pkgutil.walk_packages(
        router_dir,
        prefix="app.api.v2.routers.",
    ):
        try:
            module = importlib.import_module(modname)
            yield modname, inspect.getsource(module)
        except Exception:
            continue


def test_conftest_overrides_get_async_db():
    """TEST-01: SyncToAsyncSessionAdapter fixture covers get_async_db."""
    conftest = importlib.import_module("tests.conftest")
    source = inspect.getsource(conftest)

    assert "get_async_db" in source, "conftest must override get_async_db"
    assert (
        "SyncToAsyncSessionAdapter" in source
    ), "conftest must use SyncToAsyncSessionAdapter"
    assert (
        "_override_get_async_db" in source
    ), "conftest must define _override_get_async_db"


def test_zero_db_query_in_registered_routers():
    """TEST-02: registered router modules must not use db.query()."""
    violations = []
    for modname, source in _iter_router_module_sources():
        if "db.query(" in source:
            violations.append(modname)

    assert not violations, f"Router modules with db.query(): {violations}"


def test_zero_todo_async_migration_annotations():
    """TEST-03: TODO(async-migration) markers must be fully removed."""
    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"

    matches = []
    for py_file in app_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "TODO(async-migration)" in content:
            matches.append(str(py_file.relative_to(repo_root)))

    assert not matches, f"Files still containing TODO(async-migration): {matches}"


def test_no_depends_get_db_in_routers():
    """TEST-02: registered router modules must not use Depends(get_db)."""
    violations = []
    for modname, source in _iter_router_module_sources():
        if "Depends(get_db)" in source:
            violations.append(modname)

    assert not violations, f"Router modules with Depends(get_db): {violations}"


def test_auth_session_shared_uses_async_safe_query():
    """Shared auth-session lookup must keep async-safe query pattern."""
    module = importlib.import_module("app.api.v2.auth_session_shared")
    source = inspect.getsource(module)

    assert "db.query(" not in source, "auth_session_shared still uses db.query()"
    assert "db.execute" in source, "auth_session_shared must use db.execute(select(...))"


def test_enhanced_reports_uses_async_db():
    """API-09: enhanced_reports.py must use get_async_db, not sync get_db."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    src = (repo_root / "app" / "api" / "v2" / "routers" / "enhanced_reports.py").read_text(
        encoding="utf-8"
    )

    assert "from app.database import get_db" not in src, (
        "enhanced_reports.py still imports sync get_db"
    )
    assert "iter_db_dependency" not in src, (
        "enhanced_reports.py still uses iter_db_dependency wrapper"
    )
    assert "_get_db_dep" not in src, (
        "enhanced_reports.py still has _get_db_dep helper"
    )
    assert "get_async_db" in src, (
        "enhanced_reports.py must import get_async_db"
    )


def test_adapter_has_awaitable_wrappers():
    """TEST-01: SyncToAsyncSessionAdapter must have explicit awaitable wrappers for all awaited methods."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    conftest_files = [
        repo_root / "tests" / "conftest.py",
        repo_root / "tests" / "api" / "critical" / "conftest.py",
    ]
    required_methods = [
        "def delete(self",
        "def add(self",
        "def scalars(self",
        "def get(self",
        "def commit(self",
        "def flush(self",
        "def refresh(self",
        "def rollback(self",
        "def close(self",
        "def begin_nested(self",
        "def execute(self",
    ]

    for conftest_path in conftest_files:
        source = conftest_path.read_text(encoding="utf-8")
        rel = conftest_path.relative_to(repo_root)
        for method_sig in required_methods:
            assert method_sig in source, (
                f"{rel} SyncToAsyncSessionAdapter missing {method_sig}"
            )
