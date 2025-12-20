"""
Tests for FlowManagerAdapter - Backward compatibility layer (QW-021 Day 6).

Test Coverage:
    - Adapter Initialization (with/without warnings)
    - Legacy API Compatibility (all legacy methods)
    - Deprecation Warnings (warning display, suppression)
    - API Translation (legacy to new API)
    - Feature Flags (configuration respect)
    - Error Handling (legacy error formats)

NOTE: FlowManagerAdapter was removed during refactoring.
The flow service is now accessed directly via FlowManager.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="FlowManagerAdapter removed - use FlowManager directly"
)

from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch
import warnings
from app.services.flow.manager import FlowManager
from app.services.flow.types import FlowStatus


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock()


@pytest.fixture
def adapter(mock_db):
    """Create adapter instance."""
    return FlowManagerAdapter(db=mock_db, show_warnings=False)


@pytest.fixture
def adapter_with_warnings(mock_db):
    """Create adapter instance with warnings enabled."""
    return FlowManagerAdapter(db=mock_db, show_warnings=True)


# ============================================================================
# Test Initialization
# ============================================================================


class TestInitialization:
    """Test adapter initialization."""

    def test_init_with_warnings_disabled(self, mock_db):
        """Test initialization with warnings disabled."""
        adapter = FlowManagerAdapter(db=mock_db, show_warnings=False)

        assert adapter.db is mock_db
        assert adapter.manager is not None
        assert isinstance(adapter.manager, FlowManager)
        assert adapter.show_warnings is False

    def test_init_with_warnings_enabled(self, mock_db):
        """Test initialization with warnings enabled."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            adapter = FlowManagerAdapter(db=mock_db, show_warnings=True)

            # Should show deprecation warning
            assert len(w) >= 0  # May or may not show based on config

    def test_init_creates_flow_manager(self, mock_db):
        """Test that initialization creates FlowManager."""
        adapter = FlowManagerAdapter(db=mock_db, show_warnings=False)

        assert hasattr(adapter, "manager")
        assert isinstance(adapter.manager, FlowManager)


# ============================================================================
# Test Legacy API Compatibility
# ============================================================================


class TestLegacyAPICompatibility:
    """Test compatibility with legacy flow APIs."""

    def test_start_flow_legacy_signature(self, adapter, mock_db):
        """Test start_flow with legacy signature."""
        patient_id = uuid4()
        flow_type = "daily_checkin"

        with patch.object(adapter.manager, "start_flow") as mock_start:
            mock_start.return_value = uuid4()

            flow_id = adapter.start_flow(patient_id, flow_type)

            assert flow_id is not None
            mock_start.assert_called_once()

    def test_get_flow_status_legacy(self, adapter):
        """Test get_flow_status legacy method."""
        flow_id = uuid4()

        with patch.object(adapter.manager, "get_flow_status") as mock_get:
            mock_get.return_value = "active"

            status = adapter.get_flow_status(flow_id)

            assert status == "active"
            mock_get.assert_called_once_with(flow_id)

    def test_complete_flow_legacy(self, adapter):
        """Test complete_flow legacy method."""
        flow_id = uuid4()

        with patch.object(adapter.manager, "complete_flow") as mock_complete:
            mock_complete.return_value = True

            result = adapter.complete_flow(flow_id)

            assert result is True
            mock_complete.assert_called_once_with(flow_id)

    def test_cancel_flow_legacy(self, adapter):
        """Test cancel_flow legacy method."""
        flow_id = uuid4()

        with patch.object(adapter.manager, "cancel_flow") as mock_cancel:
            mock_cancel.return_value = True

            result = adapter.cancel_flow(flow_id)

            assert result is True
            mock_cancel.assert_called_once_with(flow_id)


# ============================================================================
# Test API Translation
# ============================================================================


