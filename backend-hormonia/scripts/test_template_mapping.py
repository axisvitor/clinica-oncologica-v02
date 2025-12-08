#!/usr/bin/env python3
"""
Direct test of template mapping without complex imports.

Tests YAML configuration and basic template_loader logic.
"""
import yaml
from pathlib import Path


def load_yaml_config():
    """Load YAML configuration directly."""
    config_path = Path(__file__).parent.parent / "app" / "config" / "flow_templates.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_template_for_treatment_type(config, treatment_type):
    """
    Simplified version of template_loader.get_template_for_treatment_type().

    Tests the core logic without SQLAlchemy dependencies.
    """
    if not treatment_type:
        return config.get("default_treatment_template", "day_1_15")

    # Normalize input
    type_lower = treatment_type.lower().strip()

    # Get treatment type mapping
    treatment_mapping = config.get("treatment_type_mapping", {})

    # Search for matching keywords (sorted by priority)
    matched_categories = []
    for category, conf in treatment_mapping.items():
        keywords = conf.get("keywords", [])
        priority = conf.get("priority", 0)

        # Check if any keyword matches
        for keyword in keywords:
            if keyword.lower() in type_lower:
                matched_categories.append((priority, conf.get("template")))
                break

    # Return highest priority match
    if matched_categories:
        matched_categories.sort(reverse=True, key=lambda x: x[0])
        return matched_categories[0][1]

    # Return default
    return config.get("default_treatment_template", "day_1_15")


def test_yaml_structure(config):
    """Test YAML structure."""
    print("Testing YAML structure...")

    assert "treatment_type_mapping" in config
    assert "default_treatment_template" in config
    assert config["default_treatment_template"] == "day_1_15"

    print("  ✓ Required sections present")
    print("  ✓ Default template: day_1_15")
    print()


def test_mapping_logic(config):
    """Test template mapping logic."""
    print("Testing template mapping logic...")

    test_cases = [
        # Hormone therapy
        ("hormone", "hormone_therapy_1"),
        ("hormonal", "hormone_therapy_1"),
        ("hormone_therapy", "hormone_therapy_1"),
        ("Hormone Therapy", "hormone_therapy_1"),

        # Chemotherapy
        ("chemotherapy", "chemotherapy_cycle_1"),
        ("quimio", "chemotherapy_cycle_1"),
        ("chemo", "chemotherapy_cycle_1"),

        # Initial
        ("initial", "day_1_15"),
        ("onboarding", "day_1_15"),

        # Monthly
        ("monthly", "day_16_45"),
        ("followup", "day_16_45"),

        # Defaults
        (None, "day_1_15"),
        ("", "day_1_15"),
        ("unknown", "day_1_15"),

        # Whitespace
        ("  hormone  ", "hormone_therapy_1"),
    ]

    for treatment_type, expected in test_cases:
        result = get_template_for_treatment_type(config, treatment_type)
        assert result == expected, \
            f"Failed: '{treatment_type}' → expected '{expected}', got '{result}'"
        print(f"  ✓ '{treatment_type}' → '{result}'")

    print()


def test_categories_structure(config):
    """Test that all categories have proper structure."""
    print("Testing category structure...")

    mapping = config["treatment_type_mapping"]

    for category, conf in mapping.items():
        assert "keywords" in conf
        assert "template" in conf
        assert "priority" in conf

        assert isinstance(conf["keywords"], list)
        assert isinstance(conf["template"], str)
        assert isinstance(conf["priority"], int)

        print(f"  ✓ Category '{category}' properly structured")

    print()


def test_no_duplicates(config):
    """Test no duplicate keywords."""
    print("Testing keyword uniqueness...")

    mapping = config["treatment_type_mapping"]
    seen = {}

    for category, conf in mapping.items():
        for keyword in conf["keywords"]:
            kw_lower = keyword.lower()
            if kw_lower in seen:
                raise AssertionError(
                    f"Duplicate keyword '{keyword}' in {seen[kw_lower]} and {category}"
                )
            seen[kw_lower] = category

    print(f"  ✓ All {len(seen)} keywords unique")
    print()


def main():
    """Run all tests."""
    print("=" * 60)
    print("TEMPLATE MAPPING VALIDATION")
    print("=" * 60)
    print()

    try:
        # Load config
        print("Loading YAML configuration...")
        config = load_yaml_config()
        print("  ✓ YAML loaded successfully")
        print()

        # Run tests
        test_yaml_structure(config)
        test_categories_structure(config)
        test_no_duplicates(config)
        test_mapping_logic(config)

        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
