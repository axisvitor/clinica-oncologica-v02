"""
Tests for refactored physicians module.

Tests cover:
- PhysicianStatisticsService
- PhysicianAvailabilityService
- CRUD endpoints
- Statistics endpoints
- Availability endpoints
- Redis caching
- Query optimization
"""

import pytest
from datetime import datetime, timedelta, date
from uuid import uuid4
from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageDirection, MessageStatus
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.appointment import Appointment, AppointmentStatus
from app.api.v2.routers.physicians.services import (
    PhysicianStatisticsService,
    PhysicianAvailabilityService,
)
from app.api.v2.routers.physicians.base import (
    _calculate_workload_level,
    validate_physician_access,
)
from app.schemas.v2.physicians import WorkloadLevel


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def physician(db: Session) -> User:
    """Create a test physician."""
    physician = User(
        id=uuid4(),
        email="physician@test.com",
        role=UserRole.DOCTOR,
        is_active=True,
        firebase_uid="test_physician",
        firebase_email_verified=True,
        firebase_display_name="Dr. Test",
        firebase_custom_claims={"specialties": ["oncology"]},
    )
    db.add(physician)
    db.commit()
    db.refresh(physician)
    return physician


@pytest.fixture
def patients(db: Session, physician: User) -> list[Patient]:
    """Create test patients."""
    patients = []
    for i in range(5):
        patient = Patient(
            id=uuid4(),
            doctor_id=physician.id,
            flow_state=FlowState.ACTIVE if i < 3 else FlowState.CANCELLED,
            created_at=datetime.utcnow(),
        )
        db.add(patient)
        patients.append(patient)

    db.commit()
    return patients


# ============================================================================
# Test Base Utilities
# ============================================================================

class TestBaseUtilities:
    """Test base utility functions."""

    def test_calculate_workload_level(self):
        """Test workload level calculation."""
        assert _calculate_workload_level(0) == WorkloadLevel.LOW
        assert _calculate_workload_level(10) == WorkloadLevel.LOW
        assert _calculate_workload_level(20) == WorkloadLevel.LOW
        assert _calculate_workload_level(30) == WorkloadLevel.MEDIUM
        assert _calculate_workload_level(50) == WorkloadLevel.MEDIUM
        assert _calculate_workload_level(75) == WorkloadLevel.HIGH
        assert _calculate_workload_level(100) == WorkloadLevel.HIGH
        assert _calculate_workload_level(150) == WorkloadLevel.OVERLOADED

    def test_validate_physician_access_admin(
        self, db: Session, physician: User
    ):
        """Test admin can access any physician."""
        admin_user = {"id": str(uuid4()), "role": UserRole.ADMIN}

        result = validate_physician_access(
            physician.id, admin_user, db, allow_patient_view=True
        )

        assert result.id == physician.id

    def test_validate_physician_access_self(
        self, db: Session, physician: User
    ):
        """Test physician can access themselves."""
        physician_user = {"id": str(physician.id), "role": UserRole.DOCTOR}

        result = validate_physician_access(
            physician.id, physician_user, db, allow_patient_view=True
        )

        assert result.id == physician.id

    def test_validate_physician_access_patient_assigned(
        self, db: Session, physician: User, patients: list[Patient]
    ):
        """Test patient can view assigned physician."""
        patient_user = {"id": str(patients[0].id), "role": UserRole.PATIENT}

        result = validate_physician_access(
            physician.id, patient_user, db, allow_patient_view=True
        )

        assert result.id == physician.id

    def test_validate_physician_access_forbidden(
        self, db: Session, physician: User
    ):
        """Test unauthorized access raises 403."""
        other_user = {"id": str(uuid4()), "role": UserRole.DOCTOR}

        with pytest.raises(Exception) as exc_info:
            validate_physician_access(
                physician.id, other_user, db, allow_patient_view=True
            )

        assert exc_info.value.status_code == 403


# ============================================================================
# Test PhysicianStatisticsService
# ============================================================================

class TestPhysicianStatisticsService:
    """Test PhysicianStatisticsService."""

    def test_calculate_patient_metrics(
        self, db: Session, physician: User, patients: list[Patient]
    ):
        """Test patient metrics calculation."""
        service = PhysicianStatisticsService(db)
        metrics = service._calculate_patient_metrics(physician.id)

        assert metrics["total"] == 5
        assert metrics["active"] == 3
        assert metrics["inactive"] == 2
        assert metrics["workload_level"] == WorkloadLevel.LOW

    def test_calculate_message_stats(
        self, db: Session, physician: User, patients: list[Patient]
    ):
        """Test message statistics calculation."""
        # Create test messages
        for patient in patients[:3]:  # Active patients
            # Inbound messages
            for _ in range(2):
                msg = Message(
                    id=uuid4(),
                    patient_id=patient.id,
                    direction=MessageDirection.INBOUND,
                    status=MessageStatus.DELIVERED,
                    content="Test message",
                    created_at=datetime.utcnow(),
                )
                db.add(msg)

            # Outbound messages
            msg = Message(
                id=uuid4(),
                patient_id=patient.id,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.DELIVERED,
                content="Response",
                created_at=datetime.utcnow(),
            )
            db.add(msg)

        db.commit()

        service = PhysicianStatisticsService(db)
        stats = service._calculate_message_stats(physician.id)

        assert stats.total_received == 6  # 2 per active patient
        assert stats.total_sent == 3  # 1 per active patient
        assert stats.unread_count >= 0

    def test_calculate_statistics_with_cache(
        self, db: Session, physician: User, patients: list[Patient]
    ):
        """Test statistics calculation with Redis caching."""
        service = PhysicianStatisticsService(db, cache_ttl=300)

        # First call should calculate
        stats1 = service.calculate_statistics(physician.id, use_cache=True)

        assert stats1.total_patients == 5
        assert stats1.active_patients == 3
        assert stats1.workload_level == WorkloadLevel.LOW

        # Second call should use cache (if Redis available)
        stats2 = service.calculate_statistics(physician.id, use_cache=True)

        assert stats2.total_patients == stats1.total_patients

    def test_calculate_batch_statistics(
        self, db: Session, physician: User
    ):
        """Test batch statistics calculation."""
        # Create another physician
        physician2 = User(
            id=uuid4(),
            email="physician2@test.com",
            role=UserRole.DOCTOR,
            is_active=True,
            firebase_uid="test_physician2",
        )
        db.add(physician2)
        db.commit()

        service = PhysicianStatisticsService(db)
        results = service.calculate_batch_statistics(
            [physician.id, physician2.id]
        )

        assert len(results) == 2
        assert physician.id in results
        assert physician2.id in results

    def test_invalidate_cache(
        self, db: Session, physician: User
    ):
        """Test cache invalidation."""
        service = PhysicianStatisticsService(db)

        # Calculate to populate cache
        service.calculate_statistics(physician.id, use_cache=True)

        # Invalidate
        service.invalidate_cache(physician.id)

        # Should recalculate on next call
        stats = service.calculate_statistics(physician.id, use_cache=True)
        assert stats is not None


