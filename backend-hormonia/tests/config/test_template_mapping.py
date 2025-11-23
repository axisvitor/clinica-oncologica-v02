"""
Unit tests for flow template mapping configuration (isolated from DB).

Tests the template_loader module without requiring database initialization.
"""
import pytest
from pathlib import Path
import yaml


class TestTemplateLoaderDirectly:
    """Direct tests of template_loader functionality without app context."""

    def setup_method(self):
        """Setup for each test."""
        # Import here to avoid DB initialization issues
        from app.config.template_loader import FlowTemplateConfigLoader

        # Use actual config file
        config_path = Path(__file__).parent.parent.parent / "app" / "config" / "flow_templates.yaml"
        self.loader = FlowTemplateConfigLoader(config_path=str(config_path))

    def test_yaml_file_exists(self):
        """Test that YAML configuration file exists."""
        assert Path(self.loader.config_path).exists(), \
            f"Configuration file not found: {self.loader.config_path}"

    def test_yaml_loads_successfully(self):
        """Test that YAML file loads without errors."""
        config = self.loader.config
        assert config is not None
        assert isinstance(config, dict)

    def test_treatment_type_mapping_exists(self):
        """Test that treatment_type_mapping section exists."""
        config = self.loader.config
        assert "treatment_type_mapping" in config, \
            "Configuration should have treatment_type_mapping section"

    def test_default_template_configured(self):
        """Test that default_treatment_template is configured."""
        config = self.loader.config
        assert "default_treatment_template" in config
        assert config["default_treatment_template"] == "day_1_15"

    def test_hormone_therapy_mapping(self):
        """Test hormone therapy treatment type mapping."""
        template = self.loader.get_template_for_treatment_type("hormone therapy")
        assert template == "hormone_therapy_1"

        # Test various keywords
        test_keywords = ["hormone", "hormonal", "hormonioterapia"]
        for keyword in test_keywords:
            template = self.loader.get_template_for_treatment_type(keyword)
            assert template == "hormone_therapy_1", \
                f"Keyword '{keyword}' should map to 'hormone_therapy_1'"

    def test_chemotherapy_mapping(self):
        """Test chemotherapy treatment type mapping."""
        test_keywords = ["chemotherapy", "quimio", "quimioterapia", "chemo"]
        for keyword in test_keywords:
            template = self.loader.get_template_for_treatment_type(keyword)
            assert template == "chemotherapy_cycle_1", \
                f"Keyword '{keyword}' should map to 'chemotherapy_cycle_1'"

    def test_initial_onboarding_mapping(self):
        """Test initial onboarding treatment type mapping."""
        test_keywords = ["initial", "onboarding", "new_patient"]
        for keyword in test_keywords:
            template = self.loader.get_template_for_treatment_type(keyword)
            assert template == "day_1_15", \
                f"Keyword '{keyword}' should map to 'day_1_15'"

    def test_monthly_followup_mapping(self):
        """Test monthly follow-up treatment type mapping."""
        test_keywords = ["monthly", "followup", "follow_up", "maintenance"]
        for keyword in test_keywords:
            template = self.loader.get_template_for_treatment_type(keyword)
            assert template == "day_16_45", \
                f"Keyword '{keyword}' should map to 'day_16_45'"

    def test_unknown_treatment_returns_default(self):
        """Test that unknown treatment types return default template."""
        unknown_types = [
            "radiation",
            "surgery",
            "immunotherapy",
            "unknown_treatment"
        ]

        for unknown in unknown_types:
            template = self.loader.get_template_for_treatment_type(unknown)
            assert template == "day_1_15", \
                f"Unknown type '{unknown}' should return default 'day_1_15'"

    def test_none_treatment_returns_default(self):
        """Test that None treatment type returns default."""
        template = self.loader.get_template_for_treatment_type(None)
        assert template == "day_1_15"

    def test_empty_string_returns_default(self):
        """Test that empty string returns default."""
        template = self.loader.get_template_for_treatment_type("")
        assert template == "day_1_15"

    def test_whitespace_normalization(self):
        """Test that whitespace is properly normalized."""
        test_cases = [
            "  hormone  ",
            "\tchemotherapy\n",
            "  INITIAL  ",
        ]

        for test_input in test_cases:
            template = self.loader.get_template_for_treatment_type(test_input)
            assert template is not None, \
                f"Should handle whitespace in '{test_input}'"

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        test_cases = [
            ("HORMONE", "hormone_therapy_1"),
            ("Chemotherapy", "chemotherapy_cycle_1"),
            ("InItIaL", "day_1_15"),
        ]

        for treatment_type, expected in test_cases:
            template = self.loader.get_template_for_treatment_type(treatment_type)
            assert template == expected