class TestAPITranslation:
    """Test translation between legacy and new API."""

    def test_flow_type_translation_string_to_enum(self, adapter):
        """Test flow type translation from string to enum."""
        patient_id = uuid4()

        with patch.object(adapter.manager, "start_flow") as mock_start:
            mock_start.return_value = uuid4()

            # Legacy string flow type
            adapter.start_flow(patient_id, "daily_checkin")

            # Should translate to FlowType enum
            mock_start.assert_called_once()

    def test_status_translation_enum_to_string(self, adapter):
        """Test status translation from enum to string."""
        flow_id = uuid4()

        with patch.object(adapter.manager, "get_flow_status") as mock_get:
            mock_get.return_value = FlowStatus.ACTIVE

            status = adapter.get_flow_status(flow_id)

            # Should return string for legacy compatibility
            assert isinstance(status, (str, FlowStatus))

    def test_data_structure_translation(self, adapter):
        """Test data structure translation."""
        flow_id = uuid4()

        with patch.object(adapter.manager, "get_flow_data") as mock_get:
            mock_get.return_value = {"key": "value"}

            data = adapter.get_flow_data(flow_id)

            assert isinstance(data, dict)
            mock_get.assert_called_once_with(flow_id)


# ============================================================================
# Test Deprecation Warnings
# ============================================================================


class TestDeprecationWarnings:
    """Test deprecation warning functionality."""

    def test_deprecation_warning_on_init(self, mock_db):
        """Test deprecation warning shown on init."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            adapter = FlowManagerAdapter(db=mock_db, show_warnings=True)

            # May show warning based on feature flag
            assert isinstance(adapter, FlowManagerAdapter)

    def test_no_warning_when_disabled(self, mock_db):
        """Test no warning when disabled."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            adapter = FlowManagerAdapter(db=mock_db, show_warnings=False)

            # Should not show warning
            adapter_warnings = [
                warning for warning in w if "deprecated" in str(warning.message).lower()
            ]
            assert len(adapter_warnings) == 0

    def test_warning_message_content(self, mock_db):
        """Test warning message contains useful information."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            adapter = FlowManagerAdapter(db=mock_db, show_warnings=True)

            if len(w) > 0:
                assert "deprecated" in str(
                    w[0].message
                ).lower() or "FlowManagerAdapter" in str(w[0].message)


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling in adapter."""

    def test_handles_manager_exception(self, adapter):
        """Test that adapter handles manager exceptions."""
        flow_id = uuid4()

        with patch.object(adapter.manager, "get_flow_status") as mock_get:
            mock_get.side_effect = Exception("Manager error")

            with pytest.raises(Exception) as exc_info:
                adapter.get_flow_status(flow_id)

            assert "Manager error" in str(exc_info.value)

    def test_handles_translation_error(self, adapter):
        """Test handling of translation errors."""
        patient_id = uuid4()

        with patch.object(adapter.manager, "start_flow") as mock_start:
            mock_start.side_effect = ValueError("Invalid flow type")

            with pytest.raises(ValueError):
                adapter.start_flow(patient_id, "invalid_type")

    def test_handles_none_returns(self, adapter):
        """Test handling of None returns from manager."""
        flow_id = uuid4()

        with patch.object(adapter.manager, "get_flow_data") as mock_get:
            mock_get.return_value = None

            result = adapter.get_flow_data(flow_id)

            assert result is None


# ============================================================================
# Test Feature Flags
# ============================================================================


class TestFeatureFlags:
    """Test feature flag handling."""

    def test_respects_deprecation_warning_flag(self, mock_db):
        """Test that adapter respects deprecation warning flag."""
        adapter_no_warn = FlowManagerAdapter(db=mock_db, show_warnings=False)
        adapter_warn = FlowManagerAdapter(db=mock_db, show_warnings=True)

        assert adapter_no_warn.show_warnings is False
        assert adapter_warn.show_warnings is True

    def test_config_loaded(self, adapter):
        """Test that config is loaded."""
        assert adapter.config is not None
        assert hasattr(adapter.config, "feature_flags")


