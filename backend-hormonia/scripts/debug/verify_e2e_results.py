"""
Quick script to verify E2E test results in database.
"""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

with conn.cursor() as cur:
    print("=" * 70)
    print("E2E TEST VERIFICATION - Database State")
    print("=" * 70)
    
    # Latest patients
    print("\n1. LATEST PATIENTS (last 5)")
    print("-" * 70)
    cur.execute('''
        SELECT id, name, flow_state, current_day, created_at
        FROM patients 
        ORDER BY created_at DESC
        LIMIT 5
    ''')
    for p in cur.fetchall():
        print(f"  {p['name']} | state={p['flow_state']} | day={p['current_day']} | {p['created_at']}")
    
    # Check for E2E Test patient
    print("\n2. E2E TEST PATIENT")
    print("-" * 70)
    cur.execute('''
        SELECT id, name, flow_state, current_day
        FROM patients 
        WHERE name LIKE 'E2E%'
        ORDER BY created_at DESC
        LIMIT 1
    ''')
    e2e_patient = cur.fetchone()
    if e2e_patient:
        patient_id = e2e_patient['id']
        print(f"  Found: {e2e_patient['name']}")
        print(f"  ID: {patient_id}")
        print(f"  Flow State: {e2e_patient['flow_state']}")
        print(f"  Current Day: {e2e_patient['current_day']}")
        
        # Check saga
        print("\n3. SAGA STATUS")
        print("-" * 70)
        cur.execute('''
            SELECT id, status, current_step, started_at, completed_at
            FROM patient_onboarding_saga
            WHERE patient_id = %s
        ''', (patient_id,))
        saga = cur.fetchone()
        if saga:
            print(f"  Status: {saga['status']}")
            print(f"  Step: {saga['current_step']}")
            print(f"  Completed: {saga['completed_at']}")
        else:
            print("  No saga found (may have been cleaned up)")
        
        # Check messages
        print("\n4. MESSAGES")
        print("-" * 70)
        cur.execute('SELECT COUNT(*) as total FROM messages WHERE patient_id = %s', (patient_id,))
        msg_count = cur.fetchone()['total']
        print(f"  Total messages: {msg_count}")
        
        # Check quiz sessions
        print("\n5. QUIZ SESSIONS")
        print("-" * 70)
        cur.execute('SELECT COUNT(*) as total FROM quiz_sessions WHERE patient_id = %s', (patient_id,))
        quiz_count = cur.fetchone()['total']
        print(f"  Total quiz sessions: {quiz_count}")
    else:
        print("  No E2E Test patient found (may have been cleaned up)")
    
    # Overall stats
    print("\n6. OVERALL DATABASE STATS")
    print("-" * 70)
    cur.execute('SELECT COUNT(*) as total FROM patients')
    print(f"  Total patients: {cur.fetchone()['total']}")
    cur.execute('SELECT COUNT(*) as total FROM messages')
    print(f"  Total messages: {cur.fetchone()['total']}")
    cur.execute('SELECT COUNT(*) as total FROM patient_onboarding_saga')
    print(f"  Total sagas: {cur.fetchone()['total']}")

conn.close()
print("\nDone!")
