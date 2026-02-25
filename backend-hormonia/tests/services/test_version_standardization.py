"""
Integration tests for version standardization across template loaders.

Tests that EnhancedTemplateLoader, VersionedTemplateLoader, and FlowTemplateValidator
all handle versions consistently using the centralized version utilities.
"""

import pytest
import importlib
from unittest.mock import Mock, patch

from app.services.template_loader_pkg import EnhancedTemplateLoader
from app.services.versioned_template_loader import VersionedTemplateLoader
from app.utils.version_utils import normalize_version, to_int_version

try:
    FlowTemplateValidator = getattr(
        importlib.import_module("app.services.flow.templates.validator"),
        "FlowTemplateValidator",
    )
except ImportError:  # Tombstoned in Phase 16
    FlowTemplateValidator = None


class TestEnhancedTemplateLoaderVersioning:
    """Test EnhancedTemplateLoader version handling."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock()

    @pytest.fixture
    def loader(self, mock_db):
        """Create template loader with mocked dependencies."""
        with patch('app.services.template_loader_pkg.loader.FlowKindRepository'), \
             patch('app.services.template_loader_pkg.loader.FlowTemplateVersionRepository'):
            return EnhancedTemplateLoader(mock_db)

    def test_semantic_version_to_int_conversion(self, loader):
        """Test conversion of semantic version to integer for DB lookup."""
        # Mock the repository
        loader.template_version_repo.get_by_flow_type_and_version = Mock(return_value=None)

        # Load with semantic version
        loader._load_from_database("onboarding", "1.2.3")

        # Verify it converts to integer major version for DB query
        loader.template_version_repo.get_by_flow_type_and_version.assert_called_with(
            "onboarding", 1
        )

    def test_integer_version_passthrough(self, loader):
        """Test integer version is properly handled."""
        loader.template_version_repo.get_by_flow_type_and_version = Mock(return_value=None)

        # Load with integer version
        loader._load_from_database("onboarding", "5")

        # Verify it uses the integer
        loader.template_version_repo.get_by_flow_type_and_version.assert_called_with(
            "onboarding", 5
        )

    def test_parse_db_template_normalizes_version(self, loader):
        """Test that database template version is normalized to semantic format."""
        # Mock database template version
        mock_version = Mock()
        mock_version.version_number = 1  # Integer in database
        mock_version.template_name = "Test Template"
        mock_version.description = "Test"
        mock_version.steps = {"1": {"day": 1, "intent": "test", "base_content": "Hello"}}
        mock_version.metadata_json = {}
        mock_version.kind = Mock(kind_key="test_flow")

        # Parse the template
        result = loader._parse_db_template_version(mock_version)

        # Verify version is normalized to semantic format
        assert result.version == "1.0.0"

    def test_load_template_returns_semantic_version(self, loader):
        """Test that loaded templates always return semantic versions."""
        # Mock successful load
        mock_template_version = Mock()
        mock_template_version.version_number = 2
        mock_template_version.template_name = "Test"
        mock_template_version.description = "Test Template"
        mock_template_version.steps = {"1": {"day": 1, "intent": "test", "base_content": "Test"}}
        mock_template_version.metadata_json = {}
        mock_template_version.kind = Mock(kind_key="test_flow")

        loader.template_version_repo.get_current_version_by_flow_type = Mock(
            return_value=mock_template_version
        )

        # Load template
        result = loader.load_flow_template("test_flow")

        # Verify version is semantic
        assert result.version == "2.0.0"


class TestVersionedTemplateLoaderVersioning:
    """Test VersionedTemplateLoader version handling."""

    @pytest.fixture
    def temp_template_path(self, tmp_path):
        """Create temporary template directory."""
        return tmp_path / "templates"

    @pytest.fixture
    def loader(self, temp_template_path):
        """Create versioned template loader."""
        temp_template_path.mkdir(parents=True, exist_ok=True)
        return VersionedTemplateLoader(temp_template_path)

    def test_create_template_normalizes_version(self, loader):
        """Test that creating templates normalizes versions."""
        # Create template with integer version
        data = {"content": "test"}
        loader.create_template("test_template", data, version=1)

        # Verify version is normalized
        templates = loader.list_templates()
        template_key = "test_template_1.0.0"
        assert template_key in loader.templates_cache
        assert loader.templates_cache[template_key]["version"] == "1.0.0"

    def test_create_template_with_semantic_version(self, loader):
        """Test creating template with semantic version."""
        data = {"content": "test"}
        loader.create_template("test_template", data, version="2.1.5")

        # Verify version is preserved
        template_key = "test_template_2.1.5"
        assert template_key in loader.templates_cache
        assert loader.templates_cache[template_key]["version"] == "2.1.5"

    def test_get_template_with_integer_version(self, loader):
        """Test getting template with integer version."""
        # Create template
        data = {"content": "test"}
        loader.create_template("test", data, version=1)

        # Get with integer version
        result = loader.get_template("test", version="1")

        # Verify we get the template
        assert result is not None
        assert result["version"] == "1.0.0"

    def test_get_template_with_semantic_version(self, loader):
        """Test getting template with semantic version."""
        # Create template
        data = {"content": "test"}
        loader.create_template("test", data, version="1.2.3")

        # Get with same version
        result = loader.get_template("test", version="1.2.3")

        # Verify we get the template
        assert result is not None
        assert result["version"] == "1.2.3"

    def test_get_latest_version_semantic_comparison(self, loader):
        """Test that latest version uses semantic comparison."""
        # Create multiple versions
        for version in ["1.0.0", "1.1.0", "2.0.0", "1.10.0"]:
            loader.create_template("test", {"content": version}, version=version)

        # Get latest version
        latest = loader.get_latest_version("test")

        # Verify semantic comparison (2.0.0 > 1.10.0 > 1.1.0 > 1.0.0)
        assert latest == "2.0.0"

    def test_list_templates_normalizes_versions(self, loader):
        """Test that listing templates shows normalized versions."""
        # Create template with integer version
        loader.create_template("test1", {"content": "test"}, version=1)
        loader.create_template("test2", {"content": "test"}, version="2.1.3")

        # List templates
        templates = loader.list_templates()

        # Verify all versions are normalized
        for template_data in templates.values():
            version = template_data["version"]
            # Should be in semantic format
            assert len(version.split(".")) == 3


@pytest.mark.skipif(
    FlowTemplateValidator is None,
    reason="app.services.flow.templates tombstoned in Phase 16 (Dead Code Removal)",
)
class TestFlowTemplateValidatorVersioning:
    """Test FlowTemplateValidator version handling."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        assert FlowTemplateValidator is not None
        return FlowTemplateValidator()

    def test_validates_semantic_version_format(self, validator):
        """Test validation accepts semantic versions."""
        assert validator._is_valid_version_format("1.2.3") is True
        assert validator._is_valid_version_format("0.0.1") is True
        assert validator._is_valid_version_format("10.20.30") is True

    def test_rejects_non_semantic_versions(self, validator):
        """Test validation rejects non-semantic versions."""
        assert validator._is_valid_version_format("1") is False
        assert validator._is_valid_version_format("1.2") is False
        assert validator._is_valid_version_format("invalid") is False

    def test_rejects_invalid_semantic_versions(self, validator):
        """Test validation rejects malformed semantic versions."""
        assert validator._is_valid_version_format("a.b.c") is False
        assert validator._is_valid_version_format("1.2.3.4") is False


