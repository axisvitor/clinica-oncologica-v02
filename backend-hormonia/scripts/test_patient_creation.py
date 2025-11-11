"""
Script to test patient creation flow and verify schema compatibility.
This script simulates the patient onboarding saga to ensure:
1. messages.priority column exists and works
2. patient_onboarding_saga.last_retry_at column exists and works
3. No UndefinedColumn errors occur
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def test_schema_compatibility():
    """Test schema compatibility for patient creation flow."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return False
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("=" * 70)
    print("PATIENT CREATION FLOW - SCHEMA COMPATIBILITY TEST")
    print("=" * 70)
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                # Test 1: Verify messages.priority column
                print("\n✓ Test 1: Verify messages.priority column")
                print("-" * 70)
                
                cur.execute("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'messages'
                    AND column_name = 'priority'
                """)
                
                result = cur.fetchone()
                if result:
                    print(f"  ✓ Column exists: {result[0]}")
                    print(f"    Type: {result[1]}")
                    print(f"    Default: {result[2]}")
                else:
                    print("  ✗ FAILED: Column 'priority' not found!")
                    return False
                
                # Test 2: Verify message_priority enum
                print("\n✓ Test 2: Verify message_priority enum")
                print("-" * 70)
                
                cur.execute("""
                    SELECT enumlabel 
                    FROM pg_enum 
                    JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
                    WHERE pg_type.typname = 'message_priority'
                    ORDER BY enumsortorder
                """)
                
                enum_values = cur.fetchall()
                if enum_values:
                    print(f"  ✓ Enum exists with {len(enum_values)} values:")
                    for val in enum_values:
                        print(f"    - {val[0]}")
                else:
                    print("  ✗ FAILED: Enum 'message_priority' not found!")
                    return False
                
                # Test 3: Verify patient_onboarding_saga.last_retry_at
                print("\n✓ Test 3: Verify patient_onboarding_saga.last_retry_at column")
                print("-" * 70)
                
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patient_onboarding_saga'
                    AND column_name = 'last_retry_at'
                """)
                
                result = cur.fetchone()
                if result:
                    print(f"  ✓ Column exists: {result[0]}")
                    print(f"    Type: {result[1]}")
                    print(f"    Nullable: {result[2]}")
                else:
                    print("  ✗ FAILED: Column 'last_retry_at' not found!")
                    return False
                
                # Test 4: Test INSERT into messages with priority
                print("\n✓ Test 4: Test INSERT into messages with priority")
                print("-" * 70)
                
                # Get a test user (doctor)
                cur.execute("SELECT id FROM users WHERE role = 'doctor' LIMIT 1")
                doctor = cur.fetchone()
                
                if not doctor:
                    print("  ⚠ No doctor found, skipping INSERT test")
                else:
                    doctor_id = doctor[0]
                    
                    # Create a test patient
                    test_phone = f"+5511999999{datetime.now().microsecond % 1000:03d}"
                    
                    cur.execute("""
                        INSERT INTO patients (doctor_id, phone, name, email)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (doctor_id, test_phone, "Test Patient Schema", "test@schema.com"))
                    
                    patient_id = cur.fetchone()[0]
                    print(f"  ✓ Created test patient: {patient_id}")
                    
                    # Try to insert a message with priority
                    try:
                        cur.execute("""
                            INSERT INTO messages (
                                patient_id, 
                                direction, 
                                type, 
                                content, 
                                status, 
                                idempotency_key,
                                priority
                            )
                            VALUES (%s, 'outbound', 'text', 'Test message', 'pending', %s, 'high')
                            RETURNING id, priority
                        """, (patient_id, f"test-{datetime.now().timestamp()}"))
                        
                        message = cur.fetchone()
                        print(f"  ✓ Created test message: {message[0]}")
                        print(f"    Priority: {message[1]}")
                        
                    except Exception as e:
                        print(f"  ✗ FAILED to insert message: {e}")
                        conn.rollback()
                        return False
                    
                    # Test 5: Test INSERT into patient_onboarding_saga with last_retry_at
                    print("\n✓ Test 5: Test INSERT into patient_onboarding_saga")
                    print("-" * 70)
                    
                    try:
                        cur.execute("""
                            INSERT INTO patient_onboarding_saga (
                                patient_id,
                                doctor_id,
                                status,
                                patient_data,
                                last_retry_at
                            )
                            VALUES (%s, %s, 'STARTED', %s, %s)
                            RETURNING id, last_retry_at
                        """, (
                            patient_id, 
                            doctor_id, 
                            '{"test": true}',
                            datetime.now(timezone.utc)
                        ))
                        
                        saga = cur.fetchone()
                        print(f"  ✓ Created test saga: {saga[0]}")
                        print(f"    Last retry at: {saga[1]}")
                        
                    except Exception as e:
                        print(f"  ✗ FAILED to insert saga: {e}")
                        conn.rollback()
                        return False
                    
                    # Cleanup test data
                    print("\n✓ Cleaning up test data...")
                    print("-" * 70)
                    
                    cur.execute("DELETE FROM patient_onboarding_saga WHERE patient_id = %s", (patient_id,))
                    cur.execute("DELETE FROM messages WHERE patient_id = %s", (patient_id,))
                    cur.execute("DELETE FROM patients WHERE id = %s", (patient_id,))
                    
                    conn.commit()
                    print("  ✓ Test data cleaned up")
                
                # Test 6: Verify indexes
                print("\n✓ Test 6: Verify relevant indexes")
                print("-" * 70)
                
                cur.execute("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'patient_onboarding_saga'
                    AND indexname = 'idx_patient_onboarding_saga_last_retry'
                """)
                
                if cur.fetchone():
                    print("  ✓ Index 'idx_patient_onboarding_saga_last_retry' exists")
                else:
                    print("  ⚠ Index 'idx_patient_onboarding_saga_last_retry' not found")
                
                print("\n" + "=" * 70)
                print("✓ ALL TESTS PASSED!")
                print("=" * 70)
                print("\nSchema is compatible with patient creation flow.")
                print("No UndefinedColumn errors should occur.")
                
                return True
                
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_schema_compatibility()
    sys.exit(0 if success else 1)
