"""
Cleanup all test patients except real ones.
"""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

# Test patient patterns to delete
TEST_PATTERNS = [
    "E2E%",
    "Test Patient%",
    "Paciente Saga Test%",
    "Patient Real DB%",
    "T38285",
    "T37101",
]

# Keep these (real patients)
KEEP_PATTERNS = [
    "Paciente Anonimo%",
]

with conn.cursor() as cur:
    print("=" * 70)
    print("LIMPEZA DE PACIENTES DE TESTE")
    print("=" * 70)
    
    # Find test patients
    conditions = " OR ".join([f"name LIKE '{p}'" for p in TEST_PATTERNS])
    cur.execute(f'''
        SELECT id, name FROM patients 
        WHERE ({conditions})
        AND name NOT LIKE 'Paciente Anonimo%'
        ORDER BY name
    ''')
    test_patients = cur.fetchall()
    
    if not test_patients:
        print("Nenhum paciente de teste encontrado.")
    else:
        print(f"\nPacientes a serem deletados: {len(test_patients)}")
        for p in test_patients:
            print(f"  - {p['name']}")
        
        patient_ids = [str(p['id']) for p in test_patients]
        
        # Delete related records
        print("\nDeletando registros relacionados...")
        
        # Quiz sessions
        cur.execute('''
            DELETE FROM quiz_sessions WHERE patient_id = ANY(%s::uuid[])
        ''', (patient_ids,))
        print(f"  Quiz sessions: {cur.rowcount}")
        
        # Messages
        cur.execute('''
            DELETE FROM messages WHERE patient_id = ANY(%s::uuid[])
        ''', (patient_ids,))
        print(f"  Mensagens: {cur.rowcount}")
        
        # Sagas
        cur.execute('''
            DELETE FROM patient_onboarding_saga WHERE patient_id = ANY(%s::uuid[])
        ''', (patient_ids,))
        print(f"  Sagas: {cur.rowcount}")
        
        # Patients
        cur.execute('''
            DELETE FROM patients WHERE id = ANY(%s::uuid[])
        ''', (patient_ids,))
        print(f"  Pacientes: {cur.rowcount}")
        
        conn.commit()
        print("\n[OK] Limpeza concluida!")
        
    # Show remaining
    print("\n" + "=" * 70)
    print("PACIENTES RESTANTES")
    print("=" * 70)
    cur.execute("SELECT name, flow_state FROM patients ORDER BY created_at")
    remaining = cur.fetchall()
    if remaining:
        for p in remaining:
            print(f"  - {p['name']} ({p['flow_state']})")
    else:
        print("  Nenhum paciente no banco.")

conn.close()
