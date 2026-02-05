"""
Critical security regression tests for patient CRUD/import fixes.
"""

from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def _user_dict(user):
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "full_name": user.full_name,
        "is_active": user.is_active,
        "firebase_uid": getattr(user, "firebase_uid", None),
    }


@pytest.mark.api
@pytest.mark.security
class TestPatientSecurityFixes:
    def test_idempotency_rbac_denies_other_doctor(
        self, client: TestClient, db_session, app_instance, app_modules
    ):
        User = app_modules["User"]
        UserRole = app_modules["UserRole"]
        Patient = app_modules["Patient"]
        get_current_user_from_session = app_modules["get_current_user_from_session"]

        doctor_one = User(
            id=uuid4(),
            email=f"doctor_one_{uuid4().hex}@example.com",
            full_name="Doctor One",
            role=UserRole.DOCTOR,
            is_active=True,
        )
        doctor_two = User(
            id=uuid4(),
            email=f"doctor_two_{uuid4().hex}@example.com",
            full_name="Doctor Two",
            role=UserRole.DOCTOR,
            is_active=True,
        )
        db_session.add_all([doctor_one, doctor_two])
        db_session.commit()

        idempotency_key = f"idem-{uuid4().hex}"
        patient = Patient(
            id=uuid4(),
            name="Idempotency Patient",
            doctor_id=doctor_one.id,
            idempotency_key=idempotency_key,
        )
        patient.set_phone("+5511999999001")
        db_session.add(patient)
        db_session.commit()

        app_instance.dependency_overrides[get_current_user_from_session] = lambda: _user_dict(
            doctor_two
        )

        try:
            response = client.post(
                "/api/v2/patients/",
                json={
                    "name": "New Patient",
                    "phone": "+5511999999002",
                    "doctor_id": str(doctor_two.id),
                },
                headers={"X-Idempotency-Key": idempotency_key},
            )
        finally:
            app_instance.dependency_overrides.pop(get_current_user_from_session, None)

        assert response.status_code == 403

    def test_import_savepoints_preserve_valid_rows(
        self, authenticated_client: TestClient, db_session
    ):
        csv_content = "\n".join(
            [
                "Name,Phone,Email,Birth Date,CPF",
                "Valid Patient,+5511999999003,valid@gmail.com,1990-01-15,52998224725",
                "Invalid Email,+5511999999004,invalid-email,1990-01-15,52998224725",
            ]
        )
        csv_file = BytesIO(csv_content.encode())

        response = authenticated_client.post(
            "/api/v2/patients/import",
            files={"file": ("patients.csv", csv_file, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == 1
        assert data["failed"] == 1
        assert any("Invalid email format" in err["message"] for err in data["errors"])

        from app.models.patient import Patient

        created_count = (
            db_session.query(Patient)
            .filter(Patient.name == "Valid Patient")
            .count()
        )
        assert created_count == 1

    def test_import_rejects_invalid_cpf_checksum(
        self, authenticated_client: TestClient
    ):
        csv_content = "\n".join(
            [
                "Name,Phone,Email,Birth Date,CPF",
                "Bad CPF,+5511999999005,badcpf@gmail.com,1985-05-20,52998224724",
            ]
        )
        csv_file = BytesIO(csv_content.encode())

        response = authenticated_client.post(
            "/api/v2/patients/import",
            files={"file": ("patients.csv", csv_file, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == 0
        assert data["failed"] == 1
        assert any("Invalid CPF checksum" in err["message"] for err in data["errors"])
