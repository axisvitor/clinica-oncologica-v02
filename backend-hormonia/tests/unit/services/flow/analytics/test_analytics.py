"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

Tests for app.services.flow.analytics.analytics which has been tombstoned.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="app.services.flow.analytics tombstoned in Phase 16 (Dead Code Removal)"
)


def test_analytics_module_tombstoned() -> None:
    pass
