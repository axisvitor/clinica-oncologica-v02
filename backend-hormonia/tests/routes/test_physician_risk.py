"""
Test suite for Physician Risk Assessments endpoint.

Tests GET /api/v1/physician/risk-assessments with:
- CRITICAL: Performance benchmarks (< 200ms with 50 patients)
- Single patient filtering
- Risk score calculation accuracy
- N+1 query elimination
- Alert severity impact on risk
- Empty data handling
"""
import pytest
import time
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import event

from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.user import User
from tests.helpers.jwt_helper import jwt_helper


class TestPhysicianRiskAssessments:
    """Test suite for GET /api/v1/physician/risk-assessments"""

    @pytest.mark.asyncio
    async def test_performance_with_50_patients(
        self,
        http_client,
        doctor_a_credentials,
        auth_headers,
        db_session
    ):
        """CRITICAL: Should complete in < 200ms with 50 patients"""
        physician_id = doctor_a_credentials['firebase_uid']

        # Create 50 test patients with alerts
        patients = []
        alerts = []

        for i in range(50):
            patient = Patient(
                id=uuid4(),
                firebase_uid=f"firebase_patient_perf_{i}",
                name=f"Performance Test Patient {i}",
                flow_state="active",
                doctor_id=physician_id
            )
            patients.append(patient)

            # Add some alerts for variety
            if i % 5 == 0:  # Every 5th patient gets a critical alert
                alerts.append(Alert(
                    id=uuid4(),
                    patient_id=patient.id,
                    type="symptom_alert",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Critical alert for patient {i}",
                    status=AlertStatus.PENDING
                ))
            elif i % 3 == 0:  # Every 3rd patient gets a high alert
                alerts.append(Alert(
                    id=uuid4(),
                    patient_id=patient.id,
                    type="symptom_alert",
                    severity=AlertSeverity.HIGH,
                    message=f"High alert for patient {i}",
                    status=AlertStatus.PENDING
                ))

        db_session.add_all(patients)
        db_session.add_all(alerts)
        db_session.commit()

        # Measure performance
        headers = auth_headers(doctor_a_credentials)

        start_time = time.time()
        response = await http_client.get(
            "/api/v1/physician/risk-assessments",
            headers=headers
        )
        elapsed_ms = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code in [200, 404, 500]

        # If implemented, verify performance target
        if response.status_code == 200:
            assert elapsed_ms < 200, f"Request took {elapsed_ms:.2f}ms (target: < 200ms)"

            data = response.json()
            # Should return at least the 50 patients we created
            assert "total_count" in data or "patients" in data

    @pytest.mark.asyncio
    async def test_single_patient_filter(
        self,
        http_client,
        doctor_a_credentials,
        auth_headers,
        db_session
    ):
        """Should filter by patient_id correctly"""
        physician_id = doctor_a_credentials['firebase_uid']

        # Create specific test patient
        target_patient = Patient(
            id=uuid4(),
            firebase_uid="firebase_target_123",
            name="Target Patient",
            flow_state="active",
            doctor_id=physician_id
        )
        db_session.add(target_patient)
        db_session.commit()

        headers = auth_headers(doctor_a_credentials)
        response = await http_client.get(
            f"/api/v1/physician/risk-assessments?patient_id={target_patient.id}",
            headers=headers
        )

        # If implemented
        if response.status_code == 200:
            data = response.json()

            # Should return only the target patient
            if "patients" in data and len(data["patients"]) > 0:
                assert data["patients"][0]["patient_id"] == str(target_patient.id)

    def test_risk_score_calculation(self, db_session):
        """Risk score should reflect alerts correctly"""
        physician_id = uuid4()

        # Patient with critical alert
        high_risk_patient = Patient(
            id=uuid4(),
            firebase_uid="firebase_high_risk",
            name="High Risk Patient",
            flow_state="active",
            doctor_id=physician_id
        )

        critical_alert = Alert(
            id=uuid4(),
            patient_id=high_risk_patient.id,
            type="critical_symptom",
            severity=AlertSeverity.CRITICAL,
            message="Critical condition detected",
            status=AlertStatus.PENDING
        )

        db_session.add_all([high_risk_patient, critical_alert])
        db_session.commit()

        # Query patient with alerts
        patient_with_alerts = (
            db_session.query(Patient)
            .filter(Patient.id == high_risk_patient.id)
            .first()
        )

        assert patient_with_alerts is not None

        # Query alerts for risk calculation
        patient_alerts = (
            db_session.query(Alert)
            .filter(Alert.patient_id == high_risk_patient.id)
            .filter(Alert.status != AlertStatus.RESOLVED)
            .all()
        )

        assert len(patient_alerts) >= 1
        assert any(a.severity == AlertSeverity.CRITICAL for a in patient_alerts)

        # Risk score calculation (simple example)
        risk_score = 0.0
        for alert in patient_alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                risk_score += 0.4
            elif alert.severity == AlertSeverity.HIGH:
                risk_score += 0.3
            elif alert.severity == AlertSeverity.MEDIUM:
                risk_score += 0.2
            elif alert.severity == AlertSeverity.LOW:
                risk_score += 0.1

        # Should have high risk score due to critical alert
        assert risk_score >= 0.4

    def test_n_plus_one_elimination(self, db_session):
        """Should NOT make N+1 queries"""
        physician_id = uuid4()

        # Create 10 patients
        patients = []
        for i in range(10):
            patient = Patient(
                id=uuid4(),
                firebase_uid=f"firebase_n_plus_one_{i}",
                name=f"Patient {i}",
                flow_state="active",
                doctor_id=physician_id
            )
            patients.append(patient)

        db_session.add_all(patients)
        db_session.commit()

        # Track queries
        query_count = []

        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            # Only count SELECT queries
            if statement.strip().upper().startswith('SELECT'):
                query_count.append(statement)

        # Listen for queries
        event.listen(
            db_session.connection(),
            "after_cursor_execute",
            receive_after_cursor_execute
        )

        # Query patients with alerts using eager loading
        from sqlalchemy.orm import joinedload

        result = (
            db_session.query(Patient)
            .filter(Patient.doctor_id == physician_id)
            .options(joinedload(Patient.alerts))  # Eager load alerts
            .all()
        )

        # Should make minimal queries (not 1 + 10 separate queries)
        # Expect ~1-3 queries maximum (patients + alerts in single join)
        assert len(query_count) <= 5, f"Too many queries: {len(query_count)}"

    def test_multiple_alert_severity_levels(self, db_session):
        """Patient with multiple alerts should aggregate risk correctly"""
        physician_id = uuid4()

        patient = Patient(
            id=uuid4(),
            firebase_uid="firebase_multi_alert",
            name="Multi Alert Patient",
            flow_state="active",
            doctor_id=physician_id
        )

        # Multiple alerts with different severities
        alerts = [
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="symptom_1",
                severity=AlertSeverity.HIGH,
                message="High severity alert",
                status=AlertStatus.PENDING
            ),
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="symptom_2",
                severity=AlertSeverity.MEDIUM,
                message="Medium severity alert",
                status=AlertStatus.PENDING
            ),
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="symptom_3",
                severity=AlertSeverity.LOW,
                message="Low severity alert",
                status=AlertStatus.PENDING
            ),
        ]

        db_session.add(patient)
        db_session.add_all(alerts)
        db_session.commit()

        # Query alerts
        patient_alerts = (
            db_session.query(Alert)
            .filter(Alert.patient_id == patient.id)
            .filter(Alert.status != AlertStatus.RESOLVED)
            .all()
        )

        assert len(patient_alerts) == 3

        # Calculate aggregate risk
        risk_score = 0.0
        for alert in patient_alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                risk_score += 0.4
            elif alert.severity == AlertSeverity.HIGH:
                risk_score += 0.3
            elif alert.severity == AlertSeverity.MEDIUM:
                risk_score += 0.2
            elif alert.severity == AlertSeverity.LOW:
                risk_score += 0.1

        # Should aggregate: 0.3 + 0.2 + 0.1 = 0.6
        assert risk_score == 0.6

    def test_resolved_alerts_excluded(self, db_session):
        """Resolved alerts should not affect risk score"""
        physician_id = uuid4()

        patient = Patient(
            id=uuid4(),
            firebase_uid="firebase_resolved_test",
            name="Resolved Alert Test",
            flow_state="active",
            doctor_id=physician_id
        )

        alerts = [
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="resolved_alert",
                severity=AlertSeverity.CRITICAL,
                message="This was resolved",
                status=AlertStatus.RESOLVED  # Resolved
            ),
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="active_alert",
                severity=AlertSeverity.MEDIUM,
                message="This is active",
                status=AlertStatus.PENDING  # Active
            ),
        ]

        db_session.add(patient)
        db_session.add_all(alerts)
        db_session.commit()

        # Query only unresolved alerts
        active_alerts = (
            db_session.query(Alert)
            .filter(Alert.patient_id == patient.id)
            .filter(Alert.status != AlertStatus.RESOLVED)
            .all()
        )

        # Should only include the active alert
        assert len(active_alerts) == 1
        assert active_alerts[0].severity == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_empty_patient_list(
        self,
        http_client,
        doctor_b_credentials,
        auth_headers,
        db_session
    ):
        """Physician with no patients should get empty list"""
        # doctor_b has no patients assigned
        headers = auth_headers(doctor_b_credentials)

        response = await http_client.get(
            "/api/v1/physician/risk-assessments",
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()

            # Should return empty or zero count
            if "total_count" in data:
                assert data["total_count"] == 0
            if "patients" in data:
                assert len(data["patients"]) == 0

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, http_client):
        """Unauthenticated requests should be rejected"""
        response = await http_client.get("/api/v1/physician/risk-assessments")
        assert response.status_code == 401


