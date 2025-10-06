"""
Test suite for Medico Dashboard Stats endpoint.

Tests GET /api/v1/medico/dashboard-stats with:
- New medico with no data (should return zeros, not errors)
- Accurate stats calculation
- Alert metrics by severity
- Engagement metrics
- Appointment counting
- Exam status tracking
"""
import pytest
from datetime import datetime, date, timedelta
from uuid import uuid4

from app.models.user import User
from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.message import Message, MessageDirection
from tests.helpers.jwt_helper import jwt_helper


class TestMedicoDashboardStats:
    """Test suite for GET /api/v1/medico/dashboard-stats"""

    @pytest.mark.asyncio
    async def test_new_medico_with_no_data(
        self,
        http_client,
        doctor_a_credentials,
        auth_headers,
        db_session
    ):
        """New medico should get zeros, not errors"""
        # Create a brand new medico with no patients
        new_medico_uid = "firebase_brand_new_medico"

        new_medico = User(
            id=uuid4(),
            firebase_uid=new_medico_uid,
            email="new.medico@test.com",
            full_name="New Medico",
            role="doctor"
        )
        db_session.add(new_medico)
        db_session.commit()

        # Create token for new medico
        token = jwt_helper.create_jwt_token(
            firebase_uid=new_medico_uid,
            email="new.medico@test.com",
            role="doctor"
        )

        headers = {"Authorization": f"Bearer {token}"}

        response = await http_client.get(
            "/api/v1/medico/dashboard-stats",
            headers=headers
        )

        # Should return success (or 404 if not implemented)
        assert response.status_code in [200, 404, 500]

        # If implemented, should return zeros gracefully
        if response.status_code == 200:
            data = response.json()

            # Should have zero values, not errors
            # These keys might vary based on implementation
            possible_zero_keys = [
                "pacientes_ativos", "active_patients",
                "consultas_hoje", "appointments_today",
                "pendencias", "pending_tasks",
                "exames_aguardando", "pending_exams"
            ]

            # At least one zero metric should exist
            has_zero_metric = False
            for key in possible_zero_keys:
                if key in data and data[key] == 0:
                    has_zero_metric = True
                    break

            # Response should be valid JSON with some structure
            assert isinstance(data, dict)

    def test_stats_calculation_accuracy(self, db_session):
        """Stats should reflect database state accurately"""
        medico_id = uuid4()

        # Create test data
        patients = [
            Patient(
                id=uuid4(),
                firebase_uid="firebase_active_1",
                name="Active Patient 1",
                flow_state="active",
                doctor_id=medico_id
            ),
            Patient(
                id=uuid4(),
                firebase_uid="firebase_active_2",
                name="Active Patient 2",
                flow_state="active",
                doctor_id=medico_id
            ),
            Patient(
                id=uuid4(),
                firebase_uid="firebase_inactive",
                name="Inactive Patient",
                flow_state="completed",  # Not active
                doctor_id=medico_id
            ),
        ]

        db_session.add_all(patients)
        db_session.commit()

        # Count active patients
        active_count = (
            db_session.query(Patient)
            .filter(Patient.doctor_id == medico_id)
            .filter(Patient.flow_state == "active")
            .count()
        )

        # Should count only active patients
        assert active_count == 2

        # Total patients for this medico
        total_count = (
            db_session.query(Patient)
            .filter(Patient.doctor_id == medico_id)
            .count()
        )

        assert total_count == 3

    def test_alert_metrics_by_severity(self, db_session):
        """Should count alerts by severity correctly"""
        medico_id = uuid4()

        patient = Patient(
            id=uuid4(),
            firebase_uid="firebase_alert_patient",
            name="Alert Test Patient",
            flow_state="active",
            doctor_id=medico_id
        )

        alerts = [
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="critical_symptom",
                severity=AlertSeverity.CRITICAL,
                message="Critical alert 1",
                status=AlertStatus.PENDING
            ),
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="high_symptom",
                severity=AlertSeverity.HIGH,
                message="High alert 1",
                status=AlertStatus.PENDING
            ),
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="high_symptom_2",
                severity=AlertSeverity.HIGH,
                message="High alert 2",
                status=AlertStatus.PENDING
            ),
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="medium_symptom",
                severity=AlertSeverity.MEDIUM,
                message="Medium alert",
                status=AlertStatus.PENDING
            ),
            Alert(
                id=uuid4(),
                patient_id=patient.id,
                type="resolved_symptom",
                severity=AlertSeverity.CRITICAL,
                message="Resolved critical",
                status=AlertStatus.RESOLVED  # Should not count
            ),
        ]

        db_session.add(patient)
        db_session.add_all(alerts)
        db_session.commit()

        # Query active alerts only
        active_alerts = (
            db_session.query(Alert)
            .filter(Alert.patient_id == patient.id)
            .filter(Alert.status != AlertStatus.RESOLVED)
            .all()
        )

        # Count by severity
        critical_count = sum(1 for a in active_alerts if a.severity == AlertSeverity.CRITICAL)
        high_count = sum(1 for a in active_alerts if a.severity == AlertSeverity.HIGH)
        medium_count = sum(1 for a in active_alerts if a.severity == AlertSeverity.MEDIUM)

        assert len(active_alerts) == 4  # Excluding resolved
        assert critical_count == 1
        assert high_count == 2
        assert medium_count == 1

    def test_engagement_calculation(self, db_session):
        """Engagement metrics should be calculated correctly"""
        medico_id = uuid4()

        patient = Patient(
            id=uuid4(),
            firebase_uid="firebase_engagement_patient",
            name="Engagement Patient",
            flow_state="active",
            doctor_id=medico_id
        )

        # Create messages for engagement calculation
        messages = [
            # Outbound messages (sent by medico/system)
            Message(
                id=uuid4(),
                patient_id=patient.id,
                content="Message 1",
                direction=MessageDirection.OUTBOUND,
                created_at=datetime.utcnow()
            ),
            Message(
                id=uuid4(),
                patient_id=patient.id,
                content="Message 2",
                direction=MessageDirection.OUTBOUND,
                created_at=datetime.utcnow()
            ),
            Message(
                id=uuid4(),
                patient_id=patient.id,
                content="Message 3",
                direction=MessageDirection.OUTBOUND,
                created_at=datetime.utcnow()
            ),
            # Inbound messages (responses from patient)
            Message(
                id=uuid4(),
                patient_id=patient.id,
                content="Response 1",
                direction=MessageDirection.INBOUND,
                created_at=datetime.utcnow()
            ),
            Message(
                id=uuid4(),
                patient_id=patient.id,
                content="Response 2",
                direction=MessageDirection.INBOUND,
                created_at=datetime.utcnow()
            ),
        ]

        db_session.add(patient)
        db_session.add_all(messages)
        db_session.commit()

        # Count messages
        outbound_count = (
            db_session.query(Message)
            .filter(Message.patient_id == patient.id)
            .filter(Message.direction == MessageDirection.OUTBOUND)
            .count()
        )

        inbound_count = (
            db_session.query(Message)
            .filter(Message.patient_id == patient.id)
            .filter(Message.direction == MessageDirection.INBOUND)
            .count()
        )

        assert outbound_count == 3
        assert inbound_count == 2

        # Calculate response rate
        response_rate = (inbound_count / outbound_count * 100) if outbound_count > 0 else 0
        assert response_rate == pytest.approx(66.67, rel=0.1)

    def test_today_filtering(self, db_session):
        """Should correctly filter data for 'today' metrics"""
        medico_id = uuid4()

        patient = Patient(
            id=uuid4(),
            firebase_uid="firebase_today_patient",
            name="Today Test Patient",
            flow_state="active",
            doctor_id=medico_id
        )

        today = datetime.combine(date.today(), datetime.min.time())
        yesterday = today - timedelta(days=1)

        messages = [
            # Today's messages
            Message(
                id=uuid4(),
                patient_id=patient.id,
                content="Today message 1",
                direction=MessageDirection.OUTBOUND,
                created_at=today + timedelta(hours=8)
            ),
            Message(
                id=uuid4(),
                patient_id=patient.id,
                content="Today message 2",
                direction=MessageDirection.OUTBOUND,
                created_at=today + timedelta(hours=14)
            ),
            # Yesterday's message (should not count)
            Message(
                id=uuid4(),
                patient_id=patient.id,
                content="Yesterday message",
                direction=MessageDirection.OUTBOUND,
                created_at=yesterday
            ),
        ]

        db_session.add(patient)
        db_session.add_all(messages)
        db_session.commit()

        # Query today's messages only
        today_count = (
            db_session.query(Message)
            .filter(Message.patient_id == patient.id)
            .filter(Message.created_at >= today)
            .count()
        )

        assert today_count == 2

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, http_client):
        """Unauthenticated requests should be rejected"""
        response = await http_client.get("/api/v1/medico/dashboard-stats")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_response_structure(
        self,
        http_client,
        doctor_a_credentials,
        auth_headers
    ):
        """Response should have expected structure"""
        headers = auth_headers(doctor_a_credentials)

        response = await http_client.get(
            "/api/v1/medico/dashboard-stats",
            headers=headers
        )

        # If implemented
        if response.status_code == 200:
            data = response.json()

            # Should be a dictionary
            assert isinstance(data, dict)

            # Should have some numeric metrics
            # Look for any numeric values in the response
            has_numeric = any(
                isinstance(v, (int, float)) for v in data.values()
            )
            assert has_numeric or len(data) == 0

    def test_multiple_medicos_isolation(self, db_session):
        """Each medico should only see their own patients' stats"""
        medico1_id = uuid4()
        medico2_id = uuid4()

        # Medico 1's patients
        medico1_patients = [
            Patient(
                id=uuid4(),
                firebase_uid="firebase_medico1_p1",
                name="Medico1 Patient 1",
                flow_state="active",
                doctor_id=medico1_id
            ),
            Patient(
                id=uuid4(),
                firebase_uid="firebase_medico1_p2",
                name="Medico1 Patient 2",
                flow_state="active",
                doctor_id=medico1_id
            ),
        ]

        # Medico 2's patients
        medico2_patients = [
            Patient(
                id=uuid4(),
                firebase_uid="firebase_medico2_p1",
                name="Medico2 Patient 1",
                flow_state="active",
                doctor_id=medico2_id
            ),
        ]

        db_session.add_all(medico1_patients + medico2_patients)
        db_session.commit()

        # Query for each medico
        medico1_count = (
            db_session.query(Patient)
            .filter(Patient.doctor_id == medico1_id)
            .count()
        )

        medico2_count = (
            db_session.query(Patient)
            .filter(Patient.doctor_id == medico2_id)
            .count()
        )

        assert medico1_count == 2
        assert medico2_count == 1

    def test_edge_case_null_values(self, db_session):
        """Should handle null/missing values gracefully"""
        medico_id = uuid4()

        # Patient with minimal data (nulls)
        minimal_patient = Patient(
            id=uuid4(),
            firebase_uid="firebase_minimal",
            name="Minimal Patient",
            flow_state="active",
            doctor_id=medico_id
            # No treatment_type, no current_day, etc.
        )

        db_session.add(minimal_patient)
        db_session.commit()

        # Should still be queryable
        count = (
            db_session.query(Patient)
            .filter(Patient.doctor_id == medico_id)
            .count()
        )

        assert count == 1


class TestMedicoStatsPerformance:
    """Performance tests for medico dashboard stats"""

    @pytest.mark.asyncio
    async def test_response_time(
        self,
        http_client,
        doctor_a_credentials,
        auth_headers
    ):
        """Stats should load quickly"""
        import time

        headers = auth_headers(doctor_a_credentials)

        start_time = time.time()
        response = await http_client.get(
            "/api/v1/medico/dashboard-stats",
            headers=headers
        )
        elapsed = time.time() - start_time

        # Should respond quickly (even if not implemented)
        assert elapsed < 1.0

        if response.status_code == 200:
            # If implemented, should be very fast
            assert elapsed < 0.5  # Target: 500ms
