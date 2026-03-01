"""Phase 26 async migration regression tests.

Source-level assertions proving all analytics, admin, system, and remaining domain
router files remain migrated from sync Session to AsyncSession patterns.
"""

import importlib
import inspect
import pathlib
import re

import pytest


WRITE_OPS = ["commit", "flush", "refresh", "rollback", "delete"]

ANALYTICS_MODULES = [
    "app.api.v2.routers.analytics.dashboard_analytics",
    "app.api.v2.routers.analytics.patient_analytics",
    "app.api.v2.routers.analytics.quiz_analytics",
    "app.api.v2.routers.dashboard",
    "app.api.v2.routers.reports",
]

ADMIN_MODULES = [
    "app.api.v2.routers.admin.compensation",
    "app.api.v2.routers.admin.activity",
    "app.api.v2.routers.admin.users",
    "app.api.v2.routers.admin.stats",
    "app.api.v2.routers.admin_extensions.audit",
    "app.api.v2.routers.admin_extensions.dlq",
]

SYSTEM_MODULES = [
    "app.api.v2.routers.health.service_health",
    "app.api.v2.routers.health.database_health",
    "app.api.v2.routers.health.monitoring",
    "app.api.v2.routers.platform_sync",
    "app.api.v2.routers.upload.handlers",
]

DOMAIN_MODULES = [
    "app.api.v2.routers.appointments",
    "app.api.v2.routers.medications",
    "app.api.v2.routers.treatments",
    "app.api.v2.routers.notifications",
    "app.api.v2.routers.alerts",
    "app.api.v2.routers.template_versions",
    "app.api.v2.routers.template_admin",
]

ALL_PHASE26_MODULES = ANALYTICS_MODULES + ADMIN_MODULES + SYSTEM_MODULES + DOMAIN_MODULES

# Gap closure modules (Plans 26-10 through 26-15)
GAP_PHYSICIANS_MODULES = [
    "app.api.v2.routers.physicians.statistics",
    "app.api.v2.routers.physicians.availability",
    "app.api.v2.routers.physicians.base",
    "app.api.v2.routers.enhanced_analytics",
    "app.api.v2.routers.performance",
]

GAP_ENHANCED_MESSAGES_MODULES = [
    "app.api.v2.routers.enhanced_messages.templates",
    "app.api.v2.routers.enhanced_messages.scheduling",
    "app.api.v2.routers.enhanced_messages.bulk",
    "app.api.v2.routers.enhanced_messages.analytics",
]

GAP_ADMIN_DI_MODULES = [
    "app.api.v2.routers.admin.dependencies",
    "app.api.v2.routers.admin.actions",
    "app.api.v2.routers.roles.dependencies",
    "app.api.v2.routers.upload",
]

GAP_TASKS_MODULES = [
    "app.api.v2.routers.tasks.dependencies",
    "app.api.v2.routers.tasks.endpoints.crud",
    "app.api.v2.routers.tasks.endpoints.operations",
    "app.api.v2.routers.tasks.endpoints.monitoring",
    "app.api.v2.routers.tasks.endpoints.bulk",
]

GAP_SYSTEM_HEALTH_MODULES = [
    "app.api.v2.routers.system.metrics",
    "app.api.v2.routers.system.initialization",
    "app.api.v2.routers.system.components",
    "app.api.v2.routers.system.health",
    "app.api.v2.routers.health.metrics",
    "app.api.v2.routers.health.core",
    "app.api.v2.routers.health.test",
    "app.api.v2.routers.localization",
    "app.api.v2.routers.webhooks",
    "app.api.v2.routers.ai.insights",
]

GAP_DEBUG_MODULES = [
    "app.api.v2.routers.debug.common",
    "app.api.v2.routers.debug.auth",
    "app.api.v2.routers.debug.database",
    "app.api.v2.routers.debug.environment",
    "app.api.v2.routers.patients.base",
]

ALL_GAP_MODULES = (
    GAP_PHYSICIANS_MODULES
    + GAP_ENHANCED_MESSAGES_MODULES
    + GAP_ADMIN_DI_MODULES
    + GAP_TASKS_MODULES
    + GAP_SYSTEM_HEALTH_MODULES
    + GAP_DEBUG_MODULES
)

ALL_MIGRATED_MODULES = ALL_PHASE26_MODULES + ALL_GAP_MODULES


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


