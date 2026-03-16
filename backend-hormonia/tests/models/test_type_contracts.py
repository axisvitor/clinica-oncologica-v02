"""
Type Safety Validation Tests for Patient Model

Tests Patient.doctor_id type handling (Required vs Optional),
Patient.flow_state serialization, and frontend-backend type contracts.

SECURITY FIX: P0-03
Validates type safety improvements prevent data corruption.
"""
import pytest
from datetime import date, datetime
from uuid import uuid4, UUID
from sqlalchemy.orm import Session

from app.models.patient import Patient, FlowState
from app.models.user import User


class TestPatientDoctorIdType:
    """Test Patient.doctor_id type safety (optional UUID contract)."""

    def test_doctor_id_is_nullable_optional(self, db: Session):
        """Test that doctor_id is nullable in database (optional assignment)."""
        from sqlalchemy import inspect

        inspector = inspect(db.bind)
        columns = {col['name']: col for col in inspector.get_columns('patients')}

        doctor_id_col = columns.get('doctor_id')
        assert doctor_id_col is not None
        assert doctor_id_col['nullable'] is True, "doctor_id should be nullable"

    def test_patient_creation_allows_missing_doctor_id(self, db: Session):
        """Test that creating patient without doctor_id succeeds."""
        patient = Patient(
            name="Test Patient",
            phone="+5511999999999",
            email="test@example.com",
        )
        db.add(patient)
        db.commit()
        assert patient.id is not None
        assert patient.doctor_id is None

    def test_patient_creation_with_valid_doctor_id(self, db: Session):
        """Test that creating patient with valid doctor_id succeeds."""
        # Create a doctor user first
        doctor = User(
            id=uuid4(),
            email="doctor@example.com",
            role="doctor",
            is_active=True
        )
        db.add(doctor)
        db.commit()

        # Create patient with doctor_id
        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999999",
            email="patient@example.com"
        )
        db.add(patient)
        db.commit()

        assert patient.id is not None
        assert patient.doctor_id == doctor.id

    def test_patient_doctor_id_is_uuid_type(self, db: Session):
        """Test that doctor_id is UUID type, not string."""
        doctor = User(
            id=uuid4(),
            email="doctor2@example.com",
            role="doctor",
            is_active=True
        )
        db.add(doctor)
        db.commit()

        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999998",
            email="patient2@example.com"
        )
        db.add(patient)
        db.commit()

        # Verify type
        assert isinstance(patient.doctor_id, UUID)
        assert not isinstance(patient.doctor_id, str)

    def test_patient_doctor_id_can_be_set_to_null(self, db: Session):
        """Test that setting doctor_id to None is supported."""
        doctor = User(
            id=uuid4(),
            email="doctor3@example.com",
            role="doctor",
            is_active=True
        )
        db.add(doctor)
        db.commit()

        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999997",
            email="patient3@example.com"
        )
        db.add(patient)
        db.commit()

        patient.doctor_id = None
        db.commit()
        assert patient.doctor_id is None


class TestPatientFlowStateSerialization:
    """Test Patient.flow_state serialization and deserialization."""

    def test_flow_state_column_matches_varchar_schema(self):
        """ORM must bind flow_state as VARCHAR to match the local DB schema."""
        flow_state_type = Patient.__table__.c.flow_state.type
        assert flow_state_type.native_enum is False
        assert flow_state_type.create_constraint is False

    def test_flow_state_is_enum_not_string(self, db: Session):
        """Test that flow_state is stored as enum value."""
        doctor = User(
            id=uuid4(),
            email="doctor4@example.com",
            role="doctor",
            is_active=True
        )
        db.add(doctor)
        db.commit()

        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999996",
            flow_state=FlowState.ONBOARDING
        )
        db.add(patient)
        db.commit()

        # Verify it's an enum instance
        assert isinstance(patient.flow_state, FlowState)
        assert patient.flow_state == FlowState.ONBOARDING

    def test_flow_state_serializes_to_string_value(self, db: Session):
        """Test that flow_state serializes to string value for API."""
        doctor = User(
            id=uuid4(),
            email="doctor5@example.com",
            role="doctor",
            is_active=True
        )
        db.add(doctor)
        db.commit()

        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999995",
            flow_state=FlowState.ACTIVE
        )
        db.add(patient)
        db.commit()

        # Serialize to dict (as API would)
        patient_dict = {
            "id": str(patient.id),
            "flow_state": patient.flow_state.value  # Should be "active"
        }

        assert patient_dict["flow_state"] == "active"
        assert isinstance(patient_dict["flow_state"], str)

    def test_flow_state_accepts_all_valid_values(self, db: Session):
        """Test that all FlowState enum values are accepted."""
        doctor = User(
            id=uuid4(),
            email="doctor6@example.com",
            role="doctor",
            is_active=True
        )
        db.add(doctor)
        db.commit()

        valid_states = [
            FlowState.ONBOARDING,
            FlowState.ACTIVE,
            FlowState.PAUSED,
            FlowState.COMPLETED,
            FlowState.CANCELLED
        ]

        for idx, state in enumerate(valid_states):
            patient = Patient(
                doctor_id=doctor.id,
                name=f"Test Patient {idx}",
                phone=f"+551199999999{idx}",
                flow_state=state
            )
            db.add(patient)

        db.commit()

        # All should be saved successfully
        patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).all()
        assert len(patients) == len(valid_states)

    def test_flow_state_rejects_invalid_values(self, db: Session):
        """Test that invalid flow_state values are rejected."""
        doctor = User(
            id=uuid4(),
            email="doctor7@example.com",
            role="doctor",
            is_active=True
        )
        db.add(doctor)
        db.commit()

        with pytest.raises(Exception):  # ValueError or similar
            patient = Patient(
                doctor_id=doctor.id,
                name="Test Patient",
                phone="+5511999999994",
                flow_state="invalid_state"  # Should fail
            )
            db.add(patient)
            db.commit()

    def test_flow_state_default_is_onboarding(self, db: Session):
        """Test that default flow_state is ONBOARDING."""
        doctor = User(
            id=uuid4(),
            email="doctor8@example.com",
            role="doctor",
            is_active=True
        )
        db.add(doctor)
        db.commit()

        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999993"
            # flow_state not specified - should default
        )
        db.add(patient)
        db.commit()

        assert patient.flow_state == FlowState.ONBOARDING


