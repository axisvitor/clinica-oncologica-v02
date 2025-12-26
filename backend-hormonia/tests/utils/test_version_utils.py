"""
Tests for version utility functions.

Tests version parsing, normalization, comparison, and validation
to ensure backward compatibility with both int and semantic versions.
"""

import pytest
from app.utils.version_utils import (
    parse_version,
    normalize_version,
    to_int_version,
    compare_versions,
    is_valid_version,
    is_semantic_version,
    get_major_version,
    get_minor_version,
    get_patch_version,
    increment_major,
    increment_minor,
    increment_patch,
    version_to_dict,
    VersionError,
    DEFAULT_VERSION,
    INITIAL_VERSION,
)


class TestParseVersion:
    """Test version parsing functionality."""

    def test_parse_semantic_version(self):
        """Test parsing semantic version strings."""
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("0.1.0") == (0, 1, 0)
        assert parse_version("10.20.30") == (10, 20, 30)

    def test_parse_integer_version(self):
        """Test parsing integer versions (legacy)."""
        assert parse_version(1) == (1, 0, 0)
        assert parse_version(5) == (5, 0, 0)
        assert parse_version(42) == (42, 0, 0)

    def test_parse_string_integer_version(self):
        """Test parsing string integers (legacy)."""
        assert parse_version("1") == (1, 0, 0)
        assert parse_version("5") == (5, 0, 0)
        assert parse_version("42") == (42, 0, 0)

    def test_parse_none_version(self):
        """Test parsing None returns default."""
        assert parse_version(None) == (1, 0, 0)

    def test_parse_invalid_version(self):
        """Test parsing invalid versions raises error."""
        with pytest.raises(VersionError):
            parse_version("invalid")
        with pytest.raises(VersionError):
            parse_version("1.2")
        with pytest.raises(VersionError):
            parse_version("1.2.3.4")
        with pytest.raises(VersionError):
            parse_version("a.b.c")


class TestNormalizeVersion:
    """Test version normalization functionality."""

    def test_normalize_semantic_version(self):
        """Test normalizing semantic versions."""
        assert normalize_version("1.2.3") == "1.2.3"
        assert normalize_version("0.1.0") == "0.1.0"

    def test_normalize_integer_version(self):
        """Test normalizing integer versions."""
        assert normalize_version(1) == "1.0.0"
        assert normalize_version(5) == "5.0.0"

    def test_normalize_string_integer_version(self):
        """Test normalizing string integer versions."""
        assert normalize_version("1") == "1.0.0"
        assert normalize_version("42") == "42.0.0"

    def test_normalize_none_version(self):
        """Test normalizing None returns default."""
        assert normalize_version(None) == "1.0.0"


class TestToIntVersion:
    """Test conversion to integer version."""

    def test_to_int_semantic_version(self):
        """Test converting semantic version to int."""
        assert to_int_version("1.2.3") == 1
        assert to_int_version("5.0.0") == 5
        assert to_int_version("42.1.2") == 42

    def test_to_int_integer_version(self):
        """Test converting integer version to int."""
        assert to_int_version(1) == 1
        assert to_int_version(5) == 5

    def test_to_int_none_version(self):
        """Test converting None to int."""
        assert to_int_version(None) == 1


class TestCompareVersions:
    """Test version comparison functionality."""

    def test_compare_equal_versions(self):
        """Test comparing equal versions."""
        assert compare_versions("1.2.3", "1.2.3") == 0
        assert compare_versions(1, "1.0.0") == 0
        assert compare_versions("5", 5) == 0

    def test_compare_less_than(self):
        """Test comparing when first version is less."""
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("1.2.3", "1.2.4") == -1
        assert compare_versions("1.2.3", "1.3.0") == -1
        assert compare_versions(1, 2) == -1

    def test_compare_greater_than(self):
        """Test comparing when first version is greater."""
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.2.4", "1.2.3") == 1
        assert compare_versions("1.3.0", "1.2.9") == 1
        assert compare_versions(2, 1) == 1

    def test_compare_major_minor_patch(self):
        """Test comparison across major, minor, patch."""
        # Major takes precedence
        assert compare_versions("2.0.0", "1.9.9") == 1
        # Minor takes precedence over patch
        assert compare_versions("1.2.0", "1.1.9") == 1
        # Patch comparison
        assert compare_versions("1.2.3", "1.2.2") == 1


class TestIsValidVersion:
    """Test version validation."""

    def test_valid_semantic_versions(self):
        """Test valid semantic versions."""
        assert is_valid_version("1.2.3") is True
        assert is_valid_version("0.0.0") is True
        assert is_valid_version("10.20.30") is True

    def test_valid_integer_versions(self):
        """Test valid integer versions."""
        assert is_valid_version(1) is True
        assert is_valid_version(42) is True
        assert is_valid_version("1") is True
        assert is_valid_version("42") is True

    def test_invalid_versions(self):
        """Test invalid versions."""
        assert is_valid_version("invalid") is False
        assert is_valid_version("1.2") is False
        assert is_valid_version("1.2.3.4") is False
        assert is_valid_version("a.b.c") is False


