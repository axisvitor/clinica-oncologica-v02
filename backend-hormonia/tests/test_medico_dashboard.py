"""
Tests for Medico Dashboard Stats Endpoint.

Test the GET /api/v1/medico/dashboard-stats endpoint functionality.
"""
import pytest
from datetime import datetime, date, timedelta
from uuid import uuid4

from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageDirection, MessageStatus
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.services.medico_stats_service import MedicoStatsService


@pytest.fixture
def sample_medico(db_session):
    """Create a sample medico (doctor) user."""
    medico = User(
        id=uuid4(),
        email="dr.test@hospital.com",
        hashed_password="hashed_password",
        full_name="Dr. Test",
        role=UserRole.DOCTOR,
        is_active=True
    )
    db_session.add(medico)
    db_session.commit()
    return medico


@pytest.fixture
def sample_patients(db_session, sample_medico):
    """Create sample patients for the medico."""
    patients = []
    for i in range(5):
        patient = Patient(
            id=uuid4(),
            doctor_id=sample_medico.id,
            phone=f"+5511999{i:06d}",
            name=f"Patient {i}",
            email=f"patient{i}@example.com",
            flow_state=FlowState.ACTIVE,
            current_day=10 + i
        )
        patients.append(patient)
        db_session.add(patient)

    # Add one inactive patient
    inactive_patient = Patient(
        id=uuid4(),
        doctor_id=sample_medico.id,
        phone="+5511999999999",
        name="Inactive Patient",
        flow_state=FlowState.INACTIVE,
        current_day=0
    )
    db_session.add(inactive_patient)

    db_session.commit()
    return patients


@pytest.fixture
def sample_messages(db_session, sample_patients):
    """Create sample messages."""
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)

    messages = []

    # Today's outbound messages (consultas_hoje)
    for i in range(3):
        msg = Message(
            id=uuid4(),
            patient_id=sample_patients[i].id,
            direction=MessageDirection.OUTBOUND,
            content=f"Consultation message {i}",
            status=MessageStatus.SENT,
            created_at=today
        )
        messages.append(msg)
        db_session.add(msg)

    # Unread inbound messages (pendencias)
    for i in range(4):
        msg = Message(
            id=uuid4(),
            patient_id=sample_patients[i].id,
            direction=MessageDirection.INBOUND,
            content=f"Patient question {i}",
            status=MessageStatus.DELIVERED,
            created_at=today
        )
        messages.append(msg)
        db_session.add(msg)

    db_session.commit()
    return messages


@pytest.fixture
def sample_alerts(db_session, sample_patients):
    """Create sample alerts."""
    alerts = []

    # Create alerts with different severities
    severities = [
        AlertSeverity.CRITICAL,
        AlertSeverity.CRITICAL,
        AlertSeverity.HIGH,
        AlertSeverity.HIGH,
        AlertSeverity.MEDIUM
    ]

    for i, severity in enumerate(severities):
        alert = Alert(
            id=uuid4(),
            patient_id=sample_patients[i].id,
            alert_type="symptom",
            severity=severity,
            description=f"Alert {i}",
            status=AlertStatus.ACTIVE
        )
        alerts.append(alert)
        db_session.add(alert)

    db_session.commit()
    return alerts


