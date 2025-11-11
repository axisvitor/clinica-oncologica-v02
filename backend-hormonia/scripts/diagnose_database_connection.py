"""
Script to diagnose database connection and schema issues.
This script verifies:
1. We're connecting to the correct database
2. All required columns exist
3. All required enums exist
4. Schema matches application expectations
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def diagnose_database():
    """Diagnose database connection and schema."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return False
    
    # Show the connection string (masked password)
    masked_url = db_url
    if '@' in masked_url:
        parts = masked_url.split('@')
        if ':' in parts[0]:
            user_pass = parts[0].split('://')[-1]
            if ':' in user_pass:
                user, _ = user_pass.split(':', 1)
                masked_url = masked_url.replace(user_pass, f"{user}:****")
    
    print("=" * 70)
    print("DATABASE CONNECTION DIAGNOSIS")
    print("=" * 70)
    print(f"\nConnection String: {masked_url}")
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                
                # 1. Database Information
                print("\n" + "=" * 70)
                print("1. DATABASE INFORMATION")
                print("=" * 70)
                
                cur.execute("SELECT current_database(), current_schema(), current_user")
                db_info = cur.fetchone()
                print(f"  Database: {db_info[0]}")
                print(f"  Schema: {db_info[1]}")
                print(f"  User: {db_info[2]}")
                
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
                print(f"  Version: {version.split(',')[0]}")
                
                # 2. Check messages table
                print("\n" + "=" * 70)
                print("2. MESSAGES TABLE ANALYSIS")
                print("=" * 70)
                
                cur.execute("""
                    SELECT column_name, data_type, column_default, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = current_schema() 
                    AND table_name = 'messages'
                    ORDER BY ordinal_position
                """)
                
                columns = cur.fetchall()
                print(f"\nTotal columns: {len(columns)}")
                
                priority_found = False
                idempotency_key_found = False
                
                print("\nColumn details:")
                for col in columns:
                    nullable = "NULL" if col[3] == "YES" else "NOT NULL"
                    default = f"DEFAULT {col[2]}" if col[2] else ""
                    print(f"  {col[0]:<25} {col[1]:<20} {nullable:<10} {default}")
                    
                    if col[0] == 'priority':
                        priority_found = True
                    if col[0] == 'idempotency_key':
                        idempotency_key_found = True
                
                print("\n✓ Critical columns check:")
                print(f"  priority: {'✓ FOUND' if priority_found else '✗ MISSING'}")
                print(f"  idempotency_key: {'✓ FOUND' if idempotency_key_found else '✗ MISSING'}")
                
                # 3. Check enums
                print("\n" + "=" * 70)
                print("3. ENUM TYPES ANALYSIS")
                print("=" * 70)
                
                cur.execute("""
                    SELECT t.typname as enum_name, 
                           array_agg(e.enumlabel ORDER BY e.enumsortorder) as values
                    FROM pg_type t 
                    JOIN pg_enum e ON t.oid = e.enumtypid
                    JOIN pg_namespace n ON t.typnamespace = n.oid
                    WHERE n.nspname = current_schema()
                    GROUP BY t.typname
                    ORDER BY t.typname
                """)
                
                enums = cur.fetchall()
                print(f"\nTotal enums: {len(enums)}")
                
                message_priority_found = False
                
                for enum in enums:
                    print(f"\n  {enum[0]}:")
                    for val in enum[1]:
                        print(f"    - {val}")
                    
                    if enum[0] == 'message_priority':
                        message_priority_found = True
                
                print("\n✓ Critical enums check:")
                print(f"  message_priority: {'✓ FOUND' if message_priority_found else '✗ MISSING'}")
                
                # 4. Test query that application would run
                print("\n" + "=" * 70)
                print("4. APPLICATION QUERY TEST")
                print("=" * 70)
                
                print("\nTesting SELECT with priority column...")
                try:
                    cur.execute("""
                        SELECT id, priority, idempotency_key 
                        FROM messages 
                        LIMIT 1
                    """)
                    print("  ✓ SELECT query works!")
                except Exception as e:
                    print(f"  ✗ SELECT query FAILED: {e}")
                    return False
                
                print("\nTesting INSERT with priority column...")
                try:
                    # Start a savepoint for rollback
                    cur.execute("SAVEPOINT test_insert")
                    
                    cur.execute("""
                        SELECT id FROM users WHERE role = 'doctor' LIMIT 1
                    """)
                    doctor = cur.fetchone()
                    
                    if doctor:
                        # Create test patient
                        cur.execute("""
                            INSERT INTO patients (doctor_id, phone, name)
                            VALUES (%s, '+5511999999999', 'Test Diagnosis')
                            RETURNING id
                        """, (doctor[0],))
                        patient_id = cur.fetchone()[0]
                        
                        # Try insert with priority
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
                            VALUES (%s, 'outbound', 'text', 'Test', 'pending', 'test-diag', 'normal')
                            RETURNING id, priority
                        """, (patient_id,))
                        
                        result = cur.fetchone()
                        print(f"  ✓ INSERT query works! (message_id: {result[0]}, priority: {result[1]})")
                        
                        # Rollback test data
                        cur.execute("ROLLBACK TO SAVEPOINT test_insert")
                    else:
                        print("  ⚠ No doctor found, skipping INSERT test")
                        
                except Exception as e:
                    print(f"  ✗ INSERT query FAILED: {e}")
                    cur.execute("ROLLBACK TO SAVEPOINT test_insert")
                    return False
                
                # 5. Check patient_onboarding_saga
                print("\n" + "=" * 70)
                print("5. PATIENT_ONBOARDING_SAGA TABLE ANALYSIS")
                print("=" * 70)
                
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = current_schema() 
                    AND table_name = 'patient_onboarding_saga'
                    AND column_name IN ('last_retry_at', 'next_retry_at', 'retry_count')
                    ORDER BY column_name
                """)
                
                saga_columns = cur.fetchall()
                print(f"\nRetry-related columns:")
                for col in saga_columns:
                    nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                    print(f"  {col[0]:<20} {col[1]:<25} {nullable}")
                
                last_retry_found = any(col[0] == 'last_retry_at' for col in saga_columns)
                print(f"\n✓ last_retry_at: {'✓ FOUND' if last_retry_found else '✗ MISSING'}")
                
                # 6. Final verdict
                print("\n" + "=" * 70)
                print("DIAGNOSIS RESULT")
                print("=" * 70)
                
                all_good = (
                    priority_found and 
                    idempotency_key_found and 
                    message_priority_found and 
                    last_retry_found
                )
                
                if all_good:
                    print("\n✓ ALL CHECKS PASSED!")
                    print("  The database schema matches application expectations.")
                    print("  No UndefinedColumn errors should occur.")
                    return True
                else:
                    print("\n✗ SCHEMA MISMATCH DETECTED!")
                    print("\nMissing components:")
                    if not priority_found:
                        print("  ✗ messages.priority column")
                    if not message_priority_found:
                        print("  ✗ message_priority enum")
                    if not last_retry_found:
                        print("  ✗ patient_onboarding_saga.last_retry_at column")
                    
                    print("\nAction required:")
                    print("  Run the migration scripts to add missing components.")
                    return False
                
    except Exception as e:
        print(f"\n✗ CONNECTION ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = diagnose_database()
    sys.exit(0 if success else 1)