class TestIsSemanticVersion:
    """Test semantic version checking."""

    def test_is_semantic_version_true(self):
        """Test valid semantic versions."""
        assert is_semantic_version("1.2.3") is True
        assert is_semantic_version("0.0.0") is True
        assert is_semantic_version("10.20.30") is True

    def test_is_semantic_version_false(self):
        """Test non-semantic versions."""
        assert is_semantic_version("1") is False
        assert is_semantic_version("1.2") is False
        assert is_semantic_version("invalid") is False
        assert is_semantic_version(1) is False


class TestVersionComponents:
    """Test getting version components."""

    def test_get_major_version(self):
        """Test getting major version."""
        assert get_major_version("1.2.3") == 1
        assert get_major_version(5) == 5
        assert get_major_version("42") == 42

    def test_get_minor_version(self):
        """Test getting minor version."""
        assert get_minor_version("1.2.3") == 2
        assert get_minor_version(5) == 0
        assert get_minor_version("42.10.0") == 10

    def test_get_patch_version(self):
        """Test getting patch version."""
        assert get_patch_version("1.2.3") == 3
        assert get_patch_version(5) == 0
        assert get_patch_version("1.2.99") == 99


class TestVersionIncrement:
    """Test version increment functions."""

    def test_increment_major(self):
        """Test incrementing major version."""
        assert increment_major("1.2.3") == "2.0.0"
        assert increment_major("0.1.0") == "1.0.0"
        assert increment_major(5) == "6.0.0"

    def test_increment_minor(self):
        """Test incrementing minor version."""
        assert increment_minor("1.2.3") == "1.3.0"
        assert increment_minor("0.1.0") == "0.2.0"
        assert increment_minor(5) == "5.1.0"

    def test_increment_patch(self):
        """Test incrementing patch version."""
        assert increment_patch("1.2.3") == "1.2.4"
        assert increment_patch("0.1.0") == "0.1.1"
        assert increment_patch(5) == "5.0.1"


class TestVersionToDict:
    """Test version dictionary conversion."""

    def test_version_to_dict_semantic(self):
        """Test converting semantic version to dict."""
        result = version_to_dict("1.2.3")
        assert result == {
            'major': 1,
            'minor': 2,
            'patch': 3,
            'string': "1.2.3",
            'integer': 1
        }

    def test_version_to_dict_integer(self):
        """Test converting integer version to dict."""
        result = version_to_dict(5)
        assert result == {
            'major': 5,
            'minor': 0,
            'patch': 0,
            'string': "5.0.0",
            'integer': 5
        }


class TestConstants:
    """Test version constants."""

    def test_default_version(self):
        """Test DEFAULT_VERSION constant."""
        assert DEFAULT_VERSION == "1.0.0"
        assert is_semantic_version(DEFAULT_VERSION)

    def test_initial_version(self):
        """Test INITIAL_VERSION constant."""
        assert INITIAL_VERSION == "0.1.0"
        assert is_semantic_version(INITIAL_VERSION)


class TestBackwardCompatibility:
    """Test backward compatibility scenarios."""

    def test_database_integer_to_semantic(self):
        """Test converting database integer versions to semantic."""
        # Simulate database storing version as integer
        db_version = 1
        semantic_version = normalize_version(db_version)
        assert semantic_version == "1.0.0"

    def test_file_semantic_to_integer(self):
        """Test converting file semantic versions to integer for DB."""
        # Simulate file storing semantic version
        file_version = "2.1.5"
        db_version = to_int_version(file_version)
        assert db_version == 2

    def test_mixed_version_comparison(self):
        """Test comparing versions in different formats."""
        assert compare_versions(1, "1.0.0") == 0
        assert compare_versions("2.0.0", 1) == 1
        assert compare_versions(1, "2.0.0") == -1

    def test_version_key_generation(self):
        """Test generating version keys for cache/files."""
        # Legacy integer version
        v1 = normalize_version(1)
        assert v1 == "1.0.0"

        # Semantic version
        v2 = normalize_version("1.2.3")
        assert v2 == "1.2.3"

        # String integer
        v3 = normalize_version("5")
        assert v3 == "5.0.0"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_whitespace_handling(self):
        """Test handling versions with whitespace."""
        assert normalize_version("  1.2.3  ") == "1.2.3"
        assert normalize_version(" 5 ") == "5.0.0"

    def test_large_version_numbers(self):
        """Test handling large version numbers."""
        assert parse_version("100.200.300") == (100, 200, 300)
        assert normalize_version(999) == "999.0.0"

    def test_zero_versions(self):
        """Test handling zero versions."""
        assert parse_version("0.0.0") == (0, 0, 0)
        assert normalize_version(0) == "0.0.0"