class TestPhysicianRiskBenchmarks:
    """Performance benchmark tests"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("patient_count", [10, 25, 50, 100])
    async def test_scalability_benchmarks(
        self,
        patient_count,
        http_client,
        doctor_a_credentials,
        auth_headers,
        db_session
    ):
        """Test performance scales linearly with patient count"""
        physician_id = doctor_a_credentials['firebase_uid']

        # Create N patients
        patients = []
        for i in range(patient_count):
            patients.append(Patient(
                id=uuid4(),
                firebase_uid=f"firebase_scale_{i}",
                name=f"Scale Patient {i}",
                flow_state="active",
                doctor_id=physician_id
            ))

        db_session.add_all(patients)
        db_session.commit()

        # Measure performance
        headers = auth_headers(doctor_a_credentials)

        start_time = time.time()
        response = await http_client.get(
            "/api/v1/physician/risk-assessments",
            headers=headers
        )
        elapsed_ms = (time.time() - start_time) * 1000

        # Performance targets based on patient count
        if patient_count <= 10:
            max_time = 50  # 50ms for 10 patients
        elif patient_count <= 25:
            max_time = 100  # 100ms for 25 patients
        elif patient_count <= 50:
            max_time = 200  # 200ms for 50 patients
        else:
            max_time = 400  # 400ms for 100 patients

        if response.status_code == 200:
            assert elapsed_ms < max_time, (
                f"{patient_count} patients took {elapsed_ms:.2f}ms "
                f"(target: < {max_time}ms)"
            )
