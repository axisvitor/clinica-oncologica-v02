#!/usr/bin/env python3
"""
Standalone test for template mapping refactoring.

Tests template_loader functionality without pytest or database dependencies.
Run directly: python3 tests/test_template_mapping_standalone.py
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Now import what we need
from app.config.template_loader import (
    FlowTemplateConfigLoader,
    get_template_for_treatment
)


def test_hormone_therapy_mapping():
    """Test hormone therapy keyword mapping."""
    print("Testing hormone therapy mapping...")

    test_cases = [
        ("hormone", "hormone_therapy_1"),
        ("hormonal", "hormone_therapy_1"),
        ("hormone_therapy", "hormone_therapy_1"),
        ("hormonioterapia", "hormone_therapy_1"),
        ("Hormone Therapy", "hormone_therapy_1"),  # case insensitive
    ]

    for treatment_type, expected in test_cases:
        result = get_template_for_treatment(treatment_type)
        assert result == expected, \
            f"FAIL: Expected '{expected}' for '{treatment_type}', got '{result}'"
        print(f"  ✓ '{treatment_type}' → '{result}'")

    print("✅ Hormone therapy mapping tests passed\n")


def test_chemotherapy_mapping():
    """Test chemotherapy keyword mapping."""
    print("Testing chemotherapy mapping...")

    test_cases = [
        ("chemotherapy", "chemotherapy_cycle_1"),
        ("quimio", "chemotherapy_cycle_1"),
        ("quimioterapia", "chemotherapy_cycle_1"),
        ("chemo", "chemotherapy_cycle_1"),
    ]

    for treatment_type, expected in test_cases:
        result = get_template_for_treatment(treatment_type)
        assert result == expected, \
            f"FAIL: Expected '{expected}' for '{treatment_type}', got '{result}'"
        print(f"  ✓ '{treatment_type}' → '{result}'")

    print("✅ Chemotherapy mapping tests passed\n")


def test_initial_mapping():
    """Test initial/onboarding keyword mapping."""
    print("Testing initial onboarding mapping...")

    test_cases = [
        ("initial", "day_1_15"),
        ("onboarding", "day_1_15"),
        ("new_patient", "day_1_15"),
    ]

    for treatment_type, expected in test_cases:
        result = get_template_for_treatment(treatment_type)
        assert result == expected, \
            f"FAIL: Expected '{expected}' for '{treatment_type}', got '{result}'"
        print(f"  ✓ '{treatment_type}' → '{result}'")

    print("✅ Initial onboarding mapping tests passed\n")


def test_monthly_mapping():
    """Test monthly follow-up keyword mapping."""
    print("Testing monthly follow-up mapping...")

    test_cases = [
        ("monthly", "day_16_45"),
        ("followup", "day_16_45"),
        ("follow_up", "day_16_45"),
        ("maintenance", "day_16_45"),
    ]

    for treatment_type, expected in test_cases:
        result = get_template_for_treatment(treatment_type)
        assert result == expected, \
            f"FAIL: Expected '{expected}' for '{treatment_type}', got '{result}'"
        print(f"  ✓ '{treatment_type}' → '{result}'")

    print("✅ Monthly follow-up mapping tests passed\n")


def test_default_template():
    """Test default template for unknown types."""
    print("Testing default template fallback...")

    test_cases = [
        None,
        "",
        "  ",
        "radiation",
        "surgery",
        "immunotherapy",
        "unknown_treatment",
    ]

    for treatment_type in test_cases:
        result = get_template_for_treatment(treatment_type)
        assert result == "day_1_15", \
            f"FAIL: Expected default 'day_1_15' for '{treatment_type}', got '{result}'"
        print(f"  ✓ '{treatment_type}' → '{result}' (default)")

    print("✅ Default template tests passed\n")


def test_whitespace_handling():
    """Test whitespace normalization."""
    print("Testing whitespace handling...")

    test_cases = [
        ("  hormone  ", "hormone_therapy_1"),
        ("\tchemotherapy\n", "chemotherapy_cycle_1"),
        ("  initial  ", "day_1_15"),
    ]

    for treatment_type, expected in test_cases:
        result = get_template_for_treatment(treatment_type)
        assert result == expected, \
            f"FAIL: Expected '{expected}' for '{repr(treatment_type)}', got '{result}'"
        print(f"  ✓ {repr(treatment_type)} → '{result}'")

    print("✅ Whitespace handling tests passed\n")


def test_yaml_structure():
    """Test YAML configuration structure."""
    print("Testing YAML configuration structure...")

    config_path = backend_path / "app" / "config" / "flow_templates.yaml"
    loader = FlowTemplateConfigLoader(config_path=str(config_path))

    # Check required sections
    config = loader.config
    assert "treatment_type_mapping" in config, "Missing treatment_type_mapping"
    assert "default_treatment_template" in config, "Missing default_treatment_template"

    print("  ✓ treatment_type_mapping exists")
    print("  ✓ default_treatment_template exists")

    # Check each category has required fields
    mapping = config["treatment_type_mapping"]
    for category, conf in mapping.items():
        assert "keywords" in conf, f"Category '{category}' missing keywords"
        assert "template" in conf, f"Category '{category}' missing template"
        assert "priority" in conf, f"Category '{category}' missing priority"

        assert isinstance(conf["keywords"], list), f"Category '{category}' keywords not a list"
        assert isinstance(conf["template"], str), f"Category '{category}' template not a string"
        assert isinstance(conf["priority"], int), f"Category '{category}' priority not an int"

        print(f"  ✓ Category '{category}' properly configured")

    print("✅ YAML structure tests passed\n")


def test_no_duplicate_keywords():
    """Test that keywords are unique across categories."""
    print("Testing keyword uniqueness...")

    config_path = backend_path / "app" / "config" / "flow_templates.yaml"
    loader = FlowTemplateConfigLoader(config_path=str(config_path))

    mapping = loader.config["treatment_type_mapping"]
    seen_keywords = {}

    for category, conf in mapping.items():
        for keyword in conf.get("keywords", []):
            keyword_lower = keyword.lower()
            if keyword_lower in seen_keywords:
                raise AssertionError(
                    f"Duplicate keyword '{keyword}' in categories "
                    f"'{seen_keywords[keyword_lower]}' and '{category}'"
                )
            seen_keywords[keyword_lower] = category

    print(f"  ✓ All {len(seen_keywords)} keywords are unique")
    print("✅ Keyword uniqueness test passed\n")


def test_flow_service_integration():
    """Test integration with PatientFlowService._select_template."""
    print("Testing PatientFlowService integration...")

    # Import here to avoid circular dependencies
    from unittest.mock import Mock
    from app.services.patient.flow_service import PatientFlowService

    # Create mock dependencies
    mock_db = Mock()
    mock_flow_engine = Mock()

    # Create service
    service = PatientFlowService(
        db=mock_db,
        flow_engine=mock_flow_engine
    )

    # Test template selection through service
    test_cases = [
        ("hormone therapy", "hormone_therapy_1"),
        ("chemotherapy", "chemotherapy_cycle_1"),
        ("initial", "day_1_15"),
        (None, "day_1_15"),
    ]

    for treatment_type, expected in test_cases:
        result = service._select_template(treatment_type)
        assert result == expected, \
            f"FAIL: Service returned '{result}' for '{treatment_type}', expected '{expected}'"
        print(f"  ✓ Service: '{treatment_type}' → '{result}'")

    print("✅ FlowService integration tests passed\n")


def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("TEMPLATE MAPPING REFACTORING TESTS")
    print("=" * 60)
    print()

    test_functions = [
        test_hormone_therapy_mapping,
        test_chemotherapy_mapping,
        test_initial_mapping,
        test_monthly_mapping,
        test_default_template,
        test_whitespace_handling,
        test_yaml_structure,
        test_no_duplicate_keywords,
        test_flow_service_integration,
    ]

    failed = 0
    passed = 0

    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} ERROR: {e}\n")
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\n⚠️  Some tests failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
