#!/usr/bin/env python3
"""
Verification script for P0-3 Phone Number Matching Fix.

Tests phone normalization and patient lookup strategies without requiring database.
Can be run standalone to verify the fix logic works correctly.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend-hormonia"
sys.path.insert(0, str(backend_path))


class MockPatientService:
    """Mock patient service for testing phone lookup strategies."""

    def __init__(self, stored_phones):
        """
        Initialize with a list of phone numbers as stored in database.

        Args:
            stored_phones: List of phone numbers in database format
        """
        self.stored_phones = stored_phones
        self.lookup_attempts = []

    def get_by_phone(self, phone: str):
        """Mock get_by_phone that tracks attempts."""
        self.lookup_attempts.append(phone)
        if phone in self.stored_phones:
            return {"phone": phone, "found": True}
        return None


def test_phone_normalization():
    """Test E.164 normalization logic."""
    from app.services.webhook_processor import WebhookProcessor
    from unittest.mock import Mock

    processor = WebhookProcessor(Mock())

    test_cases = [
        # (input, expected_output)
        ("+5511987654321", "+5511987654321"),
        ("5511987654321", "+5511987654321"),
        ("11987654321", "+5511987654321"),
        ("+55 11 98765-4321", "+5511987654321"),
        ("0005511987654321", "+5511987654321"),
        ("+5521987654321", "+5521987654321"),  # Rio
    ]

    print("Testing E.164 Normalization:")
    print("=" * 60)

    all_passed = True
    for input_phone, expected in test_cases:
        result = processor._normalize_phone_e164(input_phone)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_passed = False
        print(f"{status} '{input_phone}' → '{result}' (expected: '{expected}')")

    print()
    return all_passed


def test_phone_cleaning():
    """Test WhatsApp phone cleaning."""
    from app.services.webhook_processor import WebhookProcessor
    from unittest.mock import Mock

    processor = WebhookProcessor(Mock())

    test_cases = [
        ("5511987654321@s.whatsapp.net", "5511987654321"),
        ("+5511987654321@s.whatsapp.net", "+5511987654321"),
        ("+55 (11) 98765-4321", "+5511987654321"),
        ("005511987654321", "5511987654321"),
        ("+005511987654321", "+5511987654321"),
    ]

    print("Testing Phone Cleaning:")
    print("=" * 60)

    all_passed = True
    for input_phone, expected in test_cases:
        result = processor._clean_phone_number(input_phone)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_passed = False
        print(f"{status} '{input_phone}' → '{result}' (expected: '{expected}')")

    print()
    return all_passed


def test_lookup_strategies():
    """Test patient lookup with different stored formats."""
    from app.services.webhook_processor import WebhookProcessor
    from unittest.mock import Mock

    scenarios = [
        {
            "name": "Patient stored WITH + prefix",
            "stored": ["+5511987654321"],
            "incoming": "5511987654321@s.whatsapp.net",
            "should_find": True
        },
        {
            "name": "Patient stored WITHOUT + prefix",
            "stored": ["5511987654321"],
            "incoming": "5511987654321@s.whatsapp.net",
            "should_find": True
        },
        {
            "name": "Patient stored as local (11 digits)",
            "stored": ["11987654321"],
            "incoming": "+5511987654321@s.whatsapp.net",
            "should_find": True
        },
        {
            "name": "Patient not in database",
            "stored": ["+5521987654321"],
            "incoming": "5511987654321@s.whatsapp.net",
            "should_find": False
        },
    ]

    print("Testing Patient Lookup Strategies:")
    print("=" * 60)

    all_passed = True
    for scenario in scenarios:
        db_mock = Mock()
        processor = WebhookProcessor(db_mock)

        # Setup mock patient service
        mock_service = MockPatientService(scenario["stored"])
        processor.patient_service = mock_service

        # Clean phone (as webhook would)
        cleaned = processor._clean_phone_number(scenario["incoming"])

        # Find patient
        patient = processor._find_patient_by_phone(cleaned)

        found = patient is not None
        expected = scenario["should_find"]
        status = "✅" if found == expected else "❌"

        if found != expected:
            all_passed = False

        print(f"\n{status} {scenario['name']}")
        print(f"   Stored: {scenario['stored']}")
        print(f"   Incoming: {scenario['incoming']}")
        print(f"   Cleaned: {cleaned}")
        print(f"   Lookup attempts: {mock_service.lookup_attempts}")
        print(f"   Found: {found} (expected: {expected})")

    print()
    return all_passed


def test_real_world_scenarios():
    """Test real-world WhatsApp webhook scenarios."""
    from app.services.webhook_processor import WebhookProcessor
    from unittest.mock import Mock

    print("Testing Real-World Scenarios:")
    print("=" * 60)

    scenarios = [
        {
            "description": "Standard WhatsApp message (most common)",
            "webhook": {"key": {"remoteJid": "5511987654321@s.whatsapp.net"}},
            "db_format": "+5511987654321",
            "should_match": True
        },
        {
            "description": "WhatsApp with + in remoteJid",
            "webhook": {"key": {"remoteJid": "+5511987654321@s.whatsapp.net"}},
            "db_format": "+5511987654321",
            "should_match": True
        },
        {
            "description": "Old patient without + in database",
            "webhook": {"key": {"remoteJid": "5511987654321@s.whatsapp.net"}},
            "db_format": "5511987654321",
            "should_match": True
        },
        {
            "description": "Local format in database",
            "webhook": {"key": {"remoteJid": "5511987654321@s.whatsapp.net"}},
            "db_format": "11987654321",
            "should_match": True
        },
    ]

    all_passed = True
    for scenario in scenarios:
        db_mock = Mock()
        processor = WebhookProcessor(db_mock)

        # Setup mock
        mock_service = MockPatientService([scenario["db_format"]])
        processor.patient_service = mock_service

        # Extract phone from webhook (as _extract_message_data would)
        remote_jid = scenario["webhook"]["key"]["remoteJid"]
        cleaned = processor._clean_phone_number(remote_jid)

        # Find patient
        patient = processor._find_patient_by_phone(cleaned)

        found = patient is not None
        expected = scenario["should_match"]
        status = "✅" if found == expected else "❌"

        if found != expected:
            all_passed = False

        print(f"\n{status} {scenario['description']}")
        print(f"   WhatsApp: {remote_jid}")
        print(f"   DB format: {scenario['db_format']}")
        print(f"   Cleaned: {cleaned}")
        print(f"   Attempts: {len(mock_service.lookup_attempts)}")
        print(f"   Match: {found} (expected: {expected})")

    print()
    return all_passed


def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("P0-3 Phone Number Matching Fix - Verification")
    print("=" * 60 + "\n")

    results = []

    # Run all tests
    results.append(("E.164 Normalization", test_phone_normalization()))
    results.append(("Phone Cleaning", test_phone_cleaning()))
    results.append(("Lookup Strategies", test_lookup_strategies()))
    results.append(("Real-World Scenarios", test_real_world_scenarios()))

    # Summary
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All verification tests PASSED!")
        print("✅ Phone number matching fix is working correctly.")
        return 0
    else:
        print("❌ Some verification tests FAILED!")
        print("⚠️  Please review the fix implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