class TestMedicoStatsService:
    """Test MedicoStatsService functionality."""

    def test_get_pacientes_ativos(self, db_session, sample_medico, sample_patients):
        """Test active patients count."""
        service = MedicoStatsService(db_session, str(sample_medico.id))
        count = service.get_pacientes_ativos()
        assert count == 5  # 5 active patients (excluding inactive)

    def test_get_consultas_hoje(self, db_session, sample_medico, sample_patients, sample_messages):
        """Test today's consultations count."""
        service = MedicoStatsService(db_session, str(sample_medico.id))
        count = service.get_consultas_hoje()
        assert count == 3  # 3 outbound messages today

    def test_get_pendencias(self, db_session, sample_medico, sample_patients, sample_messages):
        """Test pending tasks count."""
        service = MedicoStatsService(db_session, str(sample_medico.id))
        count = service.get_pendencias()
        assert count == 4  # 4 unread messages

    def test_get_alert_metrics(self, db_session, sample_medico, sample_patients, sample_alerts):
        """Test alert metrics calculation."""
        service = MedicoStatsService(db_session, str(sample_medico.id))
        metrics = service.get_alert_metrics()

        assert metrics["total"] == 5
        assert metrics["critical"] == 2
        assert metrics["high"] == 2
        assert metrics["medium"] == 1
        assert metrics["low"] == 0

    def test_get_engagement_metrics(self, db_session, sample_medico, sample_patients, sample_messages):
        """Test engagement metrics calculation."""
        service = MedicoStatsService(db_session, str(sample_medico.id))
        metrics = service.get_engagement_metrics()

        assert metrics["messages_today"] == 3  # 3 outbound today
        assert metrics["messages_unread"] == 4  # 4 unread inbound
        assert metrics["response_rate"] >= 0.0
        assert metrics["response_rate"] <= 1.0

    def test_get_all_stats(self, db_session, sample_medico, sample_patients, sample_messages, sample_alerts):
        """Test complete stats calculation."""
        service = MedicoStatsService(db_session, str(sample_medico.id))
        stats = service.get_all_stats()

        assert "pacientes_ativos" in stats
        assert "consultas_hoje" in stats
        assert "pendencias" in stats
        assert "exames_aguardando" in stats
        assert "engagement" in stats
        assert "alerts" in stats
        assert "timestamp" in stats

        assert stats["pacientes_ativos"] == 5
        assert stats["consultas_hoje"] == 3
        assert stats["pendencias"] == 4
        assert stats["alerts"]["total"] == 5


class TestMedicoDashboardEndpoint:
    """Test medico dashboard API endpoint."""

    def test_dashboard_stats_requires_auth(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/api/v1/medico/dashboard-stats")
        assert response.status_code == 401

    def test_dashboard_stats_requires_doctor_role(self, client, auth_headers_patient):
        """Test that endpoint requires doctor role."""
        # This would fail if a patient token is used
        # Assuming we have a patient auth fixture
        pass  # Implement with proper auth fixtures

    def test_dashboard_stats_success(
        self,
        client,
        db_session,
        sample_medico,
        sample_patients,
        sample_messages,
        sample_alerts
    ):
        """Test successful dashboard stats retrieval."""
        # Create auth token for medico
        # This requires Firebase auth setup in tests
        # For now, this is a placeholder

        # response = client.get(
        #     "/api/v1/medico/dashboard-stats",
        #     headers={"Authorization": f"Bearer {medico_token}"}
        # )
        #
        # assert response.status_code == 200
        # data = response.json()
        #
        # assert data["pacientes_ativos"] == 5
        # assert data["consultas_hoje"] == 3
        # assert data["pendencias"] == 4
        # assert data["alerts"]["total"] == 5
        pass

    def test_dashboard_stats_caching(self, client, db_session, sample_medico):
        """Test Redis caching of dashboard stats."""
        # First request should calculate stats
        # Second request should hit cache
        # Verify cache expiration after 2 minutes
        pass


@pytest.mark.integration
class TestMedicoDashboardIntegration:
    """Integration tests for medico dashboard."""

    def test_new_medico_returns_zeros(self, db_session):
        """Test that new medico with no data returns zeros."""
        new_medico = User(
            id=uuid4(),
            email="new.doctor@hospital.com",
            hashed_password="hashed",
            full_name="Dr. New",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(new_medico)
        db_session.commit()

        service = MedicoStatsService(db_session, str(new_medico.id))
        stats = service.get_all_stats()

        assert stats["pacientes_ativos"] == 0
        assert stats["consultas_hoje"] == 0
        assert stats["pendencias"] == 0
        assert stats["alerts"]["total"] == 0

    def test_performance_with_large_dataset(self, db_session, sample_medico):
        """Test performance with large number of patients."""
        # Create 100 patients
        patients = []
        for i in range(100):
            patient = Patient(
                id=uuid4(),
                doctor_id=sample_medico.id,
                phone=f"+5511{i:09d}",
                name=f"Patient {i}",
                flow_state=FlowState.ACTIVE,
                current_day=i
            )
            patients.append(patient)
            db_session.add(patient)

        db_session.commit()

        # Measure query performance
        import time
        start_time = time.time()

        service = MedicoStatsService(db_session, str(sample_medico.id))
        stats = service.get_all_stats()

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in under 1 second even with 100 patients
        assert execution_time < 1.0
        assert stats["pacientes_ativos"] == 100
