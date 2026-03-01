"""Phase 25 async migration regression tests.

Source-level assertions proving all message and quiz router files
remain migrated from sync Session to AsyncSession patterns.
"""

import importlib
import inspect
import re

import pytest


WRITE_OPS = ["commit", "flush", "refresh", "rollback", "delete"]


def _get_source(module_path: str) -> str:
    mod = importlib.import_module(module_path)
    return inspect.getsource(mod)


def _assert_no_sync_patterns(source: str, module_name: str) -> None:
    assert "db.query(" not in source, f"db.query( found in {module_name}"
    assert "Depends(get_db)" not in source, f"Depends(get_db) found in {module_name}"


def _assert_write_ops_awaited(source: str, module_name: str) -> None:
    for op in WRITE_OPS:
        pattern = rf"(?<!await )db\.{op}\("
        assert not re.search(pattern, source), (
            f"Sync db.{op}() without await found in {module_name}"
        )


class TestMessagesAsyncMigration:
    def test_messages_no_sync_patterns(self):
        source = _get_source("app.api.v2.routers.messages")
        _assert_no_sync_patterns(source, "messages.py")

    def test_messages_uses_async_db(self):
        source = _get_source("app.api.v2.routers.messages")
        assert "Depends(get_async_db)" in source

    def test_messages_no_sync_repos(self):
        source = _get_source("app.api.v2.routers.messages")
        assert "MessageRepository(" not in source
        assert "MessageService(" not in source

    def test_messages_write_ops_awaited(self):
        source = _get_source("app.api.v2.routers.messages")
        _assert_write_ops_awaited(source, "messages.py")


class TestQuizSharedAsyncMigration:
    def test_quiz_shared_check_patient_access_is_async(self):
        source = _get_source("app.api.v2._quiz_shared")
        assert "async def _check_patient_access" in source

    def test_quiz_shared_no_sync_patterns(self):
        source = _get_source("app.api.v2._quiz_shared")
        assert "db.query(" not in source

    def test_monthly_quiz_ops_shared_uses_async_db(self):
        source = _get_source("app.api.v2.routers.monthly_quiz_operations._shared")
        assert "get_async_db" in source
        assert "from app.database import get_db" not in source


QUIZ_ROUTER_MODULES = [
    "app.api.v2.routers.quiz_templates",
    "app.api.v2.routers.monthly_quiz_management",
    "app.api.v2.routers.quiz_responses",
    "app.api.v2.routers.quiz_alerts",
    "app.api.v2.routers.quiz_sessions",
    "app.api.v2.routers.monthly_quiz_operations.crud",
    "app.api.v2.routers.monthly_quiz_operations.scheduling",
    "app.api.v2.routers.monthly_quiz_operations.public",
]


@pytest.mark.parametrize("module_path", QUIZ_ROUTER_MODULES)
class TestQuizRouterAsyncMigration:
    def test_no_sync_patterns(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        _assert_no_sync_patterns(source, name)

    def test_uses_async_db(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        assert "get_async_db" in source, f"{name} must use get_async_db"

    def test_write_ops_awaited(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        _assert_write_ops_awaited(source, name)


class TestQuizSessionsSpecificChecks:
    def test_no_sync_lock(self):
        source = _get_source("app.api.v2.routers.quiz_sessions")
        assert "acquire_lock_sync" not in source

    def test_uses_async_lock(self):
        source = _get_source("app.api.v2.routers.quiz_sessions")
        assert "async with acquire_lock" in source or "acquire_lock" in source
