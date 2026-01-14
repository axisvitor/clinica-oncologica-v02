from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import SagaStatus
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga


def _create_failed_saga(
    db_session: Session,
    patient: Patient,
    error_message: str = "Compensation failure",
) -> PatientOnboardingSaga:
    saga = PatientOnboardingSaga(
        id=uuid4(),
        patient_id=patient.id,
        doctor_id=patient.doctor_id,
        status=SagaStatus.FAILED,
        current_step=3,
        patient_data={"name": patient.name},
        execution_log=[
            {
                "step": 1,
                "action": "compensate_patient",
                "status": "compensation_failed",
                "message": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
        error_message=error_message,
        error_type="Exception",
        failed_at=datetime.now(timezone.utc),
    )
    db_session.add(saga)
    db_session.commit()
    db_session.refresh(saga)
    return saga


def test_list_compensation_failures_empty(
    client: TestClient,
    auth_headers_admin: dict,
):
    response = client.get(
        "/api/v2/admin/compensation-failures", headers=auth_headers_admin
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] == []
    assert payload["total"] == 0


def test_list_compensation_failures_with_data(
    client: TestClient,
    db_session: Session,
    auth_headers_admin: dict,
    create_test_patient,
):
    patient = create_test_patient()
    patient.patient_data = {"quarantine": True}
    db_session.add(patient)
    db_session.commit()

    saga = _create_failed_saga(db_session, patient, error_message="FK constraint")

    response = client.get(
        "/api/v2/admin/compensation-failures", headers=auth_headers_admin
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["data"][0]["saga_id"] == str(saga.id)
    assert payload["data"][0]["patient_id"] == str(patient.id)
    assert payload["data"][0]["failed_steps"][0]["step"] == 1


def test_retry_compensation_success(
    client: TestClient,
    db_session: Session,
    auth_headers_admin: dict,
    create_test_patient,
):
    patient = create_test_patient()
    patient.patient_data = {"quarantine": True}
    db_session.add(patient)
    db_session.commit()

    saga = _create_failed_saga(db_session, patient)

    with patch(
        "app.api.v2.routers.admin.compensation.get_redis_client", return_value=None
    ), patch(
        "app.api.v2.routers.admin.compensation.SagaCompensator"
    ) as compensator_mock:
        compensator_instance = compensator_mock.return_value
        compensator_instance.compensate_saga = AsyncMock()

        response = client.post(
            f"/api/v2/admin/compensation-failures/{saga.id}/retry",
            headers=auth_headers_admin,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True

    db_session.refresh(patient)
    assert not patient.patient_data or patient.patient_data.get("quarantine") is None

    db_session.refresh(saga)
    assert saga.status == SagaStatus.COMPENSATED
    assert saga.error_message is None
    assert saga.error_type is None
    assert saga.failed_at is None


def test_retry_compensation_failure(
    client: TestClient,
    db_session: Session,
    auth_headers_admin: dict,
    create_test_patient,
):
    patient = create_test_patient()
    patient.patient_data = {"quarantine": True}
    db_session.add(patient)
    db_session.commit()

    saga = _create_failed_saga(db_session, patient)

    with patch(
        "app.api.v2.routers.admin.compensation.get_redis_client", return_value=None
    ), patch(
        "app.api.v2.routers.admin.compensation.SagaCompensator"
    ) as compensator_mock:
        compensator_instance = compensator_mock.return_value
        compensator_instance.compensate_saga = AsyncMock(
            side_effect=Exception("retry failed")
        )

        response = client.post(
            f"/api/v2/admin/compensation-failures/{saga.id}/retry",
            headers=auth_headers_admin,
        )

        assert response.status_code == 500, response.text


def test_cleanup_compensation(
    client: TestClient,
    db_session: Session,
    auth_headers_admin: dict,
    create_test_patient,
):
    patient = create_test_patient()
    patient.patient_data = {"quarantine": True}
    db_session.add(patient)
    db_session.commit()

    saga = _create_failed_saga(db_session, patient)

    response = client.post(
        f"/api/v2/admin/compensation-failures/{saga.id}/cleanup",
        headers=auth_headers_admin,
    )

    assert response.status_code == 200, response.text
    db_session.refresh(patient)
    db_session.refresh(saga)

    assert patient.deleted_at is not None
    assert not patient.patient_data or patient.patient_data.get("quarantine") is None
    assert saga.status == SagaStatus.CLEANED_UP


def test_unauthorized_access(
    client: TestClient,
    auth_headers_doctor: dict,
):
    response = client.get(
        "/api/v2/admin/compensation-failures", headers=auth_headers_doctor
    )
    assert response.status_code == 403
