"""
Simple debug script for testing patient onboarding saga with mocked WhatsApp.
Run from backend-hormonia directory: venv\Scripts\python.exe -m scripts.debug.simple_saga_test
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, date
from uuid import uuid4
from unittest.mock import patch

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class MockWhatsAppService:
    """Mock WhatsApp service that logs all messages."""
    
    def __init__(self):
        self.messages_sent = 0
        self.message_history = []
        
    async def send_message(self, message):
        """Mock send_message that always succeeds."""
        self.messages_sent += 1
        msg_data = {
            "message_id": message.id if hasattr(message, 'id') else str(uuid4()),
            "content": getattr(message, 'content', str(message))[:100],
            "timestamp": datetime.now().isoformat(),
        }
        self.message_history.append(msg_data)
        print(f"  📱 [MOCK WhatsApp] Message sent: {msg_data['content'][:50]}...")
        return True


async def main():
    """Main function."""
    print("\n" + "="*60)
    print(" SIMPLE SAGA TEST - With Mocked WhatsApp")
    print("="*60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Import after path setup
    from app.database import SessionLocal
    from app.schemas.patient import PatientCreate
    from app.models.user import User, UserRole
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.core.redis_client import get_redis_client
    
    db = SessionLocal()
    mock_whatsapp = MockWhatsAppService()
    
    try:
        # 1. Get or create test doctor
        print("\n[1/4] Getting test doctor...")
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
        if not doctor:
            doctor = User(
                id=uuid4(),
                email=f"debug-{uuid4().hex[:8]}@test.local",
                full_name="Debug Doctor",
                role=UserRole.DOCTOR,
                is_active=True,
            )
            db.add(doctor)
            db.commit()
            print(f"  Created new doctor: {doctor.email}")
        else:
            print(f"  Using existing doctor: {doctor.email}")
        
        # 2. Create patient data
        print("\n[2/4] Creating patient data...")
        import random
        test_phone = f"+55119{random.randint(10000000, 99999999)}"
        patient_data = PatientCreate(
            name=f"Test Patient {uuid4().hex[:8]}",
            phone=test_phone,
            birth_date=date(1980, 5, 15),
            treatment_type="quimioterapia",
            treatment_phase="initial",
            diagnosis="Teste de onboarding",
        )
        print(f"  Name: {patient_data.name}")
        print(f"  Phone: {patient_data.phone}")
        
        # 3. Execute saga with patched WhatsApp
        print("\n[3/4] Executing saga with mocked WhatsApp...")
        
        with patch(
            'app.orchestration.saga_orchestrator.steps.SagaStepExecutor.__init__',
            wraps=lambda self, **kwargs: setattr(self, 'whatsapp_service', mock_whatsapp) or None
        ):
            # Create orchestrator and patch its whatsapp service
            orchestrator = SagaOrchestrator(db=db, redis_client=get_redis_client())
            orchestrator.whatsapp_service = mock_whatsapp
            orchestrator.step_executor.whatsapp_service = mock_whatsapp
            
            patient = await orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor.id,
                idempotency_key=f"debug-{uuid4()}",
            )
        
        # 4. Report results
        print("\n[4/4] Results:")
        if patient:
            print("  ✅ SUCCESS!")
            print(f"     Patient ID: {patient.id}")
            print(f"     Name: {patient.name}")
            print(f"     Phone: {patient.phone}")
            print(f"     Status: {patient.status}")
            print(f"\n  📊 WhatsApp Messages: {mock_whatsapp.messages_sent}")
            for msg in mock_whatsapp.message_history:
                print(f"     - {msg['content'][:60]}...")
        else:
            print("  ❌ FAILED - Patient creation returned None")
        
        print("\n" + "="*60)
        print(" TEST COMPLETE")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
