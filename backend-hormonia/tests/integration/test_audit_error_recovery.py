import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.schemas.patient import PatientCreate
from app.models.patient import Patient
from app.models.enums import SagaStatus
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.database import Base
import uuid

@pytest.fixture(autouse=True)
def setup_tables(db_session: Session):
    """Ensure all tables exist in the test database."""
    Base.metadata.create_all(bind=db_session.bind)
    yield

@pytest.mark.integration
class TestErrorRecoveryAudit:
    """
    Audit verification tests for cross-service integration and error recovery.
    Verifies Saga compensation and circuit breaker behavior.
    """

    @pytest.mark.asyncio
    async def test_patient_onboarding_saga_compensation(self, db_session: Session):
        """
        Verify that saga correctly compensates (rolls back) when a step fails.
        Scenario: Patient created, Flow initialized, but Message sending fails.
        Result: Patient record and Flow should be deleted by compensation.
        """
        # 1. Setup doctor
        from app.models.user import User
        doctor = User(
            id=uuid.uuid4(),
            email=f"saga_doc_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Saga Doctor",
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()
        doctor_id = doctor.id

        # 2. Initialize orchestrator
        orchestrator = SagaOrchestrator(db_session)
        
        # 3. Mock WhatsApp service to fail
        # Step 3 is _step_send_welcome_message
        with patch.object(orchestrator.whatsapp_service, "send_message", side_effect=Exception("WhatsApp service down")):
            
            patient_data = PatientCreate(
                name="Saga Fail Patient",
                phone="+5511999990000",
                email="saga@example.com",
                doctor_id=doctor_id
            )
            
            # 4. Execute saga - it should return None due to failure
            patient = await orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor_id
            )
            
            assert patient is None
            
            # 5. Verify compensation
            # The patient should have been deleted
            db_session.expire_all()
            deleted_patient = db_session.query(Patient).filter(Patient.name == "Saga Fail Patient").first()
            assert deleted_patient is None
            
            # Verify saga record exists with FAILED status
            saga = db_session.query(PatientOnboardingSaga).filter(
                PatientOnboardingSaga.doctor_id == doctor_id
            ).first()
            assert saga is not None
            assert saga.status == SagaStatus.FAILED
            assert "WhatsApp service down" in saga.error_message

    @pytest.mark.asyncio
    async def test_circuit_breaker_opening(self):
        """Verify that CircuitBreaker opens after multiple failures."""
        from app.core.circuit_breaker import CircuitBreaker, CircuitState
        
        breaker = CircuitBreaker(
            name="TestBreaker",
            failure_threshold=2,
            recovery_timeout=1.0
        )
        
        async def failing_func():
            raise Exception("Service Error")
            
        # 1. First failure - remains CLOSED
        await breaker.call(failing_func, fallback="fallback")
        assert breaker.state == CircuitState.CLOSED
        
        # 2. Second failure - transitions to OPEN
        await breaker.call(failing_func, fallback="fallback")
        assert breaker.state == CircuitState.OPEN
        
        # 3. Third call - fast fail without executing func
        mock_func = MagicMock()
        result = await breaker.call(mock_func, fallback="fast-fail")
        assert result == "fast-fail"
        mock_func.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Verify that CircuitBreaker recovers from OPEN to HALF_OPEN to CLOSED."""
        from app.core.circuit_breaker import CircuitBreaker, CircuitState
        
        breaker = CircuitBreaker(
            name="RecoveryBreaker",
            failure_threshold=1,
            recovery_timeout=0.1 # Short timeout for test
        )
        
        async def failing_func():
            raise Exception("Error")
            
        # 1. Open the circuit
        await breaker.call(failing_func, fallback="f")
        assert breaker.state == CircuitState.OPEN
        
        # 2. Wait for recovery timeout
        import asyncio
        await asyncio.sleep(0.2)
        
        # 3. Call should transition to HALF_OPEN then CLOSED on success
        async def success_func():
            return "success"
            
        result = await breaker.call(success_func, fallback="f")
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
