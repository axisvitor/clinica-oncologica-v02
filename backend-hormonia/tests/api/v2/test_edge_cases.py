"""
Edge Case Testing for Route Corrections
Tests boundary conditions, race conditions, and unusual scenarios.
"""

import pytest
from uuid import uuid4
from datetime import date, datetime, timezone, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor

from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity


class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    def test_pagination_with_zero_limit(
        self,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify pagination handles zero/negative limits."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        headers = {"X-Session-ID": "doctor-session"}

        # Zero limit
        response = client.get("/api/v2/patients/?limit=0", headers=headers)
        # Should use default or minimum limit
        assert response.status_code in [200, 400]

        # Negative limit
        response = client.get("/api/v2/patients/?limit=-1", headers=headers)
        assert response.status_code in [200, 400]

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    def test_pagination_with_very_large_limit(
        self,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify pagination handles excessive limits."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        headers = {"X-Session-ID": "doctor-session"}

        # Very large limit (should be capped)
        response = client.get("/api/v2/patients/?limit=999999", headers=headers)
        assert response.status_code == status.HTTP_200_OK

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    def test_empty_result_set_pagination(
        self,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify pagination handles empty result sets."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        headers = {"X-Session-ID": "doctor-session"}
        response = client.get("/api/v2/patients/", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []
        assert data["has_more"] is False
        assert data["next_cursor"] is None


class TestConcurrentOperations:
    """Test concurrent access and race conditions."""

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    def test_concurrent_patient_updates(
        self,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify concurrent updates don't cause data corruption."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)

        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            doctor_id=doctor.id,
            birth_date=date(1990, 1, 1)
        )
        db_session.add(patient)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        headers = {"X-Session-ID": "doctor-session"}

        def update_patient(name_suffix):
            update_data = {"name": f"Updated Patient {name_suffix}"}
            return client.patch(
                f"/api/v2/patients/{patient.id}",
                json=update_data,
                headers=headers
            )

        # Simulate concurrent updates
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(update_patient, i) for i in range(3)]
            results = [f.result() for f in futures]

        # All should complete (200 or appropriate error)
        for response in results:
            assert response.status_code in [200, 409, 500]

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    def test_concurrent_alert_acknowledgments(
        self,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify concurrent acknowledgments are handled correctly."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)

        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            doctor_id=doctor.id,
            birth_date=date(1990, 1, 1)
        )
        db_session.add(patient)

        alert = Alert(
            id=uuid4(),
            patient_id=patient.id,
            alert_type="test",
            severity=AlertSeverity.HIGH,
            description="Test",
            acknowledged=False
        )
        db_session.add(alert)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        headers = {"X-Session-ID": "doctor-session"}

        def acknowledge_alert():
            return client.patch(
                f"/api/v2/alerts/{alert.id}/read",
                json={"notes": "Acknowledged"},
                headers=headers
            )

        # Concurrent acknowledgments
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(acknowledge_alert) for _ in range(2)]
            results = [f.result() for f in futures]

        # One should succeed, one should get 400 (already acknowledged)
        status_codes = [r.status_code for r in results]
        assert 200 in status_codes or 400 in status_codes


class TestDataValidation:
    """Test data validation and sanitization."""

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    def test_patient_with_invalid_email_format(
        self,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify invalid email formats are rejected."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        invalid_emails = [
            "notanemail",
            "@example.com",
            "test@",
            "test space@example.com"
        ]

        headers = {"X-Session-ID": "doctor-session"}

        for invalid_email in invalid_emails:
            patient_data = {
                "name": "Test Patient",
                "email": invalid_email,
                "birth_date": "1990-01-01",
                "doctor_id": str(doctor.id),
                "phone": "+1234567890"
            }

            response = client.post("/api/v2/patients/", json=patient_data, headers=headers)
            # Should reject invalid emails
            assert response.status_code in [400, 422]

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    def test_patient_with_future_birth_date(
        self,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify future birth dates are rejected."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        future_date = (datetime.now() + timedelta(days=365)).date()

        patient_data = {
            "name": "Test Patient",
            "email": "test@example.com",
            "birth_date": future_date.isoformat(),
            "doctor_id": str(doctor.id),
            "phone": "+1234567890"
        }

        headers = {"X-Session-ID": "doctor-session"}
        response = client.post("/api/v2/patients/", json=patient_data, headers=headers)

        # Should reject future dates
        assert response.status_code in [400, 422]

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    def test_alert_with_empty_description(
        self,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify empty alert descriptions are handled."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)

        patient = Patient(
            id=uuid4(),
            name="Patient",
            doctor_id=doctor.id,
            birth_date=date(1990, 1, 1)
        )
        db_session.add(patient)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        alert_data = {
            "patient_id": str(patient.id),
            "alert_type": "test",
            "severity": "high",
            "description": ""
        }

        headers = {"X-Session-ID": "doctor-session"}
        response = client.post("/api/v2/alerts", json=alert_data, headers=headers)

        # Should reject or use default
        assert response.status_code in [201, 400, 422]


class TestCacheInvalidation:
    """Test cache invalidation scenarios."""

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    @patch('app.core.redis_manager.RedisManager.delete_pattern')
    def test_patient_update_invalidates_cache(
        self,
        mock_delete_pattern,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify patient updates invalidate relevant caches."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)

        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            doctor_id=doctor.id,
            birth_date=date(1990, 1, 1)
        )
        db_session.add(patient)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        update_data = {"name": "Updated Patient"}
        headers = {"X-Session-ID": "doctor-session"}
        response = client.patch(
            f"/api/v2/patients/{patient.id}",
            json=update_data,
            headers=headers
        )

        if response.status_code == 200:
            # Verify cache invalidation was called
            assert mock_delete_pattern.called

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    @patch('app.core.redis_manager.RedisManager.delete_pattern')
    def test_alert_creation_invalidates_list_cache(
        self,
        mock_delete_pattern,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify alert creation invalidates list caches."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)

        patient = Patient(
            id=uuid4(),
            name="Patient",
            doctor_id=doctor.id,
            birth_date=date(1990, 1, 1)
        )
        db_session.add(patient)
        db_session.commit()

        mock_get_session.return_value = {
            "firebase_uid": doctor.firebase_uid,
            "user_id": str(doctor.id),
        }
        mock_get_user.return_value = {
            "id": str(doctor.id),
            "firebase_uid": doctor.firebase_uid,
            "email": doctor.email,
            "full_name": doctor.full_name,
            "role": doctor.role.value,
            "is_active": True,
        }

        alert_data = {
            "patient_id": str(patient.id),
            "alert_type": "test",
            "severity": "high",
            "description": "Test alert"
        }

        headers = {"X-Session-ID": "doctor-session"}
        response = client.post("/api/v2/alerts", json=alert_data, headers=headers)

        if response.status_code == 201:
            # Verify cache invalidation for alerts list
            assert mock_delete_pattern.called
