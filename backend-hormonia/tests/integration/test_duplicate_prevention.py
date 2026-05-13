import time

import pytest

from app.exceptions import ValidationError
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate
from app.services.encryption import get_lgpd_encryption_service
from app.services.patient.integrity_service import PatientIntegrityService


def _build_phone_variants(seed: int) -> tuple[str, str, str]:
    suffix = f"{seed % 100000000:08d}"
    digits = f"11{9}{suffix}"
    formatted = f"(11) 9{suffix[:4]}-{suffix[4:]}"
    e164 = f"+55{digits}"
    return digits, formatted, e164


def _unique_email(seed: int) -> str:
    return f"dup_prevent_{seed}@example.com"


@pytest.mark.integration
def test_duplicate_prevention_blocks_phone_variants(
    real_db_session,
    cleanup_patients,
    real_doctor_id,
):
    seed = int(time.time() * 1000)
    digits, formatted, expected = _build_phone_variants(seed)

    repo = PatientRepository(real_db_session)
    patient = repo.create(
        PatientCreate(
            name=f"Duplicate Base {seed}",
            phone=digits,
            email=_unique_email(seed),
        ).model_dump(exclude_unset=True)
        | {"doctor_id": real_doctor_id}
    )
    cleanup_patients.track(patient.id)

    integrity_service = PatientIntegrityService(real_db_session, repo)

    with pytest.raises(ValidationError) as formatted_exc:
        integrity_service.validate_patient_data(
            patient_data=PatientCreate(
                name=f"Duplicate Formatted {seed}",
                phone=formatted,
                email=_unique_email(seed + 1),
            ),
            doctor_id=real_doctor_id,
            is_update=False,
        )
    assert formatted_exc.value.message == "Duplicate patient"
    assert formatted_exc.value.details == {"code": "duplicate_patient"}
    assert formatted not in str(formatted_exc.value)

    with pytest.raises(ValidationError) as e164_exc:
        integrity_service.validate_patient_data(
            patient_data=PatientCreate(
                name=f"Duplicate E164 {seed}",
                phone=expected,
                email=_unique_email(seed + 2),
            ),
            doctor_id=real_doctor_id,
            is_update=False,
        )
    assert e164_exc.value.message == "Duplicate patient"
    assert e164_exc.value.details == {"code": "duplicate_patient"}
    assert expected not in str(e164_exc.value)

    encryption = get_lgpd_encryption_service()
    phone_hash = encryption.hash_phone(expected)
    count = (
        real_db_session.query(Patient)
        .filter(Patient.phone_hash == phone_hash)
        .count()
    )
    assert count == 1
