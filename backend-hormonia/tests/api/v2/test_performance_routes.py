"""
Performance and Load Testing for Route Corrections
Tests response times, throughput, and resource usage.
"""

import time
from uuid import uuid4
from datetime import date
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.models.user import User, UserRole
from app.models.patient import Patient


class TestResponseTimes:
    """Test response time requirements."""

    @patch('app.core.redis_manager.RedisManager.get_session')
    @patch('app.core.redis_manager.RedisManager.get_user_by_uid')
    @patch('app.core.redis_manager.RedisManager.get')
    def test_patient_list_response_time(
        self,
        mock_redis_get,
        mock_get_user,
        mock_get_session,
        client: TestClient,
        db_session
    ):
        """Verify patient list responds within acceptable time."""
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            firebase_uid="doctor-firebase-uid",
            full_name="Doctor",
            role=UserRole.DOCTOR,
            is_active=True
        )
        db_session.add(doctor)

        # Create multiple patients
        for i in range(50):
            patient = Patient(
                id=uuid4(),
                name=f"Patient {i}",
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
        mock_redis_get.return_value = None  # Cache miss

        headers = {"X-Session-ID": "doctor-session"}

        start_time = time.time()
        response = client.get("/api/v2/patients/?limit=20", headers=headers)
        elapsed_time = time.time() - start_time

        assert response.status_code == status.HTTP_200_OK
        # Should respond within 2 seconds
        assert elapsed_time < 2.0, f"Response took {elapsed_time:.2f}s, expected < 2.0s"