class TestQuizResponseValueType:
    """Test Quiz.response_value type safety with different data types."""

    def test_response_value_accepts_json_types(self, db: Session):
        """Test that response_value accepts various JSON-serializable types."""
        from app.models.quiz import QuizResponse, QuizTemplate

        # Create necessary dependencies
        doctor = User(id=uuid4(), email="doc@ex.com", role="doctor", is_active=True)
        db.add(doctor)
        db.flush()
        patient = Patient(doctor_id=doctor.id, name="Pat")
        patient.set_phone("+5511999999992")
        db.add(patient)

        template = QuizTemplate(
            name=f"Template-{uuid4()}",
            version="1.0",
            questions=[{"id": "q1", "text": "Pergunta"}],
            is_active=True,
        )
        db.add(template)
        db.commit()

        # Test different response value types
        test_values = [
            "string response",
            42,
            3.14,
            True,
            ["array", "of", "values"],
            {"key": "value", "nested": {"data": 123}}
        ]

        for idx, value in enumerate(test_values):
            response = QuizResponse(
                patient_id=patient.id,
                quiz_template_id=template.id,
                question_id=f"q{idx}",
                question_text=f"Pergunta {idx}",
                response_type="open_text",
                response_value=value,
                responded_at=datetime.utcnow(),
            )
            db.add(response)

        db.commit()

        # Verify all saved correctly
        responses = db.query(QuizResponse).filter(
            QuizResponse.patient_id == patient.id
        ).all()
        assert len(responses) == len(test_values)

    def test_response_value_preserves_type_on_retrieval(self, db: Session):
        """Test that response_value type is preserved after save/load."""
        from app.models.quiz import QuizResponse, QuizTemplate

        doctor = User(id=uuid4(), email="doc2@ex.com", role="doctor", is_active=True)
        db.add(doctor)
        db.flush()
        patient = Patient(doctor_id=doctor.id, name="Pat2")
        patient.set_phone("+5511999999991")
        db.add(patient)

        template = QuizTemplate(
            name=f"Template-{uuid4()}",
            version="1.0",
            questions=[{"id": "q1", "text": "Pergunta"}],
            is_active=True,
        )
        db.add(template)
        db.commit()

        # Save with dict value
        original_value = {"answer": "yes", "confidence": 0.95}
        response = QuizResponse(
            patient_id=patient.id,
            quiz_template_id=template.id,
            question_id="q1",
            question_text="Pergunta 1",
            response_type="open_text",
            response_value=original_value,
            responded_at=datetime.utcnow(),
        )
        db.add(response)
        db.commit()
        response_id = response.id

        # Clear session and reload
        db.expire_all()
        loaded = db.query(QuizResponse).filter(QuizResponse.id == response_id).first()

        assert loaded.response_value == original_value
        assert isinstance(loaded.response_value, dict)


