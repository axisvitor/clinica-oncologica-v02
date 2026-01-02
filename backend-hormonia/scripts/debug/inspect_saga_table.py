"""
Script to inspect patient_onboarding_saga table with correct schema knowledge.
"""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

PATIENT_ID = 'bfa15d69-1fa8-42d4-9cb2-8e51804428b8'

with conn.cursor() as cur:
    print('=' * 70)
    print('SEARCHING IN patient_onboarding_saga')
    print('=' * 70)
    
    # 1. Check count
    cur.execute("SELECT COUNT(*) as total FROM patient_onboarding_saga")
    count = cur.fetchone()['total']
    print(f"Total rows in table: {count}")

    # 2. Search by patient_id
    cur.execute('''
        SELECT *
        FROM patient_onboarding_saga 
        WHERE patient_id = %s
    ''', (PATIENT_ID,))
    saga = cur.fetchone()
    
    if saga:
        print("\n✅ SAGA FOUND!")
        print(f"Saga ID: {saga['id']}")
        print(f"Status: {saga['status']}")
        print(f"Current Step: {saga['current_step']}")
        print(f"Started At: {saga['started_at']}")
        print(f"Completed At: {saga['completed_at']}")
        print(f"Failed At: {saga['failed_at']}")
        print(f"Error Message: {saga['error_message']}")
        
        print("\nEXECUTION LOG:")
        if saga['execution_log']:
            for entry in saga['execution_log']:
                print(f"  - {entry}")
        else:
            print("  (Empty)")

    else:
        print("\n❌ Saga NOT found by patient_id.")
        
        # 3. Check recent sagas if not found
        print("\nchecking recent 5 sagas:")
        cur.execute('''
             SELECT id, patient_id, status, started_at 
             FROM patient_onboarding_saga 
             ORDER BY started_at DESC 
             LIMIT 5
        ''')
        for s in cur.fetchall():
            print(f"  {s['started_at']} | {s['status']} | pat={s['patient_id']}")

conn.close()
