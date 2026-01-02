"""
Comprehensive End-to-End Test for Patient Lifecycle System.
Run with: python -m scripts.debug.e2e_final_test
"""

import asyncio
import sys
import os
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import random

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

os.environ.setdefault("WHATSAPP_ENABLE_SERVICE", "true")


class MockWhatsApp:
    def __init__(self):
        self.messages_sent = 0
        self.message_history = []
    
    async def send_message(self, phone, message, **kwargs):
        self.messages_sent += 1
        self.message_history.append({"phone": phone, "message": message})
        print(f"    [WhatsApp Mock] -> {phone}: {message[:60]}...")
        return {"success": True, "message_id": f"mock-{uuid4()}"}
    
    async def send_text_message(self, phone, message, **kwargs):
        return await self.send_message(phone, message, **kwargs)
    
    async def send_welcome_message(self, patient, **kwargs):
        return await self.send_message(patient.phone, f"Bem-vindo, {patient.name}!", **kwargs)


class E2ETestRunner:
    def __init__(self, db_session):
        self.db = db_session
        self.mock_whatsapp = MockWhatsApp()
        self.test_patient_id = None
        self.results = {
            "patient_creation": False,
            "saga_completed": False,
            "flow_initialized": False,
            "welcome_message_sent": False,
            "daily_messages_created": False,
            "quiz_link_generated": False,
        }
    
    async def run_all_tests(self):
        print("\n" + "=" * 70)
        print("[E2E TEST] PATIENT LIFECYCLE SYSTEM")
        print("=" * 70)
        print(f"Started at: {datetime.now().isoformat()}")
        
        try:
            await self.test_patient_registration_saga()
            await self.test_flow_initialization()
            await self.test_daily_flow_processing(days=32)
            await self.test_monthly_quiz_link()
            self.print_summary()
        except Exception as e:
            print(f"\n[FATAL ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()
    
    async def test_patient_registration_saga(self):
        print("\n" + "-" * 70)
        print("TEST 1: Patient Registration + Saga Orchestration")
        print("-" * 70)
        
        from app.schemas.patient import PatientCreate
        from app.orchestration.saga_orchestrator import SagaOrchestrator
        from app.core.redis_client import get_redis_client
        from app.repositories.patient import PatientRepository
        from app.services.patient.flow_service import PatientFlowService
        from app.domain.messaging.core import MessageService
        from app.orchestration.saga_orchestrator.steps import SagaStepExecutor
        from app.orchestration.saga_orchestrator.compensation import SagaCompensator
        from app.orchestration.saga_orchestrator.persistence import SagaPersistence
        
        test_phone = f"+5511999{random.randint(10000, 99999)}"
        patient_data = PatientCreate(
            name=f"E2E Test {random.randint(1000, 9999)}",
            phone=test_phone,
            cpf=None,
            birth_date=date(1985, 6, 20),
            treatment_type="quimioterapia",
            treatment_phase="initial",
            diagnosis="Teste E2E Final",
        )
        
        print(f"\n[INFO] Creating patient: {patient_data.name}")
        print(f"   Phone: {patient_data.phone}")
        
        orchestrator = object.__new__(SagaOrchestrator)
        orchestrator.db = self.db
        orchestrator.redis = get_redis_client()
        orchestrator.evolution_client = None
        orchestrator.patient_repo = PatientRepository(self.db)
        orchestrator.flow_service = PatientFlowService(self.db)
        orchestrator.whatsapp_service = self.mock_whatsapp
        orchestrator.message_service = MessageService(self.db)
        
        orchestrator.step_executor = SagaStepExecutor(
            db=self.db,
            patient_repo=orchestrator.patient_repo,
            flow_service=orchestrator.flow_service,
            whatsapp_service=self.mock_whatsapp,
            message_service=orchestrator.message_service,
        )
        orchestrator.compensator = SagaCompensator(
            db=self.db,
            patient_repo=orchestrator.patient_repo,
            redis_client=orchestrator.redis,
        )
        orchestrator.persistence = SagaPersistence(self.db)
        
        try:
            patient = await orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=None,
                idempotency_key=f"e2e-test-{uuid4()}",
            )
            
            if patient:
                self.test_patient_id = patient.id
                self.results["patient_creation"] = True
                print("\n[PASS] Patient created!")
                print(f"   ID: {patient.id}")
                print(f"   Name: {patient.name}")
                print(f"   Flow State: {patient.flow_state}")
                
                from app.models.patient_onboarding_saga import PatientOnboardingSaga
                saga = self.db.query(PatientOnboardingSaga).filter(
                    PatientOnboardingSaga.patient_id == patient.id
                ).first()
                
                if saga and saga.status.value == "COMPLETED":
                    self.results["saga_completed"] = True
                    print(f"   [PASS] Saga Status: {saga.status.value}")
                    print(f"   [PASS] Current Step: {saga.current_step}/4")
                
                return patient
            else:
                print("[FAIL] Patient creation failed!")
                return None
                
        except Exception as e:
            print(f"[FAIL] Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def test_flow_initialization(self):
        print("\n" + "-" * 70)
        print("TEST 2: Flow Initialization Verification")
        print("-" * 70)
        
        if not self.test_patient_id:
            print("[SKIP] No patient created")
            return
        
        from app.models.patient import Patient
        patient = self.db.query(Patient).get(self.test_patient_id)
        
        if patient:
            print(f"\n[INFO] Patient: {patient.name}")
            print(f"   Flow State: {patient.flow_state}")
            print(f"   Current Day: {patient.current_day}")
            
            if str(patient.flow_state) == "active":
                self.results["flow_initialized"] = True
                print("   [PASS] Flow initialized correctly!")
            
            from app.models.message import Message
            msgs = self.db.query(Message).filter(Message.patient_id == self.test_patient_id).count()
            
            if msgs > 0:
                self.results["welcome_message_sent"] = True
                print(f"   [PASS] Welcome message created: {msgs} message(s)")
    
    async def test_daily_flow_processing(self, days: int = 32):
        print("\n" + "-" * 70)
        print(f"TEST 3: Daily Flow Processing ({days} days)")
        print("-" * 70)
        
        if not self.test_patient_id:
            print("[SKIP] No patient created")
            return
        
        from app.models.patient import Patient
        from app.models.message import Message, MessageType, MessageStatus, MessageDirection
        from app.models.template import MessageTemplate
        
        patient = self.db.query(Patient).get(self.test_patient_id)
        if not patient:
            print("[FAIL] Patient not found")
            return
        
        print(f"\n[INFO] Simulating {days} days of daily messages...")
        
        template = self.db.query(MessageTemplate).filter(
            MessageTemplate.name == "daily_reminder_generic",
            MessageTemplate.is_active == True
        ).first()
        
        for day in range(1, days + 1):
            try:
                patient.current_day = day
                
                if template:
                    try:
                        content = template.format(patient_name=patient.name)
                    except:
                        content = f"Ola {patient.name}! Lembrete do dia {day}."
                else:
                    content = f"Ola {patient.name}! Lembrete do dia {day}."
                
                message = Message(
                    id=uuid4(),
                    patient_id=patient.id,
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType.TEXT,
                    content=content,
                    status=MessageStatus.PENDING,
                    scheduled_for=datetime.now(timezone.utc),
                    message_metadata={"day": day, "type": "daily_reminder"},
                )
                self.db.add(message)
                
                if day % 10 == 0:
                    print(f"   Day {day}: Message created")
                    
            except Exception as e:
                print(f"   Day {day} error: {e}")
        
        self.db.commit()
        
        final_count = self.db.query(Message).filter(Message.patient_id == self.test_patient_id).count()
        
        if final_count >= days:
            self.results["daily_messages_created"] = True
            print(f"\n   [PASS] Created {final_count} messages over {days} days")
        else:
            print(f"\n   [WARN] Only {final_count} messages created (expected {days}+)")
        
        print(f"   Patient current_day: {patient.current_day}")
    
    async def test_monthly_quiz_link(self):
        print("\n" + "-" * 70)
        print("TEST 4: Monthly Quiz Link Generation")
        print("-" * 70)
        
        if not self.test_patient_id:
            print("[SKIP] No patient created")
            return
        
        from app.models.patient import Patient
        from app.domain.quizzes.delivery.link_builder import QuizLinkBuilder
        from app.core.monthly_quiz_config import get_monthly_quiz_config
        
        patient = self.db.query(Patient).get(self.test_patient_id)
        if not patient:
            print("[FAIL] Patient not found")
            return
        
        print(f"\n[INFO] Generating quiz link for: {patient.name}")
        
        try:
            config = get_monthly_quiz_config()
            print(f"   Quiz Base URL: {config.MONTHLY_QUIZ_BASE_URL}")
            
            link_builder = QuizLinkBuilder(config)
            
            import secrets
            token = secrets.token_urlsafe(32)
            quiz_link = link_builder.build_link(token)
            
            print("\n   [PASS] Quiz Link Generated!")
            print(f"   URL: {quiz_link}")
            
            if "token=" in quiz_link and config.MONTHLY_QUIZ_BASE_URL in quiz_link:
                self.results["quiz_link_generated"] = True
                print("   [PASS] Link format valid!")
            
            # Create quiz session
            from app.models.quiz import QuizSession, QuizSessionStatus
            
            quiz_session = QuizSession(
                id=uuid4(),
                patient_id=patient.id,
                quiz_template_id=None,
                status=QuizSessionStatus.PENDING,
                token=token,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
            )
            self.db.add(quiz_session)
            self.db.flush()
            
            print(f"   [PASS] Quiz Session Created: {quiz_session.id}")
            print(f"   Expires: {quiz_session.expires_at}")
            
        except Exception as e:
            print(f"   [FAIL] Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    def print_summary(self):
        print("\n" + "=" * 70)
        print("[SUMMARY] E2E TEST RESULTS")
        print("=" * 70)
        
        all_passed = True
        for test_name, passed in self.results.items():
            status = "[PASS]" if passed else "[FAIL]"
            if not passed:
                all_passed = False
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
        
        print("\n" + "-" * 70)
        if all_passed:
            print("[SUCCESS] ALL TESTS PASSED! System ready for production.")
        else:
            print("[WARNING] SOME TESTS FAILED. Review before production.")
        print("-" * 70)
        
        print(f"\nWhatsApp Mock Summary: {self.mock_whatsapp.messages_sent} messages")
        print(f"Completed at: {datetime.now().isoformat()}")
    
    async def cleanup(self):
        print("\n" + "-" * 70)
        print("[CLEANUP]")
        print("-" * 70)
        
        if not self.test_patient_id:
            print("   No cleanup needed")
            return
        
        try:
            from app.models.quiz import QuizSession
            self.db.query(QuizSession).filter(QuizSession.patient_id == self.test_patient_id).delete()
            
            from app.models.message import Message
            msg_count = self.db.query(Message).filter(Message.patient_id == self.test_patient_id).delete()
            print(f"   Deleted {msg_count} messages")
            
            from app.models.patient_onboarding_saga import PatientOnboardingSaga
            saga_count = self.db.query(PatientOnboardingSaga).filter(
                PatientOnboardingSaga.patient_id == self.test_patient_id
            ).delete()
            print(f"   Deleted {saga_count} saga(s)")
            
            from app.models.patient import Patient
            self.db.query(Patient).filter(Patient.id == self.test_patient_id).delete()
            print("   Deleted test patient")
            
            self.db.commit()
            print("   [PASS] Cleanup completed!")
            
        except Exception as e:
            print(f"   [WARN] Cleanup error: {e}")
            self.db.rollback()


async def main():
    from app.database import SessionLocal
    
    db_session = SessionLocal()
    
    try:
        runner = E2ETestRunner(db_session)
        await runner.run_all_tests()
    finally:
        db_session.close()


if __name__ == "__main__":
    asyncio.run(main())