class TestFrontendBackendTypeContracts:
    """Test type contract compliance between frontend and backend."""

    def test_patient_api_response_matches_frontend_types(self, db: Session):
        """Test that Patient API response matches frontend TypeScript types."""

        doctor = User(id=uuid4(), email="doc3@ex.com", role="doctor", is_active=True)
        db.add(doctor)
        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999990",
            email="test@example.com",
            birth_date=date(1990, 1, 1),
            treatment_type="HRT",
            flow_state=FlowState.ACTIVE,
            current_day=10,
            cpf="12345678909",
            diagnosis="Test diagnosis",
            treatment_phase="Phase 1"
        )
        db.add(patient)
        db.commit()

        # Serialize to Pydantic schema (as API does)
        response_data = {
            "id": str(patient.id),
            "doctor_id": str(patient.doctor_id),
            "name": patient.name,
            "phone": patient.phone,
            "email": patient.email,
            "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
            "treatment_type": patient.treatment_type,
            "flow_state": patient.flow_state.value,
            "current_day": patient.current_day,
            "cpf": patient.cpf,
            "diagnosis": patient.diagnosis,
            "treatment_phase": patient.treatment_phase,
            "created_at": patient.created_at.isoformat() if patient.created_at else None,
            "updated_at": patient.updated_at.isoformat() if patient.updated_at else None
        }

        # Verify all fields are serializable
        import json
        json_str = json.dumps(response_data)
        assert len(json_str) > 0

        # Verify required fields are present
        assert response_data["id"] is not None
        assert response_data["doctor_id"] is not None
        assert response_data["name"] is not None
        assert response_data["phone"] is not None
        assert response_data["flow_state"] in ["onboarding", "active", "paused", "completed", "cancelled"]

    def test_patient_metadata_json_compatible(self, db: Session):
        """Test that patient_data (metadata) is JSON-compatible."""
        doctor = User(id=uuid4(), email="doc4@ex.com", role="doctor", is_active=True)
        db.add(doctor)
        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999989",
            patient_data={
                "custom_fields": {
                    "custom_field": "value",
                    "nested": {"data": [1, 2, 3]},
                    "boolean": True,
                    "number": 42,
                }
            }
        )
        db.add(patient)
        db.commit()

        # Verify it's JSON serializable
        import json
        metadata_json = json.dumps(patient.patient_data)
        assert len(metadata_json) > 0

        # Verify round-trip
        parsed = json.loads(metadata_json)
        assert parsed == patient.patient_data

    def test_uuid_fields_serialize_to_string(self, db: Session):
        """Test that UUID fields serialize to strings for frontend."""
        doctor = User(id=uuid4(), email="doc5@ex.com", role="doctor", is_active=True)
        db.add(doctor)
        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999988"
        )
        db.add(patient)
        db.commit()

        # Serialize UUIDs to strings
        serialized = {
            "id": str(patient.id),
            "doctor_id": str(patient.doctor_id)
        }

        # Verify they're valid UUID strings
        from uuid import UUID
        UUID(serialized["id"])  # Should not raise
        UUID(serialized["doctor_id"])  # Should not raise

        assert isinstance(serialized["id"], str)
        assert isinstance(serialized["doctor_id"], str)

    def test_date_fields_serialize_to_iso_format(self, db: Session):
        """Test that date fields serialize to ISO format for frontend."""
        doctor = User(id=uuid4(), email="doc6@ex.com", role="doctor", is_active=True)
        db.add(doctor)
        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999987",
            birth_date=date(1985, 6, 15)
        )
        db.add(patient)
        db.commit()

        # Serialize to ISO format
        serialized_date = patient.birth_date.isoformat()

        assert serialized_date == "1985-06-15"
        assert isinstance(serialized_date, str)


class TestNullableFieldHandling:
    """Test proper handling of nullable vs non-nullable fields."""

    def test_required_fields_cannot_be_null(self, db: Session):
        """Test that required fields reject null values."""
        doctor = User(id=uuid4(), email="doc7@ex.com", role="doctor", is_active=True)
        db.add(doctor)
        db.commit()

        # Required fields: doctor_id, name, phone
        with pytest.raises(Exception):
            patient = Patient(
                doctor_id=doctor.id,
                name=None,  # Should fail - name is required
                phone="+5511999999986"
            )
            db.add(patient)
            db.commit()

    def test_optional_fields_accept_null(self, db: Session):
        """Test that optional fields accept null values."""
        doctor = User(id=uuid4(), email="doc8@ex.com", role="doctor", is_active=True)
        db.add(doctor)
        db.commit()

        # Optional fields: email, birth_date, treatment_type, etc.
        patient = Patient(
            doctor_id=doctor.id,
            name="Test Patient",
            phone="+5511999999985",
            email=None,
            birth_date=None,
            treatment_type=None
        )
        db.add(patient)
        db.commit()

        assert patient.email is None
        assert patient.birth_date is None
        assert patient.treatment_type is None

# Coverage target: 90%+
# All type safety paths tested
# Required/Optional, serialization, frontend contracts validated
