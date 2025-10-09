import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.patient import PatientService, PatientIntegrityService
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError
from app.models.patient import Patient

# Mock FlowEngine for service instantiation
class MockFlowEngine:
    def start_flow(self, *args, **kwargs):
        return Mock()

@pytest.fixture
def db_session():
    """Provides a mock SQLAlchemy session."""
    return Mock(spec=Session)

@pytest.fixture
def patient_repository(db_session):
    """Provides a mock PatientRepository."""
    return PatientRepository(db_session)

@pytest.fixture
def patient_integrity_service(db_session, patient_repository):
    """Provides a PatientIntegrityService instance with a mocked repository."""
    return PatientIntegrityService(db=db_session, patient_repository=patient_repository)

@pytest.fixture
def patient_service(db_session, patient_repository, patient_integrity_service):
    """Provides a PatientService instance with mocked dependencies."""
    return PatientService(
        db=db_session,
        patient_repository=patient_repository,
        integrity_service=patient_integrity_service,
        flow_engine=MockFlowEngine()
    )

@pytest.mark.asyncio
async def test_create_patient_with_duplicate_cpf_raises_error(patient_service: PatientService, db_session: Session):
    """
    Test that creating a patient with a duplicate CPF raises a ValidationError.
    This test verifies the fix in `_check_duplicate_cpf`.
    """
    # Arrange
    doctor_id = uuid4()
    cpf = "12345678901"
    patient_data_1 = PatientCreate(
        name="John Doe",
        phone="11999999999",
        cpf=cpf,
        email="john.doe@example.com"
    )
    patient_data_2 = PatientCreate(
        name="Jane Doe",
        phone="11888888888",
        cpf=cpf,
        email="jane.doe@example.com"
    )

    # Mock the database query to simulate an existing patient
    existing_patient = Patient(id=uuid4(), name=patient_data_1.name, cpf=cpf)
    db_session.query(Patient).filter(Patient.cpf == cpf).first.return_value = existing_patient

    # Act & Assert
    with pytest.raises(ValidationError, match=f"Patient with CPF {cpf} already exists"):
        await patient_service.integrity_service.validate_patient_creation(patient_data_2, doctor_id)
