"""
Tests for flow template mapping configuration.

Validates that treatment type to flow template mapping works correctly
using the centralized YAML configuration.
"""
import pytest
from app.config.template_loader import (
    get_template_for_treatment,
    get_template_loader,
    FlowTemplateConfigLoader
)


class TestFlowTemplateMapping:
    """Test suite for treatment type to flow template mapping."""

    def test_hormone_therapy_keywords(self):
        """Test hormone therapy keyword matching."""
        test_cases = [
            ("hormone", "hormone_therapy_1"),
            ("hormonal", "hormone_therapy_1"),
            ("hormone_therapy", "hormone_therapy_1"),
            ("hormonioterapia", "hormone_therapy_1"),
            ("Hormone Therapy", "hormone_therapy_1"),  # Case insensitive
            ("HORMONAL TREATMENT", "hormone_therapy_1"),
        ]

        for treatment_type, expected_template in test_cases:
            template = get_template_for_treatment(treatment_type)
            assert template == expected_template, \
                f"Expected '{expected_template}' for '{treatment_type}', got '{template}'"

    def test_chemotherapy_keywords(self):
        """Test chemotherapy keyword matching."""
        test_cases = [
            ("chemotherapy", "chemotherapy_cycle_1"),
            ("quimio", "chemotherapy_cycle_1"),
            ("quimioterapia", "chemotherapy_cycle_1"),
            ("chemo", "chemotherapy_cycle_1"),
            ("Chemotherapy Treatment", "chemotherapy_cycle_1"),
        ]

        for treatment_type, expected_template in test_cases:
            template = get_template_for_treatment(treatment_type)
            assert template == expected_template, \
                f"Expected '{expected_template}' for '{treatment_type}', got '{template}'"

    def test_initial_onboarding_keywords(self):
        """Test initial onboarding keyword matching."""
        test_cases = [
            ("initial", "day_1_15"),
            ("onboarding", "day_1_15"),
            ("new_patient", "day_1_15"),
            ("Initial Treatment", "day_1_15"),
        ]

        for treatment_type, expected_template in test_cases:
            template = get_template_for_treatment(treatment_type)
            assert template == expected_template, \
                f"Expected '{expected_template}' for '{treatment_type}', got '{template}'"

    def test_monthly_followup_keywords(self):
        """Test monthly follow-up keyword matching."""
        test_cases = [
            ("monthly", "day_16_45"),
            ("followup", "day_16_45"),
            ("follow_up", "day_16_45"),
            ("maintenance", "day_16_45"),
            ("Monthly Check", "day_16_45"),
        ]

        for treatment_type, expected_template in test_cases:
            template = get_template_for_treatment(treatment_type)
            assert template == expected_template, \
                f"Expected '{expected_template}' for '{treatment_type}', got '{template}'"

    def test_default_template_for_unknown_type(self):
        """Test default template is returned for unknown treatment types."""
        unknown_types = [
            "radiation",
            "surgery",
            "immunotherapy",
            "unknown_treatment",
            "xyz123"
        ]

        for treatment_type in unknown_types:
            template = get_template_for_treatment(treatment_type)
            assert template == "day_1_15", \
                f"Expected default 'day_1_15' for unknown type '{treatment_type}', got '{template}'"

    def test_none_treatment_type(self):
        """Test None treatment type returns default."""
        template = get_template_for_treatment(None)
        assert template == "day_1_15", \
            f"Expected default 'day_1_15' for None, got '{template}'"

    def test_empty_string_treatment_type(self):
        """Test empty string returns default."""
        template = get_template_for_treatment("")
        assert template == "day_1_15", \
            f"Expected default 'day_1_15' for empty string, got '{template}'"

    def test_whitespace_normalization(self):
        """Test that whitespace is properly handled."""
        test_cases = [
            ("  hormone  ", "hormone_therapy_1"),
            ("\tchemotherapy\n", "chemotherapy_cycle_1"),
            ("  INITIAL  ", "day_1_15"),
        ]

        for treatment_type, expected_template in test_cases:
            template = get_template_for_treatment(treatment_type)
            assert template == expected_template, \
                f"Expected '{expected_template}' for '{treatment_type}', got '{template}'"

    def test_priority_matching(self):
        """Test that higher priority keywords are matched first."""
        # If a treatment type contains multiple keywords,
        # the higher priority one should win
        loader = get_template_loader()

        # Verify priority configuration exists
        mapping = loader.config.get("treatment_type_mapping", {})
        assert mapping, "Treatment type mapping should be configured"

        # Test that specific treatments have higher priority than generic
        template = get_template_for_treatment("hormone chemotherapy")
        # Should match hormone (priority 10) or chemotherapy (priority 10)
        # Both have same priority, first match wins
        assert template in ["hormone_therapy_1", "chemotherapy_cycle_1"]

    def test_configuration_reload(self):
        """Test that configuration can be reloaded."""
        loader = get_template_loader()

        # Get initial template
        template1 = get_template_for_treatment("hormone")

        # Reload configuration
        success = loader.reload_config()
        assert success, "Configuration reload should succeed"

        # Get template again
        template2 = get_template_for_treatment("hormone")

        # Should be the same
        assert template1 == template2

    def test_loader_singleton(self):
        """Test that get_template_loader returns singleton instance."""
        loader1 = get_template_loader()
        loader2 = get_template_loader()

        assert loader1 is loader2, "Should return same singleton instance"

    def test_configuration_fallback(self):
        """Test that fallback configuration works if file is missing."""
        # Create loader with non-existent config
        loader = FlowTemplateConfigLoader(config_path="/nonexistent/path.yaml")

        # Should use fallback config
        config = loader.config
        assert config is not None, "Should have fallback configuration"
        assert "flow_types" in config, "Fallback should have flow_types"
        assert "defaults" in config, "Fallback should have defaults"


