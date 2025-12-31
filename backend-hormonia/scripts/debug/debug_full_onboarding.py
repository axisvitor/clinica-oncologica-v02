"""
Debug script for testing the complete patient lifecycle:
- Patient registration
- Onboarding with Saga orchestration
- Daily flow processing

Uses mocked WhatsApp to avoid actual message sending.
Run from backend-hormonia directory with: python -m scripts.debug.debug_full_onboarding
"""

import asyncio
import sys
import os
from datetime import datetime, date
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Must set environment before imports
os.environ.setdefault("WHATSAPP_ENABLE_SERVICE", "true")


def create_mock_whatsapp():
    """Create a mock WhatsApp service that logs all messages."""
    mock = MagicMock()
    mock.messages_sent = 0
    mock.message_history = []
    
    async def mock_send_message(phone, message, **kwargs):
        mock.messages_sent += 1
        mock.message_history.append({
            "phone": phone,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "kwargs": kwargs
        })
        print(f"  📱 [MOCK WhatsApp] -> {phone}: {message[:100]}...")
        return {"success": True, "message_id": f"mock-{uuid4()}"}
    
    mock.send_message = AsyncMock(side_effect=mock_send_message)
    mock.send_welcome_message = AsyncMock(side_effect=lambda p, **kw: mock_send_message(p.phone, "Bem-vindo ao Neoplasias Litoral!", **kw))
    mock.send_text_message = AsyncMock(side_effect=mock_send_message)
    
    return mock


