import os
from contextlib import asynccontextmanager

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4, UUID
from datetime import datetime

os.environ.setdefault("MONTHLY_QUIZ_TOKEN_SECRET", "test-secret-key-for-testing")

from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.models.patient_onboarding_saga import SagaStatus, PatientOnboardingSaga
from app.schemas.patient import PatientCreate
from app.models.patient import Patient
from app.models.message import Message


@asynccontextmanager
async def _noop_acquire_lock(*args, **kwargs):
    yield "test-lock-id"

@pytest.fixture
def mock_db():
    db = MagicMock()
    # Mock add and commit
    db.add = MagicMock()
    db.commit = MagicMock()
    db.query = MagicMock()
    return db

@pytest.fixture
def mock_redis():
    return MagicMock()

@pytest.fixture
def mock_evolution():
    return MagicMock()

@pytest.fixture
def saga_orchestrator(mock_db, mock_redis, mock_evolution):
    # Patch dependencies within the class initialization or use mocks passed to constructor
    # The constructor takes db, redis, evolution.
    # It instantiates services internally: PatientRepository, PatientFlowService, UnifiedWhatsAppService, MessageService
    # We need to patch these internal services.
    
    with patch('app.orchestration.saga_orchestrator.acquire_lock', _noop_acquire_lock), \
         patch('app.orchestration.saga_orchestrator.PatientRepository') as MockRepo, \
         patch('app.orchestration.saga_orchestrator.PatientFlowService') as MockFlowService, \
         patch('app.orchestration.saga_orchestrator.UnifiedWhatsAppService') as MockWhatsApp, \
         patch('app.orchestration.saga_orchestrator.MessageService') as MockMessageService:
         
        orchestrator = SagaOrchestrator(mock_db, mock_redis, mock_evolution)
        
        # Attach mocks to the instance for configuration in tests
        orchestrator.mock_patient_repo = MockRepo.return_value
        orchestrator.mock_flow_service = MockFlowService.return_value
        orchestrator.mock_whatsapp_service = MockWhatsApp.return_value
        orchestrator.mock_message_service = MockMessageService.return_value
        
        yield orchestrator

@pytest.mark.asyncio
async def test_execute_patient_onboarding_saga_success(saga_orchestrator, mock_db):
    # Setup
    doctor_id = uuid4()
    patient_data = PatientCreate(
        name="Test Patient",
        phone="+5511999999999",
        email="test@example.com"
    )
    
    # Mock Patient Creation
    created_patient = Patient(
        id=uuid4(), 
        name=patient_data.name, 
        doctor_id=doctor_id
    )
    saga_orchestrator.mock_patient_repo.create.return_value = created_patient
    
    # Mock Flow Initialization
    saga_orchestrator.mock_flow_service.initialize_default_flow = AsyncMock()
    saga_orchestrator.mock_flow_service.activate_patient = AsyncMock()
    
    # Mock WhatsApp
    saga_orchestrator.mock_whatsapp_service.send_message = AsyncMock(return_value=True)
    
    # Execute
    result = await saga_orchestrator.execute_patient_onboarding_saga(patient_data, doctor_id)
    
    # Assertions
    assert result == created_patient
    
    # Verify DB interactions (Saga creation and updates)
    assert mock_db.add.call_count >= 1 # Saga creation (and Message creation)
    assert mock_db.commit.call_count >= 1
    
    # Verify Saga Record State (We can't check the exact object instance easily unless we capture it)
    # But we can verify add was called with a Saga object
    saga_args = [args[0] for args, _ in mock_db.add.call_args_list if isinstance(args[0], PatientOnboardingSaga)]
    assert len(saga_args) > 0
    saga = saga_args[0]
    assert saga.status == SagaStatus.COMPLETED
    assert saga.current_step == 4

@pytest.mark.asyncio
async def test_execute_patient_onboarding_saga_failure_and_compensation(saga_orchestrator, mock_db):
    # Setup
    doctor_id = uuid4()
    patient_data = PatientCreate(
        name="Test Patient",
        phone="+5511999999999"
    )
    
    # Mock Patient Creation (Success)
    created_patient = Patient(id=uuid4(), name=patient_data.name, doctor_id=doctor_id)
    saga_orchestrator.mock_patient_repo.create.return_value = created_patient
    
    # Mock Flow (Success)
    saga_orchestrator.mock_flow_service.initialize_default_flow = AsyncMock()
    saga_orchestrator.mock_flow_service.activate_patient = AsyncMock()
    
    # Mock WhatsApp (Failure)
    saga_orchestrator.mock_whatsapp_service.send_message = AsyncMock(return_value=False) # Fails
    
    # Execute
    result = await saga_orchestrator.execute_patient_onboarding_saga(patient_data, doctor_id)
    
    # Assertions
    # Welcome sending is best-effort; saga should still complete and return patient
    assert result == created_patient
    saga_orchestrator.mock_patient_repo.delete.assert_not_called()
    
    # Verify Saga State
    saga_args = [args[0] for args, _ in mock_db.add.call_args_list if isinstance(args[0], PatientOnboardingSaga)]
    assert len(saga_args) > 0
    saga = saga_args[0]
    assert saga.status == SagaStatus.COMPLETED

@pytest.mark.asyncio
async def test_resume_saga_completed(saga_orchestrator, mock_db):
    # Setup
    saga_id = uuid4()
    mock_saga = PatientOnboardingSaga(id=saga_id, status=SagaStatus.COMPLETED)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_saga
    
    # Execute
    result = await saga_orchestrator.resume_saga(saga_id)
    
    # Assertions
    assert result["status"] == "completed"
    assert result["message"] == "Saga already completed"

@pytest.mark.asyncio
async def test_resume_saga_from_step_1(saga_orchestrator, mock_db):
    # Setup: Saga failed after creating patient (step 1), needs to do flow (step 3) and message (step 4)
    saga_id = uuid4()
    patient_id = uuid4()
    doctor_id = uuid4()
    
    mock_saga = PatientOnboardingSaga(
        id=saga_id, 
        status=SagaStatus.FAILED, 
        current_step=1,
        patient_id=patient_id,
        doctor_id=doctor_id,
        patient_data={"name": "Resumed Patient", "phone": "+123"}
    )
    mock_db.query.return_value.filter.return_value.first.return_value = mock_saga
    
    # Mock Repo to return patient
    mock_patient = Patient(id=patient_id, name="Resumed Patient", doctor_id=doctor_id)
    saga_orchestrator.mock_patient_repo.get_by_id.return_value = mock_patient
    
    # Mock Services
    saga_orchestrator.mock_flow_service.initialize_default_flow = AsyncMock()
    saga_orchestrator.mock_flow_service.activate_patient = AsyncMock()
    saga_orchestrator.mock_whatsapp_service.send_message = AsyncMock(return_value=True)
    
    # Execute
    result = await saga_orchestrator.resume_saga(saga_id)
    
    # Assertions
    assert result["status"] == "completed"
    assert mock_saga.status == SagaStatus.COMPLETED
    
    # Verify steps executed
    assert saga_orchestrator.mock_flow_service.initialize_default_flow.called
    assert saga_orchestrator.mock_whatsapp_service.send_message.called
