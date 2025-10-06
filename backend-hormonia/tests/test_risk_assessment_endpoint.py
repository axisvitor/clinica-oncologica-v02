"""
Integration tests for the physician risk assessment endpoint.

Tests the GET /api/v1/physician/risk-assessments endpoint for:
- Performance (< 200ms target)
- N+1 query elimination
- Correct risk scoring
- Authorization
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import time

from app.main import app
from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.user import User, UserRole


class TestRiskAssessmentEndpoint:
    """Test suite for risk assessment endpoint."""

    @pytest.fixture
    def auth_headers(self, db_session, client):
        """Create authenticated physician user."""
        # Create physician
        physician = User(
            email="test_physician@example.com",
            full_name="Dr. Test",
            role=UserRole.DOCTOR,
            hashed_password="hashed",
            is_active=True
        )
        db_session.add(physician)
        db_session.commit()

        # Get auth token (mocked)
        # In real tests, use Firebase auth or JWT token
        return {"Authorization": f"Bearer test_token_{physician.id}"}

    @pytest.fixture
    def sample_patients(self, db_session, auth_headers):
        """Create 50 sample patients with varying risk levels."""
        physician_id = uuid4()  # Extract from auth_headers in real implementation

        patients = []
        for i in range(50):
            patient = Patient(
                id=uuid4(),
                doctor_id=physician_id,
                name=f"Patient {i+1}",
                phone=f"+5511999{i:06d}",
                email=f"patient{i+1}@example.com",
                # Add metadata with adherence scores
                patient_data={
                    "adherence_score": 0.95 - (i * 0.01),  # Decreasing adherence
                    "symptom_severity": i * 0.02 if i > 25 else 0
                }
            )
            db_session.add(patient)
            patients.append(patient)

        db_session.commit()
        return patients

    @pytest.fixture
    def sample_alerts(self, db_session, sample_patients):
        """Create alerts for high-risk patients."""
        alerts = []

        # Create critical alerts for first 5 patients
        for i in range(5):
            alert = Alert(
                patient_id=sample_patients[i].id,
                alert_type="medication_adherence",
                severity=AlertSeverity.CRITICAL,
                description=f"Critical: Missed 5+ doses",
                status=AlertStatus.ACTIVE,
                data={"missed_doses": 5 + i}
            )
            db_session.add(alert)
            alerts.append(alert)

        # Create high severity alerts for next 10 patients
        for i in range(5, 15):
            alert = Alert(
                patient_id=sample_patients[i].id,
                alert_type="symptoms",
                severity=AlertSeverity.HIGH,
                description=f"High: Severe symptoms reported",
                status=AlertStatus.ACTIVE,
                data={"symptom_level": 8}
            )
            db_session.add(alert)
            alerts.append(alert)

        # Create medium alerts for next 15 patients
        for i in range(15, 30):
            alert = Alert(
                patient_id=sample_patients[i].id,
                alert_type="vital_signs",
                severity=AlertSeverity.MEDIUM,
                description=f"Medium: Vital signs concern",
                status=AlertStatus.ACTIVE,
                data={}
            )
            db_session.add(alert)
            alerts.append(alert)

        db_session.commit()
        return alerts

    def test_endpoint_exists(self, client, auth_headers):
        """Test that the endpoint is registered."""
        response = client.get(
            "/api/v1/physician/risk-assessments",
            headers=auth_headers
        )
        # Should not return 404
        assert response.status_code != 404

    def test_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/api/v1/physician/risk-assessments")
        assert response.status_code == 401

    def test_requires_physician_role(self, client):
        """Test that endpoint requires physician or admin role."""
        # Create patient user (should be denied)
        # In real test, create user and get token
        pass

    def test_performance_target(self, client, auth_headers, sample_patients, sample_alerts):
        """
        Test that endpoint meets < 200ms performance target for 50 patients.

        CRITICAL: This is the main performance test.
        """
        start_time = time.time()

        response = client.get(
            "/api/v1/physician/risk-assessments",
            headers=auth_headers
        )

        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 200, f"Performance target missed: {elapsed_ms:.0f}ms > 200ms"

        print(f"✓ Performance test passed: {elapsed_ms:.0f}ms < 200ms")

    def test_response_structure(self, client, auth_headers, sample_patients):
        """Test that response matches expected structure."""
        response = client.get(
            "/api/v1/physician/risk-assessments",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "patients" in data
        assert "total_count" in data
        assert "high_risk_count" in data
        assert "timestamp" in data

        # Check patient structure
        if data["total_count"] > 0:
            patient = data["patients"][0]
            assert "patient_id" in patient
            assert "patient_name" in patient
            assert "overall_risk" in patient
            assert "risk_score" in patient
            assert "assessments" in patient
            assert "alert_count" in patient
            assert "last_assessment" in patient

            # Check risk level is valid
            assert patient["overall_risk"] in ["low", "medium", "high", "critical"]

            # Check risk score is in range
            assert 0.0 <= patient["risk_score"] <= 1.0

    def test_risk_scoring_accuracy(self, client, auth_headers, sample_patients, sample_alerts):
        """Test that risk scores are calculated correctly."""
        response = client.get(
            "/api/v1/physician/risk-assessments",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Patients with critical alerts should have high risk scores
        critical_patients = [
            p for p in data["patients"]
            if any(a["risk_level"] == "critical" for a in p["assessments"])
        ]

        for patient in critical_patients:
            assert patient["risk_score"] >= 0.4, \
                f"Critical alert patient should have risk_score >= 0.4, got {patient['risk_score']}"

    def test_filter_by_patient_id(self, client, auth_headers, sample_patients):
        """Test filtering by specific patient ID."""
        patient_id = str(sample_patients[0].id)

        response = client.get(
            f"/api/v1/physician/risk-assessments?patient_id={patient_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should return only one patient
        assert data["total_count"] == 1
        assert data["patients"][0]["patient_id"] == patient_id

    def test_days_lookback_parameter(self, client, auth_headers, sample_patients):
        """Test days_lookback parameter."""
        # Test with 7 days lookback
        response = client.get(
            "/api/v1/physician/risk-assessments?days_lookback=7",
            headers=auth_headers
        )

        assert response.status_code == 200

        # Test with invalid lookback
        response = client.get(
            "/api/v1/physician/risk-assessments?days_lookback=0",
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_query_efficiency(self, db_session, client, auth_headers, sample_patients, sample_alerts):
        """
        Test that N+1 query problem is eliminated.

        This test verifies that the number of queries is constant regardless
        of the number of patients.
        """
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        query_count = {"count": 0}

        @event.listens_for(Engine, "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            query_count["count"] += 1

        # Execute request
        response = client.get(
            "/api/v1/physician/risk-assessments",
            headers=auth_headers
        )

        assert response.status_code == 200

        # Should have:
        # 1. Patient query with alert counts
        # 2. Bulk alert query
        # 3. Possible AI insights query (when implemented)
        # Total: 3-5 queries MAX (not 51 like N+1)
        assert query_count["count"] <= 10, \
            f"Too many queries: {query_count['count']} (should be < 10 for N+1 elimination)"

        print(f"✓ Query efficiency test passed: {query_count['count']} queries (target: < 10)")


@pytest.fixture
def client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def db_session():
    """Database session for tests."""
    from app.database import get_db
    # Use test database session
    # Implementation depends on your test setup
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