class TestCrossLoaderCompatibility:
    """Test version compatibility across loaders."""

    def test_version_consistency_enhanced_to_versioned(self):
        """Test version can flow from EnhancedTemplateLoader to VersionedTemplateLoader."""
        # Simulate EnhancedTemplateLoader output (semantic version)
        enhanced_version = normalize_version(1)  # Database integer
        assert enhanced_version == "1.0.0"

        # Verify VersionedTemplateLoader can use it
        versioned_int = to_int_version(enhanced_version)
        assert versioned_int == 1

    def test_version_consistency_versioned_to_enhanced(self):
        """Test version can flow from VersionedTemplateLoader to EnhancedTemplateLoader."""
        # Simulate VersionedTemplateLoader output (semantic version)
        versioned_version = "2.1.5"

        # Verify EnhancedTemplateLoader can convert for DB lookup
        db_version = to_int_version(versioned_version)
        assert db_version == 2

    def test_round_trip_version_conversion(self):
        """Test round-trip version conversion preserves major version."""
        original_db_version = 3

        # Convert to semantic
        semantic = normalize_version(original_db_version)
        assert semantic == "3.0.0"

        # Convert back to int
        converted_db_version = to_int_version(semantic)
        assert converted_db_version == original_db_version

    def test_version_comparison_across_formats(self):
        """Test versions can be compared regardless of format."""
        from app.utils.version_utils import compare_versions

        # Integer vs semantic
        assert compare_versions(1, "1.0.0") == 0
        assert compare_versions(1, "2.0.0") == -1
        assert compare_versions(2, "1.9.9") == 1

        # String integer vs semantic
        assert compare_versions("1", "1.0.0") == 0
        assert compare_versions("5", "4.9.9") == 1


class TestVersionMigrationScenarios:
    """Test real-world version migration scenarios."""

    def test_legacy_int_to_semantic_migration(self):
        """Test migrating from legacy int versions to semantic versions."""
        # Legacy system uses integers
        legacy_versions = [1, 2, 3, 4, 5]

        # Convert all to semantic
        semantic_versions = [normalize_version(v) for v in legacy_versions]

        # Verify all are valid semantic versions
        assert semantic_versions == ["1.0.0", "2.0.0", "3.0.0", "4.0.0", "5.0.0"]

    def test_mixed_version_source_normalization(self):
        """Test normalizing versions from different sources."""
        # Database: integers
        db_version = 1

        # Files: semantic strings
        file_version = "1.2.3"

        # User input: string integers
        user_version = "1"

        # All should normalize consistently
        db_normalized = normalize_version(db_version)
        file_normalized = normalize_version(file_version)
        user_normalized = normalize_version(user_version)

        # Verify major versions match
        assert to_int_version(db_normalized) == 1
        assert to_int_version(file_normalized) == 1
        assert to_int_version(user_normalized) == 1

    def test_version_cache_key_generation(self):
        """Test generating consistent cache keys across version formats."""
        flow_type = "onboarding"

        # Different version formats
        versions = [1, "1", "1.0.0"]

        # Generate cache keys
        cache_keys = [
            f"{flow_type}:{normalize_version(v)}"
            for v in versions
        ]

        # All should normalize to same key
        assert len(set(cache_keys)) == 1
        assert cache_keys[0] == "onboarding:1.0.0"
