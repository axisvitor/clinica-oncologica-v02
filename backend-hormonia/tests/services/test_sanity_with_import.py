
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.models.patient import Patient
from tests.conftest import create_test_user

from app.utils.timezone import now_sao_paulo
# The suspected side-effect import
from app.tasks.messaging_taskiq import send_scheduled_message

@pytest.mark.asyncio
async def test_sanity_with_import(db_session):
    """
    Sanity check with imports to detect side effects.
    """
    print("Creating doctor (with import)...")
    doctor = create_test_user(db_session, email="sanity_imp_doc@example.com", role="doctor")
    
    patient = Patient(
        id=uuid4(),
        name="Sanity Import Patient",
        doctor_id=doctor.id,
        created_at=now_sao_paulo(),
        updated_at=now_sao_paulo()
    )
    db_session.add(patient)
    db_session.flush()
    
    created = db_session.query(Patient).get(patient.id)
    assert created is not None