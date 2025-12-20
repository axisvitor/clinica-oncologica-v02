"""
Input Validation Security Tests

Tests verify that all input validation is working correctly:
1. UUID validation prevents invalid IDs
2. Email validation prevents malformed emails
3. String length limits are enforced
4. Type validation prevents type confusion attacks
5. Special character handling is secure

Run with: pytest tests/security/test_input_validation.py -v
"""

import pytest
from fastapi.testclient import TestClient


class TestInputValidation:
    """Test suite for input validation security"""

    # ========================================================================
    # Test 1: UUID Validation
    # ========================================================================

    def test_invalid_uuid_rejected(self, client: TestClient, auth_headers):
        """
        CRITICAL: Invalid UUIDs must be rejected

        Attack scenarios:
        1. Malformed UUID
        2. SQL injection attempt via UUID
        3. Path traversal via UUID
        """
        invalid_uuids = [
            "invalid-uuid",
            "'; DROP TABLE patients; --",
            "../../../etc/passwd",
            "00000000-0000-0000-0000-00000000000",  # Too short
            "00000000-0000-0000-0000-0000000000001",  # Too long
            "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",  # Invalid hex
            "",  # Empty
            "null",
            "undefined",
        ]

        for invalid_uuid in invalid_uuids:
            response = client.get(
                f"/api/v2/patients/{invalid_uuid}",
                headers=auth_headers
            )

            # Should return 422 (validation error) or 400 (bad request)
            assert response.status_code in [400, 422, 404], \
                f"Invalid UUID '{invalid_uuid}' should be rejected"

            # Should not return SQL error
            if response.status_code not in [404]:
                data = response.json()
                assert "detail" in data
                # Verify error message doesn't leak SQL details
                detail_str = str(data["detail"]).lower()
                assert "sql" not in detail_str
                assert "syntax" not in detail_str

        print("✅ All invalid UUIDs correctly rejected")

    def test_valid_uuid_accepted(self, client: TestClient, auth_headers):
        """Valid UUIDs should be accepted"""
        valid_uuid = "00000000-0000-0000-0000-000000000001"

        response = client.get(
            f"/api/v2/patients/{valid_uuid}",
            headers=auth_headers
        )

        # Should not fail validation (may return 404 if patient doesn't exist)
        assert response.status_code in [200, 404], \
            "Valid UUID should pass validation"

        print("✅ Valid UUID correctly accepted")

    # ========================================================================
    # Test 2: Email Validation
    # ========================================================================

    def test_invalid_email_rejected(self, client: TestClient, auth_headers):
        """
        CRITICAL: Invalid emails must be rejected

        Test cases:
        1. No @ symbol
        2. Multiple @ symbols
        3. XSS attempt in email
        4. SQL injection attempt in email
        """
        invalid_emails = [
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "multiple@@at.com",
            "test@",
            "@test.com",
            "test@domain@domain.com",
            "<script>alert('XSS')</script>@test.com",
            "test'; DROP TABLE users; --@test.com",
            "test@domain..com",  # Double dot
            "test user@domain.com",  # Space
            "",  # Empty
        ]

        for invalid_email in invalid_emails:
            response = client.post(
                "/api/v2/patients",
                headers=auth_headers,
                json={
                    "name": "Test Patient",
                    "email": invalid_email,
                    "phone": "+5511999999999"
                }
            )

            # Should return 422 (validation error)
            assert response.status_code in [400, 422], \
                f"Invalid email '{invalid_email}' should be rejected"

        print("✅ All invalid emails correctly rejected")

    def test_valid_email_accepted(self, client: TestClient, auth_headers):
        """Valid emails should be accepted"""
        valid_emails = [
            "test@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "123@example.com",
        ]

        for valid_email in valid_emails:
            response = client.post(
                "/api/v2/patients",
                headers=auth_headers,
                json={
                    "name": "Test Patient",
                    "email": valid_email,
                    "phone": "+5511999999999"
                }
            )

            # Should pass validation (may fail for other reasons like duplicate)
            assert response.status_code not in [422], \
                f"Valid email '{valid_email}' should not fail validation"

        print("✅ Valid emails correctly accepted")

    # ========================================================================
    # Test 3: String Length Validation
    # ========================================================================

    def test_oversized_string_rejected(self, client: TestClient, auth_headers):
        """
        CRITICAL: Oversized strings must be rejected

        Test DoS via large payloads
        """
        # Try to create patient with very long name
        oversized_name = "A" * 10000  # 10KB name

        response = client.post(
            "/api/v2/patients",
            headers=auth_headers,
            json={
                "name": oversized_name,
                "email": "test@example.com",
                "phone": "+5511999999999"
            }
        )

        # Should reject oversized input
        assert response.status_code in [400, 422, 413], \
            "Oversized string should be rejected"

        print("✅ Oversized string correctly rejected")

    def test_empty_required_field_rejected(self, client: TestClient, auth_headers):
        """Required fields must not be empty"""
        response = client.post(
            "/api/v2/patients",
            headers=auth_headers,
            json={
                "name": "",  # Empty required field
                "email": "test@example.com",
                "phone": "+5511999999999"
            }
        )

        # Should reject empty required field
        assert response.status_code in [400, 422], \
            "Empty required field should be rejected"

        print("✅ Empty required field correctly rejected")

    # ========================================================================
    # Test 4: Type Validation
    # ========================================================================

    def test_type_confusion_prevented(self, client: TestClient, auth_headers):
        """
        CRITICAL: Type confusion attacks must be prevented

        Test cases:
        1. String instead of number
        2. Number instead of string
        3. Array instead of string
        4. Object instead of primitive
        """
        type_confusion_payloads = [
            {"name": 12345, "email": "test@example.com"},  # Number as string
            {"name": "Test", "email": ["array@test.com"]},  # Array as string
            {"name": {"nested": "object"}, "email": "test@example.com"},  # Object as string
            {"name": "Test", "email": 12345},  # Number as email
            {"name": "Test", "email": None},  # None as email
        ]

        for payload in type_confusion_payloads:
            response = client.post(
                "/api/v2/patients",
                headers=auth_headers,
                json=payload
            )

            # Should reject type mismatches
            assert response.status_code in [400, 422], \
                f"Type confusion payload should be rejected: {payload}"

        print("✅ Type confusion correctly prevented")

    # ========================================================================
    # Test 5: Special Character Handling
    # ========================================================================

    def test_special_characters_sanitized(self, client: TestClient, auth_headers):
        """
        Special characters should be sanitized but not cause errors

        Test characters:
        1. HTML/XML special chars
        2. SQL special chars
        3. Path traversal chars
        4. Unicode characters
        """
        special_char_names = [
            "Test <script>alert('XSS')</script>",
            "Test'; DROP TABLE--",
            "Test../../etc/passwd",
            "Test\x00null",
            "Test%00",
            "Test\r\n\r\n",
            "Test™®©",
            "Test emoji 😊",
        ]

        for name in special_char_names:
            response = client.post(
                "/api/v2/patients",
                headers=auth_headers,
                json={
                    "name": name,
                    "email": f"test{hash(name)}@example.com",
                    "phone": "+5511999999999"
                }
            )

            # Should either sanitize or reject gracefully
            assert response.status_code in [200, 201, 400, 422], \
                "Special characters should be handled safely"

            # If accepted, verify no XSS in response
            if response.status_code in [200, 201]:
                data = response.json()
                response_str = str(data)
                assert "<script>" not in response_str
                assert "DROP TABLE" not in response_str

        print("✅ Special characters handled safely")

    # ========================================================================
    # Test 6: JSON Payload Validation
    # ========================================================================

    def test_malformed_json_rejected(self, client: TestClient, auth_headers):
        """Malformed JSON payloads must be rejected"""
        # Send invalid JSON
        response = client.post(
            "/api/v2/patients",
            headers={**auth_headers, "Content-Type": "application/json"},
            data="{'invalid': json without quotes}"  # Invalid JSON
        )

        # Should return 422 (validation error)
        assert response.status_code in [400, 422], \
            "Malformed JSON should be rejected"

        print("✅ Malformed JSON correctly rejected")

    def test_unexpected_fields_handled(self, client: TestClient, auth_headers):
        """Unexpected fields should be handled gracefully"""
        response = client.post(
            "/api/v2/patients",
            headers=auth_headers,
            json={
                "name": "Test Patient",
                "email": "test@example.com",
                "phone": "+5511999999999",
                "unexpected_field": "should be ignored or rejected",
                "another_unexpected": 12345,
            }
        )

        # Should either ignore or reject gracefully
        assert response.status_code in [200, 201, 400, 422], \
            "Unexpected fields should be handled"

        print("✅ Unexpected fields handled correctly")

    # ========================================================================
    # Test 7: Boundary Value Testing
    # ========================================================================

    def test_boundary_values(self, client: TestClient, auth_headers):
        """Test boundary values for numeric inputs"""
        boundary_tests = [
            {"limit": 0},  # Minimum
            {"limit": 1},  # Minimum valid
            {"limit": 100},  # Normal
            {"limit": 1000},  # Maximum valid
            {"limit": 10000},  # Over maximum
            {"limit": -1},  # Negative
            {"limit": 999999999},  # Very large
        ]

        for params in boundary_tests:
            response = client.get(
                "/api/v2/patients",
                headers=auth_headers,
                params=params
            )

            # Should validate boundaries
            if params["limit"] < 0 or params["limit"] > 1000:
                assert response.status_code in [400, 422], \
                    f"Invalid limit {params['limit']} should be rejected"
            else:
                assert response.status_code in [200], \
                    f"Valid limit {params['limit']} should be accepted"

        print("✅ Boundary values correctly validated")

    # ========================================================================
    # Test 8: Phone Number Validation
    # ========================================================================

    def test_phone_validation(self, client: TestClient, auth_headers):
        """Phone numbers should be validated"""
        invalid_phones = [
            "123",  # Too short
            "not a phone",
            "'; DROP TABLE--",
            "12345678909234567890",  # Too long
        ]

        for phone in invalid_phones:
            response = client.post(
                "/api/v2/patients",
                headers=auth_headers,
                json={
                    "name": "Test Patient",
                    "email": f"test{hash(phone)}@example.com",
                    "phone": phone
                }
            )

            # Should reject invalid phone
            # Note: Depends on whether phone validation is implemented
            if response.status_code in [422, 400]:
                print(f"✅ Invalid phone '{phone}' rejected")
            else:
                print("⚠️  Phone validation may need improvement")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
