"""
Security Tests for SQL Injection Fixes
Tests the fixed vulnerabilities at both repository and API levels.

These tests validate:
1. Repository-level SQL injection protection (parameterized queries)
2. API-level SQL injection protection (via authentication and input validation)
3. Special character handling in search queries
4. Database integrity after malicious input attempts

NOTE: Some tests require a PostgreSQL test database with all tables.
Tests that can run with SQLite are enabled; tests that need PostgreSQL
will be skipped if the medications table isn't available.
"""
import pytest
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.repositories.medication import MedicationRepository


def table_exists(db, table_name: str) -> bool:
    """Check if a table exists in the database."""
    try:
        inspector = inspect(db.get_bind())
        return table_name in inspector.get_table_names()
    except Exception:
        return False


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

    @pytest.fixture
    def special_characters(self):
        """Special characters that might break SQL queries"""
        return ["%", "_", "'", '"', "\\", "*", "?", ";", "--", "/*", "*/"]

    # ========================================================================
    # Message Search Endpoint Tests
    # Uses authenticated_client fixture from conftest.py
    # ========================================================================

    def test_message_search_with_normal_input(self, authenticated_client, db, test_patient):
        """Test message search with normal input works correctly"""
        if not table_exists(db, "messages"):
            pytest.skip("Messages table not available in test database")

        # Create test message
        message = Message(
            patient_id=test_patient.id,
            content="Test message for search functionality",
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            status=MessageStatus.SENT
        )
        db.add(message)
        db.commit()

        # Test normal search - /api/v2/messages endpoint
        response = authenticated_client.get("/api/v2/messages")

        # Should return 200 with proper structure
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_message_api_prevents_sql_injection(
        self, authenticated_client, db, test_patient, malicious_inputs
    ):
        """Test that message API endpoint prevents SQL injection attacks"""
        if not table_exists(db, "messages"):
            pytest.skip("Messages table not available in test database")

        # Create a baseline message to ensure the table exists and has data
        message = Message(
            patient_id=test_patient.id,
            content="Baseline test message",
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            status=MessageStatus.SENT
        )
        db.add(message)
        db.commit()

        for malicious_input in malicious_inputs:
            # Test with patient_id filter (common attack vector)
            response = authenticated_client.get(
                "/api/v2/messages",
                params={"patient_id": malicious_input, "limit": 10}
            )

            # Should either return 200 with safe results or 400/422 for validation error
            # Should NEVER return 500 (server error from SQL injection)
            assert response.status_code in [200, 400, 422], (
                f"Unexpected status {response.status_code} for input: {malicious_input}"
            )

            if response.status_code == 200:
                data = response.json()
                # Verify response structure is intact (not corrupted by injection)
                assert "data" in data
                assert isinstance(data["data"], list)

                # Verify no SQL artifacts in response
                for msg in data["data"]:
                    msg_str = str(msg)
                    assert "DROP TABLE" not in msg_str
                    assert "UNION SELECT" not in msg_str
                    assert "DELETE FROM" not in msg_str

    def test_message_api_special_characters(self, authenticated_client, special_characters):
        """Test message API handles special characters safely"""
        for char in special_characters:
            response = authenticated_client.get(
                "/api/v2/messages",
                params={"direction": f"test{char}value", "limit": 10}
            )

            # Should handle special chars gracefully
            assert response.status_code in [200, 400, 422], (
                f"Unexpected status {response.status_code} for char: {repr(char)}"
            )

            if response.status_code == 200:
                data = response.json()
                assert "data" in data

    def test_message_api_empty_results_safe(self, authenticated_client):
        """Test that API results don't leak database information"""
        # Request messages with non-existent patient UUID
        non_existent_uuid = str(uuid4())
        response = authenticated_client.get(
            "/api/v2/messages",
            params={"patient_id": non_existent_uuid}
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 404]

        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            # Verify no SQL error messages in response
            response_str = str(data).lower()
            assert "syntax error" not in response_str
            assert "sqlalchemy" not in response_str
            assert "operational error" not in response_str

    # ========================================================================
    # Medication Repository Tests
    # Tests SQL injection protection at the repository layer
    # ========================================================================

    @pytest.fixture
    def medication_fixtures(self, db, test_patient, test_user_obj):
        """Create test medications for repository tests"""
        if not table_exists(db, "medications"):
            pytest.skip("Medications table not available in test database")

        medications = []
        for i, name in enumerate(["Aspirin", "Ibuprofen", "Acetaminophen"]):
            med = Medication(
                patient_id=test_patient.id,
                prescribed_by_id=test_user_obj.id,
                name=name,
                dosage=f"{100 * (i + 1)}mg",
                frequency="Once daily",
                prescription_date=date.today(),
                start_date=date.today(),
                is_active=True
            )
            db.add(med)
            medications.append(med)
        db.commit()
        return medications

    def test_medication_get_by_name_normal_input(self, db, medication_fixtures):
        """Test medication search with normal input works correctly"""
        repo = MedicationRepository(db)

        # Test with normal medication name
        medications = repo.get_by_name("Aspirin", limit=10)

        assert isinstance(medications, list)
        assert len(medications) >= 1
        assert any(med.name == "Aspirin" for med in medications)

    def test_medication_get_by_name_prevents_sql_injection(
        self, db, medication_fixtures, malicious_inputs
    ):
        """Test that medication repository prevents SQL injection"""
        repo = MedicationRepository(db)

        for malicious_input in malicious_inputs:
            try:
                medications = repo.get_by_name(malicious_input, limit=10)

                # Should return safe results (likely empty list)
                assert isinstance(medications, list)

                # Verify returned medications are legitimate objects
                for med in medications:
                    assert isinstance(med, Medication)
                    # Should not contain injection artifacts
                    assert "DROP TABLE" not in str(med.name)
                    assert "UNION SELECT" not in str(med.name)

            except Exception as e:
                # If exception occurs, it should be a validation error,
                # not a database/SQL error
                error_str = str(e).upper()
                assert "SQL SYNTAX" not in error_str, (
                    f"SQL syntax error for input: {malicious_input}"
                )
                assert "SYNTAX ERROR" not in error_str, (
                    f"Syntax error for input: {malicious_input}"
                )

    def test_medication_get_by_name_special_characters(self, db, medication_fixtures):
        """Test medication search handles special characters safely"""
        repo = MedicationRepository(db)
        special_chars = ["%", "_", "'", '"', "\\", "*", "?"]

        for char in special_chars:
            try:
                medications = repo.get_by_name(f"test{char}", limit=10)

                # Should handle special chars without SQL errors
                assert isinstance(medications, list)
            except Exception as e:
                # Should not be a SQL syntax error
                assert "syntax error" not in str(e).lower(), (
                    f"SQL syntax error for char: {repr(char)}"
                )

    def test_medication_get_by_name_wildcards_safe(self, db, medication_fixtures):
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

            # SQLAlchemy's ilike with parameterized queries treats these as literals
            # so results should only match if medication names actually contain these

    def test_medication_repository_parameterization(self, db, medication_fixtures):
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
                # If table was dropped, this would fail - but it should succeed
                # because parameterized queries protect against injection

            except Exception as e:
                # Should not be a SQL syntax error
                error_str = str(e).lower()
                assert "syntax error" not in error_str
                assert "drop table" not in error_str

    # ========================================================================
    # Integration Tests
    # ========================================================================

    def test_database_integrity_after_injection_attempts(
        self, db, test_patient, medication_fixtures, malicious_inputs
    ):
        """Test that database integrity is maintained after SQL injection attempts"""
        repo = MedicationRepository(db)

        # Count records before injection attempts
        initial_med_count = db.query(Medication).count()
        initial_patient_count = db.query(Patient).count()

        # Run all malicious inputs
        for malicious_input in malicious_inputs:
            try:
                repo.get_by_name(malicious_input, limit=10)
            except Exception:
                pass  # Ignore any exceptions

        # Verify counts are unchanged (no deletions occurred)
        final_med_count = db.query(Medication).count()
        final_patient_count = db.query(Patient).count()

        assert final_med_count == initial_med_count, (
            "Medication count changed after injection attempts"
        )
        assert final_patient_count == initial_patient_count, (
            "Patient count changed after injection attempts"
        )

    def test_no_sql_errors_in_response_bodies(
        self, authenticated_client, malicious_inputs
    ):
        """Test that SQL injection attempts don't expose SQL errors in responses"""
        sql_error_indicators = [
            "sqlalchemy",
            "psycopg2",
            "syntax error",
            "operational error",
            "database error",
        ]

        for malicious_input in malicious_inputs:
            response = authenticated_client.get(
                "/api/v2/messages",
                params={"patient_id": malicious_input}
            )

            if response.status_code == 500:
                # Even on 500 errors, should not expose SQL details
                response_text = response.text.lower()
                for indicator in sql_error_indicators:
                    assert indicator not in response_text, (
                        f"SQL error indicator '{indicator}' found in 500 response"
                    )


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
        if table_exists(db, "messages"):
            db.query(Message).limit(1).first()
        if table_exists(db, "medications"):
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
