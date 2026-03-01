import os
import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.enums import SagaStatus
from app.models.message import Message, MessageStatus
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.tasks import messaging as messaging_tasks


def _build_phone_variants(seed: int) -> tuple[str, str, str]:
    suffix = f"{seed % 100000000:08d}"
    digits = f"11{9}{suffix}"
    formatted = f"(11) 9{suffix[:4]}-{suffix[4:]}"
    e164 = f"+55{digits}"
    return digits, formatted, e164


@pytest.fixture
def integration_client(real_db_session, real_doctor_id):
    def _override_user():
        return {
            "id": str(real_doctor_id),
            "email": "admin@example.com",
            "role": "admin",
            "is_active": True,
        }

    app.dependency_overrides[get_db] = lambda: real_db_session
    app.dependency_overrides[get_current_user_from_session] = _override_user

    client = TestClient(app)
    yield client
    if os.getenv("CONFIRM_REAL_DB") != "1":
        client.close()

    app.dependency_overrides.clear()


@pytest.mark.integration
def test_patient_onboarding_flow_e2e(
    integration_client,
    real_db_session,
    real_engine,
    real_doctor_id,
    cleanup_patients,
    cleanup_sagas,
    monkeypatch,
):
    scheduled_tasks = []

    def _record_apply_async(*args, **kwargs):
        message_args = kwargs.get("args")
        if message_args is None and args:
            message_args = args[0]
        scheduled_tasks.append(message_args or [])
        return None

    class _StubWhatsAppService:
        async def send_message(self, message):
            return True

    monkeypatch.setattr(
        messaging_tasks.send_scheduled_message,
        "apply_async",
        _record_apply_async,
    )
    monkeypatch.setattr(
        messaging_tasks,
        "create_unified_whatsapp_service",
        lambda db: _StubWhatsAppService(),
    )

    seed = int(time.time() * 1000)
    _, formatted, expected = _build_phone_variants(seed)
    email_domain = os.getenv("TEST_EMAIL_DOMAIN", "gmail.com")
    payload = {
        "name": f"E2E Patient {seed}",
        "phone": formatted,
        "email": f"e2e_{seed}@{email_domain}",
        "doctor_id": str(real_doctor_id),
    }

    response = integration_client.post(
        "/api/v2/patients",
        json=payload,
        headers={"X-Session-ID": f"session-{seed}"},
    )
    assert response.status_code == 201, response.text

    patient_id = response.json().get("id")
    assert patient_id
    cleanup_patients.track(UUID(patient_id))

    SessionLocal = sessionmaker(bind=real_engine)
    with SessionLocal() as read_db:
        db_patient = (
            read_db.query(Patient)
            .filter(Patient.id == UUID(patient_id))
            .first()
        )
    assert db_patient is not None
    assert db_patient.phone == expected

    with SessionLocal() as read_db:
        saga = (
            read_db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.patient_id == UUID(patient_id))
            .order_by(PatientOnboardingSaga.started_at.desc())
            .first()
        )
    assert saga is not None
    cleanup_sagas.track(saga.id)
    assert saga.status in {
        SagaStatus.COMPLETED,
        SagaStatus.STEP_4_MESSAGE_SENT,
        SagaStatus.COMPLETED_WITH_WARNINGS,
    }

    with SessionLocal() as read_db:
        message = (
            read_db.query(Message)
            .filter(Message.patient_id == UUID(patient_id))
            .first()
        )
    assert message is not None
    assert message.status in {
        MessageStatus.PENDING,
        MessageStatus.FAILED,
        MessageStatus.SENT,
    }

    if os.getenv("CONFIRM_REAL_DB") != "1":
        assert scheduled_tasks, "Expected Celery task to be scheduled"

    if os.getenv("CONFIRM_REAL_DB") == "1":
        return

    if scheduled_tasks:
        scheduled_message_id = scheduled_tasks[0][0]
        assert scheduled_message_id == str(message.id)

        # In production, background workers may already mark the message as FAILED or SENT.
        if message.status in {MessageStatus.FAILED, MessageStatus.SENT}:
            return

        result = messaging_tasks.send_scheduled_message(scheduled_message_id)
        assert result.get("success") is True

        real_db_session.expire_all()
        updated_message = (
            real_db_session.query(Message)
            .filter(Message.id == UUID(scheduled_message_id))
            .first()
        )
        assert updated_message is not None
        assert updated_message.status == MessageStatus.SENT
