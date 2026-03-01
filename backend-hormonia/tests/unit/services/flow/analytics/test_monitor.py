"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

Tests for app.services.flow.analytics.monitor which has been tombstoned.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="app.services.flow.analytics tombstoned in Phase 16 (Dead Code Removal)"
)


def test_monitor_module_tombstoned() -> None:
    pass