# ============================================================================
# Test PhysicianAvailabilityService
# ============================================================================

class TestPhysicianAvailabilityService:
    """Test PhysicianAvailabilityService."""

    def test_get_schedule(
        self, db: Session, physician: User, patients: list[Patient]
    ):
        """Test getting physician schedule."""
        # Create test appointments
        today = date.today()
        for i in range(3):
            appt = Appointment(
                id=uuid4(),
                practitioner_id=physician.id,
                patient_id=patients[i].id,
                scheduled_at=datetime.combine(
                    today + timedelta(days=i),
                    datetime.min.time()
                ),
                status=AppointmentStatus.SCHEDULED.value,
            )
            db.add(appt)

        db.commit()

        service = PhysicianAvailabilityService(db)
        schedule = service.get_schedule(
            physician.id,
            today,
            today + timedelta(days=7)
        )

        assert schedule["physician_id"] == str(physician.id)
        assert len(schedule["appointments"]) == 3

    def test_is_available_no_conflicts(
        self, db: Session, physician: User
    ):
        """Test availability check with no conflicts."""
        service = PhysicianAvailabilityService(db)

        requested_datetime = datetime.utcnow() + timedelta(days=1)
        is_available = service.is_available(
            physician.id, requested_datetime, duration_minutes=30
        )

        assert is_available is True

    def test_is_available_with_conflict(
        self, db: Session, physician: User, patients: list[Patient]
    ):
        """Test availability check with conflicting appointment."""
        requested_datetime = datetime.utcnow() + timedelta(days=1)

        # Create conflicting appointment
        appt = Appointment(
            id=uuid4(),
            practitioner_id=physician.id,
            patient_id=patients[0].id,
            scheduled_at=requested_datetime,
            status=AppointmentStatus.SCHEDULED.value,
        )
        db.add(appt)
        db.commit()

        service = PhysicianAvailabilityService(db)
        is_available = service.is_available(
            physician.id, requested_datetime, duration_minutes=30
        )

        assert is_available is False


# ============================================================================
# Test Query Optimization
# ============================================================================

class TestQueryOptimization:
    """Test that queries are optimized and not N+1."""

    def test_patient_metrics_single_query(
        self, db: Session, physician: User, patients: list[Patient]
    ):
        """Test patient metrics uses single aggregation query."""
        service = PhysicianStatisticsService(db)

        # Mock to track query count
        with patch.object(db, 'query', wraps=db.query) as mock_query:
            metrics = service._calculate_patient_metrics(physician.id)

            # Should only call query once for aggregation
            assert mock_query.call_count <= 2  # Allow for subquery

        assert metrics["total"] == 5

    def test_message_stats_single_query(
        self, db: Session, physician: User, patients: list[Patient]
    ):
        """Test message stats uses optimized queries."""
        service = PhysicianStatisticsService(db)

        with patch.object(db, 'query', wraps=db.query) as mock_query:
            stats = service._calculate_message_stats(physician.id)

            # Should use minimal queries (subquery + aggregation + response time)
            assert mock_query.call_count <= 4

        assert stats is not None


# ============================================================================
# Test API Endpoints
# ============================================================================

@pytest.mark.integration
class TestPhysiciansEndpoints:
    """Integration tests for physicians endpoints."""

    def test_list_physicians(
        self, client, db: Session, physician: User, admin_token
    ):
        """Test listing physicians endpoint."""
        response = client.get(
            "/api/v2/physicians",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 1

    def test_get_physician_statistics(
        self, client, db: Session, physician: User, admin_token
    ):
        """Test getting physician statistics."""
        response = client.get(
            f"/api/v2/physicians/{physician.id}/statistics",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_patients" in data
        assert "active_patients" in data
        assert "workload_level" in data

    def test_update_physician(
        self, client, db: Session, physician: User, admin_token
    ):
        """Test updating physician information."""
        update_data = {
            "full_name": "Dr. Updated Name",
            "specialties": ["oncology", "hematology"]
        }

        response = client.patch(
            f"/api/v2/physicians/{physician.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Dr. Updated Name"
        assert len(data["specialties"]) == 2
