"""Integration tests for Celery task async DB isolation.

Phase 21 requirement FOUND-03: Celery tasks must stay on sync DB paths.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test_db")


class TestCeleryAsyncIsolation:
    """Verify task modules and shared services remain sync-safe."""

    def test_task_modules_no_async_db_in_namespace(self) -> None:
        """Import each app.tasks module and ensure async DB symbols are absent."""
        repo_root = Path(__file__).resolve().parents[2]
        tasks_root = repo_root / "app" / "tasks"
        assert tasks_root.exists(), f"Tasks directory not found: {tasks_root}"

        import_failures: list[str] = []
        violations: list[str] = []

        for py_file in sorted(tasks_root.rglob("*.py")):
            rel_file = py_file.relative_to(repo_root)
            module_name = rel_file.with_suffix("").as_posix().replace("/", ".")

            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                import_failures.append(f"{module_name}: {exc!r}")
                continue

            if "get_async_db" in module.__dict__:
                violations.append(f"{module_name}: exposes get_async_db")
            if "AsyncSession" in module.__dict__:
                violations.append(f"{module_name}: exposes AsyncSession")

        assert not import_failures, "Failed to import task modules:\n" + "\n".join(import_failures)
        assert not violations, "Async DB leakage found in task modules:\n" + "\n".join(violations)

    def test_get_async_db_runtime_guard_blocks_sync_callers(self) -> None:
        """get_async_db must fail fast when advanced without an event loop."""
        from app.core.database.async_engine import get_async_db

        async_gen = get_async_db()
        first_next = async_gen.__anext__()

        with pytest.raises(RuntimeError, match="async context"):
            first_next.send(None)

    def test_shared_service_sync_mode_via_dual_session_mixin(self) -> None:
        """DualSessionMixin should detect sync sessions and dispatch sync methods."""
        from app.core.database.dual_session import DualSessionMixin

        class TestService(DualSessionMixin):
            def __init__(self, db):
                self.db = db

        mock_sync_db = MagicMock(
            spec_set=["execute", "scalars", "get", "commit", "flush", "refresh", "add", "delete"]
        )
        mock_sync_db.execute.return_value = "sync_result"

        service = TestService(mock_sync_db)

        assert service.is_async is False
        assert service._execute("SELECT 1") == "sync_result"

    def test_shared_service_async_mode_detection(self) -> None:
        """DualSessionMixin should detect AsyncSession instances."""
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.core.database.dual_session import DualSessionMixin

        class TestService(DualSessionMixin):
            def __init__(self, db):
                self.db = db

        mock_async_db = MagicMock(spec=AsyncSession)
        service = TestService(mock_async_db)

        assert service.is_async is True

    def test_ci_lint_guard_passes_on_current_codebase(self) -> None:
        """Static CI guard and runtime checks should agree on a clean baseline."""
        repo_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "scripts/check_async_isolation.py"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )

        assert result.returncode == 0, (
            f"check_async_isolation.py failed with exit {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
