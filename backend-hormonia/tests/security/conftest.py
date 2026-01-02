"""
Security Tests Configuration
Provides fixtures specific to security testing.

This conftest extends the main test configuration with security-specific fixtures.
All base fixtures (db, client, test_user, authenticated_client, etc.) are inherited
from the parent conftest.py.
"""
import pytest
from datetime import date, datetime, timezone
from uuid import uuid4

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.medication import Medication
from app.models.treatment import Treatment, TreatmentType, TreatmentStatus


@pytest.fixture
def test_message(db, test_patient):
    """Create a test message for security tests."""
    message = Message(
        patient_id=test_patient.id,
        content="Test message for security testing",
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        status=MessageStatus.SENT,
        created_at=datetime.now(timezone.utc)
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@pytest.fixture
def test_treatment(db, test_patient, test_user_obj):
    """Create a test treatment for medication fixtures."""
    treatment = Treatment(
        id=uuid4(),
        patient_id=test_patient.id,
        doctor_id=test_user_obj.id,
        treatment_type=TreatmentType.QUIMIOTERAPIA,
        status=TreatmentStatus.ACTIVE,
        start_date=date.today(),
        diagnosis="Test diagnosis for security testing"
    )
    db.add(treatment)
    db.commit()
    db.refresh(treatment)
    return treatment


@pytest.fixture
def test_medication(db, test_patient, test_user_obj):
    """Create a test medication for security tests."""
    medication = Medication(
        patient_id=test_patient.id,
        prescribed_by_id=test_user_obj.id,
        name="Test Medication",
        dosage="100mg",
        frequency="Once daily",
        prescription_date=date.today(),
        start_date=date.today(),
        is_active=True
    )
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication


@pytest.fixture
def multiple_test_medications(db, test_patient, test_user_obj):
    """Create multiple test medications for batch testing."""
    medications = []
    med_names = [
        "Aspirin", "Ibuprofen", "Acetaminophen",
        "Naproxen", "Diclofenac"
    ]

    for i, name in enumerate(med_names):
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
    for med in medications:
        db.refresh(med)

    return medications


@pytest.fixture
def sql_injection_payloads():
    """Common SQL injection test payloads."""
    return [
        # Basic SQL injection
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "1; DELETE FROM patients WHERE 1=1",

        # UNION-based injection
        "' UNION SELECT * FROM users --",
        "' UNION SELECT username, password FROM users --",

        # Comment-based injection
        "admin'--",
        "admin'/*",

        # Stacked queries
        "'; INSERT INTO users VALUES ('hacker', 'hacked'); --",

        # Time-based blind injection
        "'; WAITFOR DELAY '0:0:5'; --",
        "' OR SLEEP(5) --",

        # Error-based injection
        "' AND (SELECT 1 FROM(SELECT COUNT(*),CONCAT(user(),0x3a,FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a) --",

        # Boolean-based blind injection
        "' AND 1=1 --",
        "' AND 1=2 --",

        # NULL byte injection
        "test\x00admin",
        "%00admin",

        # Encoded payloads
        "%27%20OR%20%271%27%3D%271",
        "&#39; OR &#39;1&#39;=&#39;1",
    ]


@pytest.fixture
def xss_payloads():
    """Common XSS test payloads for input validation testing."""
    return [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<body onload=alert('XSS')>",
        "'\"><script>alert('XSS')</script>",
        "<iframe src='javascript:alert(1)'>",
        "<object data='javascript:alert(1)'>",
        "<embed src='javascript:alert(1)'>",
    ]


@pytest.fixture
def path_traversal_payloads():
    """Common path traversal test payloads."""
    return [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "....//....//....//etc/passwd",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "..%252f..%252f..%252fetc/passwd",
        "/etc/passwd%00.jpg",
    ]
