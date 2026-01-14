import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

os.environ.setdefault("MONTHLY_QUIZ_TOKEN_SECRET", "test-secret-key-for-testing")

from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.schemas.patient import PatientCreate
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.message import Message
from app.models.template import MessageTemplate
from app.orchestration.saga_orchestrator.steps import SagaStepExecutor
from app.orchestration.saga_orchestrator.compensation import SagaCompensator


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
    
    with patch('app.orchestration.saga_orchestrator.orchestrator.acquire_lock', _noop_acquire_lock), \
         patch('app.orchestration.saga_orchestrator.orchestrator.PatientRepository') as MockRepo, \
         patch('app.orchestration.saga_orchestrator.orchestrator.PatientFlowService') as MockFlowService, \
         patch('app.orchestration.saga_orchestrator.orchestrator.UnifiedWhatsAppService') as MockWhatsApp, \
         patch('app.orchestration.saga_orchestrator.orchestrator.MessageService') as MockMessageService, \
         patch('app.tasks.messaging.send_scheduled_message') as MockSendTask:
         
        orchestrator = SagaOrchestrator(mock_db, mock_redis, mock_evolution)
        
        # Attach mocks to the instance for configuration in tests
        orchestrator.mock_patient_repo = MockRepo.return_value
        orchestrator.mock_flow_service = MockFlowService.return_value
        orchestrator.mock_whatsapp_service = MockWhatsApp.return_value
        orchestrator.mock_message_service = MockMessageService.return_value
        orchestrator.mock_send_task = MockSendTask
        
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
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_saga,  # Saga lookup
        None,       # No existing flow
    ]
    
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
    def query_side_effect(model):
        query = MagicMock()
        if model is PatientOnboardingSaga:
            query.filter.return_value.first.return_value = mock_saga
        elif model is PatientFlowState:
            query.filter.return_value.first.return_value = None
        elif model is MessageTemplate:
            query.filter.return_value.first.return_value = None
        else:
            query.filter.return_value.first.return_value = None
        return query

    mock_db.query.side_effect = query_side_effect
    
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


@pytest.mark.asyncio
async def test_compensation_failure_sends_notification():
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.flush = MagicMock()

    saga_id = uuid4()
    patient_id = uuid4()
    saga = PatientOnboardingSaga(
        id=saga_id,
        patient_id=patient_id,
        status=SagaStatus.FAILED,
        patient_data={"name": "Test Patient"},
    )
    patient = MagicMock()
    patient.id = patient_id
    patient.patient_data = {}

    def query_side_effect(model):
        query = MagicMock()
        if model is PatientOnboardingSaga:
            query.filter.return_value.first.return_value = saga
        elif model is Patient:
            query.filter.return_value.first.return_value = patient
        return query

    mock_db.query.side_effect = query_side_effect

    compensator = SagaCompensator(
        db=mock_db, patient_repo=MagicMock(), redis_client=None
    )

    notification_service = MagicMock()
    notification_service.send_alert = AsyncMock()

    with patch(
        "app.services.notification_service.get_notification_service",
        return_value=notification_service,
    ), patch(
        "sqlalchemy.orm.attributes.flag_modified",
        MagicMock(),
    ), patch(
        "app.core.monitoring_config.capture_message", MagicMock()
    ), patch(
        "app.core.monitoring_config.capture_exception", MagicMock()
    ):
        await compensator._track_compensation_failure(
            saga_id, 1, Exception("compensation error")
        )

    notification_service.send_alert.assert_called_once()
    assert mock_saga.status == SagaStatus.COMPLETED
    
    # Verify steps executed
    assert saga_orchestrator.mock_flow_service.initialize_default_flow.called
    assert saga_orchestrator.mock_message_service.schedule_message.called
    assert saga_orchestrator.mock_send_task.apply_async.called