async def test_patient_registration(db_session, doctor_id: UUID):
    """Test patient registration with saga orchestration."""
    from app.schemas.patient import PatientCreate
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.core.redis_client import get_redis_client
    
    print("\n" + "="*60)
    print("TEST 1: Patient Registration with Saga Orchestration")
    print("="*60)
    
    # Create test patient data
    test_phone = f"+5511999{uuid4().hex[:6]}"
    patient_data = PatientCreate(
        name=f"Debug Test Patient {uuid4().hex[:8]}",
        phone=test_phone,
        cpf=None,
        birth_date=date(1980, 5, 15),
        treatment_type="quimioterapia",
        treatment_phase="initial",
        diagnosis="Câncer de mama",
    )
    
    print(f"\n📋 Creating patient: {patient_data.name}")

    print(f"   Phone: {patient_data.phone}")
    print(f"   Diagnosis: {patient_data.diagnosis}")
    
    # Create mock WhatsApp and patch
    mock_whatsapp = create_mock_whatsapp()
    
    with patch.object(
        SagaOrchestrator, '__init__',
        lambda self, db, redis_client=None, evolution_client=None: None
    ):
        # Create orchestrator manually with mocked services
        orchestrator = object.__new__(SagaOrchestrator)
        orchestrator.db = db_session
        orchestrator.redis = get_redis_client()
        orchestrator.evolution_client = None
        
        # Initialize repositories
        from app.repositories.patient import PatientRepository
        from app.services.patient.flow_service import PatientFlowService
        from app.domain.messaging.core import MessageService
        from app.orchestration.saga_orchestrator.steps import SagaStepExecutor
        from app.orchestration.saga_orchestrator.compensation import SagaCompensator
        from app.orchestration.saga_orchestrator.persistence import SagaPersistence
        
        orchestrator.patient_repo = PatientRepository(db_session)
        orchestrator.flow_service = PatientFlowService(db_session)
        orchestrator.whatsapp_service = mock_whatsapp
        orchestrator.message_service = MessageService(db_session)
        
        orchestrator.step_executor = SagaStepExecutor(
            db=db_session,
            patient_repo=orchestrator.patient_repo,
            flow_service=orchestrator.flow_service,
            whatsapp_service=mock_whatsapp,
            message_service=orchestrator.message_service,
        )
        orchestrator.compensator = SagaCompensator(
            db=db_session,
            patient_repo=orchestrator.patient_repo,
            redis_client=orchestrator.redis,
        )
        orchestrator.persistence = SagaPersistence(db_session)
        
        # Execute saga
        try:
            patient = await orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor_id,
                idempotency_key=f"debug-test-{uuid4()}",
            )
            
            if patient:
                print(f"\n✅ Patient created successfully!")
                print(f"   ID: {patient.id}")
                print(f"   Name: {patient.full_name}")
                print(f"   Phone: {patient.phone}")
                print(f"   Status: {patient.status}")
                print(f"\n📊 WhatsApp Messages Sent: {mock_whatsapp.messages_sent}")
                for msg in mock_whatsapp.message_history:
                    print(f"   - {msg['phone']}: {msg['message'][:50]}...")
                return patient
            else:
                print("\n❌ Patient creation failed (returned None)")
                return None
                
        except Exception as e:
            print(f"\n❌ Error during saga: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None


async def test_daily_flows(db_session, patient_id: UUID):
    """Test daily flow processing for a patient."""
    from app.services.enhanced_flow_engine import EnhancedFlowEngine
    from app.models.patient import Patient
    from app.models.patient_flow_state import FlowState
    
    print("\n" + "="*60)
    print("TEST 2: Daily Flow Processing")
    print("="*60)
    
    # Get patient
    patient = db_session.query(Patient).get(patient_id)
    if not patient:
        print(f"\n❌ Patient {patient_id} not found")
        return
    
    print(f"\n📋 Processing flows for: {patient.full_name}")
    
    # Check flow state
    flow_state = db_session.query(FlowState).filter(
        FlowState.patient_id == patient_id
    ).first()
    
    if flow_state:
        print(f"   Current Day: {flow_state.current_day}")
        print(f"   Flow Type: {flow_state.flow_type}")
        print(f"   Status: {flow_state.status}")
    else:
        print("   ⚠️ No flow state found - initializing...")
    
    # Create mock WhatsApp
    mock_whatsapp = create_mock_whatsapp()
    
    # Patch WhatsApp service and process
    with patch('app.services.enhanced_flow_engine.UnifiedWhatsAppService', return_value=mock_whatsapp), \
         patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService.send_message', mock_whatsapp.send_message):
        
        try:
            engine = EnhancedFlowEngine(db_session)
            engine.whatsapp_service = mock_whatsapp
            
            result = await engine.process_patient_flow(patient)
            
            print(f"\n✅ Flow processed:")
            print(f"   Result: {result}")
            print(f"\n📊 WhatsApp Messages Sent: {mock_whatsapp.messages_sent}")
            for msg in mock_whatsapp.message_history:
                print(f"   - {msg['phone']}: {msg['message'][:50]}...")
                
        except Exception as e:
            print(f"\n❌ Error processing flow: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()


async def get_or_create_test_doctor(db_session):
    """Get existing doctor or create test one."""
    from app.models.user import User, UserRole
    
    # Try to find existing doctor
    doctor = db_session.query(User).filter(
        User.role == UserRole.DOCTOR
    ).first()
    
    if doctor:
        print(f"✅ Using existing doctor: {doctor.email} (ID: {doctor.id})")
        return doctor.id
    
    # Create test doctor
    doctor_id = uuid4()
    doctor = User(
        id=doctor_id,
        email=f"debug-doctor-{uuid4().hex[:8]}@test.local",
        full_name="Debug Test Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    print(f"✅ Created test doctor: {doctor.email} (ID: {doctor.id})")
    return doctor.id


async def main():
    """Main debug function."""
    print("\n" + "="*60)
    print(" DEBUG: Patient Registration, Onboarding, Saga & Daily Flows")
    print("="*60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Import database session
    from app.database import SessionLocal
    
    db_session = SessionLocal()
    
    try:
        # Step 0: Get test doctor
        print("\n" + "-"*40)
        print("SETUP: Getting test doctor")
        print("-"*40)
        doctor_id = await get_or_create_test_doctor(db_session)
        
        # Step 1: Test patient registration with saga
        patient = await test_patient_registration(db_session, doctor_id)
        
        if patient:
            # Step 2: Test daily flows
            await test_daily_flows(db_session, patient.id)
        
        print("\n" + "="*60)
        print(" DEBUG COMPLETE")
        print("="*60)
        print(f"Finished at: {datetime.now().isoformat()}")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db_session.close()


if __name__ == "__main__":
    asyncio.run(main())
