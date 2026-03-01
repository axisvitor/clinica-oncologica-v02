
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.models.patient import Patient
from tests.conftest import create_test_user

from app.utils.timezone import now_sao_paulo
@pytest.mark.asyncio
async def test_sanity_create_patient(db_session):
    """
    Minimal sanity check to verify patient creation works with doctor_id.
    """
    print("Creating doctor...")
    doctor = create_test_user(db_session, email="sanity_doc@example.com", role="doctor")
    print(f"Doctor created with ID: {doctor.id}")
    
    patient = Patient(
        id=uuid4(),
        name="Sanity Patient",
        doctor_id=doctor.id,
        created_at=now_sao_paulo(),
        updated_at=now_sao_paulo()
    )
    print(f"Adding patient with doctor_id: {patient.doctor_id}")
    db_session.add(patient)
    db_session.flush()
    print("Patient flushed successfully.")
    
    created = db_session.query(Patient).get(patient.id)
    assert created is not None
    assert created.doctor_id == doctor.id