@pytest.mark.parametrize("module_path", ALL_PHASE26_MODULES)
class TestPhase26RouterAsyncMigration:
    def test_no_sync_db_query(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        _assert_no_sync_patterns(source, name)

    def test_uses_async_db(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        assert "get_async_db" in source, f"{name} must reference get_async_db"

    def test_write_ops_awaited(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        _assert_write_ops_awaited(source, name)


@pytest.mark.parametrize("module_path", ALL_GAP_MODULES)
class TestGapClosureAsyncMigration:
    def test_no_sync_db_query(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        _assert_no_sync_patterns(source, name)

    def test_uses_async_db(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        assert (
            "get_async_db" in source
            or ("AsyncSession" in source and "await db.execute" in source)
        ), f"{name} must be async-safe (get_async_db or AsyncSession + awaited execute)"

    def test_write_ops_awaited(self, module_path: str):
        source = _get_source(module_path)
        name = module_path.rsplit(".", 1)[-1]
        _assert_write_ops_awaited(source, name)


class TestGlobalZeroSyncDI:
    """Assert zero sync DI patterns across the entire API router surface."""

    def test_no_depends_get_db_in_any_router_file(self):
        """Scan all router modules for Depends(get_db)."""
        routers_dir = pathlib.Path("app/api/v2/routers")
        violations = []
        for py_file in routers_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "Depends(get_db)" in content:
                violations.append(str(py_file))

        assert not violations, (
            f"Depends(get_db) still present in {len(violations)} files: "
            + ", ".join(violations)
        )

    def test_no_db_query_in_any_router_file(self):
        """Scan all router modules for db.query(."""
        routers_dir = pathlib.Path("app/api/v2/routers")
        violations = []
        for py_file in routers_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "db.query(" in content:
                violations.append(str(py_file))

        assert not violations, (
            f"db.query( still present in {len(violations)} files: "
            + ", ".join(violations)
        )


class TestCompensationSpecificChecks:
    """Verify compensation.py mixed-state was fully resolved."""

    def test_no_sync_session_dependency(self):
        source = _get_source("app.api.v2.routers.admin.compensation")
        assert "Session = Depends(get_db)" not in source, (
            "compensation.py still has sync Session dependency"
        )

    def test_all_handlers_use_async(self):
        source = _get_source("app.api.v2.routers.admin.compensation")
        assert "Depends(get_async_db)" in source


class TestDatabaseHealthSpecificChecks:
    """Verify database_health.py kept sync engine for pool stats."""

    def test_engine_pool_preserved(self):
        source = _get_source("app.api.v2.routers.health.database_health")
        assert "engine.pool" in source, (
            "database_health.py must keep engine.pool access for sync pool stats"
        )

    def test_text_execute_awaited(self):
        source = _get_source("app.api.v2.routers.health.database_health")
        # Verify await is used for text execute (not bare db.execute without await)
        assert "await db.execute" in source, (
            "database_health.py must use await db.execute for text queries"
        )


class TestStatsSpecificChecks:
    """Verify stats.py no longer uses sync _status_count."""

    def test_no_sync_status_count(self):
        source = _get_source("app.api.v2.routers.admin.stats")
        # The sync _status_count(db, ...) pattern must not remain
        # The call pattern is: _status_count(db, ...) vs await _status_count_async(db, ...)
        import re as re_module

        sync_pattern = r"(?<!_async)\b_status_count\(db"
        assert not re_module.search(sync_pattern, source), (
            "stats.py still calls sync _status_count(db, ...) - must use _status_count_async"
        )


class TestReportsSpecificChecks:
    """Verify reports.py removed iter_db_dependency wrapper."""

    def test_no_iter_db_dependency(self):
        source = _get_source("app.api.v2.routers.reports")
        assert "iter_db_dependency" not in source, (
            "reports.py must not use iter_db_dependency wrapper"
        )

    def test_no_get_db_dep_wrapper(self):
        source = _get_source("app.api.v2.routers.reports")
        assert "_get_db_dep" not in source, (
            "reports.py must not have _get_db_dep wrapper function"
        )

    def test_check_patient_access_is_async(self):
        source = _get_source("app.api.v2.routers.reports")
        assert "async def _check_patient_access" in source, (
            "reports.py _check_patient_access must be async"
        )