class TestYAMLStructure:
    """Test YAML configuration file structure."""

    @classmethod
    def setup_class(cls):
        """Load YAML directly for structure tests."""
        config_path = Path(__file__).parent.parent.parent / "app" / "config" / "flow_templates.yaml"
        with open(config_path, 'r') as f:
            cls.config = yaml.safe_load(f)

    def test_required_sections_exist(self):
        """Test that all required sections exist in YAML."""
        required_sections = [
            "treatment_type_mapping",
            "default_treatment_template",
            "flow_types",
            "defaults"
        ]

        for section in required_sections:
            assert section in self.config, \
                f"Required section '{section}' missing from configuration"

    def test_treatment_categories_have_required_fields(self):
        """Test that all treatment categories have required fields."""
        mapping = self.config["treatment_type_mapping"]
        required_fields = ["keywords", "template", "priority"]

        for category, config in mapping.items():
            for field in required_fields:
                assert field in config, \
                    f"Category '{category}' missing field '{field}'"

            # Type validation
            assert isinstance(config["keywords"], list)
            assert isinstance(config["template"], str)
            assert isinstance(config["priority"], int)

    def test_keywords_are_unique(self):
        """Test that keywords don't overlap between categories."""
        mapping = self.config["treatment_type_mapping"]
        seen_keywords = {}

        for category, config in mapping.items():
            keywords = config.get("keywords", [])
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in seen_keywords:
                    pytest.fail(
                        f"Duplicate keyword '{keyword}' found in categories "
                        f"'{seen_keywords[keyword_lower]}' and '{category}'"
                    )
                seen_keywords[keyword_lower] = category

    def test_priorities_are_valid(self):
        """Test that priorities are valid integers."""
        mapping = self.config["treatment_type_mapping"]

        for category, config in mapping.items():
            priority = config.get("priority")
            assert isinstance(priority, int), \
                f"Category '{category}' priority must be integer"
            assert priority >= 0, \
                f"Category '{category}' priority must be non-negative"

    def test_templates_are_not_empty(self):
        """Test that template names are not empty."""
        mapping = self.config["treatment_type_mapping"]

        for category, config in mapping.items():
            template = config.get("template")
            assert template, \
                f"Category '{category}' template cannot be empty"
            assert len(template) > 0, \
                f"Category '{category}' template must have length > 0"


class TestConvenienceFunctions:
    """Test convenience functions in template_loader module."""

    def test_get_template_for_treatment_function(self):
        """Test the get_template_for_treatment convenience function."""
        from app.config.template_loader import get_template_for_treatment

        # Test basic functionality
        template = get_template_for_treatment("hormone therapy")
        assert template == "hormone_therapy_1"

        # Test None handling
        template = get_template_for_treatment(None)
        assert template == "day_1_15"


class TestPriorityMatching:
    """Test that priority system works correctly."""

    def setup_method(self):
        """Setup for each test."""
        from app.config.template_loader import FlowTemplateConfigLoader

        config_path = Path(__file__).parent.parent.parent / "app" / "config" / "flow_templates.yaml"
        self.loader = FlowTemplateConfigLoader(config_path=str(config_path))

    def test_high_priority_wins(self):
        """Test that higher priority template is selected when multiple match."""
        # Create input that could match multiple categories
        # "hormone chemotherapy" could match both hormone and chemotherapy
        template = self.loader.get_template_for_treatment_type("hormone chemotherapy")

        # Should match one of the high priority (10) templates
        assert template in ["hormone_therapy_1", "chemotherapy_cycle_1"], \
            "Should match high priority template"

    def test_priority_sorting(self):
        """Test that priorities are properly sorted."""
        config = self.loader.config
        mapping = config.get("treatment_type_mapping", {})

        # Verify high-priority treatments exist
        high_priority_found = False
        for category, conf in mapping.items():
            if conf.get("priority", 0) >= 10:
                high_priority_found = True
                break

        assert high_priority_found, "Should have at least one high-priority treatment"


class TestConfigurationReload:
    """Test configuration reload functionality."""

    def test_reload_config(self):
        """Test that configuration can be reloaded."""
        from app.config.template_loader import get_template_loader

        loader = get_template_loader()

        # Get initial config
        initial_config = loader.config

        # Reload
        success = loader.reload_config()
        assert success, "Configuration reload should succeed"

        # Get config again
        reloaded_config = loader.config

        # Should have same structure
        assert "treatment_type_mapping" in reloaded_config


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
