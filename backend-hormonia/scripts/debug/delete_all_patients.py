"""Delete all remaining patients."""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

with conn.cursor() as cur:
    cur.execute("SELECT id FROM patients")
    patient_ids = [str(p['id']) for p in cur.fetchall()]
    
    if not patient_ids:
        print("Nenhum paciente.")
    else:
        print(f"Deletando {len(patient_ids)} paciente(s)...")
        
        # Check quiz_responses schema
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'quiz_responses'")
        cols = [c['column_name'] for c in cur.fetchall()]
        print(f"  Quiz_responses columns: {cols}")
        
        # Delete quiz_responses by quiz_session_id
        if 'quiz_session_id' in cols:
            cur.execute("DELETE FROM quiz_responses WHERE quiz_session_id IN (SELECT id FROM quiz_sessions WHERE patient_id = ANY(%s::uuid[]))", (patient_ids,))
        else:
            cur.execute("DELETE FROM quiz_responses WHERE id IN (SELECT qr.id FROM quiz_responses qr JOIN quiz_sessions qs ON qr.id = qs.id WHERE qs.patient_id = ANY(%s::uuid[]))", (patient_ids,))
        print(f"  Quiz responses: {cur.rowcount}")
        
        cur.execute("DELETE FROM quiz_sessions WHERE patient_id = ANY(%s::uuid[])", (patient_ids,))
        print(f"  Quiz sessions: {cur.rowcount}")
        
        cur.execute("DELETE FROM messages WHERE patient_id = ANY(%s::uuid[])", (patient_ids,))
        print(f"  Mensagens: {cur.rowcount}")
        
        cur.execute("DELETE FROM patient_onboarding_saga WHERE patient_id = ANY(%s::uuid[])", (patient_ids,))
        print(f"  Sagas: {cur.rowcount}")
        
        cur.execute("DELETE FROM patients WHERE id = ANY(%s::uuid[])", (patient_ids,))
        print(f"  Pacientes: {cur.rowcount}")
        
        conn.commit()
        
    cur.execute("SELECT COUNT(*) as total FROM patients")
    print(f"\nPacientes restantes: {cur.fetchone()['total']}")

conn.close()
print("Concluido!")
