from uuid import uuid4

import pytest

from app.models.patient import Patient


def test_patient_accepts_canonical_name_payload():
    patient = Patient(id=uuid4(), name="Paciente Canonico")
    assert patient.name == "Paciente Canonico"


def test_patient_rejects_legacy_first_last_name_payload():
    with pytest.raises(TypeError):
        Patient(id=uuid4(), first_name="Paciente", last_name="Legado")


def test_patient_rejects_legacy_full_name_payload():
    with pytest.raises(TypeError):
        Patient(id=uuid4(), full_name="Paciente Legado")
