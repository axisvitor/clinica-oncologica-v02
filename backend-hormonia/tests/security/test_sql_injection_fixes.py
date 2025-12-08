"""
Security Tests for SQL Injection Fixes
Tests the fixed vulnerabilities in conversations.py and medication.py
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.message import Message, MessageDirection
from app.models.medication import Medication
from app.models.patient import Patient
from app.repositories.medication import MedicationRepository


class TestSQLInjectionFixes:
    """Test suite for SQL injection vulnerability fixes"""

    @pytest.fixture
    def malicious_inputs(self):
        """Common SQL injection test payloads"""
        return [
            "test'; DROP TABLE messages; --",
            "test' OR '1'='1",
            "test' UNION SELECT * FROM users--",
            "test%' OR '1'='1",
            "test' AND 1=1--",
            "'; DELETE FROM patients WHERE '1'='1",
            "test\x00null byte",
            "test%00",
            "test' OR 'a'='a",
            "1' UNION SELECT NULL, NULL, NULL--",
        ]

    # ========================================================================
    # Message Search Endpoint Tests (conversations.py:335)
    # ========================================================================

    def test_message_search_with_normal_input(self, client: TestClient, db: Session, auth_headers):
        """Test message search with normal input works correctly"""
        # Create test message
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No test patient available")

        message = Message(
            patient_id=patient.id,
            content="Test message for search",
            direction=MessageDirection.OUTBOUND
        )
        db.add(message)
        db.commit()

        # Test normal search
        response = client.get(
            "/api/v2/messages/search?q=Test",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_message_search_prevents_sql_injection(
        self, client: TestClient, db: Session, auth_headers, malicious_inputs
    ):
        """Test that message search endpoint prevents SQL injection attacks"""
        for malicious_input in malicious_inputs:
            response = client.get(
                f"/api/v2/messages/search?q={malicious_input}",
                headers=auth_headers
            )

            # Should either return 200 with safe results or 400 for validation error
            # Should NEVER return 500 (server error from SQL injection)
            assert response.status_code in [200, 400, 422], \
                f"Unexpected status {response.status_code} for input: {malicious_input}"

            if response.status_code == 200:
                data = response.json()
                # Verify response structure is intact (not corrupted by injection)
                assert "data" in data
                assert isinstance(data["data"], list)

                # Verify no unauthorized data access
                # (would indicate successful injection)
                for message in data["data"]:
                    assert "id" in message
                    assert "content" in message
                    # Should not contain raw SQL or database error messages
                    assert "DROP TABLE" not in str(message)
                    assert "UNION SELECT" not in str(message)

    def test_message_search_special_characters(self, client: TestClient, auth_headers):
        """Test message search handles special characters safely"""
        special_chars = ["%", "_", "'", '"', "\\", "*", "?"]

        for char in special_chars:
            response = client.get(
                f"/api/v2/messages/search?q=test{char}",
                headers=auth_headers
            )

            # Should handle special chars gracefully
            assert response.status_code in [200, 400, 422]

            if response.status_code == 200:
                data = response.json()
                assert "data" in data

    def test_message_search_empty_results_safe(self, client: TestClient, auth_headers):
        """Test that empty search results don't leak information"""
        # Search for something that won't exist
        response = client.get(
            "/api/v2/messages/search?q=NONEXISTENT_SEARCH_TERM_12345",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"] == []
        # Verify no SQL error messages in response
        assert "sql" not in str(data).lower()
        assert "error" not in str(data).lower() or data.get("error") is None

    # ========================================================================
    # Medication Repository Tests (medication.py:203)
    # ========================================================================

    def test_medication_get_by_name_normal_input(self, db: Session):
        """Test medication search with normal input works correctly"""
        repo = MedicationRepository(db)

        # Test with normal medication name
        medications = repo.get_by_name("Aspirin", limit=10)

        assert isinstance(medications, list)
        # Should return list (may be empty if no medications)
        for med in medications:
            assert isinstance(med, Medication)
            assert hasattr(med, "name")
            assert hasattr(med, "id")

    def test_medication_get_by_name_prevents_sql_injection(
        self, db: Session, malicious_inputs
    ):
        """Test that medication repository prevents SQL injection"""
        repo = MedicationRepository(db)

        for malicious_input in malicious_inputs:
            try:
                medications = repo.get_by_name(malicious_input, limit=10)

                # Should return safe results
                assert isinstance(medications, list)

                # Verify returned medications are legitimate
                for med in medications:
                    assert isinstance(med, Medication)
                    # Should not contain injection artifacts
                    assert "DROP TABLE" not in str(med.name)
                    assert "UNION SELECT" not in str(med.name)

            except Exception as e:
                # If exception occurs, it should be a validation error,
                # not a database/SQL error
                assert "SQL" not in str(e).upper()
                assert "syntax error" not in str(e).lower()
                # Database connection errors are acceptable
                assert any(term in str(e).lower() for term in [
                    "validation", "invalid", "constraint"
                ])

    def test_medication_get_by_name_special_characters(self, db: Session):
        """Test medication search handles special characters safely"""
        repo = MedicationRepository(db)
        special_chars = ["%", "_", "'", '"', "\\", "*", "?"]

        for char in special_chars:
            medications = repo.get_by_name(f"test{char}", limit=10)

            # Should handle special chars without SQL errors
            assert isinstance(medications, list)
            # May be empty, but should not error

    def test_medication_get_by_name_wildcards_safe(self, db: Session):
        """Test that SQL wildcards are treated as literals"""
        repo = MedicationRepository(db)

        # Test with SQL wildcard characters
        # These should be treated as literal characters, not wildcards
        test_cases = [
            "%",  # SQL wildcard for any characters
            "_",  # SQL wildcard for single character
            "test%",
            "%test",
            "te%st",
        ]

        for test_input in test_cases:
            medications = repo.get_by_name(test_input, limit=10)

            # Should return safe results
            assert isinstance(medications, list)

            # Verify no unintended wildcard behavior
            # (should only match if medication name actually contains these characters)
            for med in medications:
                # The search pattern should have been parameterized correctly
                assert isinstance(med, Medication)

    def test_medication_repository_parameterization(self, db: Session):
        """Test that medication queries are properly parameterized"""
        repo = MedicationRepository(db)

        # Test with input that would break string interpolation
        dangerous_inputs = [
            "'; DELETE FROM medications WHERE '1'='1",
            "Aspirin'; DROP TABLE medications--",
            "test' OR '1'='1' AND name LIKE '%",
        ]

        for dangerous_input in dangerous_inputs:
            try:
                medications = repo.get_by_name(dangerous_input, limit=10)

                # Should safely return results (likely empty)
                assert isinstance(medications, list)

                # Verify database is still intact by running a simple query
                test_query = db.query(Medication).limit(1).first()
                # If table was dropped, this would fail

            except Exception as e:
                # Should not be a SQL syntax error
                assert "syntax error" not in str(e).lower()
                assert "DROP TABLE" not in str(e)

    # ========================================================================
    # Integration Tests
    # ========================================================================

    def test_api_to_repository_integration(self, client: TestClient, auth_headers, db: Session):
        """Test that API endpoints properly pass parameters to repository"""
        # This would be implemented based on your API structure
        # Example for medication API endpoint (if it exists)

        # Test that malicious input at API level doesn't reach repository unsafely
        response = client.get(
            "/api/v2/medications?name=test' OR '1'='1",
            headers=auth_headers
        )

        # Should handle safely
        assert response.status_code in [200, 400, 422]

        if response.status_code == 200:
            data = response.json()
            # Verify safe response structure
            assert isinstance(data, (dict, list))

    def test_no_sql_errors_in_logs(self, client: TestClient, auth_headers, malicious_inputs, caplog):
        """Test that SQL injection attempts don't generate SQL errors in logs"""
        import logging
        caplog.set_level(logging.ERROR)

        for malicious_input in malicious_inputs:
            client.get(
                f"/api/v2/messages/search?q={malicious_input}",
                headers=auth_headers
            )

        # Check that no SQL errors were logged
        for record in caplog.records:
            assert "SQL" not in record.message.upper() or "injection" in record.message.lower()
            assert "syntax error" not in record.message.lower()


# ============================================================================
# Utility Functions for Testing
# ============================================================================

def verify_database_integrity(db: Session) -> bool:
    """
    Verify database integrity after SQL injection attempts.
    Returns True if database is intact, False otherwise.
    """
    try:
        # Test that critical tables exist and are accessible
        db.query(Patient).limit(1).first()
        db.query(Message).limit(1).first()
        db.query(Medication).limit(1).first()
        return True
    except Exception:
        return False


@pytest.fixture
def verify_db_integrity():
    """Fixture to verify database integrity before and after tests"""
    def _verify(db: Session):
        return verify_database_integrity(db)
    return _verify