class TestFlowServiceIntegration:
    """Integration tests with PatientFlowService."""

    def test_flow_service_uses_template_loader(self):
        """Test that FlowService._select_template uses template loader."""
        from app.services.patient.flow_service import PatientFlowService
        from unittest.mock import Mock

        # Create mock dependencies
        mock_db = Mock()
        mock_flow_engine = Mock()

        # Create service
        service = PatientFlowService(
            db=mock_db,
            flow_engine=mock_flow_engine
        )

        # Test template selection
        test_cases = [
            ("hormone therapy", "hormone_therapy_1"),
            ("chemotherapy", "chemotherapy_cycle_1"),
            ("initial", "day_1_15"),
            ("unknown", "day_1_15"),  # default
            (None, "day_1_15"),  # default
        ]

        for treatment_type, expected_template in test_cases:
            template = service._select_template(treatment_type)
            assert template == expected_template, \
                f"Service should return '{expected_template}' for '{treatment_type}', got '{template}'"


class TestYAMLConfiguration:
    """Test YAML configuration structure."""

    def test_yaml_has_treatment_mapping(self):
        """Test that YAML config has treatment_type_mapping section."""
        loader = get_template_loader()
        config = loader.config

        assert "treatment_type_mapping" in config, \
            "Configuration should have treatment_type_mapping"

    def test_yaml_has_default_template(self):
        """Test that YAML config has default_treatment_template."""
        loader = get_template_loader()
        config = loader.config

        assert "default_treatment_template" in config, \
            "Configuration should have default_treatment_template"

        default = config["default_treatment_template"]
        assert default == "day_1_15", \
            f"Default template should be 'day_1_15', got '{default}'"

    def test_all_categories_have_required_fields(self):
        """Test that all treatment categories have required fields."""
        loader = get_template_loader()
        mapping = loader.config.get("treatment_type_mapping", {})

        required_fields = ["keywords", "template", "priority"]

        for category, config in mapping.items():
            for field in required_fields:
                assert field in config, \
                    f"Category '{category}' missing required field '{field}'"

            # Validate field types
            assert isinstance(config["keywords"], list), \
                f"Category '{category}' keywords should be a list"
            assert isinstance(config["template"], str), \
                f"Category '{category}' template should be a string"
            assert isinstance(config["priority"], int), \
                f"Category '{category}' priority should be an integer"

    def test_no_duplicate_keywords(self):
        """Test that keywords are not duplicated across categories."""
        loader = get_template_loader()
        mapping = loader.config.get("treatment_type_mapping", {})

        seen_keywords = set()

        for category, config in mapping.items():
            keywords = config.get("keywords", [])
            for keyword in keywords:
                keyword_lower = keyword.lower()
                assert keyword_lower not in seen_keywords, \
                    f"Duplicate keyword '{keyword}' found in category '{category}'"
                seen_keywords.add(keyword_lower)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