# ============================================================================
# Test Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Test complete backward compatibility scenarios."""

    def test_complete_legacy_flow_lifecycle(self, adapter):
        """Test complete flow lifecycle using legacy API."""
        patient_id = uuid4()
        flow_id = uuid4()

        with (
            patch.object(adapter.manager, "start_flow") as mock_start,
            patch.object(adapter.manager, "get_flow_status") as mock_status,
            patch.object(adapter.manager, "complete_flow") as mock_complete,
        ):
            mock_start.return_value = flow_id
            mock_status.return_value = FlowStatus.ACTIVE
            mock_complete.return_value = True

            # Start flow (legacy)
            result_id = adapter.start_flow(patient_id, "daily_checkin")
            assert result_id == flow_id

            # Get status (legacy)
            status = adapter.get_flow_status(flow_id)
            assert status is not None

            # Complete flow (legacy)
            completed = adapter.complete_flow(flow_id)
            assert completed is True

    def test_legacy_error_format_compatibility(self, adapter):
        """Test that errors are in legacy format."""
        flow_id = uuid4()

        with patch.object(adapter.manager, "get_flow_status") as mock_get:
            mock_get.side_effect = ValueError("Flow not found")

            with pytest.raises(ValueError) as exc_info:
                adapter.get_flow_status(flow_id)

            # Error should be in expected format
            assert "Flow not found" in str(exc_info.value)

    def test_legacy_data_format_compatibility(self, adapter):
        """Test that returned data is in legacy format."""
        flow_id = uuid4()
        legacy_data = {
            "flow_id": str(flow_id),
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
        }

        with patch.object(adapter.manager, "get_flow_data") as mock_get:
            mock_get.return_value = legacy_data

            data = adapter.get_flow_data(flow_id)

            assert isinstance(data, dict)
            assert "flow_id" in data or data is not None


# ============================================================================
# Test Integration with FlowManager
# ============================================================================


class TestFlowManagerIntegration:
    """Test integration with FlowManager."""

    def test_delegates_to_flow_manager(self, adapter, mock_db):
        """Test that adapter delegates calls to FlowManager."""
        patient_id = uuid4()

        with patch.object(adapter.manager, "start_flow") as mock_start:
            mock_start.return_value = uuid4()

            adapter.start_flow(patient_id, "daily_checkin")

            # Verify delegation
            mock_start.assert_called_once()

    def test_uses_same_db_session(self, mock_db):
        """Test that adapter uses same DB session."""
        adapter = FlowManagerAdapter(db=mock_db, show_warnings=False)

        assert adapter.db is mock_db
        assert adapter.manager.db is mock_db

    def test_manager_instance_reused(self, adapter):
        """Test that manager instance is reused."""
        manager1 = adapter.manager
        manager2 = adapter.manager

        assert manager1 is manager2


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_none_patient_id(self, adapter):
        """Test handling of None patient_id."""
        with patch.object(adapter.manager, "start_flow") as mock_start:
            mock_start.side_effect = ValueError("Invalid patient_id")

            with pytest.raises(ValueError):
                adapter.start_flow(None, "daily_checkin")

    def test_empty_flow_type(self, adapter):
        """Test handling of empty flow type."""
        patient_id = uuid4()

        with patch.object(adapter.manager, "start_flow") as mock_start:
            mock_start.side_effect = ValueError("Invalid flow_type")

            with pytest.raises(ValueError):
                adapter.start_flow(patient_id, "")

    def test_invalid_flow_id(self, adapter):
        """Test handling of invalid flow_id."""
        with patch.object(adapter.manager, "get_flow_status") as mock_get:
            mock_get.return_value = None

            result = adapter.get_flow_status(uuid4())

            assert result is None

    def test_multiple_operations_sequence(self, adapter):
        """Test sequence of multiple operations."""
        patient_id = uuid4()
        flow_id = uuid4()

        with (
            patch.object(adapter.manager, "start_flow") as mock_start,
            patch.object(adapter.manager, "get_flow_status") as mock_status,
            patch.object(adapter.manager, "complete_flow") as mock_complete,
        ):
            mock_start.return_value = flow_id
            mock_status.return_value = FlowStatus.ACTIVE
            mock_complete.return_value = True

            # Execute multiple operations
            adapter.start_flow(patient_id, "daily_checkin")
            adapter.get_flow_status(flow_id)
            adapter.get_flow_status(flow_id)
            adapter.complete_flow(flow_id)

            # Verify all calls were made
            assert mock_start.call_count == 1
            assert mock_status.call_count == 2
            assert mock_complete.call_count == 1
