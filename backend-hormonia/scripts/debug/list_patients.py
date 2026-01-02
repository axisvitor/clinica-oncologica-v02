"""List all patients in database."""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

with conn.cursor() as cur:
    print("TODOS OS PACIENTES:")
    print("-" * 80)
    cur.execute("SELECT id, name, flow_state, created_at FROM patients ORDER BY created_at DESC")
    for i, p in enumerate(cur.fetchall(), 1):
        name = p["name"] or "None"
        state = p["flow_state"] or "None"
        print(f"{i}. {name} | {state} | {p['created_at']}")

conn.close()