@pytest.mark.asyncio
async def test_resume_saga_skips_duplicate_welcome_message():
    """
    Verification Comment 1: Resume saga should not enqueue duplicate welcome message
    when one already exists for the saga.
    
    This test validates the idempotent check added to _resume_saga_internal that
    queries for existing messages before sending welcome message.
    """
    # Setup with pure mocks to avoid SQLAlchemy relationship issues
    saga_id = uuid4()
    patient_id = uuid4()
    doctor_id = uuid4()
    
    mock_db = MagicMock()
    mock_redis = MagicMock()
    
    # Mock saga
    mock_saga = MagicMock()
    mock_saga.id = saga_id
    mock_saga.status = SagaStatus.FAILED
    mock_saga.current_step = 3  # At step 3, needs to send welcome message
    mock_saga.patient_id = patient_id
    mock_saga.doctor_id = doctor_id
    mock_saga.patient_data = {"name": "Test Patient", "phone": "+5511999999999"}
    mock_saga.execution_log = []
    mock_saga.add_log_entry = MagicMock(side_effect=lambda *args: mock_saga.execution_log.append(
        {"step": args[0], "action": args[1], "status": args[2]}
    ))
    
    # Mock patient
    mock_patient = MagicMock()
    mock_patient.id = patient_id
    mock_patient.name = "Test Patient"
    
    # Mock existing message (already sent)
    mock_existing_message = MagicMock()
    mock_existing_message.id = uuid4()
    
    # Setup query side effects
    message_query = MagicMock()
    message_query.filter.return_value.first.return_value = mock_existing_message
    
    def query_side_effect(model):
        if hasattr(model, '__name__') and model.__name__ == "Message":
            return message_query
        query = MagicMock()
        query.filter.return_value.first.return_value = None
        return query
    
    mock_db.query.side_effect = query_side_effect
    mock_db.flush = MagicMock()
    mock_db.commit = MagicMock()
    
    # Create orchestrator with patches
    with patch('app.orchestration.saga_orchestrator.orchestrator.acquire_lock', _noop_acquire_lock), \
         patch('app.orchestration.saga_orchestrator.orchestrator.PatientRepository') as MockRepo, \
         patch('app.orchestration.saga_orchestrator.orchestrator.PatientFlowService') as MockFlowService, \
         patch('app.orchestration.saga_orchestrator.orchestrator.UnifiedWhatsAppService') as MockWhatsApp, \
         patch('app.orchestration.saga_orchestrator.orchestrator.MessageService') as MockMessageService:
        
        from app.orchestration.saga_orchestrator import SagaOrchestrator
        
        orchestrator = SagaOrchestrator(mock_db, mock_redis, None)
        
        # Setup patient repo mock
        MockRepo.return_value.get_by_id.return_value = mock_patient
        
        # Execute internal resume logic
        result = await orchestrator._resume_saga_internal(mock_saga)
        
        # Assertions
        assert result["status"] == "completed"
        
        # Verify add_log_entry was called with skipped_existing_message
        found_skip = False
        for entry in mock_saga.execution_log:
            if entry.get("status") == "skipped_existing_message":
                found_skip = True
                break
        assert found_skip, f"Expected skipped_existing_message in log, got: {mock_saga.execution_log}"
        
        # Verify step was updated
        assert mock_saga.current_step == 4
        
        # Verify no message was scheduled (step_send_welcome_message not called)
        # This is implicit - if message was scheduled, add_log_entry would be called with 'send_message'


@pytest.mark.asyncio
async def test_step_initialize_flow_skips_when_idempotency_flow_exists():
    mock_db = MagicMock()
    mock_db.flush = MagicMock()

    existing_flow = MagicMock()
    flow_query = MagicMock()
    flow_query.filter.return_value.first.return_value = existing_flow

    def query_side_effect(model):
        if model is PatientFlowState:
            return flow_query
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    flow_service = MagicMock()
    flow_service.initialize_default_flow = AsyncMock()
    flow_service.activate_patient = AsyncMock()

    executor = SagaStepExecutor(
        db=mock_db,
        patient_repo=MagicMock(),
        flow_service=flow_service,
        whatsapp_service=MagicMock(),
        message_service=MagicMock(),
    )

    saga = PatientOnboardingSaga(
        id=uuid4(),
        patient_data={},
        status=SagaStatus.STARTED,
        current_step=0,
        started_at=datetime.now(timezone.utc),
    )
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="+5511999999999",
        doctor_id=uuid4(),
    )

    await executor.step_initialize_flow(
        saga, patient, None, idempotency_key="idemp-1"
    )

    flow_service.initialize_default_flow.assert_not_called()
    flow_service.activate_patient.assert_not_called()
    assert saga.current_step == 3
    assert saga.status == SagaStatus.STEP_3_FLOW_INITIALIZED
    assert any(
        entry.get("status") == "skipped_existing_flow"
        for entry in saga.execution_log
    )


@pytest.mark.asyncio
async def test_step_send_welcome_message_skips_when_idempotency_message_exists():
    mock_db = MagicMock()
    mock_db.flush = MagicMock()

    template_query = MagicMock()
    template_query.filter.return_value.first.return_value = None

    existing_message = MagicMock()
    existing_message.id = uuid4()
    message_query = MagicMock()
    message_query.filter.return_value.first.return_value = existing_message

    def query_side_effect(model):
        if model is MessageTemplate:
            return template_query
        if model is Message:
            return message_query
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    message_service = MagicMock()
    message_service.schedule_message = MagicMock()

    executor = SagaStepExecutor(
        db=mock_db,
        patient_repo=MagicMock(),
        flow_service=MagicMock(),
        whatsapp_service=MagicMock(),
        message_service=message_service,
    )

    saga = PatientOnboardingSaga(
        id=uuid4(),
        patient_data={},
        status=SagaStatus.STARTED,
        current_step=0,
        started_at=datetime.now(timezone.utc),
    )
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="+5511999999999",
        doctor_id=uuid4(),
    )

    await executor.step_send_welcome_message(
        saga, patient, idempotency_key="idemp-1"
    )

    message_service.schedule_message.assert_not_called()
    assert saga.current_step == 4
    assert saga.status == SagaStatus.STEP_4_MESSAGE_SENT
    assert any(
        entry.get("status") == "skipped_existing_message"
        for entry in saga.execution_log
    )


