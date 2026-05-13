"""M014/S01 duplicate-patient oracle closure tests."""

from __future__ import annotations

import logging
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest

from app.models.patient import FlowState, Patient
from app.models.user import User, UserRole
from app.middleware.csrf import get_csrf_token
from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.utils.security import get_password_hash


DUPLICATE_CODE = "duplicate_patient"
DUPLICATE_MESSAGE = "Duplicate patient"
PROBED_EMAIL = "oracle.patient@example.com"
PROBED_PHONE = "+5511987654321"
PROBED_CPF = "52998224725"
PROBED_NAME = "Maria Oracle Probe"


def _seed_patient(db_session, doctor_id, *, email=PROBED_EMAIL, phone=PROBED_PHONE, cpf=PROBED_CPF, name=PROBED_NAME):
    patient = Patient(
        id=uuid4(),
        name=name,
        doctor_id=doctor_id,
        flow_state=FlowState.ONBOARDING,
    )
    if email is not None:
        patient.set_email(email)
    if phone is not None:
        patient.set_phone(phone)
    if cpf is not None:
        patient.set_cpf(cpf)
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _seed_doctor(db_session):
    doctor = User(
        id=uuid4(),
        email=f"oracle-other-{uuid4().hex}@example.com",
        firebase_uid=f"oracle-other-{uuid4().hex[:24]}",
        hashed_password=get_password_hash("doctorpass123"),
        full_name="Other Oracle Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _payload(test_user, *, email="fresh.oracle@example.com", phone="+5511987654322", cpf="39053344705", name=PROBED_NAME):
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "cpf": cpf,
        "birth_date": "1980-05-15",
        "treatment_type": "Quimioterapia",
        "doctor_id": str(test_user.id),
    }


def _csrf_headers():
    token = get_csrf_token()
    return {"X-CSRF-Token": token, "Cookie": f"csrf_token={token}"}


def _assert_generic_duplicate_response(response, *, forbidden_values):
    assert response.status_code == 409, response.text
    data = response.json()
    assert data["message"] == DUPLICATE_MESSAGE
    assert data["details"] == {"code": DUPLICATE_CODE}
    response_text = response.text.lower()
    assert "cpf" not in response_text
    assert "email" not in response_text
    assert "phone" not in response_text
    for value in forbidden_values:
        if value is not None:
            assert str(value).lower() not in response_text


@pytest.mark.parametrize(
    ("duplicate_field", "payload_overrides"),
    [
        ("cpf", {"cpf": PROBED_CPF, "email": "cpf-probe@example.com", "phone": "+5511987654323"}),
        ("email", {"cpf": "98765432100", "email": PROBED_EMAIL, "phone": "+5511987654324"}),
        ("phone", {"cpf": "11144477735", "email": "phone-probe@example.com", "phone": PROBED_PHONE}),
    ],
)
def test_duplicate_patient_probe_returns_generic_409_before_saga(
    authenticated_client,
    db_session,
    test_user,
    caplog,
    duplicate_field,
    payload_overrides,
):
    _seed_patient(db_session, test_user.id)
    caplog.set_level(logging.INFO)
    execute_saga = AsyncMock()

    with patch.object(
        SagaOrchestrator,
        "execute_patient_onboarding_saga",
        new=execute_saga,
    ):
        response = authenticated_client.post(
            "/api/v2/patients/",
            headers=_csrf_headers(),
            json=_payload(test_user, **payload_overrides),
        )

    execute_saga.assert_not_awaited()
    _assert_generic_duplicate_response(
        response,
        forbidden_values=[PROBED_CPF, PROBED_EMAIL, PROBED_PHONE, PROBED_NAME, duplicate_field],
    )
    assert any(
        getattr(record, "event_type", None) == "patient_duplicate_denied"
        and getattr(record, "reason", None) == DUPLICATE_CODE
        for record in caplog.records
    )
    log_text = caplog.text.lower()
    assert PROBED_EMAIL not in log_text
    assert PROBED_PHONE not in log_text
    assert PROBED_CPF not in log_text
    assert PROBED_NAME.lower() not in log_text


def test_name_like_duplicate_payload_does_not_create_name_oracle(
    authenticated_client,
    db_session,
    test_user,
):
    _seed_patient(db_session, test_user.id)

    with patch.object(
        SagaOrchestrator,
        "execute_patient_onboarding_saga",
        new=AsyncMock(),
    ) as execute_saga:
        response = authenticated_client.post(
            "/api/v2/patients/",
            headers=_csrf_headers(),
            json=_payload(
                test_user,
                name=PROBED_NAME,
                email="name-probe@example.com",
                phone=PROBED_PHONE,
                cpf="15350946056",
            ),
        )

    execute_saga.assert_not_awaited()
    _assert_generic_duplicate_response(
        response,
        forbidden_values=[PROBED_NAME, PROBED_PHONE],
    )


def test_duplicate_values_under_another_doctor_are_not_blocked_by_current_doctor_scope(
    authenticated_client,
    db_session,
    test_user,
):
    other_doctor = _seed_doctor(db_session)
    _seed_patient(db_session, other_doctor.id)
    created_patient = Patient(
        id=uuid4(),
        name="Created Under Current Doctor",
        doctor_id=test_user.id,
        flow_state=FlowState.ONBOARDING,
    )
    created_patient.set_email(PROBED_EMAIL)
    created_patient.set_phone(PROBED_PHONE)
    created_patient.set_cpf(PROBED_CPF)

    async def _create_for_current_doctor(*args, **kwargs):
        db_session.add(created_patient)
        db_session.commit()
        db_session.refresh(created_patient)
        return created_patient

    with patch.object(
        SagaOrchestrator,
        "execute_patient_onboarding_saga",
        new=AsyncMock(side_effect=_create_for_current_doctor),
    ) as execute_saga:
        response = authenticated_client.post(
            "/api/v2/patients/",
            headers=_csrf_headers(),
            json=_payload(
                test_user,
                email=PROBED_EMAIL,
                phone=PROBED_PHONE,
                cpf=PROBED_CPF,
            ),
        )

    assert response.status_code == 201, response.text
    execute_saga.assert_awaited_once()


def test_malformed_email_returns_validation_not_duplicate_oracle(
    authenticated_client,
    db_session,
    test_user,
):
    _seed_patient(db_session, test_user.id)

    with patch.object(
        SagaOrchestrator,
        "execute_patient_onboarding_saga",
        new=AsyncMock(),
    ) as execute_saga:
        response = authenticated_client.post(
            "/api/v2/patients/",
            headers=_csrf_headers(),
            json=_payload(
                test_user,
                email="not-an-email",
                phone=PROBED_PHONE,
                cpf=PROBED_CPF,
            ),
        )

    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"
    assert DUPLICATE_CODE not in response.text
    execute_saga.assert_not_awaited()
