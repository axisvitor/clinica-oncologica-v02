#!/usr/bin/env python3
"""
Debug script for testing saga flow directly.
Run with: python tests/debug_saga_flow.py
"""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env manually
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


async def test_saga_flow():
    print("=== TESTING SAGA FLOW DIRECTLY ===\n")

    # Setup database session
    from app.database import get_db
    db = next(get_db())

    # Import required components
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.schemas.patient import PatientCreate
    from app.core.redis_client import get_redis_client
    from datetime import date

    # Get admin user's doctor_id
    from app.models.user import User
    admin = db.query(User).filter(User.email == "admin@neoplasiaslitoral.com").first()
    if not admin:
        print("❌ Admin user not found!")
        return

    print(f"✅ Found admin user: {admin.email}")
    print(f"   ID: {admin.id}")
    print(f"   Role: {admin.role}")

    # Create SagaOrchestrator
    print("\n=== Initializing SagaOrchestrator ===")
    redis = get_redis_client()
    print(f"   Redis connected: {redis is not None}")

    orchestrator = SagaOrchestrator(db=db, redis_client=redis, evolution_client=None)
    print("   ✅ SagaOrchestrator created")

    # Create test patient data
    print("\n=== Creating Test Patient Data ===")
    test_patient = PatientCreate(
        name="TESTE SAGA Debug",
        phone="+5511999887766",  # Test phone
        birth_date=date(1990, 1, 15),
        treatment_type="Oncologia",
        treatment_start_date=date.today(),
    )
    print(f"   Name: {test_patient.name}")
    print(f"   Phone: {test_patient.phone}")

    # Execute saga
    print("\n=== Executing Saga ===")
    try:
        patient = await orchestrator.execute_patient_onboarding_saga(
            patient_data=test_patient,
            doctor_id=admin.id,
            current_user=admin,
            idempotency_key="test_saga_debug_001"
        )

        if patient:
            print("\n✅ SAGA COMPLETED SUCCESSFULLY!")
            print(f"   Patient ID: {patient.id}")
            print(f"   Name: {patient.name}")
            print(f"   Flow State: {patient.flow_state}")
        else:
            print("\n❌ Saga returned None (likely compensated)")

    except Exception as e:
        print(f"\n❌ Saga execution failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # Check saga record in DB
    print("\n=== Checking Saga Records ===")
    from app.models.patient_onboarding_saga import PatientOnboardingSaga
    sagas = db.query(PatientOnboardingSaga).order_by(PatientOnboardingSaga.created_at.desc()).limit(5).all()
    print(f"   Total sagas in DB: {len(sagas)}")
    for saga in sagas:
        print(f"   - {str(saga.id)[:8]}... | Status: {saga.status} | Step: {saga.current_step}")
        if saga.error_message:
            print(f"     Error: {saga.error_message[:100]}")
        if saga.execution_log:
            print(f"     Log entries: {len(saga.execution_log)}")
            for entry in saga.execution_log[-3:]:
                print(f"       - Step {entry.get('step')}: {entry.get('action')} = {entry.get('status')}")

    db.close()
    print("\n=== DEBUG COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(test_saga_flow())