@pytest.mark.asyncio
async def test_step_send_welcome_message_includes_idempotency_key():
    mock_db = MagicMock()
    mock_db.flush = MagicMock()

    template_query = MagicMock()
    template_query.filter.return_value.first.return_value = None

    message_query = MagicMock()
    message_query.filter.return_value.first.return_value = None

    def query_side_effect(model):
        if model is MessageTemplate:
            return template_query
        if model is Message:
            return message_query
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    scheduled_message = MagicMock()
    scheduled_message.id = uuid4()
    message_service = MagicMock()
    message_service.schedule_message = MagicMock(return_value=scheduled_message)

    executor = SagaStepExecutor(
        db=mock_db,
        patient_repo=MagicMock(),
        flow_service=MagicMock(),
        whatsapp_service=MagicMock(),
        message_service=message_service,
    )

    saga = PatientOnboardingSaga(
        id=uuid4(),
        patient_data={},
        status=SagaStatus.STARTED,
        current_step=0,
        started_at=datetime.now(timezone.utc),
    )
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="+5511999999999",
        doctor_id=uuid4(),
    )

    with patch("app.tasks.messaging.send_scheduled_message") as mock_task:
        mock_task.apply_async = MagicMock()
        await executor.step_send_welcome_message(
            saga, patient, idempotency_key="idemp-1"
        )

    call_kwargs = message_service.schedule_message.call_args.kwargs
    assert call_kwargs["message_metadata"]["idempotency_key"] == "idemp-1"
    mock_task.apply_async.assert_called_once()





@pytest.mark.asyncio
async def test_compensation_failure_creates_alert_and_quarantines_patient():
    """
    Verification Comment 2: Compensation failure should create Alert record
    with HIGH severity and quarantine the patient.
    """
    from app.orchestration.saga_orchestrator.compensation import SagaCompensator
    from app.models.alert import Alert, AlertSeverity
    
    # Setup
    saga_id = uuid4()
    patient_id = uuid4()
    
    mock_db = MagicMock()
    mock_redis = MagicMock()
    
    # Mock saga with patient_id
    mock_saga = MagicMock()
    mock_saga.id = saga_id
    mock_saga.patient_id = patient_id
    
    # Mock patient
    mock_patient = MagicMock()
    mock_patient.id = patient_id
    mock_patient.patient_data = {}
    
    def query_side_effect(model):
        query = MagicMock()
        if model.__name__ == "PatientOnboardingSaga":
            query.filter.return_value.first.return_value = mock_saga
        elif model.__name__ == "Patient":
            query.filter.return_value.first.return_value = mock_patient
        else:
            query.filter.return_value.first.return_value = None
        return query
    
    mock_db.query.side_effect = query_side_effect
    
    with patch('app.orchestration.saga_orchestrator.compensation.PatientRepository'):
        compensator = SagaCompensator(
            db=mock_db,
            patient_repo=MagicMock(),
            redis_client=mock_redis,
        )
    
    notification_service = MagicMock()
    notification_service.send_alert = AsyncMock()

    # Patch monitoring/notifications to avoid real calls
    with patch(
        "app.services.notification_service.get_notification_service",
        return_value=notification_service,
    ), patch(
        'app.core.monitoring_config.capture_message'
    ), patch(
        "sqlalchemy.orm.attributes.flag_modified", MagicMock()
    ):
        # Execute
        test_error = Exception("Test compensation failure")
        await compensator._track_compensation_failure(saga_id, 2, test_error)
    
    # Assertions
    # Verify Alert was created
    add_calls = mock_db.add.call_args_list
    alert_calls = [
        call for call in add_calls 
        if hasattr(call[0][0], 'alert_type')
    ]
    assert len(alert_calls) >= 1
    created_alert = alert_calls[0][0][0]
    assert created_alert.alert_type == "SAGA_COMPENSATION_FAILURE"
    assert created_alert.severity == AlertSeverity.HIGH
    assert created_alert.patient_id == patient_id
    
    # Verify patient was quarantined
    assert mock_patient.patient_data.get("quarantine") is True
    assert (
        mock_patient.patient_data.get("quarantine_reason")
        == "saga_compensation_failure"
    )
    assert "quarantine_at" in mock_patient.patient_data
    
    # Verify Redis tracking
    mock_redis.setex.assert_called_once()
    
    # Verify flush was called
    mock_db.flush.assert_called()
